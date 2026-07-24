"""StructPilot v6.0 Streamlit entrypoint."""

from __future__ import annotations

from datetime import datetime
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import tempfile
import threading
from pathlib import Path
import inspect

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass  # python-dotenv not installed, skip

import streamlit as st
import streamlit.components.v1 as components
from streamlit_paste_button import paste_image_button

from graph.app import StructPilotApp
from graph.state import PipelineState
from knowledge_base.importer import (
    KnowledgeDoc, TIER_LABELS, load_knowledge_doc,
    doc_from_dict, detect_conflicts, doc_to_text,
)
from knowledge_base.paths import (
    load_sharded_knowledge_index, add_doc_to_sharded_index,
    delete_doc_from_sharded_index, update_doc_status_in_sharded_index,
    update_doc_fields_in_sharded_index,
)
from knowledge_base.corrections import append_correction, load_corrections, make_correction, normalize_query
from knowledge_base.document_ingest import build_ingest_draft
from utils.ui_settings import load_ui_settings, save_ui_settings
from utils.perf_cache import get_cached_app, get_cached_llm_agent, mark_kb_dirty as perf_mark_kb_dirty, clear_app_cache
from utils.image_lazy import render_lazy_image, generate_thumbnail_data_url, get_cached_image_data_url
from utils.ui_state_manager import (
    init_ui_state, get_state, set_state,
    get_llm_mode, set_llm_mode, detect_llm_mode, get_mode_label,
    get_chat_display_window, get_older_summary,
    consume_last_feedback, consume_kb_dirty,
)
from validator.validator import InputValidator, extract_params_from_text
from response_profiles import (
    PROFILE_DESCRIPTIONS,
    PROFILE_LABELS,
    format_response_for_profile,
    normalize_response_profile,
)
from version import APP_DISPLAY_NAME
# Force reload to pick up version changes
import importlib
import version as _version_module
importlib.reload(_version_module)
APP_DISPLAY_NAME = _version_module.APP_DISPLAY_NAME
from ui.components import (
    render_answer_cards, parse_answer_payload, ANSWER_CARD_TYPES, render_suppressed_cards,
    render_stage_workspace, render_parameter_panel, render_image_gallery,
)
from ui.components.desk_pet import render_desk_pet, handle_pet_quick_question
from ui.styles import (
    THEMES, _WORKSPACE_CSS, _workspace_theme_css, build_global_styles,
)
from utils.file_upload import (
    ALLOWED_IMAGE_MIME_TYPES, MAX_FILE_SIZE, ALLOWED_EXTENSIONS,
    ALLOWED_AUDIO_EXTENSIONS, ALLOWED_AUDIO_MIME_TYPES, MAX_AUDIO_SIZE,
    save_uploaded_images, save_pasted_image, save_uploaded_audio,
    get_image_metadata,
)
from utils.image_processing import (
    image_data_url, run_local_ocr, run_optional_vision_model, parse_bool_env,
)


# Runtime paths and shared low-level helpers live in utils.runtime_paths to
# avoid circular imports (modules under utils/ must never import from main.py).
from utils.runtime_paths import (
    BASE_DIR, RUNTIME_ROOT, ensure_runtime_dir,
    MEMORY_DIR, UPLOAD_DIR, AUDIO_DIR, CACHE_DIR,
    IMAGE_OCR_CACHE_DIR, AUDIO_CACHE_DIR,
    GUIDE_CARDS_PATH, CORRECTIONS_PATH, INGEST_ASSET_ROOT,
    file_sha256, _read_json_cache, _write_json_cache,
)

APP_API_VERSION = "v4-response-profile-1"
GUIDE_VISUAL_HASH_DISTANCE_THRESHOLD = 42

STATUS_LABELS = {
    "pending": ("⚪", "待处理"),
    "in_progress": ("🔵", "进行中"),
    "passed": ("✅", "已通过"),
    "failed": ("❌", "未通过"),
    "skipped": ("⏭️", "已跳过"),
}


def make_session_id() -> str:
    return "session_" + datetime.now().strftime("%Y%m%d_%H%M%S")


