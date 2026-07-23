"""Performance caching layer for StructPilot.

This module provides Streamlit-native caching for:
1. Knowledge-base JSON files via @st.cache_data (cross-rerun, file-mtime-aware)
2. StructPilotApp singleton via @st.cache_resource (avoids graph rebuild)
3. LLM Agent singleton via @st.cache_resource (avoids config reload)
4. RAG search result LRU cache (in-memory, per-process)

Design principles:
- All caches are transparent wrappers — callers get the same data type back.
- st.cache_data uses file mtime as cache invalidation key, so editing a JSON
  on disk automatically busts the cache on the next rerun.
- st.cache_resource is used for stateful objects (StructPilotApp, LLMAgent)
  that must persist across reruns without reinitialization.
- RAG search cache uses a composite key (software, cp_id, query_hash) and
  an LRU eviction policy (max 100 entries) to bound memory.
- Everything degrades gracefully without an API key — caching works in
  basic mode just as well as in AI mode.

Integration points:
- main.py:2311  → replace `StructPilotApp()` with `get_cached_app()`
- NavigatorAgent.__init__  → use `cached_load_json()` instead of `load_json_with_fallback()`
- SOPAgent.__init__  → same
- ExpertAgent.__init__  → same
- KnowledgeRetriever.search  → wrap with `rag_search_cache`
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

_BASE_DIR = Path(__file__).resolve().parent.parent
_KNOWLEDGE_DIR = _BASE_DIR / "knowledge_base"

# Maximum RAG search results cached in memory (LRU eviction).
_RAG_CACHE_MAX_SIZE = 100

# In-process LRU cache for RAG search results.
# Key: (software, cp_id, query_hash, top_k)
# Value: List[Tuple[str, str, float]]
_rag_cache: OrderedDict[Tuple[str, str, str, int], List[Tuple[str, str, float]]] = OrderedDict()
_rag_cache_lock = threading.Lock()

# Flag to allow cache clearing when knowledge base changes.
_kb_dirty = False


def mark_kb_dirty() -> None:
    """Signal that the knowledge base has been modified and caches should be busted.

    Call this after writing/updating any knowledge JSON file.
    """
    global _kb_dirty
    _kb_dirty = True
    _clear_rag_cache()
    # Also clear st.cache_data for JSON files
    _cached_load_json_impl.clear()
    _cached_load_json_by_path_impl.clear()


def _clear_rag_cache() -> None:
    """Clear the in-memory RAG search result cache."""
    with _rag_cache_lock:
        _rag_cache.clear()


def _file_mtime_key(path: str) -> float:
    """Return file modification time for cache invalidation.

    Returns 0.0 if the file does not exist (cache will still work, just
    won't auto-invalidate on file changes).
    """
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_load_json_impl(primary_relpath: str, legacy_filename: str, _mtime: float, default: Any) -> Any:
    """Internal cached implementation. Do not call directly — use cached_load_json."""
    # Try primary path first
    candidates = [_KNOWLEDGE_DIR / primary_relpath]
    if legacy_filename:
        candidates.append(_KNOWLEDGE_DIR / legacy_filename)

    for path in candidates:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue

    return default if default is not None else []


def cached_load_json(primary_relpath: str, legacy_filename: str = "", default: Any = None) -> Any:
    """Load a knowledge-base JSON file with Streamlit caching.

    This is a drop-in replacement for ``load_json_with_fallback`` that adds
    @st.cache_data so the JSON is parsed only once per file modification.

    The cache key includes the file's mtime, so editing the JSON on disk
    automatically busts the cache on the next Streamlit rerun.

    Parameters
    ----------
    primary_relpath : str
        Relative path under knowledge_base/ (e.g. "flows/pipeline_checkpoints.json").
    legacy_filename : str
        Legacy flat filename fallback (e.g. "pipeline_checkpoints.json").
    default : Any
        Default value if file is missing or unreadable.

    Returns
    -------
    Any
        Parsed JSON content (list or dict), or ``default``.
    """
    # Compute mtime for cache invalidation — file edits will bust the cache
    mtime = _file_mtime_key(str(_KNOWLEDGE_DIR / primary_relpath))
    if legacy_filename:
        mtime = max(mtime, _file_mtime_key(str(_KNOWLEDGE_DIR / legacy_filename)))
    return _cached_load_json_impl(primary_relpath, legacy_filename, mtime, default)


@st.cache_data(show_spinner=False, max_entries=16)
def _cached_load_json_by_path_impl(abs_path: str, _mtime: float, default: Any) -> Any:
    """Internal cached implementation. Do not call directly — use cached_load_json_by_path."""
    path = Path(abs_path)
    if not path.exists():
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def cached_load_json_by_path(abs_path: str, default: Any = None) -> Any:
    """Load a JSON file by absolute path with Streamlit caching.

    Used for files outside knowledge_base/ (e.g. config/llm_config.json).
    Cache key includes file mtime for auto-invalidation.
    """
    mtime = _file_mtime_key(abs_path)
    return _cached_load_json_by_path_impl(abs_path, mtime, default)


@st.cache_data(show_spinner=False, max_entries=32)
def cached_load_jsonl(abs_path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file with Streamlit caching.

    Returns an empty list if the file is missing or unreadable.
    """
    path = Path(abs_path)
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
    except Exception:
        pass
    return rows


def rag_search_cache(
    retriever: Any,
    query: str,
    top_k: int = 3,
    software: str = "",
    cp_id: str = "",
) -> List[Tuple[str, str, float]]:
    """Wrapper around KnowledgeRetriever.search with in-memory LRU cache.

    Cache key = (software, cp_id, sha256(query), top_k).
    If the knowledge base is marked dirty, the cache is cleared before lookup.

    This is safe to call in both basic mode (lexical search) and AI mode
    (embedding search). The retriever itself handles the embedding/no-embedding
    branching.

    Parameters
    ----------
    retriever : KnowledgeRetriever
        The retriever instance (must have a ``search`` method).
    query : str
        User query text.
    top_k : int
        Number of top results to return.
    software : str
        Current software context ("relion" / "cryosparc") for cache isolation.
    cp_id : str
        Current checkpoint ID for cache isolation.

    Returns
    -------
    List[Tuple[str, str, float]]
        List of (doc_id, text, score) tuples.
    """
    global _kb_dirty
    if _kb_dirty:
        _clear_rag_cache()
        _kb_dirty = False

    query_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:16]
    cache_key = (software or "", cp_id or "", query_hash, top_k)

    with _rag_cache_lock:
        if cache_key in _rag_cache:
            # Move to end (most recently used)
            _rag_cache.move_to_end(cache_key)
            return _rag_cache[cache_key]

    # Cache miss — perform actual search
    results = retriever.search(query, top_k=top_k)

    with _rag_cache_lock:
        _rag_cache[cache_key] = results
        # LRU eviction
        while len(_rag_cache) > _RAG_CACHE_MAX_SIZE:
            _rag_cache.popitem(last=False)

    return results


