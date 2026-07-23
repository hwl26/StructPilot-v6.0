"""Knowledge-base path helpers.

The project is moving from a flat ``knowledge_base/*.json`` layout to a
governed layout with flows, qa, terminology, rules, faults, guides, sources,
and review folders.  These helpers keep runtime code conservative: read the
new location first and fall back to the legacy flat file when needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class KnowledgeBasePaths:
    root: str

    def path(self, relpath: str) -> str:
        return os.path.join(self.root, *relpath.replace("\\", "/").split("/"))

    def first_existing(self, *relpaths: str) -> Optional[str]:
        for relpath in relpaths:
            path = self.path(relpath)
            if os.path.exists(path):
                return path
        return None


def load_json_with_fallback(
    knowledge_dir: str,
    primary_relpath: str,
    legacy_filename: Optional[str] = None,
    default: Any = None,
) -> Any:
    """Load JSON from the governed path, falling back to the legacy file."""
    paths = KnowledgeBasePaths(knowledge_dir)
    candidates = [primary_relpath]
    if legacy_filename:
        candidates.append(legacy_filename)
    path = paths.first_existing(*candidates)
    if not path:
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file, skipping blank lines and malformed rows."""
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
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
    return rows


def iter_runtime_allowed_docs(knowledge_dir: str) -> Iterable[Dict[str, Any]]:
    """Yield formally approved QA docs that are allowed in runtime answers."""
    formal_path = KnowledgeBasePaths(knowledge_dir).path("qa/formal_answers.jsonl")
    for doc in load_jsonl(formal_path):
        if doc.get("runtime_allowed", True) is False:
            continue
        status = doc.get("status") or doc.get("review_status")
        if status and status not in {"formal_ready", "approved", "expert_approved"}:
            continue
        yield doc


def source_label(doc: Dict[str, Any]) -> str:
    source = doc.get("source") or doc.get("sources") or ""
    if isinstance(source, list):
        return "; ".join(str(item) for item in source if item)
    return str(source)


