"""Card-based answer rendering for StructPilot.

Replaces monolithic markdown answers with structured, collapsible cards.
Each card type has its own visual style, icon, and default collapse state.

Supported card types:
    - judgment    : Current judgment / situation assessment
    - params      : Parameter suggestions (name + value + range + note)
    - steps       : Operation steps (numbered list)
    - explanation : Principle explanation (default collapsed in concise mode)
    - screenshot  : Related screenshots / reference images
    - qc          : Quality-control judgment
    - decision    : Decision options with comparison
    - log         : Round log (default collapsed)

Two input modes:
    1. Structured JSON (from NLU Answer Composer):
       {"cards": [{"type": "params", "title": "...", "items": [...], ...}, ...]}
    2. Plain markdown text (fallback / degraded mode):
       The text is wrapped into a single "explanation" card.

Output mode (concise / teaching / expert) controls which cards are
collapsed by default and which are hidden entirely.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import streamlit as st

from components.qa_card import render_qa_card

# ---------------------------------------------------------------------------
# Card type registry
# ---------------------------------------------------------------------------

OutputMode = Literal["concise", "teaching", "expert"]

ANSWER_CARD_TYPES: Dict[str, Dict[str, Any]] = {
    "judgment": {
        "icon": "🎯",
        "label": "当前判断",
        "default_expanded": {"concise": True, "teaching": True, "expert": True},
        "always_show": True,
    },
    "params": {
        "icon": "⚙️",
        "label": "参数建议",
        "default_expanded": {"concise": True, "teaching": True, "expert": True},
        "always_show": True,
    },
    "steps": {
        "icon": "📋",
        "label": "操作步骤",
        "default_expanded": {"concise": True, "teaching": True, "expert": True},
        "always_show": True,
    },
    "explanation": {
        "icon": "📖",
        "label": "原理解释",
        "default_expanded": {"concise": True, "teaching": True, "expert": True},
        "always_show": False,
    },
    "screenshot": {
        "icon": "🖼️",
        "label": "相关截图",
        "default_expanded": {"concise": False, "teaching": True, "expert": True},
        "always_show": False,
    },
    "qc": {
        "icon": "✅",
        "label": "质控判断",
        "default_expanded": {"concise": False, "teaching": True, "expert": True},
        "always_show": False,
    },
    "decision": {
        "icon": "🔀",
        "label": "决策选项",
        "default_expanded": {"concise": True, "teaching": True, "expert": True},
        "always_show": True,
    },
    "log": {
        "icon": "📝",
        "label": "本轮日志",
        "default_expanded": {"concise": False, "teaching": False, "expert": True},
        "always_show": False,
    },
}

# Display order for cards
CARD_ORDER = ["judgment", "params", "steps", "explanation", "screenshot", "qc", "decision", "log"]


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------

def parse_answer_payload(content: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Parse an assistant message into a list of card dicts.

    Priority:
      1. metadata["answer_cards"] -- structured JSON from NLU Answer Composer
      2. metadata["qa_trace"]["answer_cards"] -- alternative location
      3. content starts with ```json ... ``` block containing {"cards": [...]}
      4. Fallback: wrap entire content as a single explanation card

    Each card dict has:
        - type: one of ANSWER_CARD_TYPES keys
        - title: display title (optional, defaults to type label)
        - content: markdown text or structured data
        - items: optional list for params/steps/screenshot
        - collapsed: optional override for collapse state

    Performance: results are cached via st.cache_data to avoid re-parsing
    the same content on every Streamlit rerun.
    """
    # Performance: convert metadata to JSON string for cache key, then use cached parse
    try:
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True) if metadata else ""
        return _cached_parse_answer_payload(content, metadata_json)
    except (TypeError, ValueError):
        # Fallback: if metadata is not JSON-serializable, parse directly
        return _parse_answer_payload_impl(content, metadata)


@st.cache_data(show_spinner=False, max_entries=128)
def _cached_parse_answer_payload(content: str, metadata_hashable: Optional[str] = None) -> List[Dict[str, Any]]:
    """Cached version of parse_answer_payload.

    Note: metadata is converted to a JSON string for cache key hashing.
    """
    import json as _json
    metadata = _json.loads(metadata_hashable) if metadata_hashable else None
    return _parse_answer_payload_impl(content, metadata)


