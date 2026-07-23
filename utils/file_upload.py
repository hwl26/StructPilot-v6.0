"""File upload security configuration and persistence helpers.

Extracted from main.py to isolate upload validation, path-safe naming, and
on-disk persistence logic from the Streamlit entrypoint.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path

import streamlit as st

# ============= File Upload Security Configuration =============
# 允许的图片 MIME 类型
ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

# 最大文件大小：10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
}
MAX_AUDIO_SIZE = 25 * 1024 * 1024


def get_image_metadata(path: str) -> dict:
    """Return safe local image facts for prompts and audit logs."""
    meta = {"width": None, "height": None, "mode": "", "format": ""}
    if not path or not os.path.exists(path):
        return meta
    try:
        from PIL import Image

        with Image.open(path) as im:
            meta.update({
                "width": int(im.width),
                "height": int(im.height),
                "mode": str(im.mode or ""),
                "format": str(im.format or ""),
            })
    except Exception:
        pass
    return meta


def save_uploaded_images(files) -> list:
    """Persist uploaded files to disk and return image reference dicts.

    Validates file type, size, and extension for security.
    """
    from utils.runtime_paths import UPLOAD_DIR, file_sha256

    refs = []
    for f in files or []:
        # Validate file size
        file_size = len(f.getbuffer())
        if file_size > MAX_FILE_SIZE:
            st.warning(f"文件 {f.name} 超过最大限制 {MAX_FILE_SIZE // (1024*1024)}MB，已跳过")
            continue

        # Validate file extension
        file_ext = Path(f.name).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            st.warning(f"文件 {f.name} 类型不支持（仅支持图片格式），已跳过")
            continue

        # Validate MIME type
        mime_type = getattr(f, "type", "")
        if mime_type and mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            st.warning(f"文件 {f.name} MIME 类型 {mime_type} 不支持，已跳过")
            continue

        # Secure filename - use timestamp + hash to prevent path traversal
        safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{hashlib.sha256(f.name.encode()).hexdigest()[:8]}{file_ext}"
        out = UPLOAD_DIR / safe_name
        out.write_bytes(f.getbuffer())
        image_meta = get_image_metadata(str(out))
        refs.append({
            "image_name": f.name,
            "image_path": str(out),
            "mime_type": mime_type,
            "sha256": file_sha256(str(out)),
            "source_type": "upload",
            "created_at": datetime.now().isoformat(),
            "width": image_meta.get("width"),
            "height": image_meta.get("height"),
            "image_format": image_meta.get("format"),
            "mode": image_meta.get("mode"),
        })
    return refs


def save_pasted_image(pil_image) -> dict:
    """Persist a PIL image from clipboard paste and return an image reference dict."""
    from utils.runtime_paths import UPLOAD_DIR, file_sha256

    name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    out = UPLOAD_DIR / name
    pil_image.save(str(out), format="PNG")
    image_meta = get_image_metadata(str(out))
    return {
        "image_name": name,
        "image_path": str(out),
        "mime_type": "image/png",
        "sha256": file_sha256(str(out)),
        "source_type": "paste",
        "created_at": datetime.now().isoformat(),
        "width": image_meta.get("width"),
        "height": image_meta.get("height"),
        "image_format": image_meta.get("format"),
        "mode": image_meta.get("mode"),
    }


def save_uploaded_audio(file) -> str:
    """Persist one uploaded audio file after size/type checks and return its path."""
    from utils.runtime_paths import AUDIO_DIR

    if file is None:
        return ""
    file_size = len(file.getbuffer())
    if file_size > MAX_AUDIO_SIZE:
        raise ValueError(f"音频超过最大限制 {MAX_AUDIO_SIZE // (1024 * 1024)}MB")
    file_ext = Path(file.name).suffix.lower()
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("音频格式不支持")
    mime_type = getattr(file, "type", "")
    if mime_type and mime_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise ValueError(f"音频 MIME 类型 {mime_type} 不支持")
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{hashlib.sha256(file.name.encode()).hexdigest()[:8]}{file_ext}"
    out = AUDIO_DIR / safe_name
    out.write_bytes(file.getbuffer())
    return str(out)
