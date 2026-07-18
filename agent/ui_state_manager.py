"""Centralized Streamlit session_state manager for StructPilot.

This module provides a single entry point for all UI-related session state,
ensuring that:
- current_stage, current_software, chat_history, last_answer persist across reruns
- scroll positions are remembered per (stage, tab) pair
- expand/collapse states are tracked
- output mode (简洁/教学/专家) is preserved
- mode (basic/ai) is tracked and can be toggled at runtime

Design principles:
- All state is stored in st.session_state with namespaced keys ("sp_*").
- The manager is a thin wrapper — it does not replace PipelineState (which is
  the authoritative data model), it only manages UI-facing state.
- Every getter has a safe default so the UI never crashes on first load.
- The manager works identically in basic mode and AI mode.

Integration points:
- main.py:2540  → use get_state()/set_state() instead of direct session_state access
- main.py:1199  → use init_ui_state() to bootstrap all defaults at once
- main.py:2856  → use get_output_mode() / get_history_limit()
- main.py:2685  → use get_software() / set_software()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

# Namespace prefix for all StructPilot UI state keys.
_PREFIX = "sp_"

# Default values for all managed UI state keys.
_DEFAULTS: Dict[str, Any] = {
    # Core navigation state (mirrors PipelineState for UI convenience)
    "current_stage": "",
    "current_software": "relion",
    "current_cp_id": "",
    "current_cp_name": "",
    # Chat display state
    "history_limit": 8,
    "last_answer": "",
    "last_feedback": "",
    # Output mode: "concise" | "teaching" | "expert"
    "output_mode": "teaching",
    # Mode: "basic" | "ai" — auto-detected from API key availability
    "llm_mode": "basic",
    # Scroll position memory: { "stage_tab": scrollY }
    "scroll_positions": {},
    # Expand/collapse state: { "expander_key": bool }
    "expander_states": {},
    # Sidebar note cache: { "cp_id": note_text }
    "cp_notes": {},
    # Pending pasted images (clipboard)
    "pending_pasted": [],
    "last_pasted_sig": "",
    # Voice input
    "voice_transcript": "",
    "voice_transcript_editor": "",
    # Distill draft (knowledge extraction)
    "distill_draft": None,
    # Knowledge base dirty flag (when user adds/edits KB content)
    "kb_dirty": False,
    # Ingest draft (operation knowledge)
    "operation_ingest_draft": None,
    # Normalized query (last user input)
    "last_normalized_query": None,
}


def init_ui_state() -> None:
    """Initialize all StructPilot UI state keys with defaults.

    Call this once at the top of main.py, before any UI rendering.
    Uses setdefault so existing values are never overwritten.
    """
    for key, default in _DEFAULTS.items():
        full_key = f"{_PREFIX}{key}"
        if full_key not in st.session_state:
            st.session_state[full_key] = default() if callable(default) else default
        # Also set without prefix for backward compat with existing main.py code
        # that reads st.session_state["current_software"] etc.
        if key not in st.session_state:
            st.session_state[key] = st.session_state[full_key]


def get_state(key: str, default: Any = None) -> Any:
    """Get a UI state value by key (without prefix).

    Falls back to the unprefixed key for backward compatibility with
    existing main.py code.
    """
    full_key = f"{_PREFIX}{key}"
    if full_key in st.session_state:
        return st.session_state[full_key]
    if key in st.session_state:
        return st.session_state[key]
    return default


def set_state(key: str, value: Any) -> None:
    """Set a UI state value (both prefixed and unprefixed for compat)."""
    st.session_state[f"{_PREFIX}{key}"] = value
    st.session_state[key] = value


# ---------------------------------------------------------------------------
# Navigation state helpers
# ---------------------------------------------------------------------------

def get_software() -> str:
    """Return current software ('relion' or 'cryosparc')."""
    return get_state("current_software", "relion")


def set_software(software: str) -> None:
    """Set current software."""
    set_state("current_software", software)


def get_current_cp_id() -> str:
    """Return current checkpoint ID."""
    return get_state("current_cp_id", "")


def set_current_cp(cp_id: str, cp_name: str = "") -> None:
    """Set current checkpoint ID and name."""
    set_state("current_cp_id", cp_id)
    set_state("current_cp_name", cp_name)


# ---------------------------------------------------------------------------
# Chat display helpers
# ---------------------------------------------------------------------------

def get_history_limit() -> int:
    """Return the number of chat messages to display."""
    return int(get_state("history_limit", 8))


def set_history_limit(limit: int) -> None:
    """Set the number of chat messages to display."""
    set_state("history_limit", max(3, min(50, limit)))


def get_last_answer() -> str:
    """Return the last assistant answer (for quick re-display)."""
    return get_state("last_answer", "")


def set_last_answer(answer: str) -> None:
    """Store the last assistant answer."""
    set_state("last_answer", answer)


def get_last_feedback() -> str:
    """Return the last feedback message (info toast)."""
    return get_state("last_feedback", "")


def set_last_feedback(feedback: str) -> None:
    """Set the feedback message and clear it after display."""
    set_state("last_feedback", feedback)


def consume_last_feedback() -> str:
    """Pop and return the last feedback message (auto-clears after read)."""
    msg = get_state("last_feedback", "")
    if msg:
        set_state("last_feedback", "")
    return msg


# ---------------------------------------------------------------------------
# Output mode helpers
# ---------------------------------------------------------------------------

def get_output_mode() -> str:
    """Return current output mode: 'concise', 'teaching', or 'expert'."""
    return get_state("output_mode", "teaching")


def set_output_mode(mode: str) -> None:
    """Set output mode. Invalid values default to 'teaching'."""
    if mode not in ("concise", "teaching", "expert"):
        mode = "teaching"
    set_state("output_mode", mode)


# ---------------------------------------------------------------------------
# LLM mode helpers (basic / ai)
# ---------------------------------------------------------------------------

def get_llm_mode() -> str:
    """Return current LLM mode: 'basic' or 'ai'.

    'basic' = no API key configured, uses keyword matching + rule-based answers.
    'ai' = API key configured, uses RAG + LLM rewriting.
    """
    return get_state("llm_mode", "basic")


def set_llm_mode(mode: str) -> None:
    """Set LLM mode."""
    if mode not in ("basic", "ai"):
        mode = "basic"
    set_state("llm_mode", mode)


def detect_llm_mode(llm_enabled: bool) -> str:
    """Auto-detect LLM mode based on whether the API key is configured.

    Parameters
    ----------
    llm_enabled : bool
        Whether the LLMAgent has a valid provider + API key.

    Returns
    -------
    str
        'ai' if enabled, 'basic' otherwise.
    """
    return "ai" if llm_enabled else "basic"


def get_mode_label() -> str:
    """Return a human-readable label for the current mode."""
    mode = get_llm_mode()
    if mode == "ai":
        return "AI 增强模式"
    return "基础模式"


# ---------------------------------------------------------------------------
# Scroll position memory
# ---------------------------------------------------------------------------

def save_scroll_position(stage: str, tab: str, scroll_y: float) -> None:
    """Save scroll position for a (stage, tab) pair.

    Parameters
    ----------
    stage : str
        Checkpoint ID (e.g. "cp_01").
    tab : str
        Tab name (e.g. "guide", "sop", "chat").
    scroll_y : float
        Vertical scroll position in pixels.
    """
    positions = get_state("scroll_positions", {})
    key = f"{stage}_{tab}"
    positions[key] = scroll_y
    set_state("scroll_positions", positions)


def get_scroll_position(stage: str, tab: str) -> float:
    """Get saved scroll position for a (stage, tab) pair. Returns 0 if none."""
    positions = get_state("scroll_positions", {})
    return positions.get(f"{stage}_{tab}", 0.0)


def clear_scroll_positions() -> None:
    """Clear all saved scroll positions."""
    set_state("scroll_positions", {})


# ---------------------------------------------------------------------------
# Expander/collapse state helpers
# ---------------------------------------------------------------------------

def get_expander_state(key: str, default: bool = False) -> bool:
    """Get the expand/collapse state of an expander by key."""
    states = get_state("expander_states", {})
    return states.get(key, default)


def set_expander_state(key: str, expanded: bool) -> None:
    """Set the expand/collapse state of an expander by key."""
    states = get_state("expander_states", {})
    states[key] = expanded
    set_state("expander_states", states)


def toggle_expander(key: str, default: bool = False) -> bool:
    """Toggle an expander's state and return the new value."""
    current = get_expander_state(key, default)
    new_state = not current
    set_expander_state(key, new_state)
    return new_state