def _parse_answer_payload_impl(content: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Actual implementation of parse_answer_payload (uncached)."""
    metadata = metadata or {}

    # 1. Structured cards from metadata
    raw_cards = metadata.get("answer_cards")
    if not raw_cards:
        qa_trace = metadata.get("qa_trace") or {}
        raw_cards = qa_trace.get("answer_cards")

    if isinstance(raw_cards, list) and raw_cards:
        cards = []
        for item in raw_cards:
            if isinstance(item, dict):
                cards.append(_normalize_card(item))
        if cards:
            return cards

    # 2. Try to extract JSON block from content (```json ... ```)
    if content:
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and isinstance(data.get("cards"), list):
                    cards = [_normalize_card(c) for c in data["cards"] if isinstance(c, dict)]
                    if cards:
                        return cards
            except (json.JSONDecodeError, KeyError):
                pass

    # 3. Try to parse content as direct JSON (no code block)
    # 修复：概念问答返回的是纯 JSON 字符串，需要直接解析
    if content and content.strip().startswith("{"):
        try:
            data = json.loads(content.strip())
            if isinstance(data, dict) and isinstance(data.get("cards"), list):
                cards = [_normalize_card(c) for c in data["cards"] if isinstance(c, dict)]
                if cards:
                    return cards
        except (json.JSONDecodeError, KeyError):
            # 容错增强：尝试清理格式后重试
            try:
                cleaned = content.strip()
                # 移除常见占位符：### placeholder_id ###、### content ###
                cleaned = re.sub(r'###\s+\w+\s+###', '', cleaned)
                # 修复转义符：\n → 真实换行
                cleaned = cleaned.replace('\\n', '\n')
                # 移除【术语库权威条目】等标记
                cleaned = re.sub(r'【[^】]+】', '', cleaned)
                # 再次尝试解析
                data = json.loads(cleaned)
                if isinstance(data, dict) and isinstance(data.get("cards"), list):
                    cards = [_normalize_card(c) for c in data["cards"] if isinstance(c, dict)]
                    if cards:
                        return cards
            except Exception:
                pass

    # 4. Fallback: single explanation card
    return [{
        "type": "explanation",
        "title": "",
        "content": content or "",
        "items": [],
        "collapsed": None,
    }]


def _normalize_card(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw card dict from various NLU output formats."""
    card_type = str(raw.get("type") or raw.get("card_type") or "explanation").strip().lower()
    if card_type not in ANSWER_CARD_TYPES:
        card_type = "explanation"

    title = str(raw.get("title") or raw.get("label") or "").strip()
    content = str(raw.get("content") or raw.get("text") or raw.get("body") or "").strip()
    items = raw.get("items") or raw.get("data") or []
    collapsed = raw.get("collapsed")
    if collapsed is not None:
        collapsed = bool(collapsed)

    return {
        "type": card_type,
        "title": title,
        "content": content,
        "items": items if isinstance(items, list) else [],
        "collapsed": collapsed,
    }


# ---------------------------------------------------------------------------
# Card rendering
# ---------------------------------------------------------------------------

def render_answer_cards(
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    output_mode: OutputMode = "teaching",
    is_last: bool = False,
    key_prefix: str = "",
    suppress_types: Optional[List[str]] = None,
) -> None:
    """Render an assistant message as a series of structured cards.

    Parameters
    ----------
    content : str
        The raw message content (markdown or JSON-embedded).
    metadata : dict, optional
        Message metadata; may contain ``answer_cards`` from NLU.
    output_mode : {'concise', 'teaching', 'expert'}
        Controls default collapse states and card visibility.
    is_last : bool
        Whether this is the most recent message (affects expansion defaults).
    key_prefix : str
        Unique prefix for Streamlit widget keys to avoid collisions.
    suppress_types : list of str, optional
        Card types to SKIP rendering here (e.g. ['screenshot', 'params']).
        Suppressed card data is accumulated into ``st.session_state._extracted_cards``
        for consumption by the workspace panel. This enables the chat/workspace split:
        chat stays text-only while rich cards render in the dedicated workspace area.
    """
    if suppress_types is None:
        suppress_types = []
    cards = parse_answer_payload(content, metadata)
    if not cards:
        st.markdown(content)
        return

    visible_cards = [c for c in cards if c.get("type", "explanation") not in suppress_types]
    if not visible_cards:
        st.markdown(content)
        return

    def _sort_key(card: Dict[str, Any]) -> int:
        t = card.get("type", "explanation")
        return CARD_ORDER.index(t) if t in CARD_ORDER else len(CARD_ORDER)

    cards.sort(key=_sort_key)

    for idx, card in enumerate(cards):
        _render_single_card(card, output_mode, is_last, f"{key_prefix}_c{idx}", suppress_types=suppress_types)


def _render_single_card(
    card: Dict[str, Any],
    output_mode: OutputMode,
    is_last: bool,
    key: str,
    suppress_types: Optional[List[str]] = None,
) -> None:
    """Render one card with appropriate collapse behavior.

    If ``suppress_types`` contains this card's type, the card is NOT rendered
    inline. Instead its data is accumulated into ``st.session_state._extracted_cards``
    for later consumption by the workspace panel (chat/workspace split).
    """
    if suppress_types is None:
        suppress_types = []
    card_type = card.get("type", "explanation")
    spec = ANSWER_CARD_TYPES.get(card_type, ANSWER_CARD_TYPES["explanation"])

    # --- Suppression path: accumulate for workspace, skip chat rendering ---
    if card_type in suppress_types:
        _accumulate_suppressed_card(card, key)
        return  # ← do NOT render anything in chat

    # Response depth is decided at generation time. Rendering may collapse
    # secondary cards, but never hides evidence or risk content.
    default_expanded = spec["default_expanded"].get(output_mode, True)
    collapsed_override = card.get("collapsed")
    if collapsed_override is not None:
        default_expanded = not collapsed_override

    icon = spec["icon"]
    title = card.get("title") or spec["label"]
    content = card.get("content", "")
    items = card.get("items", [])

    # Build expander label
    label = f"{icon} {title}"

    with st.expander(label, expanded=default_expanded):
        if card_type == "params":
            _render_params_card(items, content, key)
        elif card_type == "steps":
            _render_steps_card(items, content, key)
        elif card_type == "screenshot":
            _render_screenshot_card(items, content, key)
        elif card_type == "decision":
            _render_decision_card(items, content, key)
        elif card_type == "qc":
            _render_qc_card(items, content, key)
        elif card_type == "log":
            _render_log_card(content, key)
        else:
            # judgment, explanation, or unknown
            if content:
                st.markdown(content)
            if items:
                st.json(items)


def _accumulate_suppressed_card(card: Dict[str, Any], key: str) -> None:
    """Store a suppressed card's data in session state for workspace consumption.

    The workspace panel calls ``render_suppressed_cards()`` to display all
    accumulated rich cards (params, screenshots, etc.) in a dedicated area,
    keeping the chat area clean and text-focused.
    """
    extracted = st.session_state.get("_extracted_cards", [])
    extracted.append({
        "type": card.get("type", "unknown"),
        "title": card.get("title", ""),
        "content": card.get("content", ""),
        "items": card.get("items", []),
        "key": key,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    st.session_state._extracted_cards = extracted


def render_suppressed_cards(key_prefix: str = "ws_extracted") -> int:
    """Render all suppressed cards in the workspace panel.

    Call this from the workspace's '课题组经验' section to show params,
    screenshots, and other rich cards that were suppressed from chat.

    Returns
    -------
    int
        Number of suppressed cards rendered.
    """
    extracted: List[Dict[str, Any]] = list(st.session_state.get("_extracted_cards", []))
    if not extracted:
        return 0

    st.markdown(f"**从对话中提取**（{len(extracted)} 条）")

    for idx, entry in enumerate(extracted):
        card_type = entry.get("type", "unknown")
        spec = ANSWER_CARD_TYPES.get(card_type, ANSWER_CARD_TYPES["explanation"])
        icon = spec["icon"]
        label = spec["label"]
        title = entry.get("title") or label
        content = entry.get("content", "")
        items = entry.get("items", [])

        exp_label = f"{icon} {title}"
        with st.expander(exp_label, expanded=(idx < 2)):  # Expand first 2 by default
            if card_type == "params":
                _render_params_card(items, content, f"{key_prefix}_{idx}")
            elif card_type == "screenshot":
                _render_screenshot_card(items, content, f"{key_prefix}_{idx}")
            elif card_type == "steps":
                _render_steps_card(items, content, f"{key_prefix}_{idx}")
            elif card_type == "decision":
                _render_decision_card(items, content, f"{key_prefix}_{idx}")
            elif card_type == "qc":
                _render_qc_card(items, content, f"{key_prefix}_{idx}")
            else:
                if content:
                    st.markdown(content)
                if items:
                    st.json(items)

    return len(extracted)


def _render_params_card(items: List[Any], content: str, key: str) -> None:
    """Render parameter suggestions as a styled table."""
    if content:
        st.markdown(content)

    if not items:
        return

    # Build a parameter table
    rows = []
    for item in items:
        if isinstance(item, dict):
            rows.append({
                "参数": item.get("name") or item.get("param") or item.get("key") or "",
                "推荐值": item.get("value") or item.get("recommended") or item.get("default") or "",
                "范围": item.get("range") or item.get("valid_range") or "",
                "说明": item.get("note") or item.get("description") or item.get("comment") or "",
            })
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({
                "参数": str(item[0]),
                "推荐值": str(item[1]),
                "范围": str(item[2]) if len(item) > 2 else "",
                "说明": str(item[3]) if len(item) > 3 else "",
            })

    if rows:
        st.table(rows)


def _render_steps_card(items: List[Any], content: str, key: str) -> None:
    """Render operation steps as a numbered list."""
    if content:
        st.markdown(content)

    if not items:
        return

    steps = []
    for item in items:
        if isinstance(item, dict):
            step_text = item.get("text") or item.get("step") or item.get("description") or ""
            note = item.get("note") or item.get("tip") or ""
            if step_text:
                if note:
                    steps.append(f"{step_text}\n  - 💡 {note}")
                else:
                    steps.append(step_text)
        elif isinstance(item, str):
            steps.append(item)

    if steps:
        # Fold if more than 5 steps
        if len(steps) > 5:
            for i, step in enumerate(steps[:5], start=1):
                st.markdown(f"**{i}.** {step}")
            with st.expander(f"展开全部 {len(steps)} 步", expanded=False):
                for i, step in enumerate(steps[5:], start=6):
                    st.markdown(f"**{i}.** {step}")
        else:
            for i, step in enumerate(steps, start=1):
                st.markdown(f"**{i}.** {step}")


def _render_screenshot_card(items: List[Any], content: str, key: str) -> None:
    """Render screenshots as thumbnails with click-to-expand."""
    if content:
        st.markdown(content)

    if not items:
        return

    # Performance: use lazy image loading with thumbnails
    try:
        from utils.image_lazy import render_lazy_image
    except ImportError:
        render_lazy_image = None

    cols = st.columns(min(len(items), 3))
    for i, item in enumerate(items):
        col = cols[i % len(cols)]
        with col:
            if isinstance(item, dict):
                img_path = item.get("path") or item.get("image") or item.get("url") or ""
                caption = item.get("caption") or item.get("label") or item.get("name") or ""
                if img_path:
                    try:
                        if render_lazy_image:
                            render_lazy_image(img_path, caption=caption, use_container_width=True, use_thumbnail=True, key=f"{key}_img_{i}")
                        else:
                            st.image(img_path, caption=caption, use_container_width=True)
                    except Exception:
                        st.caption(f"📷 {caption or img_path}")
            elif isinstance(item, str):
                try:
                    if render_lazy_image:
                        render_lazy_image(item, use_container_width=True, use_thumbnail=True, key=f"{key}_img_{i}")
                    else:
                        st.image(item, use_container_width=True)
                except Exception:
                    st.caption(f"📷 {item}")


def _render_decision_card(items: List[Any], content: str, key: str) -> None:
    """Render decision options with comparison."""
    if content:
        st.markdown(content)

    if not items:
        return

    for item in items:
        if isinstance(item, dict):
            option = item.get("option") or item.get("name") or ""
            pros = item.get("pros") or item.get("advantage") or ""
            cons = item.get("cons") or item.get("disadvantage") or ""
            recommended = item.get("recommended") or item.get("is_recommended") or False

            badge = " ⭐ 推荐" if recommended else ""
            st.markdown(f"**{option}{badge}**")
            if pros:
                st.markdown(f"  - ✅ {pros}")
            if cons:
                st.markdown(f"  - ⚠️ {cons}")
        elif isinstance(item, str):
            st.markdown(f"- {item}")


def _render_qc_card(items: List[Any], content: str, key: str) -> None:
    """Render quality-control checks as a checklist.

    Thin wrapper: 核心渲染委托给 components.qa_card.render_qa_card，
    以统一三态（pass / warn / fail）颜色与图标规范。
    """
    render_qa_card(items, content=content, key=key)


def _render_log_card(content: str, key: str) -> None:
    """Render a log block, typically in monospace."""
    if not content:
        return
    st.code(content, language="text")