@st.cache_data(show_spinner=False)
def load_guide_cards() -> dict:
    if not GUIDE_CARDS_PATH.exists():
        return {}
    try:
        data = json.loads(GUIDE_CARDS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cards = data.get("cards", []) if isinstance(data, dict) else data
    if not isinstance(cards, list):
        return {}
    result = {}
    for card in cards:
        if not isinstance(card, dict):
            continue
        cp_id = str(card.get("checkpoint_id") or card.get("id") or "").strip()
        if cp_id:
            result[cp_id] = card
    return result


def resolve_guide_asset(path: str) -> str:
    if not path:
        return ""
    # V4 改进：优先从「外部截图根」解析（上级目录 StructPilot_Visual_UI images），
    # 缺失则回退原 BASE_DIR 相对解析（保留铁律 10 的 Demo 截图路径）。
    try:
        from utils.assets import resolve_screenshot

        resolved = resolve_screenshot(path)
        if resolved:
            return resolved
    except Exception:
        pass
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / path
    return str(candidate) if candidate.exists() else ""


def guide_image_signature(image_item: dict) -> str:
    """Return a stable signature so guide tabs do not reuse the same screenshot."""
    if not isinstance(image_item, dict):
        return ""
    raw_path = str(image_item.get("path") or image_item.get("image") or image_item.get("image_path") or "").strip()
    image_path = resolve_guide_asset(raw_path)
    if image_path:
        try:
            return f"sha256:{file_sha256(image_path)}"
        except OSError:
            pass
    if raw_path:
        return "path:" + raw_path.replace("\\", "/").lower()
    return ""


def guide_image_visual_hash(image_item: dict) -> str:
    """Return a perceptual hash for similar guide screenshots."""
    if not isinstance(image_item, dict):
        return ""
    raw_path = str(image_item.get("path") or image_item.get("image") or image_item.get("image_path") or "").strip()
    image_path = resolve_guide_asset(raw_path)
    if not image_path:
        return ""
    try:
        from PIL import Image, ImageOps

        with Image.open(image_path) as im:
            gray = ImageOps.grayscale(im).resize((16, 16))
            pixels = list(gray.getdata())
    except Exception:
        return ""
    if not pixels:
        return ""
    avg = sum(pixels) / len(pixels)
    return "".join("1" if value >= avg else "0" for value in pixels)


def hamming_distance(left: str, right: str) -> int:
    if not left or not right or len(left) != len(right):
        return max(len(left), len(right))
    return sum(a != b for a, b in zip(left, right))


def prewarm_runtime_caches() -> dict:
    """Preload local guide/SOP/RAG caches so common clicks answer immediately."""
    report = {"guide_cards": 0, "guide_images": 0, "sop_cards": 0, "rag_docs": 0, "rag_hits": 0, "errors": []}
    try:
        load_guide_cards.clear()
    except Exception:
        pass
    try:
        cards = load_guide_cards()
        report["guide_cards"] = len(cards)
        for card in cards.values():
            for substep in card.get("substeps", []) or []:
                images = substep.get("images") or []
                if not images and substep.get("image"):
                    images = [{"path": substep.get("image")}]
                if not images and substep.get("path"):
                    images = [{"path": substep.get("path")}]
                for image in images:
                    path = resolve_guide_asset(str(image.get("path") or ""))
                    if path:
                        image_data_url(path)
                        report["guide_images"] += 1
    except Exception as exc:
        report["errors"].append(f"guide:{exc}")

    _app = globals().get("app")
    _state = globals().get("state")
    if _app is None or _state is None:
        report["errors"].append("app/state not yet initialized; skipping SOP/RAG prewarm")
        return report

    old_cp_id = getattr(_state, "current_cp_id", "")
    old_cp_name = getattr(_state, "current_cp_name", "")
    old_action = getattr(_state, "action_tag", "")
    try:
        for cp in _app.navigator.checkpoints:
            cp_id = cp.get("checkpoint_id")
            if not cp_id:
                continue
            _state.current_cp_id = cp_id
            _state.current_cp_name = cp.get("checkpoint_cn", "")
            _app.sop.quick_sop(_state)
            report["sop_cards"] += 1
    except Exception as exc:
        report["errors"].append(f"sop:{exc}")
    finally:
        _state.current_cp_id = old_cp_id
        _state.current_cp_name = old_cp_name
        _state.action_tag = old_action

    try:
        corpus = _app.retriever.build_corpus(force_rebuild=True)
        report["rag_docs"] = len(corpus or [])
        hits = _app.retriever.search("cryo em motion correction ctf pixel size", top_k=3)
        report["rag_hits"] = len(hits or [])
    except Exception as exc:
        report["errors"].append(f"rag:{exc}")
    return report


def render_guide_card(card: dict, key_prefix: str = "") -> None:
    """Render image tabs, clickable hot spots and parameter cards."""
    if not isinstance(card, dict) or not card:
        return
    substeps = card.get("substeps") if isinstance(card.get("substeps"), list) else []
    if not substeps:
        return

    st.markdown(
        """
<style>
.sp-guide-placeholder {
  min-height: 220px;
  border: 1px dashed #b8c4d6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  background: #f8fafc;
  padding: 18px;
  margin-top: 8px;
}
.sp-param-grid {
  display: grid;
  grid-template-columns: minmax(120px, 0.9fr) minmax(180px, 1.4fr) minmax(180px, 1.4fr) minmax(120px, 1fr);
  gap: 1px;
  background: #dbe3ef;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  overflow: hidden;
  margin-top: 10px;
}
.sp-param-cell {
  background: #ffffff;
  padding: 9px 10px;
  font-size: 0.88rem;
  line-height: 1.45;
}
.sp-param-head {
  background: #eef4fb;
  font-weight: 650;
  color: #334155;
}
.sp-param-name {
  font-weight: 650;
  color: #0f766e;
  cursor: help;
  text-decoration: underline dotted #94a3b8;
  text-underline-offset: 3px;
}
.sp-guide-image-wrap {
  position: relative;
  display: inline-block;
  max-width: 100%;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.sp-guide-image-wrap img {
  display: block;
  width: 100%;
  height: auto;
}
.sp-hotspot {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid #fff;
  background: #2563eb;
  color: #fff !important;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  font-weight: 700;
  text-decoration: none !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.28);
}
.sp-hotspot:hover { background: #0f766e; }
.sp-image-switch-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 8px 0 10px 0;
}
.sp-image-badge {
  border: 1px solid #dbe3ef;
  background: #f8fafc;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 0.78rem;
  color: #334155;
}
.sp-param-card {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 10px 12px;
  margin-top: 8px;
}
.sp-param-card summary {
  cursor: pointer;
  font-weight: 650;
  color: #0f172a;
}
.sp-param-meta {
  color: #64748b;
  font-size: 0.82rem;
  margin: 4px 0 8px 0;
}
.sp-param-tip {
  margin-top: 6px;
  font-size: 0.88rem;
  line-height: 1.5;
}
@media (max-width: 720px) {
  .sp-param-grid { grid-template-columns: 1fr; }
  .sp-param-head { display: none; }
}
.sp-guide-shell {
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px 16px;
  margin: 10px 0 12px 0;
}
.sp-guide-kicker {
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.sp-guide-title {
  color: #0f172a;
  font-size: 1.12rem;
  font-weight: 750;
  line-height: 1.35;
  margin: 0;
}
.sp-guide-note {
  color: #64748b;
  font-size: 0.88rem;
  line-height: 1.55;
  margin-top: 6px;
}
.sp-screen-panel {
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
  margin-top: 10px;
}
.sp-screen-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #475569;
  font-size: 0.82rem;
  margin-bottom: 8px;
}
.sp-screen-title { font-weight: 650; color: #334155; }
.sp-image-badge { border-radius: 6px; padding: 5px 9px; background: #ffffff; }
.sp-param-list {
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  overflow: hidden;
  margin-top: 12px;
  background: #ffffff;
}
.sp-param-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #eef4fb;
  color: #334155;
  font-weight: 700;
  font-size: 0.9rem;
}
.sp-param-card {
  border-radius: 0;
  border-width: 1px 0 0 0;
  margin-top: 0;
}
.sp-param-titleline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sp-param-check {
  width: 15px;
  height: 15px;
  border-radius: 4px;
  border: 1px solid #93c5fd;
  background: #dbeafe;
  display: inline-block;
}
.sp-param-chip {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 0.74rem;
  font-weight: 650;
  padding: 2px 7px;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    title = str(card.get("title") or "Guide card")
    cp_id = str(card.get("checkpoint_id") or card.get("cp_id") or "StructPilot Guide")
    status = str(card.get("status") or "")
    review_note = "阶段切换后优先显示真实界面截图、关键参数和可点击热区；参数建议仍需结合项目记录核对。"
    if status and status not in {"reviewed", "runtime_allowed"}:
        review_note = f"Draft guide card pending expert review. {review_note}"
    st.markdown(
        f'<section class="sp-guide-shell"><div class="sp-guide-kicker">{html.escape(cp_id)}</div>'
        f'<h3 class="sp-guide-title">{html.escape(title)}</h3>'
        f'<div class="sp-guide-note">{html.escape(review_note)}</div></section>',
        unsafe_allow_html=True,
    )

    labels = [str(item.get("label") or item.get("tab_name") or item.get("id") or f"step_{i + 1}") for i, item in enumerate(substeps)]
    tabs = st.tabs(labels)
    used_image_signatures = set()
    used_visual_hashes = []
    for tab_idx, (tab, item) in enumerate(zip(tabs, substeps)):
        with tab:
            images = item.get("images") if isinstance(item.get("images"), list) else []
            if not images and item.get("image"):
                images = [{"path": item.get("image"), "caption": item.get("caption") or item.get("label"), "image_id": "1"}]
            if not images and item.get("path"):
                images = [{"path": item.get("path"), "caption": item.get("caption") or item.get("label"), "image_id": "1"}]

            unique_images = []
            duplicate_count = 0
            for image_item in images:
                signature = guide_image_signature(image_item)
                if signature and signature in used_image_signatures:
                    duplicate_count += 1
                    continue
                visual_hash = guide_image_visual_hash(image_item)
                if visual_hash and any(hamming_distance(visual_hash, seen_hash) <= GUIDE_VISUAL_HASH_DISTANCE_THRESHOLD for seen_hash in used_visual_hashes):
                    duplicate_count += 1
                    continue
                if signature:
                    used_image_signatures.add(signature)
                if visual_hash:
                    used_visual_hashes.append(visual_hash)
                unique_images.append(image_item)
            images = unique_images

            params = item.get("parameters") if isinstance(item.get("parameters"), list) else []
            selected_image_idx = 0
            if len(images) > 1:
                image_options = []
                image_label_map = {}
                for img_idx, img in enumerate(images, start=1):
                    img_id = str(img.get("image_id") or img_idx)
                    caption = str(img.get("caption") or img.get("filename") or img.get("path") or "image")
                    label = f"图 {img_id}: {caption}"
                    image_options.append(label)
                    image_label_map[label] = img_idx - 1
                item_key = re.sub(r"[^0-9A-Za-z_]+", "_", str(item.get("id") or item.get("label") or tab_idx))
                selected_label = st.radio(
                    "选择截图",
                    image_options,
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"guide_image_{key_prefix}_{cp_id}_{tab_idx}_{item_key}",
                )
                selected_image_idx = image_label_map.get(selected_label, 0)

            if images:
                image_item = images[min(selected_image_idx, len(images) - 1)]
                images_to_show = [(selected_image_idx + 1, image_item)]
            else:
                placeholder = "该按钮暂无独立截图。" if duplicate_count else "Image placeholder"
                if duplicate_count:
                    placeholder = "已隐藏与其他按钮重复或相似的截图，避免 I/O、Motion、2D 等页面显示相同图片。"
                images_to_show = [(1, {"caption": placeholder})]

            for image_idx, image_item in images_to_show:
                image_id = str(image_item.get("image_id") or image_idx)
                image_path = resolve_guide_asset(str(image_item.get("path") or image_item.get("image") or ""))
                caption = html.escape(str(image_item.get("caption") or item.get("caption") or item.get("label") or ""))
                if image_path:
                    data_url = image_data_url(image_path)
                    hotspots = []
                    for param in params:
                        if not isinstance(param, dict):
                            continue
                        ref = str(param.get("image_ref") or "@image#1")
                        match = re.search(r"@image#(\d+)", ref)
                        ref_id = match.group(1) if match else "1"
                        if ref_id != image_id:
                            continue
                        x = param.get("hotspot_x")
                        y = param.get("hotspot_y")
                        if x is None or y is None:
                            continue
                        order = html.escape(str(param.get("hotspot_order") or "?"))
                        pname = html.escape(str(param.get("param_name_cn") or param.get("name_cn") or param.get("name") or param.get("id") or param.get("param_id") or "parameter"))
                        anchor = html.escape(str(param.get("param_id") or param.get("id") or param.get("name") or pname))
                        hotspots.append(
                            f'<a class="sp-hotspot" href="#sp-param-{anchor}" title="{pname}" '
                            f'style="left:{float(x):.3f}%;top:{float(y):.3f}%;">{order}</a>'
                        )
                    st.markdown(
                        f'<div class="sp-screen-panel"><div class="sp-screen-topbar">'
                        f'<span class="sp-screen-title">界面截图</span><span>{image_idx} / {max(len(images), 1)}</span></div>'
                        f'<div class="sp-guide-image-wrap"><img src="{data_url}" alt="{caption}">{"".join(hotspots)}</div>'
                        f'<div class="sp-param-meta">{caption}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    placeholder = html.escape(str(image_item.get("caption") or item.get("caption") or "Image placeholder"))
                    st.markdown(f'<div class="sp-guide-placeholder">{placeholder}</div>', unsafe_allow_html=True)

            if not params:
                continue

            # 改动8：过滤掉标记为 show_in_checklist=false 的参数，减少冗余信息
            visible_params = [
                p for p in params
                if isinstance(p, dict) and p.get("show_in_checklist", True)
            ]
            if not visible_params:
                continue

            cells = ['<div class="sp-param-list"><div class="sp-param-list-head"><span>参数核对</span><span>Parameter checklist</span></div>']
            for param in visible_params:
                pid = html.escape(str(param.get("param_id") or param.get("id") or param.get("name") or "parameter"))
                name_cn = html.escape(str(param.get("param_name_cn") or param.get("name_cn") or param.get("name") or pid))
                name_en = html.escape(str(param.get("param_name_en") or param.get("name_en") or ""))
                default = html.escape(str(param.get("default_value") or param.get("default") or ""))
                unit = html.escape(str(param.get("unit") or ""))
                ptype = html.escape(str(param.get("type") or ""))
                desc = html.escape(str(param.get("description") or param.get("meaning") or ""))
                tips = param.get("tips") if isinstance(param.get("tips"), dict) else {}
                official = html.escape(str(tips.get("official_doc") or param.get("official_doc") or param.get("how_to_choose") or ""))
                mistake = html.escape(str(tips.get("common_mistake") or param.get("common_mistake") or param.get("risk") or ""))
                meta = " · ".join(x for x in [name_en, ptype, f"默认 {default}{unit}" if default else ""] if x)
                chips = []
                if ptype:
                    chips.append(f'<span class="sp-param-chip">{ptype}</span>')
                if default:
                    chips.append(f'<span class="sp-param-chip">default {default}{unit}</span>')
                card_parts = [
                    f'<details id="sp-param-{pid}" class="sp-param-card">',
                    f'<summary><span class="sp-param-titleline"><span class="sp-param-check"></span><span>{name_cn}</span>{"".join(chips)}</span></summary>',
                    f'<div class="sp-param-meta">{html.escape(meta)}</div>',
                    f'<div>{desc}</div>',
                ]
                if official:
                    card_parts.append(f'<div class="sp-param-tip"><b>官方/规则：</b>{official}</div>')
                # 「实验室经验」字段已移除（见优化建议），仅保留官方说明与常见陷阱
                if mistake:
                    card_parts.append(f'<div class="sp-param-tip"><b>⚠️ 常见陷阱：</b>{mistake}</div>')
                card_parts.append('</details>')
                cells.append("".join(card_parts))
            cells.append('</div>')
            st.markdown("".join(cells), unsafe_allow_html=True)


def build_session_report(state: PipelineState, cp_total: int) -> str:
    lines = [
        "# StructPilot cryo-EM Session Report",
        "",
        f"生成时间：{datetime.now().isoformat()}",
        f"Session ID：{state.session_id}",
        f"当前阶段：{state.current_cp_id} · {state.current_cp_name}",
        f"流程进度：{len(state.completed)}/{cp_total}",
        "",
        "## 1. Checkpoint Summary",
        f"- Passed: {', '.join(state.completed) if state.completed else 'None'}",
        f"- Failed: {', '.join(state.failed) if state.failed else 'None'}",
        f"- Skipped: {', '.join(state.skipped) if state.skipped else 'None'}",
        "",
        "## 2. Captured Parameters",
    ]
    if state.params:
        for k, v in state.params.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- None")
    lines.extend(["", "## 3. QC / Fault Notes"])
    if state.last_qc_result:
        for k, v in state.last_qc_result.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No QC warning recorded.")
    lines.extend(["", "## 4. Recent Conversation"])
    for msg in state.messages[-20:]:
        content = msg.content.replace("\n", " ")[:500]
        lines.append(f"- [{msg.timestamp}] {msg.role} / {msg.action_tag}: {content}")
    lines.extend(["", "## 5. Notes", "- 本报告由 StructPilot 自动生成，可作为实验记录初稿。"])
    return "\n".join(lines)


def describe_image_refs(image_refs: list | None) -> str:
    """Build compact image context, including dimensions when available."""
    if not image_refs:
        return ""
    lines = ["Attached screenshot/image context for the current cryo-EM processing turn."]
    for idx, ref in enumerate(image_refs, start=1):
        name = ref.get("image_name", f"image_{idx}")
        source = ref.get("source_type", "upload")
        mime = ref.get("mime_type", "")
        width = ref.get("width")
        height = ref.get("height")
        dims = f", {width}x{height}px" if width and height else ""
        lines.append(f"Image {idx}: {name} ({source}, {mime}{dims})")
    return "\n".join(lines)


CRITICAL_IMAGE_PARAMS = {
    "pixel_size",
    "accelerating_voltage",
    "voltage",
    "spherical_aberration",
    "amplitude_contrast",
    "total_dose",
    "dose_per_frame",
    "eer_fractionation",
    "box_size",
    "ctf_fit",
}


def normalize_param_key(key: str) -> str:
    aliases = {
        "voltage": "accelerating_voltage",
        "kv": "accelerating_voltage",
        "cs": "spherical_aberration",
        "angpix": "pixel_size",
        "apix": "pixel_size",
        "dose": "total_dose",
    }
    clean = re.sub(r"[^a-z0-9_]+", "_", str(key or "").strip().lower()).strip("_")
    return aliases.get(clean, clean)


def is_critical_param(key: str) -> bool:
    return normalize_param_key(key) in CRITICAL_IMAGE_PARAMS


def coerce_param_value(key: str, value):
    key = normalize_param_key(key)
    if isinstance(value, str):
        value = value.strip()
    if key in {"box_size", "eer_fractionation", "accelerating_voltage"}:
        return int(float(value))
    if key in {"pixel_size", "spherical_aberration", "amplitude_contrast", "total_dose", "dose_per_frame", "ctf_fit"}:
        return float(value)
    return value


def same_param_value(left, right) -> bool:
    try:
        return abs(float(left) - float(right)) <= max(1e-6, abs(float(right)) * 0.002)
    except Exception:
        return str(left).strip().lower() == str(right).strip().lower()


def evidence_for_value(text: str, value) -> str:
    if not text:
        return ""
    value_text = str(value)
    idx = text.lower().find(value_text.lower())
    if idx < 0:
        return text.strip().replace("\n", " ")[:160]
    start = max(0, idx - 55)
    end = min(len(text), idx + len(value_text) + 55)
    return text[start:end].strip().replace("\n", " ")[:180]


def extract_params_with_evidence(text: str, source: str, confidence: float, authority: str) -> list:
    candidates = []
    for key, value in extract_params_from_text(text or "").items():
        norm_key = normalize_param_key(key)
        try:
            value = coerce_param_value(norm_key, value)
        except Exception:
            continue
        candidates.append(
            {
                "key": norm_key,
                "value": value,
                "source": source,
                "authority": authority,
                "confidence": float(confidence),
                "critical": is_critical_param(norm_key),
                "evidence": evidence_for_value(text or "", value),
            }
        )
    return candidates


def arbitrate_image_params(candidates: list, current_params: dict | None = None) -> dict:
    current_params = current_params or {}
    accepted = {}
    pending = []
    rejected = []
    non_vision_sources = {"user_text", "ocr", "filename"}

    indexed_candidates = [{**cand, "_candidate_index": idx} for idx, cand in enumerate(candidates)]
    for cand in indexed_candidates:
        key = normalize_param_key(cand.get("key", ""))
        if not key:
            rejected.append({**cand, "reason": "missing parameter key"})
            continue
        cand = {**cand, "key": key, "critical": is_critical_param(key)}
        value = cand.get("value")
        source = cand.get("source", "unknown")
        confidence = float(cand.get("confidence") or 0)
        existing = current_params.get(key)

        if source == "vision_model" and cand["critical"]:
            pending.append({**cand, "reason": "vision model is advisory for critical parameters"})
            continue
        if source == "user_text" and confidence >= 0.8:
            accepted[key] = value
            continue
        if existing not in (None, "") and same_param_value(existing, value) and confidence >= 0.65:
            accepted[key] = existing
            continue
        if not cand["critical"] and source in non_vision_sources and confidence >= 0.85:
            accepted[key] = value
            continue
        if cand["critical"]:
            corroborated = any(
                other.get("_candidate_index") != cand.get("_candidate_index")
                and normalize_param_key(other.get("key", "")) == key
                and other.get("source") in non_vision_sources
                and source in non_vision_sources
                and same_param_value(other.get("value"), value)
                for other in indexed_candidates
            )
            if corroborated and confidence >= 0.8:
                accepted[key] = value
                continue
            pending.append({**cand, "reason": "critical parameter requires user confirmation or corroboration"})
            continue
        pending.append({**cand, "reason": "confidence below auto-merge threshold"})
    def public_candidate(item: dict) -> dict:
        return {k: v for k, v in item.items() if k != "_candidate_index"}

    return {
        "accepted": accepted,
        "pending": [public_candidate(item) for item in pending],
        "rejected": [public_candidate(item) for item in rejected],
        "candidates": [public_candidate(item) for item in indexed_candidates],
    }


def infer_image_observations(image_refs: list | None, user_text: str = "", current_params: dict | None = None) -> list:
    """Create local, auditable screenshot observations before any LLM reasoning.

    OCR/vision outputs are treated as evidence. Only arbitration-approved
    parameters may be merged into state.params; critical parameters stay pending
    unless user text or corroborated local evidence supports them.
    """
    observations = []
    if not image_refs:
        return observations
    context_text = user_text or ""
    validator = InputValidator()
    for idx, ref in enumerate(image_refs, start=1):
        name = str(ref.get("image_name") or f"image_{idx}")
        joined = f"{context_text}\n{name}".lower()
        software = "unknown"
        if "relion" in joined:
            software = "relion"
        elif "cryosparc" in joined or "cryo sparc" in joined:
            software = "cryosparc"

        stage = "unknown"
        stage_patterns = [
            ("cp_01", ["import", "导入"]),
            ("cp_02", ["motion", "运动校正", "motioncorr"]),
            ("cp_03", ["ctf", "ctffind"]),
            ("cp_04", ["pick", "picker", "挑"]),
            ("cp_05", ["extract", "提取"]),
            ("cp_06", ["2d", "二维"]),
            ("cp_07", ["ab-initio", "ab initio", "初始模型"]),
            ("cp_08", ["heterogeneous", "3d class", "三维分类"]),
            ("cp_09", ["refine", "homogeneous", "精修"]),
        ]
        for cp_id, tokens in stage_patterns:
            if any(token in joined for token in tokens):
                stage = cp_id
                break

        candidates = []
        candidates.extend(extract_params_with_evidence(context_text, "user_text", 0.95, "user_text"))
        candidates.extend(extract_params_with_evidence(name, "filename", 0.55, "filename"))

        ocr = run_local_ocr(str(ref.get("image_path") or ""))
        if ocr.get("text"):
            candidates.extend(extract_params_with_evidence(ocr.get("text", ""), "ocr", 0.88, "local_ocr"))
        vision = run_optional_vision_model(ref, user_text)
        for cand in vision.get("candidates") or []:
            if isinstance(cand, dict):
                candidates.append({**cand, "source": "vision_model", "authority": "vision_model", "confidence": float(cand.get("confidence") or 0.5)})

        arbitration = arbitrate_image_params(candidates, current_params or {})
        params = arbitration.get("accepted") or {}
        param_check = validator.validate_params({**(current_params or {}), **params}) if params else None
        observation = {
            "image_name": name,
            "image_path": ref.get("image_path", ""),
            "software_guess": software,
            "stage_guess": stage,
            "visible_params": params,
            "accepted_params": params,
            "pending_params": arbitration.get("pending", []),
            "rejected_params": arbitration.get("rejected", []),
            "param_candidates": arbitration.get("candidates", []),
            "arbitration": arbitration,
            "ocr": {
                "available": bool(ocr.get("available")),
                "engine": ocr.get("engine", "none"),
                "text_excerpt": (ocr.get("text") or "").strip().replace("\n", " ")[:500],
                "error": ocr.get("error", ""),
            },
            "vision": vision,
            "confidence": "metadata_text",
            "width": ref.get("width"),
            "height": ref.get("height"),
            "sha256": ref.get("sha256", ""),
            "validation": param_check.to_dict() if param_check else {},
        }
        observations.append(observation)
    return observations


def format_image_observations(observations: list | None) -> str:
    """Format structured image evidence for downstream reasoning and audit logs."""
    if not observations:
        return ""
    lines = [
        "Local structured screenshot recognition: OCR/rules/vision are evidence only. "
        "Only accepted parameters enter state.params; pending/rejected candidates are not auto-written."
    ]
    for idx, obs in enumerate(observations, start=1):
        dims = f"{obs.get('width')}x{obs.get('height')}px" if obs.get("width") and obs.get("height") else "unknown-size"
        accepted = obs.get("accepted_params") or obs.get("visible_params") or {}
        pending = obs.get("pending_params") or []
        rejected = obs.get("rejected_params") or []
        ocr = obs.get("ocr") or {}
        vision = obs.get("vision") or {}
        accepted_text = ", ".join(f"{k}={v}" for k, v in accepted.items()) or "none"
        pending_text = ", ".join(
            f"{p.get('key')}={p.get('value')}({p.get('reason')})" for p in pending[:6]
        ) or "none"
        lines.append(
            f"Image {idx}: software={obs.get('software_guess')}, stage={obs.get('stage_guess')}, "
            f"size={dims}, OCR={ocr.get('engine', 'none')}/available={ocr.get('available', False)}, "
            f"vision_enabled={vision.get('enabled', False)}, accepted=[{accepted_text}], "
            f"pending=[{pending_text}], rejected={len(rejected)}"
        )
        validation = obs.get("validation") or {}
        if validation.get("concerns"):
            lines.append(f"Parameter validation concerns: {'; '.join(validation.get('concerns') or [])}")
    return "\n".join(lines)


def is_local_flow_command(text: str, image_refs: list | None = None) -> bool:
    """Return True for deterministic workflow commands that should not wait on LLM."""
    if image_refs:
        return False
    lowered = (text or "").lower().strip()
    if not lowered:
        return False
    triggers = [
        "开始", "start", "从头", "完成", "done", "通过", "ok", "没问题", "已经完成", "做完",
        "跳过", "skip", "进度", "progress", "到哪里了", "报告", "总结", "report",
        "怎么做", "如何做", "步骤", "操作", "流程", "sop", "标准流程", "指导", "指引",
    ]
    return any(token in lowered for token in triggers)


def handle_local_flow_command(text: str, response_profile: str = "teaching") -> PipelineState:
    """Run navigator/SOP deterministically for fast workflow feedback."""
    response_profile = normalize_response_profile(response_profile)
    state.response_profile = response_profile
    app.memory.ingest_user_message(state, text)
    reply, action = app.navigator.handle_input(state, text)
    if action == "stage_guide_sop":
        prefix = getattr(state, "_nav_prefix", "") or reply
        sop_reply = app.sop.quick_sop(state)
        reply = f"{prefix}\n\n---\n\n{sop_reply}" if prefix else sop_reply
        state._nav_prefix = ""
        action = "stage_guide"
    elif action == "param_advice":
        reply = app.expert.explain(state, text)
        action = "param_advice"
    elif action == "fault_diagnosis":
        validation = app.validator.validate_feedback(text)
        state.last_qc_result = validation.to_dict()
    if not reply:
        reply = app.navigator.get_stage_guide(state)
        action = "stage_guide"
    guide_card = load_guide_cards().get(state.current_cp_id, {}) if action == "stage_guide" else {}
    state.action_tag = action
    reply = format_response_for_profile(
        reply,
        response_profile,
        evidence_hint="本地流程规则与当前检查站 SOP。",
    )
    state.agent_reply = reply
    qa_trace = {
        "llm_enabled": False,
        "embedding_enabled": bool(getattr(app.llm, "embedding_enabled", False)),
        "images_attached": False,
        "image_count": 0,
        "image_observations_count": len(getattr(state, "image_observations", []) or []),
        "retrieved_docs": [],
        "citations": [],
        "timings_ms": {"total": 0, "retrieval": 0, "llm": 0},
        "fallback": True,
        "fallback_reason": "local_rule_mode",
        "guard": {"passed": True, "missing_facts": [], "checked_facts": []},
        "mode_label": "规则模式",
        "response_profile": response_profile,
    }
    metadata = {
        "local_only": True,
        "qa_trace": qa_trace,
        "response_profile": response_profile,
    }
    if guide_card:
        metadata["guide_card"] = guide_card
    state.add_message(
        "assistant",
        reply,
        action_tag=action,
        metadata=metadata,
    )
    try:
        app.memory.capture_state(state)
    except Exception as exc:
        state.error = f"会话保存失败：{exc}"
        state.error_node = "memory"
    return state


# --------------------------------------------------------------------------- #
# Page config & theme
# --------------------------------------------------------------------------- #
st.set_page_config(page_title=APP_DISPLAY_NAME, page_icon="🔬", layout="wide", initial_sidebar_state="expanded")

_ui_settings = load_ui_settings()
st.session_state.setdefault("ui_theme", _ui_settings["ui_theme"])
st.session_state.setdefault("selected_history_limit", _ui_settings["history_limit"])
st.session_state.setdefault("bg_image", _ui_settings.get("bg_image", ""))
st.session_state.setdefault("bg_opacity", _ui_settings.get("bg_opacity", 0.12))
st.session_state.setdefault("pet_enabled", _ui_settings.get("pet_enabled", True))
st.session_state.setdefault("pet_type", _ui_settings.get("pet_type", "penguin"))
st.session_state.setdefault("pet_size", _ui_settings.get("pet_size", 64))
st.session_state.setdefault("last_feedback", "")
st.session_state.setdefault("cp_notes", {})

# Apply pending pet changes BEFORE widget instantiation (Streamlit forbids
# modifying widget-bound session_state keys after the widget is created)
if "_pending_pet_type" in st.session_state:
    st.session_state.pet_type = st.session_state.pop("_pending_pet_type")
    save_ui_settings(pet_type=st.session_state.pet_type)
if "_pending_pet_enabled" in st.session_state:
    st.session_state.pet_enabled = st.session_state.pop("_pending_pet_enabled")
    save_ui_settings(pet_enabled=st.session_state.pet_enabled)
if "_pending_pet_size" in st.session_state:
    st.session_state.pet_size = int(st.session_state.pop("_pending_pet_size"))
    save_ui_settings(pet_size=st.session_state.pet_size)
# Clear pet action text BEFORE the widget is instantiated
if "_pending_clear_pet_action" in st.session_state:
    st.session_state.pop("_pending_clear_pet_action", None)
    st.session_state["_pet_action"] = ""

# Performance optimization: initialize centralized UI state manager
init_ui_state()

# 三模式架构：app_mode 控制UI层渲染方式（beginner / teaching / expert）
# 底层12步工作流、知识库、LangGraph 编排完全不受影响
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "beginner"  # 默认入门模式
if "mode_history" not in st.session_state:
    st.session_state.mode_history = []  # 记录切换历史
if "teaching_progress" not in st.session_state:
    st.session_state.teaching_progress = {}  # 教学进度追踪

# 视图详细程度控制（影响LLM回答和界面展示）
if "output_detail_level" not in st.session_state:
    st.session_state.output_detail_level = "详细"  # 简化/详细/完整

if st.session_state.ui_theme not in THEMES:
    st.session_state.ui_theme = "静谧蓝"
_theme = THEMES.get(st.session_state.ui_theme, THEMES["静谧蓝"])
_is_dark = st.session_state.ui_theme == "深邃黑"

# 背景图：用户可在「设置」中指定本地图片路径；为保证文字可读，叠加一层
# 半透明的主题色遮罩（opacity 越小背景图越清晰）。文件不存在时安静跳过。
_bg_url = image_data_url(st.session_state.get("bg_image", ""))
_bg_alpha = max(0.0, min(1.0, 1.0 - float(st.session_state.get("bg_opacity", 0.12))))
if _bg_url:
    if _is_dark:
        _bg_css = (
            f"linear-gradient(rgba(15,23,42,{_bg_alpha}), rgba(15,23,42,{_bg_alpha})), "
            f"url('{_bg_url}')"
        )
    else:
        _bg_css = (
            f"linear-gradient(rgba(255,255,255,{_bg_alpha}), rgba(255,255,255,{_bg_alpha})), "
            f"url('{_bg_url}')"
        )
    _app_bg = f"background: {_bg_css}; background-size: cover; background-position: center; background-attachment: fixed;"
else:
    _app_bg = f"background: {_theme['app']};"

# 右上角双机构 logo（上海科技大学 + iHuman 研究所）。文件存在才显示。
# Logo 放在侧边栏顶部而非 fixed 定位，避免被 Streamlit header 遮挡。
_logo1 = image_data_url(str(BASE_DIR / "assets" / "logo_shanghaitech.png"))
_logo2 = image_data_url(str(BASE_DIR / "assets" / "logo_ihuman.png"))
_logo_imgs = "".join(
    f'<img class="sp-brand-logo sp-brand-logo-{idx}" src="{u}" alt="institution logo" />'
    for idx, u in enumerate((_logo1, _logo2), start=1) if u
)

st.markdown(build_global_styles(_theme, _is_dark, _app_bg), unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# App & state bootstrap
# --------------------------------------------------------------------------- #
# Performance optimization: use @st.cache_resource to avoid rebuilding
# StructPilotApp (and all its agents, retriever, LangGraph) on every rerun.
# The app singleton is shared across all sessions in the same Streamlit process.
def _supports_current_app_api(candidate) -> bool:
    try:
        return "response_profile" in inspect.signature(candidate.handle).parameters
    except (AttributeError, TypeError, ValueError):
        return False


if "app" not in st.session_state or not _supports_current_app_api(st.session_state.app):
    # Session state can outlive a source-code hot reload. Clear only the app
    # resource here so the configured LLM singleton remains available.
    get_cached_app.clear()
    st.session_state.app = get_cached_app(APP_API_VERSION)
app: StructPilotApp = st.session_state.app

# Ensure LLM agent is the cached singleton (config may have been updated)
_cached_llm = get_cached_llm_agent()
if _cached_llm is not app.llm:
    app.llm = _cached_llm
    if hasattr(app, 'retriever'):
        app.retriever.llm = _cached_llm

if Path(getattr(app.memory, "memory_dir", "")).resolve() != MEMORY_DIR.resolve():
    from agents.memory_agent import MemoryAgent

    app.memory = MemoryAgent(memory_dir=str(MEMORY_DIR))

# Performance optimization: auto-detect LLM mode (basic / ai) and store in UI state
_llm_mode = detect_llm_mode(bool(getattr(app.llm, "enabled", False)))
set_llm_mode(_llm_mode)

# Clear KB cache if user modified knowledge base content
if consume_kb_dirty():
    perf_mark_kb_dirty()


def checkpoint_id_from_metadata(msg) -> str:
    """Extract checkpoint_id from message metadata or content."""
    meta = getattr(msg, "metadata", None) or {}
    if isinstance(meta, dict):
        cp = meta.get("checkpoint_id", "")
        if cp:
            return str(cp)
    # Fallback: search content for cp_xx pattern
    import re
    content = getattr(msg, "content", "") or ""
    m = re.search(r'\b(cp_\d+)\b', content)
    return m.group(1) if m else ""


def capture_state_safely(target_state: PipelineState, success_message: str = "") -> bool:
    """Persist state without letting a database write failure break the UI."""
    try:
        app.memory.capture_state(target_state)
    except Exception as exc:
        st.session_state.last_feedback = f"当前操作已完成，但会话保存失败：{exc}"
        return False
    if success_message:
        st.session_state.last_feedback = success_message
    return True


def trim_chat_history(state: PipelineState, max_messages: int = 50) -> None:
    """Trim chat history to prevent session_state bloat.

    When the number of messages exceeds ``max_messages``, older messages are
    summarized into a compact archive (persisted in ``st.session_state``) and
    dropped from ``state.messages``. Only the most recent ``max_messages``
    entries are kept, which is far more than LangGraph needs for context
    (``_build_context`` reads the last 10, ``_update_session_summary`` the
    last 6).

    The archived summary is re-injected into ``state.session_summary`` on every
    call so it stays visible to ``_build_context`` even after
    ``_update_session_summary`` overwrites the field during a reply turn.

    Idempotent: repeated calls with an unchanged state have no extra effect.
    """
    archived = st.session_state.get("_archived_chat_summary", "")

    if len(state.messages) <= max_messages:
        # Re-inject archived summary if _update_session_summary overwrote it.
        if archived and archived not in (state.session_summary or ""):
            base = state.session_summary or ""
            state.session_summary = (archived + "\n\n" + base).strip() if base else archived
        return

    # Keep only the most recent max_messages entries.
    old_messages = state.messages[:-max_messages]
    recent_messages = state.messages[-max_messages:]

    # Build compact text snippets for the messages being archived.
    old_texts = []
    for msg in old_messages:
        role = getattr(msg, "role", "unknown")
        content = getattr(msg, "content", str(msg))[:200]
        old_texts.append(f"[{role}] {content}")

    new_block = "--- 早期对话 ---\n" + "\n".join(old_texts)
    new_archived = (archived + "\n\n" + new_block).strip() if archived else new_block
    # Cap the archive so it cannot grow without bound across many trims.
    st.session_state._archived_chat_summary = new_archived[-2000:]

    # Surface the archive in session_summary for _build_context / SQLite persistence.
    old_summary = state.session_summary or ""
    if old_summary:
        state.session_summary = (st.session_state._archived_chat_summary + "\n\n" + old_summary)[-2000:]
    else:
        state.session_summary = st.session_state._archived_chat_summary

    state.messages = recent_messages


def explain_connection_result(result: str, label: str = "LLM", base_url: str = "") -> str:
    """Add actionable diagnostics when a provider test returns a raw requests error."""
    text = result or ""
    if "成功" in text or "ok" in text.lower():
        return text
    if "网络权限拒绝" in text or "Windows 网络权限" in text or "HTTP " in text:
        return text
    host_hint = ""
    if base_url:
        host_hint = f"目标：{base_url}。"
    if "WinError 10013" in text:
        return (
            f"{label}连接失败：Windows 网络权限拒绝了本程序的出站 HTTPS 连接。"
            "常见原因是防火墙、杀毒软件、代理/VPN 策略、校园/单位网络策略，"
            f"或 python.exe/streamlit.exe 未被允许访问网络。{host_hint}原始错误：{text[:520]}"
        )
    if "HTTPSConnectionPool" in text or "Max retries exceeded" in text or "Failed to establish a new connection" in text:
        return (
            f"{label}连接失败：无法建立到服务商的 HTTPS 连接。"
            "请先确认当前终端能访问该 Base URL，必要时配置代理/VPN或放行防火墙。"
            f"{host_hint}原始错误：{text[:520]}"
        )
    if "Invalid token" in text or "invalid token" in text.lower():
        return f"{label}连接失败：当前 API Key 无效或已过期，请在服务商控制台重新生成 Key 后保存。原始错误：{text[:520]}"
    if "401" in text or "403" in text:
        return f"{label}连接失败：API Key 无效、额度/权限不足，或当前 Key 没有访问该模型的权限。原始错误：{text[:520]}"
    if "404" in text:
        return f"{label}连接失败：接口路径或模型名可能不被服务商支持。请核对 Base URL 和 Model。原始错误：{text[:520]}"
    if "429" in text:
        return f"{label}连接失败：服务商限流或额度不足，请稍后重试或检查账号额度。原始错误：{text[:520]}"
    return text


def inject_smart_scroll() -> None:
    """Keep scrolling inside the chat pane and preserve reading position."""
    target = st.session_state.get("_sp_scroll_target", "none")
    st.session_state._sp_scroll_target = "none"
    session_key = json.dumps(str(getattr(state, "session_id", "default")))
    target_json = json.dumps(str(target or "none"))
    st.html(
        f"""
        <script>
        (function() {{
            const doc = window.parent.document;
            const target = {target_json};
            const storageKey = 'sp-chat-scroll:' + {session_key};
            const badgeId = 'sp-new-answer-badge';

            function findScrollablePane(anchor) {{
                let node = anchor ? anchor.parentElement : null;
                while (node && node !== doc.body) {{
                    const style = window.parent.getComputedStyle(node);
                    const overflow = style.overflowY;
                    if (node.scrollHeight > node.clientHeight + 24 && (overflow === 'auto' || overflow === 'scroll')) {{
                        return node;
                    }}
                    node = node.parentElement;
                }}
                return null;
            }}

            function readSaved() {{
                try {{ return JSON.parse(window.parent.sessionStorage.getItem(storageKey) || 'null'); }}
                catch (e) {{ return null; }}
            }}

            function save(pane) {{
                const payload = {{
                    top: pane.scrollTop,
                    atBottom: pane.scrollHeight - pane.scrollTop - pane.clientHeight < 72
                }};
                try {{ window.parent.sessionStorage.setItem(storageKey, JSON.stringify(payload)); }} catch (e) {{}}
            }}

            function removeBadge() {{
                const old = doc.getElementById(badgeId);
                if (old) old.remove();
            }}

            function showBadge(pane) {{
                removeBadge();
                const button = doc.createElement('button');
                button.id = badgeId;
                button.textContent = '有新回答，点击查看';
                button.style.cssText = 'position:fixed;right:58px;bottom:82px;z-index:999996;border:1px solid #93c5fd;background:#eff6ff;color:#1d4ed8;padding:8px 12px;border-radius:6px;font-size:13px;font-weight:650;box-shadow:0 6px 18px rgba(15,23,42,.14);cursor:pointer;';
                button.onclick = function() {{
                    pane.scrollTo({{top:pane.scrollHeight, behavior:'smooth'}});
                    save(pane);
                    removeBadge();
                }};
                doc.body.appendChild(button);
            }}

            setTimeout(function() {{
                const bottom = doc.getElementById('chat-bottom');
                const pane = findScrollablePane(bottom);
                if (!pane) return;
                const saved = readSaved();
                if (target === 'chat_bottom') {{
                    if (!saved || saved.atBottom) {{
                        pane.scrollTo({{top:pane.scrollHeight, behavior:'smooth'}});
                        removeBadge();
                    }} else {{
                        pane.scrollTop = Math.min(saved.top || 0, pane.scrollHeight - pane.clientHeight);
                        showBadge(pane);
                    }}
                }} else if (target === 'step_workspace') {{
                    const ws = doc.getElementById('sp-work-area');
                    if (ws) {{
                        ws.scrollIntoView({{behavior:'smooth', block:'start'}});
                        removeBadge();
                    }}
                }} else if (saved && !saved.atBottom) {{
                    pane.scrollTop = Math.min(saved.top || 0, pane.scrollHeight - pane.clientHeight);
                }}
                pane.addEventListener('scroll', function() {{
                    save(pane);
                    if (pane.scrollHeight - pane.scrollTop - pane.clientHeight < 72) removeBadge();
                }}, {{passive:true}});
                save(pane);
            }}, 320);
        }})();
        </script>
        """
    )


def render_scroll_shortcuts() -> None:
    """Render fixed right-side shortcuts for jumping to page top or bottom."""
    st.html(
        """
        <script>
        (function() {
            const doc = window.parent.document;
            const win = window.parent;
            const styleId = 'sp-scroll-shortcuts-style';
            const barId = 'sp-scroll-shortcuts';
            const topAnchorId = 'sp-page-top-anchor';
            const bottomAnchorId = 'sp-page-bottom-anchor';

            let style = doc.getElementById(styleId);
            if (!style) {
                style = doc.createElement('style');
                style.id = styleId;
                style.textContent = `
                    #sp-scroll-shortcuts {
                        position: fixed;
                        right: 12px;
                        top: 50%;
                        transform: translateY(-50%);
                        z-index: 999997;
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        pointer-events: auto;
                    }
                    #sp-scroll-shortcuts button {
                        width: 34px;
                        height: 34px;
                        border: 1px solid rgba(148, 163, 184, 0.34);
                        border-radius: 8px;
                        background: rgba(255, 255, 255, 0.92);
                        color: #334155;
                        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.10);
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 18px;
                        font-weight: 800;
                        line-height: 1;
                        cursor: pointer;
                        user-select: none;
                        touch-action: manipulation;
                        transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
                    }
                    #sp-scroll-shortcuts button:hover {
                        transform: translateY(-1px);
                        border-color: rgba(99, 102, 241, 0.62);
                        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
                    }
                    #sp-scroll-shortcuts button:active {
                        transform: translateY(0);
                    }
                    @media (max-width: 760px) {
                        #sp-scroll-shortcuts {
                            right: 10px;
                            top: auto;
                            bottom: 92px;
                            transform: none;
                        }
                        #sp-scroll-shortcuts button {
                            width: 34px;
                            height: 34px;
                            font-size: 16px;
                        }
                    }
                `;
                doc.head.appendChild(style);
            }

            const existing = doc.getElementById(barId);
            if (existing) existing.remove();

            let topAnchor = doc.getElementById(topAnchorId);
            if (!topAnchor) {
                topAnchor = doc.createElement('div');
                topAnchor.id = topAnchorId;
                topAnchor.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:1px;pointer-events:none;';
                doc.body.prepend(topAnchor);
            }
            let bottomAnchor = doc.getElementById(bottomAnchorId);
            if (!bottomAnchor) {
                bottomAnchor = doc.createElement('div');
                bottomAnchor.id = bottomAnchorId;
                bottomAnchor.style.cssText = 'width:1px;height:1px;pointer-events:none;';
                doc.body.appendChild(bottomAnchor);
            }

            function findMainScroller() {
                const candidates = [
                    doc.querySelector('[data-testid="stMain"]'),
                    doc.querySelector('section[data-testid="stMain"]'),
                    doc.querySelector('.stMain'),
                    doc.scrollingElement,
                    doc.documentElement,
                    doc.body
                ].filter(Boolean);
                return candidates.find(function(el) {
                    return el.scrollHeight > el.clientHeight + 24;
                }) || doc.scrollingElement || doc.documentElement || doc.body;
            }
            function scrollMain(direction, smooth) {
                const main = findMainScroller();
                const top = direction === 'bottom' ? Math.max(0, main.scrollHeight - main.clientHeight) : 0;
                const behavior = smooth === false ? 'auto' : 'smooth';
                if (main.scrollTo) main.scrollTo({ top: top, behavior: behavior });
                else main.scrollTop = top;
                if (direction === 'top') {
                    win.scrollTo({ top: 0, behavior: behavior });
                    topAnchor.scrollIntoView({ behavior: behavior, block: 'start' });
                } else {
                    win.scrollTo({ top: Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight), behavior: behavior });
                    bottomAnchor.scrollIntoView({ behavior: behavior, block: 'end' });
                }
                return { top: main.scrollTop, max: Math.max(0, main.scrollHeight - main.clientHeight) };
            }
            const inlineScroll = "event.preventDefault();event.stopPropagation();" +
                "const m=document.querySelector('[data-testid=\\\"stMain\\\"]')||document.querySelector('section[data-testid=\\\"stMain\\\"]')||document.scrollingElement||document.documentElement||document.body;" +
                "const d=this.getAttribute('data-sp-scroll');" +
                "const t=d==='bottom'?Math.max(0,m.scrollHeight-m.clientHeight):0;" +
                "if(m.scrollTo)m.scrollTo({top:t,behavior:'smooth'});else m.scrollTop=t;" +
                "setTimeout(()=>{if(m.scrollTo)m.scrollTo({top:t,behavior:'auto'});else m.scrollTop=t;},220);" +
                "return false;";
            win.StructPilotScrollTo = function(direction) {
                scrollMain(direction, true);
                setTimeout(function() { scrollMain(direction, false); }, 180);
                setTimeout(function() { scrollMain(direction, false); }, 420);
                return false;
            };

            const bar = doc.createElement('div');
            bar.id = barId;
            bar.setAttribute('data-sp-version', '3');
            bar.innerHTML = `
                <button type="button" data-sp-scroll="top" aria-label="回到页面顶端" title="回到页面顶端">↑</button>
                <button type="button" data-sp-scroll="bottom" aria-label="到页面底端" title="到页面底端">↓</button>
            `;
            bar.querySelectorAll('[data-sp-scroll]').forEach(function(button) {
                button.setAttribute('onclick', inlineScroll);
                button.setAttribute('onpointerdown', inlineScroll);
            });
            bar.addEventListener('pointerdown', function(event) {
                const button = event.target.closest('[data-sp-scroll]');
                if (!button) return;
                event.preventDefault();
                event.stopPropagation();
                win.StructPilotScrollTo(button.getAttribute('data-sp-scroll'));
            }, true);
            bar.addEventListener('click', function(event) {
                const button = event.target.closest('[data-sp-scroll]');
                if (!button) return;
                event.preventDefault();
                event.stopPropagation();
                win.StructPilotScrollTo(button.getAttribute('data-sp-scroll'));
            }, true);
            doc.body.appendChild(bar);
        })();
        </script>
        """
    )


render_scroll_shortcuts()

if "state" not in st.session_state:
    latest_sid = app.memory.get_latest_session_id()
    restored = app.memory.load_state(latest_sid) if latest_sid else None
    st.session_state.state = restored or PipelineState(session_id=latest_sid or make_session_id())

state: PipelineState = st.session_state.state
trim_chat_history(state)
st.session_state.setdefault("_sp_scroll_target", "none")
cp_total = len(app.navigator.checkpoints) or 12
cp_progress = len(state.completed) / cp_total if cp_total else 0


def run_command(
    text: str,
    image_refs: list | None = None,
    *,
    input_metadata: dict | None = None,
    response_profile: str | None = None,
) -> None:
    """Send text (and optional images) through the agent pipeline and persist."""
    image_refs = image_refs or []
    input_metadata = dict(input_metadata or {})
    response_profile = normalize_response_profile(
        response_profile or get_state("output_mode", "teaching")
    )
    state.response_profile = response_profile
    progress = st.status(
        "正在处理图片和问题…" if image_refs else "正在理解问题…",
        expanded=True,
        state="running",
    )
    if image_refs:
        progress.write(f"上传完成：已接收 {len(image_refs)} 张图片")
    query_view = normalize_query(
        text,
        default_software=getattr(state, "software", ""),
        default_checkpoint=getattr(state, "current_cp_id", ""),
    )
    st.session_state.last_normalized_query = query_view.to_dict()
    if image_refs:
        state.pending_images.extend(image_refs)

    if image_refs:
        progress.write("正在执行 OCR、参数抽取和图像证据校验…")
    observations = infer_image_observations(image_refs, text, state.params)
    if observations:
        if not hasattr(state, "image_observations"):
            state.image_observations = []
        state.image_observations.extend(observations)
        for obs in observations:
            accepted_params = obs.get("accepted_params") or (obs.get("arbitration") or {}).get("accepted") or {}
            if accepted_params:
                state.params.update(accepted_params)
        param_result = InputValidator().validate_params(state.params)
        pending_candidates = [p for obs in observations for p in (obs.get("pending_params") or [])]
        rejected_candidates = [p for obs in observations for p in (obs.get("rejected_params") or [])]
        if not param_result.passed:
            state.last_qc_result = param_result.to_dict()
        elif pending_candidates or rejected_candidates:
            state.last_qc_result = {
                "passed": True,
                "summary": "Image recognition produced candidates requiring review",
                "concerns": [
                    f"{len(pending_candidates)} pending parameter candidate(s) were not written to state.params",
                    f"{len(rejected_candidates)} rejected parameter candidate(s) were kept for audit",
                ],
                "suggestion": "Confirm critical parameters from microscope/job metadata before accepting them.",
                "metadata": {
                    "pending_image_params": pending_candidates[:20],
                    "rejected_image_params": rejected_candidates[:20],
                },
            }

    if is_local_flow_command(text, image_refs):
        progress.write("正在匹配本地流程规则与 SOP…")
        new_state = handle_local_flow_command(text, response_profile=response_profile)
        for msg in reversed(new_state.messages):
            if msg.role == "user":
                msg.metadata.update(input_metadata)
                msg.metadata["response_profile"] = response_profile
                if image_refs:
                    msg.image_refs = image_refs
                    msg.metadata["image_observations"] = observations
                break
        st.session_state.state = new_state
        capture_state_safely(new_state)
        progress.update(label="回答已生成", state="complete", expanded=False)
        return

    image_context = describe_image_refs(image_refs)
    observation_context = format_image_observations(observations)
    context_blocks = [block for block in (image_context, observation_context) if block]
    agent_query = query_view.normalized or text
    agent_text = f"{agent_query}\n\n" + "\n\n".join(context_blocks) if context_blocks else agent_query
    progress.write("正在检索知识库并生成回答…")
    _stream_box = st.empty()
    _stream_box.markdown("正在生成回答…")
    _accum = {"text": ""}

    def _stream_sink(chunk: str) -> None:
        _accum["text"] += chunk
        _stream_box.markdown(_accum["text"] + "▌")

    new_state = app.handle(
        state,
        agent_text,
        response_profile=response_profile,
        stream_sink=_stream_sink,
    )
    _stream_box.empty()
    for msg in reversed(new_state.messages):
        if msg.role == "user":
            msg.content = text
            msg.image_refs = image_refs
            msg.metadata["normalized_query"] = query_view.to_dict()
            msg.metadata["response_profile"] = response_profile
            msg.metadata.update(input_metadata)
            if image_refs:
                msg.metadata["image_context"] = image_context
                msg.metadata["image_observations"] = observations
            break
    st.session_state.state = new_state
    capture_state_safely(new_state)
    progress.update(label="识别、检索和回答已完成", state="complete", expanded=False)

    # LLM 降级提示：仅当 LLM 实际调用失败时提醒用户（排除规则模式等有意降级）
    _last_msg = new_state.messages[-1] if new_state.messages else None
    _trace = getattr(_last_msg, "metadata", {}).get("qa_trace", {}) if _last_msg else {}
    if _trace.get("fallback") and str(_trace.get("fallback_reason", "")).startswith("llm_error"):
        _reason = _trace.get("fallback_reason", "未知原因")
        st.warning(f"⚠️ LLM 调用失败（{_reason}），已使用本地规则回复。请在设置页检查 API 配置。")


def switch_checkpoint(cp_id: str) -> None:
    """Jump the active coaching context to a checkpoint without changing pass/fail progress."""
    cp = next((item for item in app.navigator.checkpoints if item.get("checkpoint_id") == cp_id), None)
    if not cp:
        st.session_state.last_feedback = f"未找到阶段：{cp_id}"
        return
    state.current_cp_id = cp_id
    state.current_cp_name = cp.get("checkpoint_cn", "")
    state.session_started = True
    rec = state.checkpoint_records.get(cp_id)
    if rec is None or rec.status == "pending":
        state.mark_checkpoint(cp_id, "in_progress", "手动跳转到该阶段", "sidebar_jump")
    state.user_input = ""
    state.user_input_lower = ""
    state.action_tag = "stage_guide_sop"
    state._nav_prefix = f"已切换到 {cp_id} · {state.current_cp_name}"
    sop_reply = app.sop.quick_sop(state)
    state.action_tag = "stage_guide"
    full_reply = f"{state._nav_prefix}\n\n---\n\n{sop_reply}"
    state._nav_prefix = ""
    state.agent_reply = full_reply
    guide_card = load_guide_cards().get(cp_id, {})
    state.add_message(
        "assistant",
        state.agent_reply,
        action_tag="stage_guide",
        metadata={
            "source": "sidebar_checkpoint_jump",
            "checkpoint_id": cp_id,
            "guide_card": guide_card,
            "local_only": True,
        },
    )
    try:
        app.memory.capture_state(state)
    except Exception:
        pass
    st.session_state.state = state
    st.session_state._sp_scroll_target = "step_workspace"
    capture_state_safely(state, f"已切换到：{cp_id} · {state.current_cp_name}")


# --------------------------------------------------------------------------- #
# Sidebar: progress + session management + summary
# --------------------------------------------------------------------------- #
with st.sidebar:
    # Compact brand header: logo + title in one row
    st.markdown(
        '<div class="sp-brand-block">'
        f'<div class="sp-brand-bar">{_logo_imgs}</div>'
        f'<div class="sp-app-title">{APP_DISPLAY_NAME}</div>'
        '<div class="sp-app-subtitle">cryo-EM 流程陪跑</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Runtime engine indicator (rule-only / AI-enhanced).
    _cur_mode = get_llm_mode()
    _mode_icon = "🤖" if _cur_mode == "ai" else "📘"
    _mode_color = "#059669" if _cur_mode == "ai" else "#64748b"
    st.markdown(
        f'<div class="sp-mode-indicator" style="display:flex;align-items:center;gap:6px;margin:4px 0 8px 0;">'
        f'<span style="font-size:1rem;">{_mode_icon}</span>'
        f'<span style="font-size:0.82rem;color:{_mode_color};font-weight:600;">运行引擎：{get_mode_label()}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ✨ 用户登录/笔记入口
    from utils.user_manager import get_current_user, set_local_user
    current_user = get_current_user()

    with st.expander("👤 用户笔记", expanded=False):
        if not current_user:
            st.caption("本地模式：输入用户名后可保存个人笔记")
            username_input = st.text_input("用户名", placeholder="例：张三", key="user_login_input", label_visibility="collapsed")
            if st.button("登录", use_container_width=True, key="user_login_btn"):
                if username_input.strip():
                    set_local_user(username_input)
                    st.rerun()
                else:
                    st.warning("请输入用户名")
        else:
            st.caption(f"当前用户：**{current_user}**")
            from utils.user_manager import load_user_notes
            notes = load_user_notes(current_user)
            st.caption(f"已保存 {len(notes)} 条笔记")
            if st.button("📝 查看我的笔记", use_container_width=True, key="view_my_notes"):
                st.session_state["_show_user_notes"] = True
            if st.button("🚪 退出登录", use_container_width=True, key="user_logout"):
                set_local_user("")
                st.rerun()

    # P0-A2: 软件切换入口（RELION / cryoSPARC）
    _software_options = {"RELION": "relion", "cryoSPARC": "cryosparc"}
    _sw_labels = list(_software_options.keys())
    _sw_idx = 0 if state.software == "relion" else 1
    _selected_sw = st.selectbox("软件", options=_sw_labels, index=_sw_idx, key="software_selector")
    _new_sw = _software_options[_selected_sw]
    if _new_sw != state.software:
        state.software = _new_sw
        state.add_message("assistant", f"已切换到 {_selected_sw} 陪跑模式。", action_tag="software_switch")
        st.rerun()

    # 三模式切换器
    st.markdown("### 交互模式")
    _mode_options = {
        "beginner": "🌱 入门模式",
        "teaching": "🎓 教学模式",
        "expert": "⚙️ 高级模式",
    }
    _mode_labels = list(_mode_options.values())
    _current_mode = st.session_state.app_mode
    _mode_idx = list(_mode_options.keys()).index(_current_mode)
    _selected_mode_label = st.selectbox(
        "选择模式",
        options=_mode_labels,
        index=_mode_idx,
        key="mode_selector",
        help="入门：傻瓜式SOP；教学：原理卡片+测验；高级：参数导出+预设",
    )
    _new_mode = [k for k, v in _mode_options.items() if v == _selected_mode_label][0]
    if _new_mode != _current_mode:
        st.session_state.mode_history.append((_current_mode, _new_mode))
        st.session_state.app_mode = _new_mode
        st.rerun()

    st.markdown("### 流程进度")
    st.progress(cp_progress, text=f"{len(state.completed)}/{cp_total} · {cp_progress:.0%}")

    _stats_html = (
        f'<div class="sp-progress-stats">'
        f'<span class="sp-stat-passed">✓ {len(state.completed)}</span>'
        f'<span class="sp-stat-failed">✕ {len(state.failed)}</span>'
        f'<span class="sp-stat-skipped">– {len(state.skipped)}</span>'
        f'</div>'
    )
    st.markdown(_stats_html, unsafe_allow_html=True)

    # 入门模式：显示定制化流程提示
    if st.session_state.app_mode == "beginner" and st.session_state.get("onboarding_completed"):
        workflow = st.session_state.get("recommended_workflow", {})
        if workflow:
            total_steps = len(workflow.get("steps", []))
            skip_count = len(workflow.get("skip_steps", []))
            st.caption(
                f"📌 定制流程：{total_steps} 步（跳过 {skip_count} 步）  \n"
                f"目标：{st.session_state.user_profile.get('goal', '未知')}"
            )

    sidebar_checkpoints = sorted(app.navigator.checkpoints, key=lambda item: item.get("order", 999))
    current_idx = next((i for i, cp in enumerate(sidebar_checkpoints) if cp.get("checkpoint_id") == state.current_cp_id), -1)
    current_cp = sidebar_checkpoints[current_idx] if current_idx >= 0 else None
    if current_cp:
        st.caption(current_cp.get('checkpoint_cn', state.current_cp_name))

    status_icons = {
        "pending": "○",
        "in_progress": "●",
        "passed": "✓",
        "failed": "✕",
        "skipped": "–",
    }

    # 按阶段分组检查点
    phases_dict = {}
    current_phase = None
    for cp in sidebar_checkpoints:
        phase = cp.get("phase", "未分类")
        if phase not in phases_dict:
            phases_dict[phase] = []
        phases_dict[phase].append(cp)
        # 确定当前步骤所在阶段
        if cp.get("checkpoint_id") == state.current_cp_id:
            current_phase = phase

    # 渲染分组折叠的检查点
    with st.container(border=False):
        for phase_name, phase_cps in phases_dict.items():
            # 当前阶段默认展开
            is_current_phase = (phase_name == current_phase)

            with st.expander(f"{'▼' if is_current_phase else '▶'} {phase_name}", expanded=is_current_phase):
                for cp in phase_cps:
                    cid = cp.get("checkpoint_id", "")
                    rec = state.checkpoint_records.get(cid)
                    status = rec.status if rec else "pending"
                    is_current = (cid == state.current_cp_id)
                    if status == "in_progress" and not is_current:
                        status = "pending"
                    _, status_label = STATUS_LABELS.get(status, ("", status))
                    icon = status_icons.get(status, "○")
                    stage_name = cp.get("checkpoint_cn") or cp.get("checkpoint_name") or "checkpoint"

                    # 入门模式：检查是否在跳过列表中
                    is_skipped_in_workflow = False
                    if st.session_state.app_mode == "beginner" and st.session_state.get("onboarding_completed"):
                        skip_steps = st.session_state.get("recommended_workflow", {}).get("skip_steps", [])
                        if cid in skip_steps:
                            is_skipped_in_workflow = True
                            icon = "⊗"  # 跳过标记（st.button 不渲染 Markdown，⊗ 图标已足够）

                    # 当前步骤使用实心圆点强调
                    if is_current:
                        button_label = f"● {icon}  {stage_name}"
                    else:
                        button_label = f"{icon}  {stage_name}"

                    if st.button(
                        button_label,
                        key=f"checkpoint_nav_{cid}",
                        help=f"{cid} · {stage_name} — {status_label}",
                        use_container_width=True,
                        type="primary" if is_current else "secondary",
                    ):
                        switch_checkpoint(cid)
                        st.rerun()

                    # 当前步骤显示备注区
                    if is_current:
                        _note_val = st.session_state.cp_notes.get(cid, "")
                        _note_key = f"cp_note_{cid}"
                        if _note_key not in st.session_state:
                            st.session_state[_note_key] = _note_val
                        _new_note = st.text_area(
                            "备注",
                            key=_note_key,
                            label_visibility="collapsed",
                            height=68,
                            placeholder="在此记录当前阶段的备注、参数或注意事项...",
                            help="为当前检查点添加备注，备注会自动保存",
                        )
                        if _new_note != st.session_state.cp_notes.get(cid, ""):
                            st.session_state.cp_notes[cid] = _new_note

    st.divider()
    st.markdown("### 会话")

    # 新建会话
    st.text_input("新会话名称", key="new_session_name", placeholder="例如：膜蛋白样品A")
    if st.button("＋ 新建会话", use_container_width=True, type="secondary"):
        new_id = make_session_id()
        new_state = PipelineState(session_id=new_id)
        setattr(new_state, "session_name", st.session_state.get("new_session_name", "").strip() or new_id)
        capture_state_safely(new_state)
        st.session_state.state = new_state
        st.session_state.last_feedback = "已新建会话"
        st.rerun()

    # 历史会话列表（可点击切换，与检查点列表交互一致）
    sessions = {item["session_id"]: item for item in app.memory.list_sessions()}
    if sessions:
        with st.expander(f"历史会话（{len(sessions)}）", expanded=False):
            for sid, meta in sessions.items():
                sname = meta.get("session_name", sid)
                is_current = (sid == state.session_id)
                if is_current:
                    btn_label = f"● {sname}"
                else:
                    btn_label = f"○ {sname}"
                if st.button(
                    btn_label,
                    key=f"session_nav_{sid}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                ):
                    restored = app.memory.load_state(sid)
                    if restored is not None:
                        st.session_state.state = restored
                        st.session_state.last_feedback = "已恢复会话"
                        st.rerun()

    # 会话管理（重命名/删除）
    with st.expander("会话管理"):
        rename_value = st.text_input("重命名", value=getattr(state, "session_name", state.session_id), key="rename_session_input")
        if st.button("保存名称", use_container_width=True):
            setattr(state, "session_name", rename_value.strip() or state.session_id)
            app.memory.rename_session(state.session_id, getattr(state, "session_name", state.session_id))
            capture_state_safely(state)
            st.session_state.last_feedback = "已保存名称"
            st.rerun()

        st.caption(f"当前会话：{state.session_id}")
        confirm_delete = st.checkbox("确认删除当前会话（不可恢复）", key="confirm_delete_session")
        if st.button("删除当前会话", use_container_width=True, disabled=not confirm_delete):
            app.memory.delete_session(state.session_id)
            latest = app.memory.get_latest_session_id()
            restored = app.memory.load_state(latest) if latest else None
            st.session_state.state = restored or PipelineState(session_id=make_session_id())
            st.session_state.last_feedback = "已删除会话"
            st.rerun()

    st.caption(f"LLM：{app.llm.status_text()}")


# --------------------------------------------------------------------------- #
# UI: workspace CSS + output mode + quick questions
# --------------------------------------------------------------------------- #

# Quick questions per checkpoint (used in chat tab)
_QUICK_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "cp_01": [
        ("pixel size 怎么设？", "pixel size 应该怎么设置？实验室常用值是多少？"),
        ("电压和 Cs 怎么填？", "加速电压和球差 Cs 值应该填多少？"),
        ("导入哪些文件？", "应该导入 movies 还是 micrographs？文件格式要求？"),
    ],
    "cp_02": [
        ("漂移太大怎么办？", "运动校正后漂移很大，应该怎么处理？"),
        ("B-factor 怎么设？", "MotionCor2 的 B-factor 默认值是多少？需要调整吗？"),
        ("patch 大小怎么选？", "Number of patches 应该设多少？5x5 够吗？"),
    ],
    "cp_03": [
        ("CTF fit 质量怎么判断？", "CTF 拟合质量怎么判断好坏？分辨率阈值是多少？"),
        ("哪些照片该删？", "Manual Curate 时应该剔除哪些照片？标准是什么？"),
        ("defocus 范围怎么设？", "defocus 搜索范围应该设多大？"),
    ],
    "cp_04": [
        ("颗粒直径怎么测？", "怎么用 PyMOL 测定蛋白外接圆直径？"),
        ("Blob 还是 Topaz？", "Blob Picker 和 Topaz 应该选哪个？怎么组合？"),
        ("NCC vs Power 怎么看？", "NCC vs Power 图怎么解读？怎么判断真假粒子？"),
    ],
    "cp_05": [
        ("box size 怎么算？", "box size 应该怎么计算？公式是什么？"),
        ("要不要 bin？", "第一轮要不要 Fourier crop？crop 到多少？"),
        ("box 太大太小会怎样？", "box size 太大或太小会有什么问题？"),
    ],
    "cp_06": [
        ("class 很糊怎么办？", "2D 分类结果很模糊，class 不清晰怎么办？"),
        ("分类数怎么设？", "Number of classes 应该设多少？100 还是 50？"),
        ("可以进入 3D 吗？", "2D 分类后什么时候可以进入 3D？判断标准是什么？"),
    ],
    "cp_07": [
        ("初始模型不好怎么办？", "Ab-initio 生成的 3D 模型不像蛋白怎么办？"),
        ("要做几个 class？", "Ab-initio 应该做几个 class？3 个够吗？"),
        ("忘了去重怎么办？", "忘记 Remove Duplicates 会有什么影响？"),
    ],
    "cp_08": [
        ("输入所有 model 吗？", "Heterogeneous Refinement 要输入所有 Ab-initio model 吗？"),
        ("选哪个 class？", "3D 分类后应该选哪个 class 进入精修？"),
        ("构象差异怎么看？", "怎么判断不同 class 之间是否有真实构象差异？"),
    ],
    "cp_09": [
        ("FSC 怎么看？", "FSC 曲线怎么看？0.143 阈值意味着什么？"),
        ("取向偏侧怎么办？", "取向分布不均匀怎么办？怎么改善？"),
        ("Non-uniform 必须做吗？", "Non-uniform Refinement 是必须的吗？不做会怎样？"),
    ],
    "cp_10": [
        ("什么时候做 CTF 精修？", "什么时候适合做 CTF refinement？需要什么前提？"),
        ("能提多少分辨率？", "CTF 精修通常能提升多少分辨率？"),
        ("Local 还是 Global？", "Local CTF 和 Global CTF 有什么区别？都要做吗？"),
    ],
    "cp_11": [
        ("B-factor 怎么选？", "锐化的 B-factor 应该怎么选？自动还是手动？"),
        ("mask 怎么做？", "mask 应该怎么做才不会虚高 FSC？"),
        ("分辨率怎么确认？", "最终分辨率怎么确认？金标准 FSC 是什么？"),
    ],
    "cp_12": [
        ("Ramachandran 标准？", "Ramachandran 图的合格标准是什么？"),
        ("FSC_work vs FSC_free？", "FSC_work 和 FSC_free 差距大说明什么？"),
        ("低分辨率怎么建模？", "分辨率不够时应该怎么建模？Cα trace 够吗？"),
    ],
}


def _get_current_checkpoint_data(app: StructPilotApp, state: PipelineState) -> dict:
    """Get the current checkpoint JSON data."""
    cp_id = state.current_cp_id
    for cp in app.navigator.checkpoints:
        if cp.get("checkpoint_id") == cp_id:
            return cp
    return {}


def _render_output_mode_toggle(compact: bool = False) -> str:
    """Render view detail level selector (影响LLM回答详细程度和界面展示)."""
    from utils.ui_state_manager import get_output_mode, set_output_mode

    # 新版：三级视图切换
    view_options = {
        "简化": {
            "icon": "⚡",
            "desc": "简洁回答，只给结论",
            "profile": "concise",
        },
        "详细": {
            "icon": "📖",
            "desc": "完整解释，包含原理",
            "profile": "standard",
        },
        "完整": {
            "icon": "🔬",
            "desc": "全部细节+参数+公式",
            "profile": "comprehensive",
        },
    }

    current_level = st.session_state.output_detail_level

    if compact:
        # 紧凑模式：segmented_control
        selected = st.segmented_control(
            "当前视图",
            options=list(view_options.keys()),
            default=current_level,
            format_func=lambda x: f"{view_options[x]['icon']} {x}",
            key="view_detail_selector",
            label_visibility="collapsed",
            help="调节LLM回答的详细程度和界面信息密度",
        )
    else:
        # 完整模式：带说明的选择器
        st.markdown("**回答详细程度**")
        cols = st.columns(3)
        selected = current_level

        for i, (level, opt) in enumerate(view_options.items()):
            with cols[i]:
                is_current = (level == current_level)
                if st.button(
                    f"{opt['icon']} **{level}**\n\n{opt['desc']}",
                    key=f"view_{level}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                ):
                    selected = level

    # 保存状态并同步到 output_mode
    if selected != current_level:
        st.session_state.output_detail_level = selected
        # 同步到原有的 output_mode 系统
        set_output_mode(view_options[selected]["profile"])
        st.rerun()

    # 返回当前profile（保持向后兼容）
    return view_options[current_level]["profile"]



def _render_quick_questions(state: PipelineState, key_prefix: str = "qq") -> None:
    """Render quick question chips for the current checkpoint."""
    cp_id = state.current_cp_id
    questions = _QUICK_QUESTIONS.get(cp_id, [])
    if not questions:
        return

    st.markdown("**快捷提问**")
    cols = st.columns(min(len(questions), 3))
    for i, (short_q, full_q) in enumerate(questions):
        with cols[i % len(cols)]:
            if st.button(
                short_q,
                key=f"{key_prefix}_{cp_id}_{i}",
                use_container_width=True,
                help=full_q,
            ):
                run_command(full_q)
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()


def _render_summary_cards(checkpoint: dict, state: PipelineState) -> None:
    """渲染左侧摘要卡片（紧凑网格布局）。"""
    if not checkpoint:
        return

    cp_id = checkpoint.get("checkpoint_id", "")
    stage_goal = checkpoint.get("stage_goal", "")
    input_needed = checkpoint.get("input_needed", "")
    sw_data = checkpoint.get(state.software, {}) if isinstance(checkpoint.get(state.software), dict) else {}
    sw_output = sw_data.get("output", "")
    key_steps = sw_data.get("key_steps", []) or []
    qc_checks = checkpoint.get("qc_check", []) or []

    # 2x2 网格布局
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        if stage_goal:
            with st.expander("🎯 目标", expanded=True):
                st.caption(stage_goal[:150] + "..." if len(stage_goal) > 150 else stage_goal)

    with row1_col2:
        if input_needed or sw_output:
            with st.expander("📥📤 I/O", expanded=True):
                if input_needed:
                    st.caption(f"输入: {input_needed[:80]}")
                if sw_output:
                    st.caption(f"输出: {sw_output[:80]}")

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        if key_steps:
            with st.expander(f"📋 步骤({len(key_steps)})", expanded=False):
                for idx, step in enumerate(key_steps[:3], 1):
                    st.caption(f"{idx}. {step[:60]}")

    with row2_col2:
        if qc_checks:
            with st.expander(f"✅ 质控({len(qc_checks)})", expanded=False):
                for qc in qc_checks[:3]:
                    st.caption(f"• {qc[:60]}")


# --------------------------------------------------------------------------- #
# Main area: tabs
# --------------------------------------------------------------------------- #
st.markdown(_WORKSPACE_CSS, unsafe_allow_html=True)
st.markdown(_workspace_theme_css(_theme, _is_dark), unsafe_allow_html=True)

if st.session_state.last_feedback:
    st.info(st.session_state.last_feedback)
    st.session_state.last_feedback = ""

# 动态Tab：根据模式决定显示哪些Tab
_app_mode = st.session_state.get("app_mode", "beginner")
if _app_mode in ["beginner", "teaching"]:
    # 入门/教学模式：只显示对话和设置
    tab_labels = ["对话陪跑", "设置"]
    tab_chat, tab_settings = st.tabs(tab_labels)
    tab_report = None  # 不显示报告导出
else:
    # 高级模式/原v6：显示全部Tab
    tab_labels = ["对话陪跑", "报告导出", "设置"]
    tab_chat, tab_report, tab_settings = st.tabs(tab_labels)

# ----- Tab 1: chat ----- #
with tab_chat:
    # --- Helper functions (defined in tab scope for closure access) ---
    def render_qa_trace(msg, key_prefix: str) -> None:
        if not st.session_state.get("show_diagnostics", False):
            return
        trace = getattr(msg, "metadata", {}).get("qa_trace") if getattr(msg, "role", "") == "assistant" else None
        if not trace:
            return
        timings = trace.get("timings_ms", {}) or {}
        citations = trace.get("citations", []) or []
        mode = trace.get("mode_label") or "规则模式"
        fallback = "降级" if trace.get("fallback") else "正常"
        guard = trace.get("guard", {}) or {}
        guard_text = "守门通过" if guard.get("passed", True) else "守门回退"
        total_ms = timings.get("total", 0)
        st.caption(
            f"{mode} · {fallback} · {guard_text} · {total_ms} ms · "
            f"RAG {len(citations)} · 图 {trace.get('image_count', 0)}"
        )
        with st.expander("问答链路明细", expanded=False):
            st.json(trace)

    def render_user_understanding_feedback(msg, key_prefix: str) -> None:
        if not st.session_state.get("show_diagnostics", False):
            return
        meta = getattr(msg, "metadata", {}) or {}
        normalized = meta.get("normalized_query") or {}
        if not normalized:
            return
        understood = normalized.get("normalized") or getattr(msg, "content", "")
        st.caption(
            f"已理解为：{understood} · 置信度 {float(normalized.get('confidence', 0) or 0):.2f}"
        )
        with st.expander("纠正这次理解", expanded=False):
            with st.form(f"query_correction_{key_prefix}"):
                corrected = st.text_area("正确理解", value=understood, height=80)
                note = st.text_input("说明", value="")
                submitted = st.form_submit_button("提交待审核纠正", use_container_width=True)
            if submitted:
                correction = make_correction(
                    session_id=state.session_id,
                    kind="query_understanding",
                    original_query=getattr(msg, "content", ""),
                    normalized_query=understood,
                    corrected_query=corrected.strip(),
                    user_note=note.strip(),
                    checkpoint_id=normalized.get("checkpoint_id") or state.current_cp_id,
                    software=normalized.get("software") or state.software,
                    metadata={"normalized_query": normalized},
                )
                append_correction(CORRECTIONS_PATH, correction)
                st.session_state.last_feedback = "已记录理解纠正，进入知识审核队列。"
                st.rerun()

    def render_answer_feedback(msg, key_prefix: str) -> None:
        if not st.session_state.get("show_diagnostics", False):
            return
        with st.expander("纠正这条回答", expanded=False):
            with st.form(f"answer_correction_{key_prefix}"):
                kind = st.selectbox(
                    "问题类型",
                    options=["answer_wrong", "missing_step", "wrong_parameter", "wrong_image", "other"],
                    format_func=lambda x: {
                        "answer_wrong": "回答不准确",
                        "missing_step": "缺少步骤",
                        "wrong_parameter": "参数不对",
                        "wrong_image": "截图不匹配",
                        "other": "其他",
                    }.get(x, x),
                )
                note = st.text_area("请写出正确说法或补充说明", height=90)
                submitted = st.form_submit_button("提交待审核反馈", use_container_width=True)
            if submitted and note.strip():
                correction = make_correction(
                    session_id=state.session_id,
                    kind=kind,
                    answer_excerpt=getattr(msg, "content", "")[:1200],
                    user_note=note.strip(),
                    checkpoint_id=state.current_cp_id,
                    software=state.software,
                    metadata={"qa_trace": (getattr(msg, "metadata", {}) or {}).get("qa_trace", {})},
                )
                append_correction(CORRECTIONS_PATH, correction)
                st.session_state.last_feedback = "已记录回答反馈，进入知识审核队列。"
                st.rerun()

    def _render_qa_acceptance(msg, msg_idx: int, is_last: bool) -> None:
        """独立 QA 验收流程：快速反馈回答质量。"""
        if not is_last:
            return  # 只对最新回答显示验收按钮

        # 初始化验收状态
        if "qa_acceptance" not in st.session_state:
            st.session_state.qa_acceptance = {}

        acceptance_key = f"msg_{msg_idx}"
        current_status = st.session_state.qa_acceptance.get(acceptance_key, "pending")

        if current_status == "pending":
            st.divider()
            st.caption("💡 这个回答对你有帮助吗？")
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("👍 有帮助", key=f"qa_accept_{msg_idx}", use_container_width=True):
                    st.session_state.qa_acceptance[acceptance_key] = "accepted"
                    # 可选：记录到分析日志
                    st.rerun()

            with col2:
                if st.button("👎 不够好", key=f"qa_reject_{msg_idx}", use_container_width=True):
                    st.session_state.qa_acceptance[acceptance_key] = "rejected"
                    st.session_state[f"qa_feedback_open_{msg_idx}"] = True
                    st.rerun()

            with col3:
                if st.button("⏭️ 跳过", key=f"qa_skip_{msg_idx}", use_container_width=True):
                    st.session_state.qa_acceptance[acceptance_key] = "skipped"
                    st.rerun()

        elif current_status == "accepted":
            st.success("✓ 已标记为有帮助，感谢反馈！")

        elif current_status == "rejected":
            st.warning("已标记为不够好")
            # 显示反馈表单
            if st.session_state.get(f"qa_feedback_open_{msg_idx}", False):
                with st.form(f"qa_feedback_form_{msg_idx}"):
                    st.caption("请告诉我们哪里可以改进：")
                    feedback_type = st.radio(
                        "问题类型",
                        options=["不够准确", "信息不全", "难以理解", "其他"],
                        horizontal=True,
                        key=f"qa_feedback_type_{msg_idx}",
                    )
                    feedback_note = st.text_area(
                        "具体说明（可选）",
                        height=80,
                        key=f"qa_feedback_note_{msg_idx}",
                    )
                    submitted = st.form_submit_button("提交反馈", use_container_width=True)

                    if submitted:
                        # 记录反馈
                        correction = make_correction(
                            session_id=state.session_id,
                            kind="qa_rejected",
                            answer_excerpt=getattr(msg, "content", "")[:1200],
                            user_note=f"[{feedback_type}] {feedback_note.strip()}",
                            checkpoint_id=state.current_cp_id,
                            software=state.software,
                            metadata={"qa_trace": (getattr(msg, "metadata", {}) or {}).get("qa_trace", {})},
                        )
                        append_correction(CORRECTIONS_PATH, correction)
                        st.session_state[f"qa_feedback_open_{msg_idx}"] = False
                        st.session_state.last_feedback = "感谢反馈，我们会持续改进！"
                        st.rerun()


    def render_user_multimodal_evidence(msg) -> None:
        """Show the exact uploaded media and the auditable recognition summary."""
        metadata = getattr(msg, "metadata", {}) or {}
        image_refs = getattr(msg, "image_refs", []) or []
        if image_refs:
            cols = st.columns(min(len(image_refs), 3))
            for idx, ref in enumerate(image_refs[:6]):
                path = str(ref.get("image_path") or "")
                with cols[idx % len(cols)]:
                    if path and os.path.exists(path):
                        # 保留 st.image：此处需要 use_column_width=True 填充列宽，
                        # render_lazy_image 仅支持固定 width 参数，迁移会改变渲染效果。
                        st.image(path, caption=ref.get("image_name") or f"图片 {idx + 1}", use_column_width=True)
                    else:
                        st.caption(f"图片不可用：{ref.get('image_name') or idx + 1}")

        observations = metadata.get("image_observations") or []
        for obs in observations[:3]:
            accepted = obs.get("accepted_params") or {}
            params_text = "，".join(f"{k}={v}" for k, v in accepted.items()) or "未自动采纳参数"
            ocr = obs.get("ocr") or {}
            confidence_values = [
                float(item.get("confidence") or 0)
                for item in (obs.get("param_candidates") or [])
                if isinstance(item, dict)
            ]
            confidence = max(confidence_values, default=0.0)
            confidence_text = f"{confidence:.2f}" if confidence else "未提供"
            summary = (
                f"识别摘要：软件 {obs.get('software_guess', 'unknown')}，"
                f"阶段 {obs.get('stage_guess', 'unknown')}，{params_text}；"
                f"证据置信度 {confidence_text}"
            )
            st.caption(summary)
            if ocr.get("text_excerpt"):
                st.caption(f"OCR：{ocr.get('text_excerpt')[:220]}")

        if metadata.get("input_modality") == "voice":
            st.caption("语音转写结果：模型未返回词级置信度，请核对上方文字后再采用参数建议。")

    # --- 1. Step 状态行（紧凑单行） ---
    _current_cp = _get_current_checkpoint_data(app, state)
    _cp_cn = _current_cp.get("checkpoint_cn", "未知阶段")
    _phase = _current_cp.get("phase", "")
    _order = _current_cp.get("order", 0)
    _sw_label = "cryoSPARC" if state.software == "cryosparc" else "RELION"

    # 计算进度
    total_checkpoints = len(app.navigator.checkpoints)
    passed_count = sum(1 for rec in state.checkpoint_records.values() if rec.status == "passed")
    progress_text = f"{passed_count}/{total_checkpoints}"

    step_bar_html = f"""
    <div class="sp-step-bar">
        <span class="sp-step-label">步骤 {_order} · {_cp_cn}</span>
        <span class="sp-step-progress">{progress_text}</span>
        <span class="sp-step-badge sw">{_sw_label}</span>
        <span class="sp-step-badge ph">{_phase}</span>
    </div>
    """
    st.markdown(step_bar_html, unsafe_allow_html=True)

    # 读取当前回答深度，供后续对话生成使用
    from utils.ui_state_manager import get_output_mode
    _output_mode = normalize_response_profile(get_output_mode())

    # --- 2. 快速操作按钮（精简：完成 + 更多 + 回答深度） ---
    _is_first_use = (state.current_cp_id == "cp_01" and not state.messages)

    if _is_first_use:
        qa, qb, qc, qd = st.columns([1.5, 0.9, 0.9, 1.2])
    else:
        qa, qb, qc = st.columns([2.5, 1, 1.2])

    # 主操作：完成
    with qa:
        if st.button("✓ 完成", use_container_width=True, key="quick_完成",
                     help="标记当前阶段完成，进入下一阶段", type="primary"):
            run_command("完成")
            st.session_state._sp_scroll_target = "chat_bottom"
            st.rerun()

    # 首次使用时显示"开始"按钮
    if _is_first_use:
        with qb:
            if st.button("▶ 开始", use_container_width=True, key="quick_开始",
                         help="开始新的陪跑流程，进入第一阶段"):
                run_command("开始")
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()

    # 更多操作（折叠）
    with (qc if _is_first_use else qb):
        with st.popover("更多 ▾", use_container_width=True):
            if st.button("📊 进度", use_container_width=True, key="quick_进度",
                         help="查看当前流程进度和各阶段状态"):
                run_command("进度")
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()
            if st.button("⚠️ 报错", use_container_width=True, key="quick_报错",
                         help="报告当前阶段遇到的问题，获取故障诊断"):
                run_command("报错")
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()
            if st.button("⏭️ 跳过", use_container_width=True, key="quick_跳过",
                         help="跳过当前阶段，进入下一阶段"):
                run_command("跳过")
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()

    # 回答深度选择器（仅在高级模式/原v6模式下显示）
    # 入门模式和教学模式有固定呈现方式，不需要视图切换
    _app_mode = st.session_state.get("app_mode", "beginner")
    _show_view_switcher = (_app_mode not in ["beginner", "teaching"])

    if _show_view_switcher:
        with (qd if _is_first_use else qc):
            _render_output_mode_toggle(compact=True)
    elif not _is_first_use:
        # 入门/教学模式下，右侧留空或显示提示
        with qc:
            st.caption("💬 当前模式有固定呈现")

    # 智能滚动锚点：切换步骤 / 新提问后整页定位到此处
    st.markdown('<span id="sp-work-area"></span>', unsafe_allow_html=True)

    # ====================================================================
    # 三模式路由：根据 app_mode 渲染不同界面
    # ====================================================================
    _current_cp = _get_current_checkpoint_data(app, state)
    _app_mode = st.session_state.app_mode

    if _app_mode == "beginner":
        # 入门模式：单栏简化布局
        from modes import render_beginner_view
        render_beginner_view(_current_cp, state, app, run_command)

    elif _app_mode == "teaching":
        # 教学模式：单栏教学卡片+测验
        from modes import render_teaching_view
        render_teaching_view(_current_cp, state, app)

    if _app_mode == "expert":
        # 高级模式和默认：保留原有双栏布局（workspace + chat）
        # --- 4. Two-column layout: workspace + chat ---
        _ws_col, _chat_col = st.columns([0.30, 0.70], gap="small")

        # ===== Left column: Stage workspace =====
        with _ws_col:
            _current_cp = _get_current_checkpoint_data(app, state)

            # 详细工作区（Step 导航 + 内容）
            try:
                workspace_container = st.container(height=420, border=False)
            except TypeError:
                workspace_container = st.container(border=False)

            with workspace_container:
                render_stage_workspace(
                    _current_cp,
                    state.software,
                    state,
                    app,
                    on_switch=switch_checkpoint,
                    key_prefix="ws_main",
                )
                if st.session_state.get("_extracted_cards"):
                    st.divider()
                    render_suppressed_cards(key_prefix="ws_extracted")

                # P2-10: 预加载下一检查点的图片（后台线程，不阻塞 UI）
                try:
                    from utils.image_lazy import preload_next_step_images
                    _preload_cp_id = _current_cp.get("checkpoint_id", "") if isinstance(_current_cp, dict) else ""
                    if _preload_cp_id:
                        _preload_checkpoints = app.navigator.checkpoints if hasattr(app, "navigator") else []
                        _preload_guide_cards = load_guide_cards()
                        threading.Thread(
                            target=preload_next_step_images,
                            args=(_preload_cp_id, _preload_checkpoints, _preload_guide_cards),
                            daemon=True,
                        ).start()
                except Exception:
                    pass  # 预加载失败不影响主流程

        # ===== Right column: Chat history =====
        with _chat_col:
            # 准备搜索和定位所需的变量（在折叠区之前定义，供下方使用）
            _stage_opts = ["全部"] + [
                cp.get("checkpoint_id")
                for cp in sorted(app.navigator.checkpoints, key=lambda c: c.get("order", 999))
            ]
            _cp_labels = {
                cp.get("checkpoint_id"): f"{cp.get('checkpoint_id')} · {cp.get('checkpoint_cn') or cp.get('checkpoint_name', '')}"
                for cp in app.navigator.checkpoints
            }

            # --- A. 固定高度、内部可滚动的聊天容器 ---
            # height= 需要 Streamlit >= 1.38；旧版本回退到无高度容器（仍可用，只是不固定高度）
            # 初始化搜索和定位的默认值
            _chat_q = ""
            _stage_filter = "全部"
            _show_diagnostics = False

            try:
                scroll_pane = st.container(height=420, border=True)
            except TypeError:
                scroll_pane = st.container(border=True)
            with scroll_pane:
                st.markdown('<div id="chat-scroll-pane"></div>', unsafe_allow_html=True)

                # Top anchor + jump-to-latest
                st.markdown(
                    '<div id="chat-top"></div>'
                    '<a href="#chat-bottom" style="text-decoration:none;font-size:0.8rem;color:#64748b;">跳到最新</a>',
                    unsafe_allow_html=True,
                )

                # --- B./C. 搜索框与步骤定位已移到外部折叠区 ---
                # 使用 session_state 来获取搜索和过滤条件
                _chat_q = st.session_state.get("chat_search_query", "")
                _stage_filter = st.session_state.get("chat_stage_filter", "全部")
                _show_diagnostics = st.session_state.get("show_diagnostics", False)

                def _msg_stage(m):
                    """从消息 metadata 推断其所属步骤（checkpoint_id）。"""
                    md = getattr(m, "metadata", None) or {}
                    cp = md.get("checkpoint_id") or ""
                    if not cp:
                        nq = md.get("normalized_query") or {}
                        if isinstance(nq, dict):
                            cp = nq.get("checkpoint_id") or ""
                    return cp

                _q = (_chat_q or "").strip().lower()
                _filtering = bool(_q) or (_stage_filter != "全部")

                if _filtering:
                    # 在全部历史消息上做关键词 / 步骤过滤，不再走窗口折叠
                    shown = list(state.messages)
                    if _stage_filter != "全部":
                        _ctx = ""
                        _kept = []
                        for _m in shown:
                            _c = _msg_stage(_m)
                            if _c:
                                _ctx = _c
                            if _ctx == _stage_filter:
                                _kept.append(_m)
                        shown = _kept
                    if _q:
                        shown = [m for m in shown if _q in (getattr(m, "content", "") or "").lower()]
                    older_messages = []
                else:
                    history_limit = int(st.session_state.selected_history_limit)
                    shown, older_messages = get_chat_display_window(state.messages, history_limit)
                    if len(state.messages) > history_limit:
                        st.caption(f"显示最近 {history_limit} 条（共 {len(state.messages)} 条）。可在「设置」中调整条数。")

    
                # Folded older messages
                if older_messages:
                    older_summary = get_older_summary(older_messages)
                    with st.expander(older_summary, expanded=False):
                        for oi, omsg in enumerate(older_messages):
                            with st.chat_message(omsg.role):
                                content = getattr(omsg, "content", "")
                                if len(content) > 200:
                                    first_line = content.lstrip("#").strip().splitlines()[0][:60] if content.strip() else ""
                                    st.caption(f"{first_line}…" if first_line else "(空消息)")
                                else:
                                    st.markdown(content)
    
                if not shown:
                    if _filtering:
                        st.warning("未找到匹配的对话记录，试着换关键词或切换步骤。")
                    else:
                        st.info("还没有对话。点上方「开始」或在下方输入框开始陪跑。")

                st.session_state._extracted_cards = []
                st.session_state._workspace_guide_cards = []
    
                for i, msg in enumerate(shown):
                    is_last = i == len(shown) - 1
                    if is_last:
                        st.markdown(
                            '<div id="latest-message" style="scroll-margin-top: 1rem;"></div>',
                            unsafe_allow_html=True,
                        )
                    with st.chat_message(msg.role):
                        action_tag = getattr(msg, "action_tag", "") or ""
                        is_sop = "sop" in action_tag or "stage_guide" in action_tag
                        guide_card = getattr(msg, "metadata", {}).get("guide_card") if msg.role == "assistant" else None
                        _content_len = len(getattr(msg, "content", "") or "")
                        _meta_keys = list((getattr(msg, "metadata", {}) or {}).keys())
                        if st.session_state.get("show_diagnostics", False):
                            st.caption(f"🐛 DEBUG [{i}] role={msg.role}, tag={action_tag}, content_len={_content_len}, meta_keys={_meta_keys}, is_sop={is_sop}, has_guide_card={bool(guide_card)}")

                        # --- B域优化：guide_card 存入 session_state 供工作区消费，不在聊天区内嵌截图 ---
                        if guide_card and msg.role == "assistant":
                            _gc_list = st.session_state.get("_workspace_guide_cards", [])
                            _gc_list.append({"card": guide_card, "action_tag": action_tag, "msg_idx": i})
                            st.session_state._workspace_guide_cards = _gc_list

                        # --- B域优化 v2：SOP 长文本迁移至工作区，聊天区仅显示摘要 ---
                        if msg.role == "assistant" and guide_card and is_sop:
                            # 提取 SOP 全文供工作区 📋 SOP tab 消费
                            _sop_full = msg.content or ""
                            if _sop_full:
                                st.session_state["_workspace_sop_full"] = _sop_full
                                st.session_state["_workspace_sop_cp_id"] = checkpoint_id_from_metadata(msg)

                            # 聊天区仅显示精简摘要（2-3行）
                            _nav_line = ""
                            if "\n---" in _sop_full:
                                _nav_line = _sop_full.split("\n---")[0].strip()
                            elif "\n" in _sop_full:
                                _nav_line = _sop_full.split("\n")[0].strip()
                            else:
                                _nav_line = _sop_full[:120]

                            st.markdown(f"📋 **{(_nav_line or '已切换步骤')}**")
                            st.caption("👈 完整 SOP 流程、参数说明和截图请查看左侧「📋 SOP」面板")
                            render_qa_trace(msg, f"trace_{i}_guide")
                            render_answer_feedback(msg, f"{i}_guide")
                            continue

                        if msg.role == "assistant":
                            # 助手回答：文本卡（judgment/explanation/steps/decision/qc/log）保留在聊天；
                            # screenshot + params 卡被抑制，数据累积到 st.session_state._extracted_cards
                            # 供工作区「💡 课题组经验」区展示。
                            render_answer_cards(
                                msg.content,
                                getattr(msg, "metadata", None),
                                normalize_response_profile(
                                    (getattr(msg, "metadata", None) or {}).get("response_profile", "teaching")
                                ),
                                is_last,
                                f"card_{i}",
                                suppress_types=["screenshot", "params"],
                            )
                            # 注意：guide_card 不再在聊天中回退渲染（已存入 _workspace_guide_cards）
                            # 注意：image_refs 不再在聊天内联渲染（图片应在工作区查看）
                        else:
                            # 用户消息：纯文本
                            st.markdown(msg.content)
                            render_user_multimodal_evidence(msg)

                        render_qa_trace(msg, f"trace_{i}")
                        if msg.role == "user":
                            render_user_understanding_feedback(msg, f"{i}")
                        elif msg.role == "assistant":
                            # v6.0 增强：独立 QA 验收流程（在诊断工具外也可见）
                            _render_qa_acceptance(msg, i, is_last)
                            render_answer_feedback(msg, f"{i}")

                # Bottom anchor + back-to-top
                st.markdown(
                    '<div id="chat-bottom"></div>'
                    '<a href="#chat-top" style="text-decoration:none;font-size:0.8rem;color:#64748b;">回到顶部</a>',
                    unsafe_allow_html=True,
                )


            # --- 紧凑工具栏（搜索/定位/诊断/沉淀 收入 popover，不占垂直空间） ---
            _tc1, _tc2, _tc3, _tc4 = st.columns([1, 1, 1, 1])
            with _tc1:
                with st.popover("🔍 搜索", use_container_width=True):
                    st.text_input("搜索历史对话", key="chat_search_query")
            with _tc2:
                with st.popover("📍 定位", use_container_width=True):
                    st.selectbox(
                        "定位到步骤",
                        options=_stage_opts,
                        index=0,
                        format_func=lambda cid: _cp_labels.get(cid, cid),
                        key="chat_stage_filter",
                    )
            with _tc3:
                with st.popover("🔧 诊断", use_container_width=True):
                    st.toggle(
                        "显示诊断信息与审核工具",
                        value=False,
                        key="show_diagnostics",
                        help="显示运行引擎、耗时、RAG 命中、理解纠正和回答审核入口。",
                    )
            with _tc4:
                with st.popover("💾 沉淀", use_container_width=True):
                    if state.messages:
                        _last_assistant_msg = next(
                            (m for m in reversed(state.messages) if m.role == "assistant"), None
                        )
                        if _last_assistant_msg:
                            if st.button("沉淀经验", key="distill_btn", use_container_width=True,
                                         help="把最新一条 AI 回答抽取成知识条目，存入知识库供后续检索"):
                                _msgs = state.messages
                                _last_idx = next(
                                    (i for i, m in reversed(list(enumerate(_msgs))) if m.role == "assistant"), -1
                                )
                                if _last_idx > 0 and _msgs[_last_idx - 1].role == "user":
                                    _pair = _msgs[_last_idx - 1: _last_idx + 1]
                                else:
                                    _user_idx = next(
                                        (i for i in range(_last_idx - 1, max(0, _last_idx - 5), -1)
                                         if _msgs[i].role == "user"), -1
                                    )
                                    if _user_idx >= 0:
                                        _pair = [_msgs[_user_idx], _msgs[_last_idx]]
                                    else:
                                        _pair = [_msgs[_last_idx]]

                                snippet = "\n\n".join(f"{m.role}: {m.content}" for m in _pair)

                                context_info = []
                                if state.current_cp_id:
                                    context_info.append(f"checkpoint: {state.current_cp_id}")
                                if state.software:
                                    context_info.append(f"software: {state.software}")
                                if state.params:
                                    key_params = list(state.params.items())[:5]
                                    context_info.append(f"params: {dict(key_params)}")

                                if context_info:
                                    snippet = f"[Context: {'; '.join(context_info)}]\n\n{snippet}"

                                draft = app.llm.extract_knowledge_doc(snippet)
                                draft.setdefault("doc_id", f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                                draft.setdefault("checkpoint_id", state.current_cp_id or "")
                                draft.setdefault("software", state.software or "")
                                st.session_state.distill_draft = draft
                                st.rerun()
                    else:
                        st.caption("暂无对话可沉淀")

            if st.session_state.get("chat_stage_filter") != "全部":
                st.session_state._sp_scroll_target = "chat_bottom"

            if st.session_state.get("distill_draft"):
                draft = st.session_state.distill_draft
                with st.form("distill_form"):
                    st.markdown("**沉淀这条经验到知识库**")
                    d_title = st.text_input("标题（原话）", value=draft.get("title_cn", ""),
                                            placeholder="用自己的话描述这条经验")
                    d_polish = st.toggle("✨ AI润色内容", value=True,
                                         help="开启后 AI 会自动整理摘要、步骤等字段；关闭则直接保存原始提取内容")
                    fc1, fc2 = st.columns(2)
                    submitted = fc1.form_submit_button("💾 写入知识库", use_container_width=True)
                    cancelled = fc2.form_submit_button("取消", use_container_width=True)
                if submitted:
                    _title = d_title.strip() or draft.get("title_cn", "")
                    if d_polish:
                        # AI润色：用 LLM 重新提取，覆盖草稿内容
                        try:
                            polished = app.llm.extract_knowledge_doc(
                                draft.get("_raw_snippet", _title)
                            )
                            draft.update({k: v for k, v in polished.items() if k != "doc_id"})
                        except Exception:
                            pass  # 润色失败时静默降级，使用原始草稿
                    doc = KnowledgeDoc(
                        doc_id=draft.get("doc_id") or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        software=draft.get("software", ""),
                        checkpoint_id=draft.get("checkpoint_id", ""),
                        title_cn=_title,
                        summary=draft.get("summary", ""),
                        action_steps=draft.get("action_steps", []),
                        qc_checks=draft.get("qc_checks", []),
                        common_errors=draft.get("common_errors", []),
                        tags=draft.get("tags", []),
                        tier=draft.get("tier", "note"),
                        status=draft.get("status", "draft"),
                        source="distill",
                        imported_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    add_doc_to_sharded_index(str(BASE_DIR / "knowledge_base"), doc.to_dict())
                    app.retriever.invalidate_corpus_cache()
                    st.session_state.distill_draft = None
                    st.session_state.last_feedback = (
                        f"✅ 已沉淀经验：{doc.doc_id}"
                        f" — 可在左侧「⚙️ 设置」→「已导入知识管理」中查看"
                    )
                    st.rerun()
                if cancelled:
                    st.session_state.distill_draft = None
                    st.rerun()


        st.session_state.setdefault("pending_pasted", [])
        st.session_state.setdefault("last_pasted_sig", "")
        st.session_state.setdefault("voice_transcript", "")
        st.session_state.setdefault("_temp_voice_transcript", None)

        if st.session_state.get("_temp_voice_transcript") is not None:
            st.session_state.voice_transcript = st.session_state._temp_voice_transcript
            st.session_state._temp_voice_transcript = None

        # ---- 语音输入（折叠面板，默认收起） ----
        with st.expander("🎤 语音输入", expanded=bool(st.session_state.get("voice_transcript", ""))):
            st.caption(app.llm.audio_status_text())
            recorded_voice = None
            if hasattr(st, "audio_input"):
                use_mic = st.checkbox("启用麦克风录音（需浏览器授权）", key="enable_mic_recording", value=False)
                if use_mic:
                    st.caption("💡 录音结束后自动转写；如提示错误请授权麦克风，或使用下方文件上传")
                    st.info(
                        "🔊 **麦克风权限授权指引**：\n"
                        "- Chrome/Edge：点击浏览器地址栏左侧的「🔒」图标，在「权限」中允许麦克风\n"
                        "- Firefox：点击地址栏左侧的「🔒」图标 → 「麦克风」→ 选择「允许」\n"
                        "- 如果提示已拒绝，请在浏览器设置中搜索「麦克风」并允许此网站访问\n"
                        "- 授权后刷新页面，录音按钮会显示为蓝色可点击状态"
                    )
                    try:
                        recorded_voice = st.audio_input("点击开始录音")
                    except Exception as exc:
                        recorded_voice = None
                        st.error(f"麦克风录音初始化失败：{exc}\n\n请检查：\n1. 浏览器是否已授权麦克风权限\n2. 是否有其他程序占用了麦克风\n3. 或使用下方「上传语音文件」功能")
            uploaded_voice = st.file_uploader(
                "上传语音文件（上传后自动转写）",
                type=["mp3", "wav", "m4a", "mp4", "mpeg", "mpga", "webm", "ogg"],
                key="voice_input_uploader",
            )
            voice_file = recorded_voice or uploaded_voice

            def _stable_sig(f):
                if f is None:
                    return ""
                try:
                    sz = getattr(f, "size", 0) or 0
                    nm = getattr(f, "name", "") or ""
                    return f"{nm}:{sz}"
                except Exception:
                    return ""

            def _is_valid_audio(f):
                if f is None:
                    return False
                try:
                    sz = getattr(f, "size", 0) or 0
                    return sz > 500
                except Exception:
                    return False

            valid_voice = voice_file if _is_valid_audio(voice_file) else None
            if valid_voice is not None and app.llm.audio_enabled:
                cur_sig = _stable_sig(valid_voice)
                if cur_sig and st.session_state.get("_last_voice_sig") != cur_sig:
                    st.session_state._last_voice_sig = cur_sig
                    try:
                        with st.status("正在读取并转写语音…", expanded=True) as voice_status:
                            voice_status.write("正在保存音频...")
                            audio_path = save_uploaded_audio(valid_voice)
                            voice_status.write("语音上传完成，正在检查识别缓存…")
                            audio_digest = file_sha256(audio_path)
                            audio_cache_key = hashlib.sha256(
                                f"{audio_digest}:{app.llm.audio_model}:zh".encode("utf-8")
                            ).hexdigest()
                            audio_cache_path = AUDIO_CACHE_DIR / f"{audio_cache_key}.json"
                            cached_audio = _read_json_cache(audio_cache_path)
                            if cached_audio and cached_audio.get("text"):
                                transcript = str(cached_audio.get("text", ""))
                                voice_status.write("已命中相同音频的转写缓存。")
                            else:
                                voice_status.write("正在调用语音识别模型…")
                                transcript = app.llm.transcribe_audio(audio_path, language="zh")
                                _write_json_cache(
                                    audio_cache_path,
                                    {
                                        "text": transcript,
                                        "audio_sha256": audio_digest,
                                        "model": app.llm.audio_model,
                                        "language": "zh",
                                        "created_at": datetime.now().isoformat(),
                                    },
                                )
                            voice_status.update(label="语音转写完成，请核对文本", state="complete", expanded=False)
                        st.session_state._temp_voice_transcript = transcript
                        st.session_state.last_feedback = "✅ 语音已自动转写，可编辑后发送或追加到输入框。"
                        st.rerun()
                    except Exception as exc:
                        st.session_state.last_feedback = f"语音转写失败：{exc}"
                        st.session_state._last_voice_sig = f"failed:{cur_sig}"

            vc1, vc3 = st.columns([1, 1])
            with vc1:
                if st.button("🔄 重新转写", use_container_width=True, disabled=voice_file is None or not app.llm.audio_enabled):
                    st.session_state._last_voice_sig = None
                    st.rerun()
            with vc3:
                if st.button("🗑️ 清空", use_container_width=True):
                    st.session_state._temp_voice_transcript = None
                    st.session_state._last_voice_sig = None
                    st.rerun()

            if not app.llm.audio_enabled:
                st.warning("请先在「设置」里配置语音转写模型和 API Key。")

            # 调试信息（开发模式可见）
            if st.session_state.get("show_diagnostics", False):
                transcript_val = st.session_state.get("voice_transcript", "")
                st.caption(f"DEBUG: voice_transcript = '{transcript_val}' (len={len(transcript_val)})")

            voice_text = st.text_area(
                "转写文本（可编辑后发送或填入输入框）",
                height=70,
                key="voice_transcript",
                placeholder="转写结果会出现在这里；可以直接编辑修正术语，然后发送或追加到输入框与手打文字合并。",
            )

            # 提示用户按钮状态
            if not voice_text.strip():
                st.caption("⚠️ 转写文本为空，「填入输入框」和「直接发送」按钮不可用。请先上传语音文件并等待转写完成。")
            if voice_text.strip():
                if st.button("✅ 直接发送（含已粘贴的截图）", use_container_width=True, type="primary"):
                    image_refs = []
                    for img in st.session_state.pending_pasted:
                        image_refs.append(save_pasted_image(img))
                    st.session_state.pending_pasted = []
                    st.session_state.last_pasted_sig = ""
                    st.session_state._temp_voice_transcript = None
                    st.session_state._last_voice_sig = None
                    run_command(
                        voice_text.strip(),
                        image_refs,
                        input_metadata={"input_modality": "voice", "transcript_reviewed": True},
                        response_profile=_output_mode,
                    )
                    st.session_state._sp_scroll_target = "chat_bottom"
                    st.rerun()
                st.caption("💡 或点「📝 填入输入框」把文字追加到底部输入框，继续手打补充、附加文件后一起发送")

        # ---- JS：将转写文本注入到主 chat_input（必须在 expander 外部，确保始终执行） ----
        if st.session_state.get("_inject_voice_text"):
            inject_text = st.session_state._inject_voice_text
            st.session_state._inject_voice_text = ""
            escaped = json.dumps(inject_text, ensure_ascii=False)
            js_code = f"""
            (function() {{
                var attempts = 0;
                var maxAttempts = 40;
                var injectedText = {escaped};
                function tryInject() {{
                    attempts++;
                    var chatArea = document.querySelector('[data-testid="stChatInputTextArea"]');
                    if (!chatArea) {{
                        if (attempts < maxAttempts) setTimeout(tryInject, 200);
                        return;
                    }}
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    var currentVal = chatArea.value || '';
                    var newVal = currentVal ? (currentVal + (currentVal.endsWith(' ') ? '' : ' ') + injectedText) : injectedText;
                    nativeSetter.call(chatArea, newVal);
                    chatArea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    chatArea.focus();
                    chatArea.setSelectionRange(newVal.length, newVal.length);
                }}
                setTimeout(tryInject, 300);
            }})();
            """
            js_b64 = base64.b64encode(js_code.encode('utf-8')).decode('ascii')
            st.markdown(
                f'<img src="data:," style="display:none!important;width:0!important;height:0!important;" onerror="eval(atob(\'{js_b64}\'))">',
                unsafe_allow_html=True,
            )

        # ---- 截图粘贴（紧凑单行） ----
        paste_col1, paste_col2 = st.columns([1, 8])
        with paste_col1:
            paste_result = paste_image_button(label="📋 粘贴", key="chat_paste_btn", errors="ignore")
        with paste_col2:
            if not st.session_state.pending_pasted:
                st.caption("Ctrl+V 粘贴截图，或下方输入框拖拽文件")
        if paste_result is not None and paste_result.image_data is not None:
            sig = hashlib.sha256(paste_result.image_data.tobytes()).hexdigest()
            if sig != st.session_state.last_pasted_sig:
                st.session_state.last_pasted_sig = sig
                st.session_state.pending_pasted.append(paste_result.image_data)
                st.rerun()

        if st.session_state.pending_pasted:
            _pc = st.columns(min(len(st.session_state.pending_pasted) + 1, 5))
            for i, img in enumerate(st.session_state.pending_pasted):
                _pc[i % len(_pc)].image(img, width=80)
            with _pc[-1]:
                if st.button("🗑️ 清空截图", key="clear_pasted", use_container_width=True):
                    st.session_state.pending_pasted = []
                    st.rerun()

        chat_value = st.chat_input("输入：开始 / 完成 / 报错 / box size 怎么设…", accept_file="multiple")
        if chat_value:
            text = (chat_value.text or "").strip()
            files = chat_value.files or []
            with st.spinner("正在保存图片..."):
                image_refs = save_uploaded_images(files)
            for img in st.session_state.pending_pasted:
                image_refs.append(save_pasted_image(img))
            st.session_state.pending_pasted = []
            st.session_state.last_pasted_sig = ""
            send_text = text or ("[图片消息]" if image_refs else "")
            if send_text:
                run_command(
                    send_text,
                    image_refs,
                    input_metadata={"input_modality": "image" if image_refs else "text"},
                    response_profile=_output_mode,
                )
                st.session_state._sp_scroll_target = "chat_bottom"
                st.rerun()

        # 智能整页滚动：根据本次 rerun 的触发源定位到最佳位置
        inject_smart_scroll()

# ----- Tab 2: report (仅高级模式) ----- #
if tab_report is not None:
    with tab_report:
        st.markdown("### 流程报告")
        st.markdown(app.navigator.generate_report(state))
        st.divider()
        report_text = build_session_report(state, cp_total)
        col_md, col_wf = st.columns(2)
        with col_md:
            st.download_button(
                "📄 导出实验记录报告（.md）",
                data=report_text,
                file_name=f"StructPilot_Experiment_Record_{state.session_id}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_wf:
            # ✨ 导出 CryoSPARC Workflow JSON（仅 cryosparc 用户可见）
            if state.software.lower() in ("cryosparc", "cryosparc4", "cs"):
                from utils.cryosparc_workflow import generate_cryosparc_workflow
                import json

                workflow = st.session_state.get("recommended_workflow", {})
                params = {
                    "pixel_size": getattr(state, "pixel_size", None),
                    "voltage": getattr(state, "voltage", None),
                    "Cs": getattr(state, "Cs", None),
                    "total_dose": getattr(state, "total_dose", None),
                    "particle_diameter": getattr(state, "particle_diameter", None),
                    "bfactor": getattr(state, "bfactor", None),
                    "box_size": getattr(state, "box_size", None),
                }
                wf_json = generate_cryosparc_workflow(workflow, params,
                                                      workflow_name=f"StructPilot_{state.session_id[:8]}",
                                                      software=state.software)
                if wf_json:
                    st.download_button(
                        "📦 导出 CryoSPARC Workflow",
                        data=json.dumps(wf_json, ensure_ascii=False, indent=2),
                        file_name=f"StructPilot_Workflow_{state.session_id[:8]}.json",
                        mime="application/json",
                        use_container_width=True,
                        help="下载后可在 CryoSPARC GUI → Workflows → Import Workflow 导入，一键创建所有 Job 并连线",
                    )
                else:
                    st.caption("（当前软件不支持）")
            else:
                st.caption("（CryoSPARC 专属功能）")

        if st.button("💾 保存当前会话", use_container_width=True):
            capture_state_safely(state)
            st.session_state.last_feedback = "当前会话已保存到本地 SQLite。"
            st.rerun()

# ----- Tab 3: settings ----- #
with tab_settings:
    # 入门/教学模式：只显示简化的界面设置和数据清除
    if _app_mode in ["beginner", "teaching"]:
        st.markdown("### 🎨 界面设置")

        st_theme_simple = st.selectbox(
            "主题风格",
            options=list(THEMES.keys()),
            index=list(THEMES.keys()).index(st.session_state.get("ui_theme", "静谧蓝"))
                  if st.session_state.get("ui_theme", "静谧蓝") in THEMES else 0,
            key="ui_theme_simple",
            help="切换主题会实时生效"
        )

        col_pet1, col_pet2 = st.columns(2)
        with col_pet1:
            st_pet_simple = st.toggle(
                "桌宠陪伴（右下角小动物）",
                value=st.session_state.get("pet_enabled", True),
                key="pet_enabled_simple",
                help="在右下角显示一只可爱的科研伙伴"
            )

        with col_pet2:
            if st_pet_simple:
                pet_type_options = {
                    "penguin": "🐧 冷冻企鹅",
                    "cat": "🐱 科研小猫",
                    "dog": "🐶 实验小狗",
                }
                current_pet = st.session_state.get("pet_type", "penguin")
                sel_pet_simple = st.selectbox(
                    "桌宠类型",
                    options=list(pet_type_options.keys()),
                    format_func=lambda x: pet_type_options[x],
                    index=list(pet_type_options.keys()).index(current_pet) if current_pet in pet_type_options else 0,
                    key="pet_type_simple",
                )
            else:
                sel_pet_simple = st.session_state.get("pet_type", "penguin")

        if st.button("保存界面设置", use_container_width=True, type="primary"):
            st.session_state.ui_theme = st_theme_simple
            st.session_state.pet_enabled = st_pet_simple
            st.session_state.pet_type = sel_pet_simple
            save_ui_settings(
                ui_theme=st_theme_simple,
                pet_enabled=st_pet_simple,
                pet_type=sel_pet_simple,
            )
            st.success("✅ 界面设置已保存")
            st.rerun()

        st.divider()
        st.markdown("### 🔄 数据管理")

        if st.button("清除会话数据（重置问卷）", use_container_width=True):
            # 清除问卷完成标记，让用户重新回答问卷
            st.session_state.onboarding_completed = False
            st.session_state.user_profile = {}
            st.session_state.recommended_workflow = {}
            st.session_state.onboarding_step = 1
            st.success("✅ 会话数据已清除，刷新页面重新开始")

        st.caption("💡 点击上方按钮后刷新页面，即可重新填写需求问卷")

        st.divider()
        st.markdown("### ⚙️ 需要更多高级功能？")
        st.info(
            "LLM 配置、知识库管理等功能在「**高级模式**」中提供。\n\n"
            "点击左侧边栏的「选择模式」切换到「高级模式」查看完整功能。"
        )

    # 高级模式：显示完整设置（LLM、向量检索、知识库等）
    else:
        st.markdown("### LLM 设置")
        cfg = app.llm.load_config()
        provider_options = {
            "不启用": {"provider": "none", "model": "", "base_url": ""},
            "OpenAI": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
            "DeepSeek": {"provider": "openai_compatible", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
            "OpenRouter": {"provider": "openai_compatible", "model": "openai/gpt-4o-mini", "base_url": "https://openrouter.ai/api/v1"},
            "Ollama 本地模型": {"provider": "openai_compatible", "model": "llama3.1", "base_url": "http://localhost:11434/v1"},
            "自定义 OpenAI-compatible API": {"provider": "openai_compatible", "model": cfg.get("model", app.llm.model), "base_url": cfg.get("base_url", app.llm.base_url)},
            "Anthropic / Claude（需兼容代理）": {"provider": "anthropic", "model": "claude-3-5-sonnet-latest", "base_url": "https://api.anthropic.com/v1"},
            "Google Gemini（原生）": {"provider": "gemini", "model": "gemini-1.5-pro", "base_url": "https://generativelanguage.googleapis.com/v1beta"},
        }
        provider_options_list = list(provider_options.keys())
        current_provider = cfg.get("provider", app.llm.provider)
        current_base_url = (cfg.get("base_url") or app.llm.base_url or "").lower()
        default_index = 0
        if current_provider and current_provider != "none":
            for idx, (name, opts) in enumerate(provider_options.items()):
                if opts.get("provider") == current_provider:
                    opt_base = (opts.get("base_url") or "").lower()
                    if current_provider == "openai_compatible":
                        if opt_base and current_base_url and opt_base == current_base_url:
                            default_index = idx
                            break
                        if name == "自定义 OpenAI-compatible API":
                            default_index = idx
                    else:
                        default_index = idx
                        break
        service_name = st.selectbox("服务商", options=provider_options_list, index=default_index)
        preset = provider_options[service_name]
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            llm_model = st.text_input("Model", value=preset.get("model") or cfg.get("model", app.llm.model or ""))
            llm_timeout = st.number_input("Timeout 秒", min_value=5, max_value=180, value=int(cfg.get("timeout", app.llm.timeout or 30)), step=5)
        with fcol2:
            llm_base_url = st.text_input("Base URL", value=preset.get("base_url") or cfg.get("base_url", app.llm.base_url or ""))
            llm_api_key = st.text_input("API Key", value=cfg.get("api_key", app.llm.api_key or ""), type="password")
        if service_name == "OpenAI":
            llm_provider = "openai_compatible"
        else:
            llm_provider = preset["provider"]
        lc1, lc2 = st.columns(2)
        with lc1:
            if st.button("保存 LLM 配置", use_container_width=True):
                app.llm.save_config(provider=llm_provider, api_key=llm_api_key, model=llm_model, base_url=llm_base_url, timeout=float(llm_timeout))
                # Performance: clear cached app/LLM so next rerun picks up new config
                clear_app_cache()
                set_llm_mode(detect_llm_mode(bool(app.llm.enabled)))
                st.success("LLM 配置已保存")
                st.rerun()
        with lc2:
            if st.button("测试 LLM 连接", use_container_width=True):
                app.llm.save_config(provider=llm_provider, api_key=llm_api_key, model=llm_model, base_url=llm_base_url, timeout=float(llm_timeout))
                result = explain_connection_result(app.llm.test_connection(), "LLM", llm_base_url)
                if "成功" in result or "ok" in result.lower():
                    st.success(result)
                else:
                    st.error(result)
    
        st.divider()
        st.markdown("### 向量检索（RAG embedding）")
        st.caption("配置后，对话会按你的问题检索相关站点/经验要点喂给模型。留空则关闭检索，对话照常运行。")
        emb_cfg = app.llm.load_config()
        ec1, ec2 = st.columns(2)
        with ec1:
            emb_model = st.text_input("Embedding Model", value=emb_cfg.get("embedding_model", ""),
                                      placeholder="如 BAAI/bge-m3")
            emb_base_url = st.text_input("Embedding Base URL", value=emb_cfg.get("embedding_base_url", ""),
                                         placeholder="留空复用主 LLM Base URL")
        with ec2:
            emb_api_key = st.text_input("Embedding API Key", value=emb_cfg.get("embedding_api_key", ""),
                                        type="password", placeholder="留空复用主 LLM API Key")
            emb_status = "已启用" if app.llm.embedding_enabled else "未启用"
            st.text_input("Embedding 状态", value=emb_status, disabled=True)
        eb1, eb2 = st.columns(2)
        with eb1:
            if st.button("保存 Embedding 配置", use_container_width=True):
                app.llm.save_embedding_config(embedding_model=emb_model, embedding_base_url=emb_base_url,
                                              embedding_api_key=emb_api_key)
                # Performance: clear RAG cache so new embeddings take effect
                clear_app_cache()
                st.success("Embedding 配置已保存")
                st.rerun()
        with eb2:
            if st.button("测试 Embedding 连接", use_container_width=True):
                app.llm.save_embedding_config(embedding_model=emb_model, embedding_base_url=emb_base_url,
                                              embedding_api_key=emb_api_key)
                app.llm.reload()
                if not emb_model.strip():
                    result = "向量检索未启用：请先填写 Embedding 模型。"
                    st.error(result)
                else:
                    result = explain_connection_result(app.llm.test_embedding_connection(), "向量检索", emb_base_url or llm_base_url)
                    if "成功" in result:
                        st.success(result)
                    else:
                        st.error(result)
        if st.button("重建检索缓存", use_container_width=True,
                     help="清空 embeddings_cache.json 和语料缓存，下次检索时重新计算所有向量。"):
            app.retriever.clear_cache()
            app.retriever.invalidate_corpus_cache()
            st.success("检索缓存已清空，将在下次提问时重建")
        if st.button("预热 SOP / 图文指导 / RAG", use_container_width=True,
                     help="提前加载阶段 SOP、guide 截图和检索语料，减少第一次点击后的等待。"):
            with st.spinner("正在预热本地缓存..."):
                warm = prewarm_runtime_caches()
            if warm.get("errors"):
                st.warning(
                    "预热完成，但有部分警告："
                    f"图文指导卡片 {warm.get('guide_cards', 0)} 条，"
                    f"指导图片 {warm.get('guide_images', 0)} 张，"
                    f"SOP 卡片 {warm.get('sop_cards', 0)} 条，"
                    f"知识库文档 {warm.get('rag_docs', 0)} 条，"
                    f"errors={'; '.join(warm.get('errors', []))}"
                )
            else:
                st.success(
                    f"预热完成：图文指导卡片 {warm.get('guide_cards', 0)} 条，"
                    f"指导图片 {warm.get('guide_images', 0)} 张，"
                    f"SOP 卡片 {warm.get('sop_cards', 0)} 条，"
                    f"知识库文档 {warm.get('rag_docs', 0)} 条，"
                    f"本次预热检索命中 {warm.get('rag_hits', 0)} 条。"
                )
    
        st.divider()
        st.markdown("### 语音转写")
        st.caption("配置后，可在对话页把录音或音频文件转成可编辑文本，再确认发送。")
        audio_cfg = app.llm.load_config()
        audio_model_value = app.llm.normalize_audio_model(audio_cfg.get("audio_model") or app.llm.audio_model or "")
        ac1, ac2 = st.columns(2)
        with ac1:
            audio_model = st.text_input(
                "Audio Model",
                value=audio_model_value,
                placeholder="如 FunAudioLLM/SenseVoiceSmall",
                help="硅基流动 /audio/transcriptions 接口模型：FunAudioLLM/SenseVoiceSmall。若少写最后一个 l，保存时会自动纠正。",
            )
            audio_base_url = st.text_input(
                "Audio Base URL",
                value=audio_cfg.get("audio_base_url", ""),
                placeholder="留空复用主 LLM Base URL",
            )
        with ac2:
            audio_api_key = st.text_input(
                "Audio API Key",
                value=audio_cfg.get("audio_api_key", ""),
                type="password",
                placeholder="留空复用主 LLM API Key",
            )
            st.text_input("语音状态", value=app.llm.audio_status_text(), disabled=True)
        ab1, ab2 = st.columns(2)
        with ab1:
            if st.button("保存语音转写配置", use_container_width=True):
                normalized_audio_model = app.llm.normalize_audio_model(audio_model)
                app.llm.save_audio_config(
                    audio_model=normalized_audio_model,
                    audio_base_url=audio_base_url,
                    audio_api_key=audio_api_key,
                )
                if normalized_audio_model != audio_model.strip():
                    st.success(f"语音转写配置已保存，模型名已自动纠正为：{normalized_audio_model}")
                else:
                    st.success("语音转写配置已保存")
        with ab2:
            if st.button("测试语音连接", use_container_width=True):
                normalized_audio_model = app.llm.normalize_audio_model(audio_model) or app.llm.audio_model
                app.llm.save_audio_config(
                    audio_model=normalized_audio_model,
                    audio_base_url=audio_base_url,
                    audio_api_key=audio_api_key,
                )
                app.llm.reload()
                if not normalized_audio_model.strip():
                    result = "语音转写未启用：请先填写 Audio Model。"
                    st.error(result)
                else:
                    result = explain_connection_result(app.llm.test_audio_connection(), "语音转写", audio_base_url or llm_base_url)
                    if "成功" in result:
                        st.success(result)
                    else:
                        st.error(result)
    
        st.divider()
        st.markdown("### 界面设置")
        st_theme = st.selectbox("主题风格", options=list(THEMES.keys()), key="ui_theme",
                               help="切换主题会实时生效，保存后会写入配置文件")
        st_hist = st.slider("对话显示条数", min_value=3, max_value=50, value=int(st.session_state.selected_history_limit), step=1)
        st_pet = st.toggle("桌宠陪伴（右下角小动物）", key="pet_enabled",
                           help="在右下角显示一只可爱的科研伙伴，摸头、摸身体、拽尾巴有不同反应，还可以拖动哦～")
        _pet_options = {"cat": "科研小猫", "penguin": "冷冻企鹅", "dog": "实验小狗", "rabbit": "实验兔兔", "robot": "AI助手"}
        # 确保 session_state 中的 pet_type 合法（防止旧配置或异常值导致空白选项）
        if st.session_state.get("pet_type", "penguin") not in _pet_options:
            st.session_state.pet_type = "penguin"
        st_pet_type = st.selectbox("选择伙伴", options=list(_pet_options.keys()),
                                    format_func=lambda x: _pet_options.get(x, x),
                                    key="pet_type",
                                    disabled=not st.session_state.get("pet_enabled", True),
                                    help="冷冻企鹅最配冷冻电镜哦！")
        _pet_size_options = {"48": "小号 (48px)", "64": "中号 (64px)", "80": "大号 (80px)"}
        _cur_pet_size = str(st.session_state.get("pet_size", 64))
        if _cur_pet_size not in _pet_size_options:
            _cur_pet_size = "64"
        st.selectbox("伙伴尺寸", options=list(_pet_size_options.keys()),
                     format_func=lambda x: _pet_size_options.get(x, x),
                     key="pet_size",
                     disabled=not bool(st.session_state.get("pet_enabled", True)),
                     help="也可以右键伙伴在菜单中快速调整大小")
        if st.session_state.get("pet_enabled", True):
            st.caption("+ 右键伙伴可打开设置菜单 · 三连击打开快捷问题面板～")
    
        st.markdown("**背景图**")
        bg_file = st.file_uploader("上传背景图（PNG/JPG）", type=["png", "jpg", "jpeg"], key="bg_image_uploader")
        if bg_file is not None:
            # Validate background image
            file_size = len(bg_file.getbuffer())
            if file_size > MAX_FILE_SIZE:
                st.error(f"背景图超过最大限制 {MAX_FILE_SIZE // (1024*1024)}MB")
            else:
                file_ext = Path(bg_file.name).suffix.lower()
                if file_ext not in {".png", ".jpg", ".jpeg"}:
                    st.error("背景图仅支持 PNG/JPG 格式")
                else:
                    with st.spinner("正在处理背景图..."):
                        bg_dir = BASE_DIR / "assets"
                        bg_dir.mkdir(parents=True, exist_ok=True)
                        # Use secure filename
                        safe_name = f"background_{hashlib.sha256(bg_file.name.encode()).hexdigest()[:8]}{file_ext}"
                        bg_out = bg_dir / safe_name
                        bg_out.write_bytes(bg_file.getbuffer())
                        st.session_state.bg_image = str(bg_out)
                        st.caption(f"已上传：{bg_out.name}")
        st_bg_opacity = st.slider("背景遮罩浓度", min_value=0.0, max_value=1.0, value=float(st.session_state.bg_opacity), step=0.02,
                                  help="数值越大白色遮罩越浓、文字越清晰；数值越小背景图越明显。建议 0.1~0.2。")
        if st.session_state.bg_image:
            if st.button("清除背景图", key="clear_bg"):
                st.session_state.bg_image = ""
                save_ui_settings(bg_image="")
                st.success("已清除背景图")
    
        if st.button("保存界面设置", use_container_width=True):
            # ui_theme 已通过 key="ui_theme" 自动同步到 session_state，无需手动写入
            st.session_state.selected_history_limit = st_hist
            st.session_state.bg_opacity = st_bg_opacity
            # pet_enabled / pet_type / pet_size 已通过 key 实时同步到 session_state
            _final_pet_enabled = bool(st.session_state.get("pet_enabled", True))
            _final_pet_type = st.session_state.get("pet_type", "penguin")
            _final_pet_size = int(st.session_state.get("pet_size", 64))
            if _final_pet_type not in _pet_options:
                st.session_state.pet_type = "penguin"
                _final_pet_type = "penguin"
            save_ui_settings(ui_theme=st_theme, history_limit=int(st_hist),
                             bg_image=st.session_state.bg_image, bg_opacity=float(st_bg_opacity),
                             pet_enabled=_final_pet_enabled, pet_type=_final_pet_type,
                             pet_size=_final_pet_size)
            st.success("界面设置已保存")

        # ✨ 个人笔记管理
        st.divider()
        st.markdown("### 📝 个人笔记")
        from utils.user_manager import get_current_user, load_user_notes, save_user_note, delete_user_note
        current_user = get_current_user()

        if not current_user:
            st.info("请在左侧边栏「👤 用户笔记」中登录后使用此功能")
        else:
            notes = load_user_notes(current_user)
            st.caption(f"共 {len(notes)} 条笔记")

            # 新建笔记
            with st.expander("➕ 新建笔记", expanded=False):
                # 获取步骤列表（防御性检查）
                checkpoint_list = getattr(state, 'checkpoints', [])
                if not checkpoint_list:
                    # 如果没有加载 checkpoints，使用默认列表
                    checkpoint_list = [
                        {"checkpoint_id": "cp_01", "checkpoint_cn": "数据导入"},
                        {"checkpoint_id": "cp_02", "checkpoint_cn": "运动校正"},
                        {"checkpoint_id": "cp_03", "checkpoint_cn": "CTF估计"},
                        {"checkpoint_id": "cp_04", "checkpoint_cn": "颗粒挑选"},
                        {"checkpoint_id": "cp_05", "checkpoint_cn": "颗粒提取"},
                        {"checkpoint_id": "cp_06", "checkpoint_cn": "2D分类"},
                        {"checkpoint_id": "cp_07", "checkpoint_cn": "Ab-initio"},
                        {"checkpoint_id": "cp_08", "checkpoint_cn": "3D分类"},
                        {"checkpoint_id": "cp_09", "checkpoint_cn": "3D精修"},
                        {"checkpoint_id": "cp_10", "checkpoint_cn": "CTF精修"},
                        {"checkpoint_id": "cp_11", "checkpoint_cn": "后处理"},
                        {"checkpoint_id": "cp_12", "checkpoint_cn": "模型构建"},
                    ]

                note_step = st.selectbox(
                    "关联步骤",
                    options=[cp.get("checkpoint_id") for cp in checkpoint_list],
                    format_func=lambda cid: next((c.get("checkpoint_cn") for c in checkpoint_list if c.get("checkpoint_id")==cid), cid),
                    key="new_note_step"
                )
                note_content = st.text_area("笔记内容", height=100, key="new_note_content", placeholder="记录关键参数、踩坑经验、个人心得...")
                note_tags_str = st.text_input("标签（逗号分隔）", key="new_note_tags", placeholder="例：CTF, 参数调优")
                if st.button("💾 保存笔记", key="save_new_note", use_container_width=True):
                    if note_content.strip():
                        tags = [t.strip() for t in note_tags_str.split(",") if t.strip()]
                        if save_user_note(current_user, note_step, note_content.strip(), tags):
                            st.success("✅ 笔记已保存")
                            st.rerun()
                        else:
                            st.error("保存失败")
                    else:
                        st.warning("请输入笔记内容")

            # 查看已有笔记
            if notes:
                st.markdown("**我的笔记列表**")
                for note in reversed(notes[-10:]):  # 最新10条
                    with st.expander(f"📌 {note.get('step', '')} · {note.get('timestamp', '')[:16]}", expanded=False):
                        st.markdown(note.get("content", ""))
                        if note.get("tags"):
                            st.caption(f"标签：{', '.join(note.get('tags'))}")
                        if st.button("🗑️ 删除", key=f"del_note_{note.get('id')}"):
                            if delete_user_note(current_user, note.get("id")):
                                st.success("已删除")
                                st.rerun()
            else:
                st.caption("暂无笔记")


        st.divider()
        st.markdown("### 📚 知识文档导入")
        _col_k1, _col_k2 = st.columns([1, 1])
        with _col_k1:
            _import_tier = st.selectbox(
                "文档权重",
                options=["sop", "note"],
                format_func=lambda x: TIER_LABELS.get(x, x),
                index=1,
                key="knowledge_import_tier",
                help="正式SOP=高权重（实验室标准流程），个人笔记=中权重（个人经验）"
            )
        with _col_k2:
            _import_status = st.selectbox(
                "初始状态",
                options=["formal_ready", "draft"],
                format_func=lambda x: "正式可用" if x == "formal_ready" else "草稿（待审核）",
                index=0,
                key="knowledge_import_status",
                help="草稿在检索时降权50%，且不参与正式SOP生成"
            )
        knowledge_file = st.file_uploader("上传知识文档（YAML/JSON）", type=["yaml", "yml", "json"], key="knowledge_doc_uploader")
        if knowledge_file is not None and st.button("📥 导入知识文档", use_container_width=True):
            file_size = len(knowledge_file.getbuffer())
            if file_size > MAX_FILE_SIZE:
                st.error(f"知识文档超过最大限制 {MAX_FILE_SIZE // (1024*1024)}MB")
            else:
                file_ext = Path(knowledge_file.name).suffix.lower()
                if file_ext not in {".yaml", ".yml", ".json"}:
                    st.error("知识文档仅支持 YAML/JSON 格式")
                else:
                    with st.spinner("正在导入知识文档..."):
                        safe_name = f"knowledge_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{file_ext}"
                        tmp_path = UPLOAD_DIR / safe_name
                        tmp_path.write_bytes(knowledge_file.getbuffer())
                        try:
                            doc = load_knowledge_doc(str(tmp_path))
                            doc.tier = _import_tier
                            doc.status = _import_status
                            doc.source = "import"
                            doc.imported_at = datetime.now().isoformat(timespec="seconds")
                            add_doc_to_sharded_index(str(BASE_DIR / "knowledge_base"), doc.to_dict())
                            tier_label = TIER_LABELS.get(doc.tier, doc.tier)
                            status_label = "正式可用" if doc.status == "formal_ready" else "草稿"
                            st.success(f"已导入：{doc.doc_id}（{tier_label} / {status_label}）")
                            app.retriever.invalidate_corpus_cache()
                            # Performance: mark KB dirty so perf_cache clears on next access
                            st.session_state._kb_dirty = True
                            perf_mark_kb_dirty()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"导入失败：{exc}")
                        finally:
                            if tmp_path.exists():
                                tmp_path.unlink()
    
        with st.expander("图文操作文档导入", expanded=False):
            st.caption("支持文本/Markdown/JSON/YAML 和截图批次。系统先生成草稿，人工确认后才进入知识库。")
            op_doc = st.file_uploader(
                "上传操作文档或主截图",
                type=["txt", "md", "markdown", "json", "yaml", "yml", "png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"],
                key="operation_doc_uploader",
            )
            op_images = st.file_uploader(
                "补充截图",
                type=["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"],
                accept_multiple_files=True,
                key="operation_doc_images",
            )
            ic1, ic2 = st.columns(2)
            with ic1:
                ingest_tier = st.selectbox("草稿权重", options=["note", "sop"], format_func=lambda x: TIER_LABELS.get(x, x), key="operation_ingest_tier")
            with ic2:
                ingest_status = st.selectbox(
                    "草稿状态",
                    options=["draft", "formal_ready"],
                    format_func=lambda x: "草稿（待审核）" if x == "draft" else "正式可用",
                    key="operation_ingest_status",
                )
            if op_doc is not None and st.button("生成可审核草稿", use_container_width=True):
                file_size = len(op_doc.getbuffer()) + sum(len(img.getbuffer()) for img in (op_images or []))
                if file_size > MAX_FILE_SIZE * 5:
                    st.error(f"图文材料总大小超过最大限制 {MAX_FILE_SIZE * 5 // (1024*1024)}MB")
                else:
                    source_ext = Path(op_doc.name).suffix.lower()
                    safe_source = UPLOAD_DIR / f"opdoc_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{source_ext}"
                    safe_source.write_bytes(op_doc.getbuffer())
                    image_paths = []
                    try:
                        for idx, image_file in enumerate(op_images or [], start=1):
                            image_ext = Path(image_file.name).suffix.lower()
                            tmp_img = UPLOAD_DIR / f"opdoc_img_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{idx}{image_ext}"
                            tmp_img.write_bytes(image_file.getbuffer())
                            image_paths.append(tmp_img)
                        draft = build_ingest_draft(
                            safe_source,
                            INGEST_ASSET_ROOT,
                            default_software=state.software,
                            tier=ingest_tier,
                            status=ingest_status,
                            extra_image_paths=image_paths,
                        )
                        st.session_state.operation_ingest_draft = draft.to_dict()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"草稿生成失败：{exc}")
                    finally:
                        for path in [safe_source] + image_paths:
                            try:
                                if path.exists():
                                    path.unlink()
                            except Exception:
                                pass
    
            draft_payload = st.session_state.get("operation_ingest_draft")
            if draft_payload:
                draft_doc = draft_payload.get("doc", {})
                draft_images = draft_payload.get("images", []) or []
                for warning in draft_payload.get("warnings", []) or []:
                    st.warning(warning)
                with st.form("operation_ingest_review_form"):
                    st.markdown("**审核草稿**")
                    r_doc_id = st.text_input("doc_id", value=draft_doc.get("doc_id", ""))
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        r_software = st.text_input("software", value=draft_doc.get("software", state.software))
                        r_checkpoint = st.text_input("checkpoint_id", value=draft_doc.get("checkpoint_id", state.current_cp_id))
                    with rc2:
                        r_tier = st.selectbox("权重", options=["note", "sop"], index=0 if draft_doc.get("tier") != "sop" else 1, format_func=lambda x: TIER_LABELS.get(x, x))
                        r_status = st.selectbox("状态", options=["draft", "formal_ready"], index=0 if draft_doc.get("status") != "formal_ready" else 1, format_func=lambda x: "草稿（待审核）" if x == "draft" else "正式可用")
                    r_title = st.text_input("标题", value=draft_doc.get("title_cn", ""))
                    r_summary = st.text_area("摘要", value=draft_doc.get("summary", ""), height=90)
    
                    def _join_draft(value):
                        return "\n".join(value) if isinstance(value, list) else (value or "")
    
                    r_steps = st.text_area("操作步骤（每行一条）", value=_join_draft(draft_doc.get("action_steps")), height=120)
                    r_qc = st.text_area("质控要点（每行一条）", value=_join_draft(draft_doc.get("qc_checks")), height=80)
                    r_errors = st.text_area("常见错误（每行一条）", value=_join_draft(draft_doc.get("common_errors")), height=80)
                    r_tags = st.text_input("标签（逗号分隔）", value=", ".join(draft_doc.get("tags", []) if isinstance(draft_doc.get("tags"), list) else []))
                    approve = st.form_submit_button("确认写入知识库", use_container_width=True)
                    cancel = st.form_submit_button("丢弃草稿", use_container_width=True)
                if draft_images:
                    st.caption(f"已保存截图 {len(draft_images)} 张")
                    for image in draft_images[:6]:
                        image_path = image.get("stored_path", "")
                        if image_path and os.path.exists(image_path):
                            render_lazy_image(image_path, caption=image.get("caption") or image.get("source_name"), width=240)
                if approve:
                    def _split_lines(value):
                        return [item.strip() for item in (value or "").splitlines() if item.strip()]
    
                    doc = KnowledgeDoc(
                        doc_id=r_doc_id.strip() or f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        software=r_software.strip() or state.software,
                        checkpoint_id=r_checkpoint.strip(),
                        title_cn=r_title.strip(),
                        summary=r_summary.strip(),
                        action_steps=_split_lines(r_steps),
                        qc_checks=_split_lines(r_qc),
                        common_errors=_split_lines(r_errors),
                        image_refs=[img.get("stored_path", "") for img in draft_images if img.get("stored_path")],
                        tags=[item.strip() for item in r_tags.split(",") if item.strip()],
                        tier=r_tier,
                        status=r_status,
                        source="document_ingest",
                        imported_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    add_doc_to_sharded_index(str(BASE_DIR / "knowledge_base"), doc.to_dict())
                    app.retriever.invalidate_corpus_cache()
                    st.session_state.operation_ingest_draft = None
                    st.session_state.last_feedback = f"已写入图文知识草稿：{doc.doc_id}"
                    st.rerun()
                if cancel:
                    st.session_state.operation_ingest_draft = None
                    st.rerun()
    
        with st.expander("📂 已导入知识管理", expanded=False):
            _knowledge_dir = str(BASE_DIR / "knowledge_base")
            all_docs = load_sharded_knowledge_index(_knowledge_dir)
            user_docs = [d for d in all_docs if d.get("tier") != "builtin" and d.get("source") != "builtin"]
            if not user_docs:
                st.info("暂无导入的知识文档。上传YAML/JSON文件或使用「沉淀经验」来添加。")
            else:
                def _doc_tags(doc: dict) -> list[str]:
                    tags = doc.get("tags") or []
                    return [str(tag).strip().lower() for tag in tags if str(tag).strip()] if isinstance(tags, list) else []
    
                def _grade_from_doc(doc: dict, field: str, default: str = "未标注") -> str:
                    value = str(doc.get(field) or "").strip()
                    if value:
                        return value.upper() if field.endswith("_grade") and len(value) <= 2 else value
                    tags = _doc_tags(doc)
                    if field == "evidence_grade":
                        for grade in ("a", "b", "c", "d"):
                            if grade in tags:
                                return grade.upper()
                    if field == "risk_grade":
                        for grade in ("high", "medium", "low"):
                            if grade in tags:
                                return grade
                    if field == "source_grade":
                        source_text = " ".join(str(doc.get(k) or "") for k in ("source", "source_url", "summary")).lower()
                        if "official" in source_text or "readthedocs" in source_text or "guide.cryosparc" in source_text:
                            return "A"
                        if doc.get("image_refs"):
                            return "B"
                        if doc.get("source") in {"distill", "user_correction"}:
                            return "C"
                    return default
    
                def _doc_hit_count(doc: dict) -> int:
                    hit_stats = st.session_state.get("kb_hit_stats") or {}
                    stat = hit_stats.get(str(doc.get("doc_id") or ""), {})
                    if isinstance(stat, dict):
                        try:
                            return int(stat.get("hits") or 0)
                        except Exception:
                            pass
                    for key in ("recent_hits", "hit_count", "usage_count", "query_count"):
                        try:
                            return int(doc.get(key) or 0)
                        except Exception:
                            pass
                    return 0
    
                hit_stats_path = RUNTIME_ROOT / "knowledge_hit_counts.json"
                try:
                    hit_payload = json.loads(hit_stats_path.read_text(encoding="utf-8")) if hit_stats_path.exists() else {}
                    st.session_state.kb_hit_stats = hit_payload.get("counts", {}) if isinstance(hit_payload, dict) else {}
                except Exception:
                    st.session_state.kb_hit_stats = {}
    
                formal_count = sum(1 for d in user_docs if d.get("status") == "formal_ready")
                draft_count = sum(1 for d in user_docs if d.get("status") == "draft")
                deprecated_count = sum(1 for d in user_docs if d.get("status") == "deprecated")
                image_doc_count = sum(1 for d in user_docs if d.get("image_refs"))
                high_risk_count = sum(1 for d in user_docs if _grade_from_doc(d, "risk_grade", "").lower() == "high")
                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("正式", formal_count)
                mc2.metric("草稿", draft_count)
                mc3.metric("废弃", deprecated_count)
                mc4.metric("含图文", image_doc_count)
                mc5.metric("高风险", high_risk_count)
                st.caption(f"共 {len(user_docs)} 条知识（不含内置检查站）。草稿和废弃不会作为正式 SOP 的主要证据。")
                conflicts = detect_conflicts(all_docs)
                if conflicts:
                    for cf in conflicts:
                        with st.warning(f"⚠️ 站点 {cf['checkpoint_id']} 可能存在知识矛盾"):
                            st.write(f"**{cf['reason']}**")
                            for did, title in zip(cf["docs"], cf["titles"]):
                                st.markdown(f"- `{did}` — {title}")
                            st.caption("建议在下方列表中审核并调整权重/状态")
    
                fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1])
                with fc1:
                    status_filter = st.selectbox("状态筛选", ["全部", "正式", "草稿", "废弃"], key="kb_status_filter")
                with fc2:
                    risk_filter = st.selectbox("风险筛选", ["全部", "high", "medium", "low", "未标注"], key="kb_risk_filter")
                with fc3:
                    evidence_filter = st.selectbox("证据筛选", ["全部", "A", "B", "C", "D", "未标注"], key="kb_evidence_filter")
                with fc4:
                    sort_opt = st.selectbox("排序", ["按时间(新→旧)", "按站点", "按权重", "按命中"], key="kb_sort_opt")
    
                status_map = {"正式": "formal_ready", "草稿": "draft", "废弃": "deprecated"}
                filtered_docs = list(user_docs)
                if status_filter != "全部":
                    filtered_docs = [d for d in filtered_docs if d.get("status", "formal_ready") == status_map.get(status_filter)]
                if risk_filter != "全部":
                    filtered_docs = [d for d in filtered_docs if _grade_from_doc(d, "risk_grade") == risk_filter]
                if evidence_filter != "全部":
                    filtered_docs = [d for d in filtered_docs if _grade_from_doc(d, "evidence_grade") == evidence_filter]
    
                if sort_opt == "按时间(新→旧)":
                    filtered_docs.sort(key=lambda d: d.get("imported_at", ""), reverse=True)
                elif sort_opt == "按站点":
                    filtered_docs.sort(key=lambda d: (d.get("checkpoint_id", ""), d.get("title_cn", "")))
                elif sort_opt == "按命中":
                    filtered_docs.sort(key=_doc_hit_count, reverse=True)
                else:
                    _tw = {"sop": 3, "note": 2, "draft": 1}
                    filtered_docs.sort(key=lambda d: _tw.get(d.get("tier", "note"), 0), reverse=True)
    
                if not filtered_docs:
                    st.info("当前筛选条件下没有知识条目。")
    
                for i, d in enumerate(filtered_docs):
                    did = d.get("doc_id", f"doc_{i}")
                    title = d.get("title_cn") or d.get("title_en") or did
                    cp = d.get("checkpoint_id", "")
                    tier = d.get("tier", "note")
                    status = d.get("status", "formal_ready")
                    src = d.get("source", "import")
                    src_label = {"import": "📥导入", "distill": "💬沉淀", "builtin": "📘内置", "document_ingest": "🖼️图文", "user_correction": "🧾纠错"}.get(src, src)
                    tier_label = TIER_LABELS.get(tier, tier)
                    status_icon = "✅" if status == "formal_ready" else ("🚫" if status == "deprecated" else "📝")
                    status_label = {"formal_ready": "正式", "draft": "草稿", "deprecated": "废弃"}.get(status, status)
                    evidence_grade = _grade_from_doc(d, "evidence_grade")
                    risk_grade = _grade_from_doc(d, "risk_grade")
                    source_grade = _grade_from_doc(d, "source_grade")
                    image_count = len(d.get("image_refs") or [])
                    hit_count = _doc_hit_count(d)
    
                    with st.container():
                        hc1, hc2, hc3, hc4 = st.columns([3, 1.2, 1.4, 1.2])
                        with hc1:
                            st.markdown(f"**{title}**  `{did}`")
                        with hc2:
                            st.caption(f"{src_label} {cp}")
                        with hc3:
                            st.caption(f"🏷️{tier_label} · 图 {image_count} · 命中 {hit_count}")
                        with hc4:
                            st.caption(f"{status_icon}{status_label}")
                        summary = (d.get("summary") or "")[:120]
                        if summary:
                            st.caption(summary)
                        st.caption(f"来源等级 {source_grade} · 证据等级 {evidence_grade} · 风险等级 {risk_grade} · 审核状态 {d.get('review_status') or status_label}")
                        bc0, bc1, bc2, bc3, bc4, bc5 = st.columns([1, 1, 1, 1, 1, 1])
                        with bc0:
                            if st.button("✏️编辑", key=f"kb_edit_{i}", use_container_width=True):
                                st.session_state[f"kb_editing_{i}"] = not st.session_state.get(f"kb_editing_{i}", False)
                        with bc1:
                            if st.button("👁️查看", key=f"kb_view_{i}", use_container_width=True):
                                st.session_state[f"kb_detail_{i}"] = not st.session_state.get(f"kb_detail_{i}", False)
                        with bc2:
                            new_tier = "note" if tier == "sop" else "sop"
                            new_tier_label = TIER_LABELS.get(new_tier, new_tier)
                            if st.button(f"→{new_tier_label}", key=f"kb_tier_{i}", use_container_width=True):
                                update_doc_status_in_sharded_index(str(BASE_DIR / "knowledge_base"), did, status, new_tier)
                                app.retriever.invalidate_corpus_cache()
                                st.rerun()
                        with bc3:
                            new_status = "draft" if status == "formal_ready" else "formal_ready"
                            new_status_label = "转草稿" if new_status == "draft" else "转正"
                            if st.button(f"{status_icon}{new_status_label}", key=f"kb_status_{i}", use_container_width=True):
                                update_doc_status_in_sharded_index(str(BASE_DIR / "knowledge_base"), did, new_status)
                                app.retriever.invalidate_corpus_cache()
                                st.rerun()
                        with bc4:
                            new_status = "draft" if status == "deprecated" else "deprecated"
                            new_status_label = "恢复草稿" if new_status == "draft" else "废弃"
                            if st.button(new_status_label, key=f"kb_deprecate_{i}", use_container_width=True):
                                update_doc_status_in_sharded_index(str(BASE_DIR / "knowledge_base"), did, new_status)
                                app.retriever.invalidate_corpus_cache()
                                st.rerun()
                        with bc5:
                            if st.button("🗑️删除", key=f"kb_del_{i}", use_container_width=True):
                                delete_doc_from_sharded_index(str(BASE_DIR / "knowledge_base"), did)
                                app.retriever.invalidate_corpus_cache()
                                st.rerun()
                        # ── 内联编辑表单 ──────────────────────────
                        if st.session_state.get(f"kb_editing_{i}", False):
                            with st.form(key=f"kb_edit_form_{i}"):
                                st.caption(f"编辑知识条目 `{did}`")
                                edit_title = st.text_input(
                                    "标题", value=d.get("title_cn") or d.get("title_en") or "",
                                    key=f"kb_edit_title_{i}",
                                )
                                edit_summary = st.text_area(
                                    "摘要 / 内容", value=d.get("summary") or "",
                                    height=120, key=f"kb_edit_summary_{i}",
                                )
                                ec1, ec2 = st.columns(2)
                                with ec1:
                                    _status_opts = ["formal_ready", "draft", "deprecated"]
                                    edit_status = st.selectbox(
                                        "状态", options=_status_opts,
                                        index=_status_opts.index(status) if status in _status_opts else 0,
                                        format_func=lambda x: {"formal_ready": "✅ 正式", "draft": "📝 草稿", "deprecated": "🚫 废弃"}.get(x, x),
                                        key=f"kb_edit_status_{i}",
                                    )
                                with ec2:
                                    _tier_opts = ["sop", "note"]
                                    edit_tier = st.selectbox(
                                        "权重", options=_tier_opts,
                                        index=_tier_opts.index(tier) if tier in _tier_opts else 1,
                                        format_func=lambda x: TIER_LABELS.get(x, x),
                                        key=f"kb_edit_tier_{i}",
                                    )
                                _saved = st.form_submit_button("💾 保存修改", use_container_width=True)
                            if _saved:
                                update_doc_fields_in_sharded_index(
                                    str(BASE_DIR / "knowledge_base"), did,
                                    {
                                        "title_cn": edit_title,
                                        "summary": edit_summary,
                                        "status": edit_status,
                                        "tier": edit_tier,
                                    },
                                )
                                app.retriever.invalidate_corpus_cache()
                                st.session_state[f"kb_editing_{i}"] = False
                                st.success(f"已保存：{edit_title}")
                                st.rerun()
                        if st.session_state.get(f"kb_detail_{i}", False):
                            st.json({k: v for k, v in d.items() if k not in ("ui_keywords", "ui_elements")}, expanded=False)
                            for img_path in (d.get("image_refs") or [])[:4]:
                                if img_path and os.path.exists(img_path):
                                    render_lazy_image(img_path, width=220)
                        st.divider()
    
        with st.expander("用户纠错审核", expanded=False):
            corrections = load_corrections(CORRECTIONS_PATH, limit=50)
            if not corrections:
                st.info("暂无用户纠错记录。用户在对话中提交理解纠正或回答反馈后，会出现在这里。")
            else:
                st.caption(f"最近 {len(corrections)} 条待审核纠错。纠错记录采用追加日志保存，便于审计和回溯。")
                for idx, item in enumerate(corrections):
                    title = item.get("user_note") or item.get("corrected_query") or item.get("kind", "correction")
                    title = str(title).strip()[:80] or item.get("correction_id", f"corr_{idx}")
                    with st.container():
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            st.markdown(f"**{title}**")
                            st.caption(
                                f"{item.get('kind', '')} · {item.get('software', '')} · "
                                f"{item.get('checkpoint_id', '')} · {item.get('created_at', '')}"
                            )
                        with c2:
                            if st.button("查看", key=f"corr_view_{idx}", use_container_width=True):
                                st.session_state[f"corr_detail_{idx}"] = not st.session_state.get(f"corr_detail_{idx}", False)
                        with c3:
                            if st.button("转知识草稿", key=f"corr_to_doc_{idx}", use_container_width=True):
                                summary = item.get("user_note") or item.get("corrected_query") or item.get("answer_excerpt") or "User correction"
                                doc = KnowledgeDoc(
                                    doc_id=f"corr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}",
                                    software=item.get("software") or state.software,
                                    checkpoint_id=item.get("checkpoint_id") or state.current_cp_id,
                                    title_cn=f"用户纠错：{item.get('kind', 'correction')}",
                                    summary=str(summary).strip(),
                                    action_steps=[item.get("corrected_query", "")] if item.get("corrected_query") else [],
                                    common_errors=[item.get("answer_excerpt", "")[:300]] if item.get("answer_excerpt") else [],
                                    tags=["user_correction", item.get("kind", "correction")],
                                    tier="note",
                                    status="draft",
                                    source="user_correction",
                                    imported_at=datetime.now().isoformat(timespec="seconds"),
                                )
                                add_doc_to_sharded_index(str(BASE_DIR / "knowledge_base"), doc.to_dict())
                                app.retriever.invalidate_corpus_cache()
                                st.session_state.last_feedback = f"已转为知识草稿：{doc.doc_id}"
                                st.rerun()
                        if st.session_state.get(f"corr_detail_{idx}", False):
                            st.json(item, expanded=False)
                        st.divider()
    
    # --------------------------------------------------------------------------- #
    # 高级模式专属功能面板（仅在 expert 模式下渲染）
    # --------------------------------------------------------------------------- #
if st.session_state.app_mode == "expert":
    st.markdown("---")
    from modes import render_expert_view
    # 在底部追加高级功能（导出、预设、贡献经验）
    with st.expander("⚙️ 高级功能", expanded=False):
        render_expert_view(_current_cp, state.software)

# --------------------------------------------------------------------------- #
# Desk Pets (bottom-right companions)
# --------------------------------------------------------------------------- #
if st.session_state.get("pet_enabled", True):
    _cp_name = state.current_cp_name or "等待开始"
    _completed = len(state.completed)
    _failed = len(state.failed)
    _cp_total_num = cp_total
    if not state.session_started:
        _pet_ctx = "idle"
    elif _failed > 0 and state.current_cp_id in state.failed:
        _pet_ctx = "error"
    elif _completed >= _cp_total_num:
        _pet_ctx = "done"
    else:
        _pet_ctx = "working"

    _pet_type = st.session_state.get("pet_type", "penguin")

    _pets = {
        "cat": {
            "svg": (
                '<svg class="sp-pet-body" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<g class="sp-cat-hearts" opacity="0">'
                '<text class="sp-cat-heart sp-cat-h1" x="10" y="0" font-size="10" fill="#f472b6">❤</text>'
                '<text class="sp-cat-heart sp-cat-h2" x="32" y="-2" font-size="8" fill="#fb7185">❤</text>'
                '<text class="sp-cat-heart sp-cat-h3" x="52" y="2" font-size="9" fill="#f472b6">❤</text>'
                '</g>'
                '<g class="sp-pet-tail-group" style="transform-origin:50px 40px">'
                '<path class="sp-pet-tail" d="M50 40 Q58 34 56 24 Q53 16 48 18 Q44 20 46 26 Q48 30 44 30" stroke="#94a3b8" stroke-width="3" stroke-linecap="round" fill="none" stroke-linejoin="round"/>'
                '</g>'
                '<ellipse cx="30" cy="46" rx="17" ry="12" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.8"/>'
                '<path class="sp-cat-stripe" d="M22 38 Q24 36 26 38" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
                '<path class="sp-cat-stripe" d="M34 38 Q36 36 38 38" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
                '<path class="sp-cat-paw-l" d="M20 56 Q18 53 22 54 Q24 55 22 57 Z" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.2" stroke-linejoin="round"/>'
                '<path class="sp-cat-paw-r" d="M38 56 Q40 53 36 54 Q34 55 36 57 Z" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.2" stroke-linejoin="round"/>'
                '<g class="sp-cat-ear-l"><path d="M15 30 L10 16 L22 28 Z" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.8" stroke-linejoin="round"/><path d="M14 28 L12 20 L19 27 Z" fill="#fbcfe8" opacity="0.7"/></g>'
                '<g class="sp-cat-ear-r"><path d="M45 30 L50 16 L38 28 Z" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.8" stroke-linejoin="round"/><path d="M46 28 L48 20 L41 27 Z" fill="#fbcfe8" opacity="0.7"/></g>'
                '<ellipse cx="30" cy="34" rx="15" ry="13" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.8"/>'
                '<path class="sp-cat-forehead" d="M26 24 Q30 20 34 24" stroke="#cbd5e1" stroke-width="1.3" stroke-linecap="round" fill="none"/>'
                '<path class="sp-cat-forehead" d="M28 23 Q30 20 32 23" stroke="#e2e8f0" stroke-width="1" stroke-linecap="round" fill="none"/>'
                '<circle cx="23" cy="33" r="3.5" fill="#fff" stroke="#cbd5e1" stroke-width="0.7"/>'
                '<circle cx="37" cy="33" r="3.5" fill="#fff" stroke="#cbd5e1" stroke-width="0.7"/>'
                '<ellipse class="sp-pet-eye-pupil sp-cat-pupil-l" cx="23" cy="33" rx="2.2" ry="2.8" fill="#1e293b"/>'
                '<ellipse class="sp-pet-eye-pupil sp-cat-pupil-r" cx="37" cy="33" rx="2.2" ry="2.8" fill="#1e293b"/>'
                '<circle cx="22.2" cy="32" r="0.8" fill="#fff"/>'
                '<circle cx="36.2" cy="32" r="0.8" fill="#fff"/>'
                '<path class="sp-cat-eye-closed-l" d="M20 33 Q23 36 26 33" stroke="#1e293b" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0"/>'
                '<path class="sp-cat-eye-closed-r" d="M34 33 Q37 36 40 33" stroke="#1e293b" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0"/>'
                '<ellipse cx="30" cy="40" rx="2" ry="1.3" fill="#f87171"/>'
                '<path class="sp-cat-mouth" d="M28 42 Q30 45 32 42" stroke="#64748b" stroke-width="1.3" stroke-linecap="round" fill="none"/>'
                '<path class="sp-cat-mouth-open" d="M28 42 Q30 46 32 42 Q30 44 28 42" fill="#f87171" stroke="#64748b" stroke-width="0.8" opacity="0"/>'
                '<g class="sp-cat-whiskers-l">'
                '<line x1="14" y1="37" x2="5" y2="35" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '<line x1="14" y1="40" x2="4" y2="40" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '<line x1="14" y1="43" x2="5" y2="45" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '</g>'
                '<g class="sp-cat-whiskers-r">'
                '<line x1="46" y1="37" x2="55" y2="35" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '<line x1="46" y1="40" x2="56" y2="40" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '<line x1="46" y1="43" x2="55" y2="45" stroke="#94a3b8" stroke-width="1" stroke-linecap="round"/>'
                '</g>'
                '</svg>'
            ),
            "msgs": {
                "idle": ["喵～准备好开始实验了吗？", "点「开始」陪你做实验喵！", "趴在电脑上等你好久了喵～", "打个哈欠…要不要开始呀？"],
                "working": [
                    f"喵！正在「{_cp_name}」，专注中～",
                    f"已经完成 {_completed}/{_cp_total_num} 个检查点了喵！",
                    "遇到报错点「报错」，我帮你闻闻哪里不对～",
                    "SOP里的质控要点要仔细看哦喵～",
                    "我在你键盘旁边守着，数据不会跑掉的！",
                    "咕噜咕噜…这步很重要，慢慢来喵",
                    "舔爪子等你结果…加油喵！",
                ],
                "error": [
                    "喵？！报错了？别慌，我看看！",
                    "把错误信息点「报错」告诉我喵～",
                    "实验出问题很正常的喵，我们一起解决！",
                    "毛都炸起来了…快说什么情况！",
                ],
                "done": [
                    "喵呜！！全部完成啦！好棒好棒！",
                    "快导出报告，然后给我小鱼干奖励！",
                    "辛苦了喵！我也要去睡觉了zzz…",
                    "完美收工！在你键盘上踩个梅花印",
                ],
            },
        },
        "penguin": {
            "svg": (
                '<svg class="sp-pet-body" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<ellipse cx="32" cy="54" rx="14" ry="3" fill="#0f172a" opacity="0.08"/>'
                '<path d="M18 46 Q14 38 16 26 Q18 14 32 12 Q46 14 48 26 Q50 38 46 46 Z" fill="#1e293b" stroke="#334155" stroke-width="1.8" stroke-linejoin="round"/>'
                '<path d="M22 44 Q20 34 24 24 Q28 18 32 18 Q36 18 40 24 Q44 34 42 44 Z" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.2"/>'
                '<g class="sp-pet-tail-group" style="transform-origin:15px 36px"><ellipse class="sp-pet-tail" cx="15" cy="36" rx="4" ry="9" fill="#1e293b" stroke="#334155" stroke-width="1.2" transform="rotate(8 15 36)"/></g>'
                '<g class="sp-pet-tail-group" style="transform-origin:49px 36px"><ellipse class="sp-pet-tail" cx="49" cy="36" rx="4" ry="9" fill="#1e293b" stroke="#334155" stroke-width="1.2" transform="rotate(-8 49 36)"/></g>'
                '<circle cx="26" cy="28" r="3.5" fill="#fff" stroke="#e2e8f0" stroke-width="0.6"/>'
                '<circle cx="38" cy="28" r="3.5" fill="#fff" stroke="#e2e8f0" stroke-width="0.6"/>'
                '<circle class="sp-pet-eye-pupil" cx="27" cy="28" r="2" fill="#0f172a"/>'
                '<circle class="sp-pet-eye-pupil" cx="39" cy="28" r="2" fill="#0f172a"/>'
                '<circle cx="26.2" cy="27" r="0.6" fill="#fff"/>'
                '<circle cx="38.2" cy="27" r="0.6" fill="#fff"/>'
                '<path d="M30 33 L32 37 L34 33 Z" fill="#f97316" stroke="#ea580c" stroke-width="0.8" stroke-linejoin="round"/>'
                '<path d="M20 48 L16 56 L22 56 L24 50 Z" fill="#f97316" stroke="#ea580c" stroke-width="1.2" stroke-linejoin="round"/>'
                '<path d="M44 48 L48 56 L42 56 L40 50 Z" fill="#f97316" stroke="#ea580c" stroke-width="1.2" stroke-linejoin="round"/>'
                '<ellipse cx="25" cy="40" rx="3" ry="4" fill="#e0f2fe" opacity="0.3" transform="rotate(-10 25 40)"/>'
                '<ellipse cx="39" cy="40" rx="3" ry="4" fill="#e0f2fe" opacity="0.3" transform="rotate(10 39 40)"/>'
                '<circle cx="20" cy="18" r="1.5" fill="#7dd3fc" opacity="0.6"/>'
                '<circle cx="44" cy="17" r="1.2" fill="#7dd3fc" opacity="0.5"/>'
                '<circle cx="14" cy="24" r="1" fill="#bae6fd" opacity="0.4"/>'
                '</svg>'
            ),
            "msgs": {
                "idle": ["咕噜～低温环境就绪！", "准备好了吗？我最喜欢冷冻电镜了！", "液氦温度-196°C，很舒服～"],
                "working": [
                    f"「{_cp_name}」阶段，保持冷静！",
                    f"进度 {_completed}/{_cp_total_num}，冰上稳扎稳打！",
                    "报错了？别冻住，点「报错」告诉我～",
                    "CTF参数要仔细看哦，冰晶是敌人",
                    "低温下数据最稳定，慢慢来",
                ],
                "error": [
                    "哎呀！冰有问题？让我看看～",
                    "点「报错」告诉我具体情况，我不怕冷",
                    "别着急，每个电镜人都踩过冰污染的坑",
                ],
                "done": [
                    "数据处理完毕！完美收工！",
                    "记得导出报告，别忘了保存.mrc文件",
                    "辛苦啦！我先回液氮里待着了",
                ],
            },
        },
        "dog": {
            "svg": (
                '<svg class="sp-pet-body" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<g class="sp-pet-tail-group" style="transform-origin:12px 38px"><path class="sp-pet-tail" d="M12 38 Q6 34 8 26" stroke="#92400e" stroke-width="3.5" stroke-linecap="round" fill="none"/></g>'
                '<ellipse cx="34" cy="44" rx="18" ry="14" fill="#fef3c7" stroke="#d97706" stroke-width="1.8"/>'
                '<ellipse cx="22" cy="24" rx="7" ry="10" fill="#fef3c7" stroke="#d97706" stroke-width="1.8" transform="rotate(-15 22 24)"/>'
                '<ellipse cx="44" cy="24" rx="7" ry="10" fill="#fef3c7" stroke="#d97706" stroke-width="1.8" transform="rotate(15 44 24)"/>'
                '<ellipse cx="22" cy="26" rx="4" ry="6" fill="#fcd34d" opacity="0.6" transform="rotate(-15 22 26)"/>'
                '<ellipse cx="44" cy="26" rx="4" ry="6" fill="#fcd34d" opacity="0.6" transform="rotate(15 44 26)"/>'
                '<ellipse cx="34" cy="32" rx="15" ry="13" fill="#fef9c3" stroke="#d97706" stroke-width="1.8"/>'
                '<circle cx="28" cy="30" r="3.2" fill="#fff" stroke="#fcd34d" stroke-width="0.6"/>'
                '<circle cx="40" cy="30" r="3.2" fill="#fff" stroke="#fcd34d" stroke-width="0.6"/>'
                '<circle class="sp-pet-eye-pupil" cx="28.5" cy="30" r="2.2" fill="#1e293b"/>'
                '<circle class="sp-pet-eye-pupil" cx="40.5" cy="30" r="2.2" fill="#1e293b"/>'
                '<circle cx="27.7" cy="29" r="0.7" fill="#fff"/>'
                '<circle cx="39.7" cy="29" r="0.7" fill="#fff"/>'
                '<ellipse cx="34" cy="38" rx="4" ry="3" fill="#1e293b"/>'
                '<ellipse cx="34" cy="37" rx="1.2" ry="0.8" fill="#64748b"/>'
                '<path d="M34 41 Q30 45 26 43" stroke="#92400e" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
                '<path d="M34 41 Q38 45 42 43" stroke="#92400e" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
                '<ellipse cx="52" cy="40" rx="4" ry="3" fill="#f87171" opacity="0.5"/>'
                '<path d="M46 20 L52 14 L50 20" fill="#dc2626" stroke="#b91c1c" stroke-width="0.8" stroke-linejoin="round"/>'
                '</svg>'
            ),
            "msgs": {
                "idle": ["汪！准备好开始了吗？", "我是你的实验小助手，汪汪！", "摇尾巴等你哦～"],
                "working": [
                    f"汪汪！正在「{_cp_name}」，好棒！",
                    f"已完成 {_completed}/{_cp_total_num}，继续加油！",
                    "有问题随时叫我！点「报错」就好",
                    "SOP就是我的指令，我帮你盯着进度",
                    "数据要仔细核对哦，别漏了细节",
                ],
                "error": [
                    "汪呜！出问题了？我帮你看看哪里不对",
                    "别急，点「报错」我帮你找问题",
                    "实验路上总有小坑，我们跨过去！",
                ],
                "done": [
                    "汪汪！全部完成！你是最棒的！",
                    "尾巴摇到飞起！记得导出报告哦",
                    "好棒好棒！奖励自己一根骨头",
                ],
            },
        },
        "robot": {
            "svg": (
                '<svg class="sp-pet-body" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<g class="sp-pet-tail-group" style="transform-origin:32px 10px"><line class="sp-pet-tail" x1="32" y1="10" x2="32" y2="4" stroke="#64748b" stroke-width="1.5" stroke-linecap="round"/>'
                '<circle cx="32" cy="3" r="2.5" fill="#ef4444"/></g>'
                '<rect x="16" y="18" width="32" height="28" rx="6" fill="#f1f5f9" stroke="#64748b" stroke-width="1.8"/>'
                '<rect x="20" y="22" width="24" height="12" rx="3" fill="#1e293b" stroke="#475569" stroke-width="1"/>'
                '<rect class="sp-pet-eye-pupil" x="23" y="25" width="6" height="6" rx="1.5" fill="#22d3ee" opacity="0.95" style="transform-origin:26px 28px"/>'
                '<rect class="sp-pet-eye-pupil" x="35" y="25" width="6" height="6" rx="1.5" fill="#22d3ee" opacity="0.95" style="transform-origin:38px 28px"/>'
                '<rect x="26" y="37" width="12" height="4" rx="2" fill="#94a3b8"/>'
                '<circle cx="22" cy="44" r="2" fill="#94a3b8"/>'
                '<circle cx="32" cy="44" r="2" fill="#94a3b8"/>'
                '<circle cx="42" cy="44" r="2" fill="#94a3b8"/>'
                '<rect x="22" y="46" width="20" height="4" rx="2" fill="#94a3b8"/>'
                '<rect x="10" y="26" width="6" height="10" rx="3" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5"/>'
                '<rect x="48" y="26" width="6" height="10" rx="3" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5"/>'
                '<line x1="13" y1="38" x2="13" y2="48" stroke="#64748b" stroke-width="1.5" stroke-linecap="round"/>'
                '<line x1="51" y1="38" x2="51" y2="48" stroke="#64748b" stroke-width="1.5" stroke-linecap="round"/>'
                '<rect x="24" y="50" width="6" height="8" rx="1" fill="#f1f5f9" stroke="#64748b" stroke-width="1.2"/>'
                '<rect x="34" y="50" width="6" height="8" rx="1" fill="#f1f5f9" stroke="#64748b" stroke-width="1.2"/>'
                '<rect x="48" y="18" width="3" height="6" rx="1" fill="#fbbf24"/>'
                '</svg>'
            ),
            "msgs": {
                "idle": ["系统就绪，等待指令。", "StructPilot AI助手已启动。", "请点击「开始」初始化流程。"],
                "working": [
                    f"当前阶段：{_cp_name}，执行中...",
                    f"进度：{_completed}/{_cp_total_num}，继续处理",
                    "检测到异常？请点击「报错」进行诊断",
                    "质控参数分析中，请核对SOP",
                    "知识库检索待命，有问题随时问",
                ],
                "error": [
                    "警报：检测到异常。请描述问题进行故障诊断",
                    "错误已记录，点击「报错」获取解决方案",
                    "建议检查参数配置和输入文件",
                ],
                "done": [
                    "任务完成！所有阶段已通过",
                    "建议导出实验报告进行归档",
                    "会话结束。StructPilot随时待命。",
                ],
            },
        },
        "rabbit": {
            "svg": (
                '<svg class="sp-pet-body" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<ellipse cx="34" cy="58" rx="14" ry="3" fill="#0f172a" opacity="0.08"/>'
                '<g class="sp-pet-tail-group" style="transform-origin:14px 44px"><circle class="sp-pet-tail" cx="14" cy="44" r="5" fill="#f8fafc" stroke="#d1d5db" stroke-width="1.5"/></g>'
                '<ellipse cx="34" cy="46" rx="16" ry="13" fill="#f9fafb" stroke="#d1d5db" stroke-width="1.8"/>'
                '<ellipse cx="24" cy="14" rx="4" ry="12" fill="#f9fafb" stroke="#d1d5db" stroke-width="1.8" transform="rotate(-8 24 14)"/>'
                '<ellipse cx="42" cy="14" rx="4" ry="12" fill="#f9fafb" stroke="#d1d5db" stroke-width="1.8" transform="rotate(8 42 14)"/>'
                '<ellipse cx="24" cy="16" rx="2" ry="8" fill="#fbcfe8" opacity="0.6" transform="rotate(-8 24 16)"/>'
                '<ellipse cx="42" cy="16" rx="2" ry="8" fill="#fbcfe8" opacity="0.6" transform="rotate(8 42 16)"/>'
                '<ellipse cx="32" cy="34" rx="14" ry="12" fill="#fff" stroke="#d1d5db" stroke-width="1.8"/>'
                '<circle cx="26" cy="32" r="3" fill="#fff" stroke="#e5e7eb" stroke-width="0.5"/>'
                '<circle cx="38" cy="32" r="3" fill="#fff" stroke="#e5e7eb" stroke-width="0.5"/>'
                '<circle class="sp-pet-eye-pupil" cx="26.5" cy="32" r="2" fill="#1e293b"/>'
                '<circle class="sp-pet-eye-pupil" cx="38.5" cy="32" r="2" fill="#1e293b"/>'
                '<circle cx="25.8" cy="31" r="0.7" fill="#fff"/>'
                '<circle cx="37.8" cy="31" r="0.7" fill="#fff"/>'
                '<ellipse cx="32" cy="38" rx="2" ry="1.5" fill="#f472b6"/>'
                '<path d="M32 39 L32 41" stroke="#9ca3af" stroke-width="1" stroke-linecap="round"/>'
                '<path d="M32 41 Q28 43 26 41" stroke="#9ca3af" stroke-width="1.2" stroke-linecap="round" fill="none"/>'
                '<path d="M32 41 Q36 43 38 41" stroke="#9ca3af" stroke-width="1.2" stroke-linecap="round" fill="none"/>'
                '<ellipse cx="20" cy="36" rx="3" ry="2" fill="#fca5a5" opacity="0.4"/>'
                '<ellipse cx="44" cy="36" rx="3" ry="2" fill="#fca5a5" opacity="0.4"/>'
                '<line x1="18" y1="37" x2="10" y2="35" stroke="#d1d5db" stroke-width="0.8" stroke-linecap="round"/>'
                '<line x1="18" y1="39" x2="10" y2="39" stroke="#d1d5db" stroke-width="0.8" stroke-linecap="round"/>'
                '<line x1="46" y1="37" x2="54" y2="35" stroke="#d1d5db" stroke-width="0.8" stroke-linecap="round"/>'
                '<line x1="46" y1="39" x2="54" y2="39" stroke="#d1d5db" stroke-width="0.8" stroke-linecap="round"/>'
                '</svg>'
            ),
            "msgs": {
                "idle": ["蹦蹦～准备好开始了吗？", "竖起耳朵等你哦～", "实验兔兔报到！随时待命～", "要不要开始呀？"],
                "working": [
                    f"蹦蹦！正在「{_cp_name}」，加油！",
                    f"已完成 {_completed}/{_cp_total_num}，继续蹦跶！",
                    "有问题点「报错」，我竖耳朵听～",
                    "SOP要仔细看哦，我来帮你盯进度",
                    "参数核对好了吗？我帮你看着呢",
                    "蹦跶蹦跶…这步很重要，慢慢来",
                ],
                "error": [
                    "耳朵竖起来了！出什么问题了？",
                    "点「报错」告诉我，我帮你看看",
                    "别着急，每个实验都有小坎坷",
                    "抖抖耳朵…快说什么情况！",
                ],
                "done": [
                    "蹦蹦蹦！！全部完成啦！好棒！",
                    "开心到原地蹦跳！记得导出报告",
                    "辛苦啦！我要去啃胡萝卜庆祝了",
                    "完美收工！给你一个兔兔抱抱",
                ],
            },
        },
    }
    _pet_data = _pets.get(_pet_type, _pets["penguin"])
    _pet_svg = _pet_data["svg"]
    _pet_msgs_map = _pet_data["msgs"]

    _interact_msgs = {
        "cat": {
            "pet": ["舒服～继续操作吧！", "点头中…这一步很关键", "准备好就点「完成」", "参数要仔细核对哦", "检测到进度，加油！", "SOP对照一下会更稳", "质控不马虎，结果才靠谱"],
            "body": ["需要帮忙吗？", "参数卡住了可以问我", "SOP在哪一步？", "上传图片可辅助诊断", "现在进展如何？", "遇到报错别慌"],
            "tail": ["注意检查参数设置！", "偏离SOP了，回看一下", "可能漏了关键步骤", "建议重新校准", "这一步要更仔细", "别急，再核对一遍"],
        },
        "penguin": {
            "pet": ["操作规范，进展顺利", "设备状态良好，继续", "样品准备很关键", "SOP要严格遵守哦"],
            "body": ["需要查询知识库吗？", "当前步骤的要点？", "质控指标正常吗？"],
            "tail": ["注意安全操作规程", "设备参数需重新校准", "检查流程是否合规"],
        },
        "dog": {
            "pet": ["操作得不错！继续", "协作顺利，加油", "SOP执行很到位", "效率很高，继续保持"],
            "body": ["需要解答什么问题？", "下一步计划？", "参数配置确认了吗？"],
            "tail": ["注意检查关键步骤", "别跳过质控环节", "建议重新审视流程"],
        },
        "robot": {
            "pet": ["操作状态：正常。系统运行中。", "检测到规范操作，记录已保存。", "协作效率：良好。继续执行。"],
            "body": ["指令已接收，等待输入。", "系统就绪，请下达任务。", "数据采集中，请稍候。"],
            "tail": ["警告：检测到偏离标准流程。", "警报：关键参数未设置。", "错误：操作顺序异常。"],
        },
        "rabbit": {
            "pet": ["蹦蹦～操作得不错！", "竖耳朵听你指挥！", "协作很顺利，继续加油", "SOP执行到位，棒棒的"],
            "body": ["需要帮什么忙吗？", "下一步该做什么呢？", "参数配置好了吗？", "遇到问题可以问我哦"],
            "tail": ["注意检查关键步骤！", "别跳过质控环节～", "建议重新审视流程", "抖抖耳朵…这里要更仔细"],
        },
    }
    _i_msgs = _interact_msgs.get(_pet_type, _interact_msgs["cat"])
    _pet_default = "你好～"
    import json as _json
    _pet_ctx_msgs = _json.dumps(_pet_msgs_map.get(_pet_ctx, [_pet_default]), ensure_ascii=False)
    _pet_pet_msgs = _json.dumps(_i_msgs["pet"], ensure_ascii=False)
    _pet_body_msgs = _json.dumps(_i_msgs["body"], ensure_ascii=False)
    _pet_tail_msgs = _json.dumps(_i_msgs["tail"], ensure_ascii=False)

    # Quick questions based on current context
    _quick_qs = []
    if not state.session_started:
        _quick_qs = [
            "我是新手，怎么开始？",
            "12个检查点都是什么？",
            "这个软件怎么用？",
        ]
    else:
        _cp_cur = state.current_cp_name or "当前步骤"
        _quick_qs = [
            f"{_cp_cur}的SOP是什么？",
            f"{_cp_cur}有什么常见问题？",
            f"{_cp_cur}关键参数怎么设？",
            "下一步该做什么？",
            "我卡住了，帮帮我！",
        ]
    _pet_quick_qs = _json.dumps(_quick_qs, ensure_ascii=False)

    # Render the desk pet through an isolated Streamlit custom component so
    # its JavaScript runs reliably and can send quick-question events back.
    _theme_name = _ui_settings.get("theme", "light")
    _is_dark = _theme_name == "dark"
    _pet_theme = {
        "sidebar": "#f8fafc",
        "sidebar_border": "#e2e8f0",
        "app": "#ffffff",
        "text": "#0f172a",
        "accent": "#2563eb",
    }
    if _is_dark:
        _pet_theme = {
            "sidebar": "#1e293b",
            "sidebar_border": "#334155",
            "app": "#0f172a",
            "text": "#f1f5f9",
            "accent": "#3b82f6",
        }
    pet_value = render_desk_pet(
        pet_type=_pet_type,
        pet_svg=_pet_svg,
        ctx_msgs=_pet_msgs_map.get(_pet_ctx, [_pet_default]),
        pet_msgs=_i_msgs["pet"],
        body_msgs=_i_msgs["body"],
        tail_msgs=_i_msgs["tail"],
        quick_qs=_quick_qs,
        theme=_pet_theme,
        is_dark=_is_dark,
        pet_mood=_pet_ctx,
        pet_size=int(st.session_state.get("pet_size", 64)),
    )
    # Handle actions from desk pet (via hidden text input)
    if pet_value:
        try:
            _pet_action = json.loads(pet_value) if isinstance(pet_value, str) else pet_value
            if isinstance(_pet_action, dict):
                _action_type = _pet_action.get("action")
                if _action_type == "quick_q":
                    handle_pet_quick_question(
                        _pet_action.get("question", ""),
                        run_command,
                        response_profile=get_state("output_mode", "teaching"),
                    )
                elif _action_type == "switch_pet":
                    _new_pet = _pet_action.get("pet_type", "penguin")
                    if _new_pet in _pet_options:
                        st.session_state["_pending_pet_type"] = _new_pet
                    st.session_state["_pending_clear_pet_action"] = True
                    st.rerun()
                elif _action_type == "hide_pet":
                    st.session_state["_pending_pet_enabled"] = False
                    st.session_state["_pending_clear_pet_action"] = True
                    st.rerun()
                elif _action_type == "set_size":
                    _new_size = int(_pet_action.get("pet_size", 64))
                    if _new_size in {48, 64, 80}:
                        st.session_state["_pending_pet_size"] = _new_size
                    st.session_state["_pending_clear_pet_action"] = True
                    st.rerun()
        except (json.JSONDecodeError, TypeError):
            pass