def get_rag_cache_stats() -> Dict[str, int]:
    """Return RAG cache statistics for debugging."""
    with _rag_cache_lock:
        return {
            "entries": len(_rag_cache),
            "max_size": _RAG_CACHE_MAX_SIZE,
        }


@st.cache_resource(show_spinner=False)
def get_cached_llm_agent() -> Any:
    """Create or return the singleton LLMAgent instance.

    Uses @st.cache_resource so the agent (and its config) persists across
    Streamlit reruns without reloading config files.

    Returns
    -------
    LLMAgent
    """
    from agents.llm_agent import LLMAgent
    return LLMAgent()


@st.cache_resource(show_spinner=False)
def get_cached_app(app_api_version: str = "v4-response-profile-1") -> Any:
    """Create or return the singleton StructPilotApp instance.

    This is the single most impactful optimization: without this, every
    Streamlit rerun that loses session_state would rebuild the entire
    LangGraph, KnowledgeRetriever, and all agent instances (which collectively
    load 10+ JSON files).

    With @st.cache_resource, the StructPilotApp is created once per Streamlit
    server process and shared across all sessions.

    Returns
    -------
    StructPilotApp
    """
    # app_api_version is intentionally part of the cache key. Increment it
    # whenever the public orchestration interface changes so a live Streamlit
    # process cannot keep serving an object created from an older class shape.
    _ = app_api_version
    from graph.app import StructPilotApp
    app = StructPilotApp()

    # Ensure the LLM agent is the cached singleton
    cached_llm = get_cached_llm_agent()
    if cached_llm is not app.llm:
        app.llm = cached_llm
        if hasattr(app, 'retriever'):
            app.retriever.llm = cached_llm

    return app


def clear_all_caches() -> None:
    """Clear all performance caches.

    Call this when the user modifies knowledge base content or LLM settings.
    """
    global _kb_dirty
    _kb_dirty = True
    _clear_rag_cache()
    cached_load_json.clear()
    cached_load_json_by_path.clear()
    cached_load_jsonl.clear()
    # Note: st.cache_resource for app/llm should NOT be cleared on every
    # KB change — only when the user explicitly requests a full reset.


def clear_app_cache() -> None:
    """Force-rebuild the StructPilotApp and LLM Agent singletons.

    Use this when the user changes LLM configuration and needs the app
    to pick up new settings.
    """
    get_cached_app.clear()
    get_cached_llm_agent.clear()
    _clear_rag_cache()
