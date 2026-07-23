"""Image processing helpers: data URLs, local OCR, and optional vision hook.

Extracted from main.py to isolate image-based recognition logic from the
Streamlit entrypoint.
"""

from __future__ import annotations

import base64
import mimetypes
import os

import streamlit as st


@st.cache_data(show_spinner=False)
def image_data_url(path: str) -> str:
    """Read a local image file and return a base64 data URL, or '' if missing.

    内嵌为 data URL，避免 Streamlit 静态文件路径限制；文件不存在时安静返回空串。
    """
    if not path or not os.path.exists(path):
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@st.cache_data(show_spinner=False)
def run_local_ocr(path: str) -> dict:
    """Run local OCR when an OCR engine is installed; never calls network services."""
    from utils.runtime_paths import file_sha256, IMAGE_OCR_CACHE_DIR, _read_json_cache, _write_json_cache

    result = {"available": False, "engine": "none", "text": "", "error": ""}
    if not path or not os.path.exists(path):
        result["error"] = "image file missing"
        return result
    try:
        digest = file_sha256(path)
        cache_path = IMAGE_OCR_CACHE_DIR / f"{digest}.json"
        cached = _read_json_cache(cache_path)
        if cached:
            cached["cache_hit"] = True
            return cached
    except Exception:
        digest = ""
        cache_path = None
    try:
        import pytesseract  # type: ignore

        text = pytesseract.image_to_string(path) or ""
        result.update({"available": True, "engine": "pytesseract", "text": text})
        result["cache_hit"] = False
        if cache_path is not None:
            _write_json_cache(cache_path, result)
        return result
    except Exception as exc:
        result["error"] = str(exc)[:220]
        result["cache_hit"] = False
        if cache_path is not None:
            _write_json_cache(cache_path, result)
        return result


def run_optional_vision_model(ref: dict, user_text: str = "") -> dict:
    """Optional advisory hook. Vision output is never authoritative for critical params."""
    if not parse_bool_env("STRUCTPILOT_ENABLE_VISION", False):
        return {"enabled": False, "available": False, "candidates": [], "error": "disabled"}
    return {
        "enabled": True,
        "available": False,
        "candidates": [],
        "error": "vision hook not configured; set up a reviewed local/remote vision adapter before use",
    }
