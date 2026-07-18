"""Parameter panel component for StructPilot.

Renders parameter cards in a clean, structured layout with:
  - Parameter name (monospace, highlighted)
  - Recommended value (bold)
  - Valid range (muted)
  - Description / note (regular text)

Folds automatically when there are more than 5 parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

# Performance: track CSS injection to avoid repeated st.markdown calls
_PARAM_CSS_INJECTED = False


def render_parameter_panel(
    params: List[Dict[str, Any]],
    key_prefix: str = "pp",
    collapse_threshold: int = 5,
) -> None:
    """Render a list of parameters as styled cards.

    Parameters
    ----------
    params : list of dict
        Each dict should have keys: name, value, range, note.
        Missing keys default to empty strings.
    key_prefix : str
        Unique prefix for widget keys.
    collapse_threshold : int
        Number of parameters above which the panel collapses by default.
    """
    if not params:
        st.caption("暂无参数信息。")
        return

    # Performance: inject CSS once per session, not per card
    _ensure_param_css()

    should_collapse = len(params) > collapse_threshold

    if should_collapse:
        # Show summary + first few, then expandable
        st.markdown(f"**关键参数（{len(params)} 项，展示前 {collapse_threshold} 项）**")
        for param in params[:collapse_threshold]:
            _render_param_card(param, key_prefix)
        with st.expander(f"展开全部 {len(params)} 项参数", expanded=False):
            for i, param in enumerate(params[collapse_threshold:], start=collapse_threshold):
                _render_param_card(param, f"{key_prefix}_{i}")
    else:
        st.markdown(f"**关键参数（{len(params)} 项）**")
        for i, param in enumerate(params):
            _render_param_card(param, f"{key_prefix}_{i}")


def _render_param_card(param: Dict[str, Any], key: str) -> None:
    """Render a single parameter as a styled card."""
    import html as _html
    name = _html.escape(str(param.get("name") or param.get("param") or param.get("key") or ""))
    value = _html.escape(str(param.get("value") or param.get("recommended") or param.get("default") or ""))
    valid_range = _html.escape(str(param.get("range") or param.get("valid_range") or ""))
    note = _html.escape(str(param.get("note") or param.get("description") or param.get("comment") or ""))
    unit = _html.escape(str(param.get("unit") or ""))
    source = _html.escape(str(param.get("source") or ""))

    value_display = f"{value} {unit}".strip() if value else "—"
    range_display = f"<span class='sp-param-range'>范围: {valid_range}</span>" if valid_range else ""
    note_display = f"<div class='sp-param-note'>{note}</div>" if note else ""
    source_display = f"<span class='sp-param-source'>{source}</span>" if source else ""

    card_html = (
        f'<div class="sp-param-card-item" style="border:1px solid #e2e8f0;'
        f'border-radius:8px;padding:10px 14px;margin:6px 0;background:#ffffff;">'
        f'<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;">'
        f'<code style="font-size:0.9rem;color:#0f766e;font-weight:600;">{name}</code>'
        f'<span style="font-weight:700;color:#1e293b;">{value_display}</span>'
        f'{range_display}{source_display}</div>{note_display}</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)


def _ensure_param_css() -> None:
    """Inject CSS for parameter cards once per Streamlit session.

    Performance: uses a module-level flag to avoid repeated st.markdown
    calls. Streamlit deduplicates identical <style> tags, but the Python-side
    string formatting and st.markdown call still has overhead when called
    per-card in a loop.
    """
    global _PARAM_CSS_INJECTED
    if _PARAM_CSS_INJECTED:
        return
    _inject_param_css()
    _PARAM_CSS_INJECTED = True


def _inject_param_css() -> None:
    """Inject CSS for parameter cards (idempotent)."""
    css = """
    <style>
    .sp-param-range {
        font-size: 0.78rem;
        color: #64748b;
        background: #f1f5f9;
        padding: 1px 6px;
        border-radius: 4px;
    }
    .sp-param-note {
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.5;
        margin-top: 4px;
    }
    .sp-param-source {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-left: auto;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_param_table(
    params: List[Dict[str, Any]],
    key_prefix: str = "pt",
) -> None:
    """Render parameters as a Streamlit table (alternative to cards).

    Use this when there are many parameters and a table is more compact.
    """
    if not params:
        st.caption("暂无参数信息。")
        return

    rows = []
    for param in params:
        rows.append({
            "参数": param.get("name", ""),
            "推荐值": param.get("value", ""),
            "范围": param.get("range", ""),
            "说明": param.get("note", ""),
        })

    st.table(rows)