def load_sharded_knowledge_index(knowledge_dir: str) -> List[Dict[str, Any]]:
    """Load the knowledge index from the sharded ``knowledge_index/`` directory.

    The legacy single ``knowledge_index.json`` was split into per-checkpoint
    shards (see ``knowledge_index_manifest.json``). This helper iterates every
    ``*.json`` file in ``knowledge_index/`` (sorted by name) and concatenates
    their doc lists so callers get a single flat list as before.

    Falls back to the legacy single file when the shard directory is absent,
    but only if that file still holds a real list (the placeholder backup
    note is a dict and is ignored). Returns ``[]`` on any error.
    """
    paths = KnowledgeBasePaths(knowledge_dir)
    shard_dir = paths.path("knowledge_index")
    docs: List[Dict[str, Any]] = []
    if os.path.isdir(shard_dir):
        for name in sorted(os.listdir(shard_dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(shard_dir, name), "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        docs.append(item)
        return docs
    # Fallback to the legacy single file when no shard directory exists.
    legacy_path = paths.path("knowledge_index.json")
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
    return docs


def _shard_file_for_doc(knowledge_dir: str, doc: Dict[str, Any]) -> str:
    """Return the shard file path a doc belongs to.

    Routes by ``checkpoint_id`` (e.g. ``cp_01`` -> ``cp_01_import.json``).
    Docs without a checkpoint go to ``cp_00_general.json``.
    """
    paths = KnowledgeBasePaths(knowledge_dir)
    cp = str(doc.get("checkpoint_id") or "").strip().lower()
    if not cp:
        cp = "cp_00"
    # Match shard naming: cp_XX_<label>.json. Find the matching shard.
    shard_dir = paths.path("knowledge_index")
    if os.path.isdir(shard_dir):
        for name in sorted(os.listdir(shard_dir)):
            if name.startswith(cp + "_") and name.endswith(".json"):
                return os.path.join(shard_dir, name)
    # Fallback: cp_00_general.json or create a generic shard name
    if cp == "cp_00":
        return os.path.join(shard_dir, "cp_00_general.json")
    return os.path.join(shard_dir, f"{cp}_user.json")


def _read_shard_list(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _write_shard_list(path: str, docs: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


def add_doc_to_sharded_index(knowledge_dir: str, doc: Dict[str, Any]) -> None:
    """Add or replace a doc in the sharded knowledge index.

    Routes the doc to its checkpoint shard, replacing any existing doc with
    the same ``doc_id``. Falls back to the legacy single-file write when the
    shard directory is absent.
    """
    paths = KnowledgeBasePaths(knowledge_dir)
    shard_dir = paths.path("knowledge_index")
    if not os.path.isdir(shard_dir):
        # Legacy fallback: write to the single file.
        legacy_path = paths.path("knowledge_index.json")
        existing = _read_shard_list(legacy_path)
        existing = [item for item in existing if item.get("doc_id") != doc.get("doc_id")]
        existing.append(doc)
        _write_shard_list(legacy_path, existing)
        return

    shard_path = _shard_file_for_doc(knowledge_dir, doc)
    docs = _read_shard_list(shard_path)
    docs = [item for item in docs if item.get("doc_id") != doc.get("doc_id")]
    docs.append(doc)
    _write_shard_list(shard_path, docs)


def delete_doc_from_sharded_index(knowledge_dir: str, doc_id: str) -> bool:
    """Delete a doc by id from whichever shard holds it. Returns True if removed."""
    paths = KnowledgeBasePaths(knowledge_dir)
    shard_dir = paths.path("knowledge_index")
    if not os.path.isdir(shard_dir):
        legacy_path = paths.path("knowledge_index.json")
        docs = _read_shard_list(legacy_path)
        new_docs = [d for d in docs if d.get("doc_id") != doc_id]
        if len(new_docs) == len(docs):
            return False
        _write_shard_list(legacy_path, new_docs)
        return True

    removed = False
    for name in sorted(os.listdir(shard_dir)):
        if not name.endswith(".json"):
            continue
        shard_path = os.path.join(shard_dir, name)
        docs = _read_shard_list(shard_path)
        new_docs = [d for d in docs if d.get("doc_id") != doc_id]
        if len(new_docs) != len(docs):
            _write_shard_list(shard_path, new_docs)
            removed = True
    return removed


def update_doc_fields_in_sharded_index(
    knowledge_dir: str, doc_id: str, fields: Dict[str, Any]
) -> bool:
    """Update arbitrary content fields (title/summary/…) of a doc in the sharded index.

    Mirrors update_doc_status_in_sharded_index but merges an arbitrary field dict,
    used by the inline knowledge editor in the advanced-mode settings tab.
    """
    paths = KnowledgeBasePaths(knowledge_dir)
    shard_dir = paths.path("knowledge_index")
    if not os.path.isdir(shard_dir):
        legacy_path = paths.path("knowledge_index.json")
        docs = _read_shard_list(legacy_path)
        updated = False
        for d in docs:
            if d.get("doc_id") == doc_id:
                d.update(fields)
                updated = True
        if updated:
            _write_shard_list(legacy_path, docs)
        return updated

    updated = False
    for name in sorted(os.listdir(shard_dir)):
        if not name.endswith(".json"):
            continue
        shard_path = os.path.join(shard_dir, name)
        docs = _read_shard_list(shard_path)
        changed = False
        for d in docs:
            if d.get("doc_id") == doc_id:
                d.update(fields)
                updated = True
                changed = True
        if changed:
            _write_shard_list(shard_path, docs)
    return updated


def update_doc_status_in_sharded_index(
    knowledge_dir: str, doc_id: str, status: str, tier: Optional[str] = None
) -> bool:
    """Update status (and optionally tier) of a doc in the sharded index."""
    paths = KnowledgeBasePaths(knowledge_dir)
    shard_dir = paths.path("knowledge_index")
    if not os.path.isdir(shard_dir):
        legacy_path = paths.path("knowledge_index.json")
        docs = _read_shard_list(legacy_path)
        updated = False
        for d in docs:
            if d.get("doc_id") == doc_id:
                d["status"] = status
                if tier is not None:
                    d["tier"] = tier
                updated = True
        if updated:
            _write_shard_list(legacy_path, docs)
        return updated

    updated = False
    for name in sorted(os.listdir(shard_dir)):
        if not name.endswith(".json"):
            continue
        shard_path = os.path.join(shard_dir, name)
        docs = _read_shard_list(shard_path)
        changed = False
        for d in docs:
            if d.get("doc_id") == doc_id:
                d["status"] = status
                if tier is not None:
                    d["tier"] = tier
                updated = True
                changed = True
        if changed:
            _write_shard_list(shard_path, docs)
    return updated