# ---------------------------------------------------------------------------
# Chat history folding helpers
# ---------------------------------------------------------------------------

def get_chat_display_window(messages: list, limit: Optional[int] = None) -> tuple:
    """Split messages into (recent_window, folded_older) for display.

    The recent window contains the last ``limit`` messages (default from
    get_history_limit). The folded portion contains earlier messages that
    will be shown in a collapsed expander.

    Parameters
    ----------
    messages : list
        All chat messages (state.messages).
    limit : int, optional
        Number of recent messages to show. Defaults to get_history_limit().

    Returns
    -------
    tuple
        (recent_messages, older_messages)
    """
    if limit is None:
        limit = get_history_limit()
    total = len(messages)
    if total <= limit:
        return messages, []
    recent = messages[-limit:]
    older = messages[:-limit]
    return recent, older


def get_older_summary(older_messages: list) -> str:
    """Generate a compact summary for folded older messages.

    Parameters
    ----------
    older_messages : list
        Messages that will be hidden in the expander.

    Returns
    -------
    str
        Summary text like "查看更早的 15 条消息（5 轮对话）"
    """
    count = len(older_messages)
    if count == 0:
        return ""
    # Count user messages to estimate "rounds"
    user_count = sum(1 for m in older_messages if getattr(m, "role", "") == "user")
    rounds = user_count or (count // 2)
    return f"查看更早的 {count} 条消息（约 {rounds} 轮对话）"


# ---------------------------------------------------------------------------
# Knowledge base dirty flag
# ---------------------------------------------------------------------------

def is_kb_dirty() -> bool:
    """Check if the knowledge base has been modified and caches need clearing."""
    return bool(get_state("kb_dirty", False))


def mark_kb_dirty() -> None:
    """Mark the knowledge base as dirty (caches will be cleared on next access)."""
    set_state("kb_dirty", True)
    # Also clear perf_cache RAG cache
    try:
        from utils.perf_cache import mark_kb_dirty as _mark
        _mark()
    except Exception:
        pass


def consume_kb_dirty() -> bool:
    """Check and clear the KB dirty flag. Returns True if it was dirty."""
    dirty = is_kb_dirty()
    if dirty:
        set_state("kb_dirty", False)
    return dirty


# ---------------------------------------------------------------------------
# Session state migration helper
# ---------------------------------------------------------------------------

def ensure_state_consistency(app: Any, state: Any) -> None:
    """Synchronize UI state with the authoritative PipelineState.

    Call this after loading/restoring a session to make sure the UI
    state matches the pipeline state.

    Parameters
    ----------
    app : StructPilotApp
        The application instance (for LLM mode detection).
    state : PipelineState
        The current pipeline state.
    """
    set_state("current_software", state.software or "relion")
    set_state("current_cp_id", state.current_cp_id or "")
    set_state("current_cp_name", state.current_cp_name or "")

    # Auto-detect LLM mode
    llm_enabled = bool(getattr(app.llm, "enabled", False))
    set_llm_mode(detect_llm_mode(llm_enabled))
