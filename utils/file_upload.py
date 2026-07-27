"""File upload security configuration and persistence helpers.

Extracted from main.py to isolate upload validation, path-safe naming, and
on-disk persistence logic from the Streamlit entrypoint.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import io
import os
from pathlib import Path
import tempfile
import warnings

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
MAX_IMAGES_PER_REQUEST = 8
MAX_IMAGE_PIXELS = 40_000_000

_FORMAT_EXTENSIONS = {
    "PNG": {".png"},
    "JPEG": {".jpg", ".jpeg"},
    "GIF": {".gif"},
    "WEBP": {".webp"},
    "BMP": {".bmp"},
    "TIFF": {".tif", ".tiff"},
}


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def validate_image_bytes(data: bytes, file_ext: str) -> dict:
    """Validate actual image structure/format before any bytes reach disk."""
    from PIL import Image, UnidentifiedImageError

    if not data:
        raise ValueError("图片内容为空")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                width, height = int(image.width), int(image.height)
                image_format = str(image.format or "").upper()
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError(f"图片像素数超过限制（最多 {MAX_IMAGE_PIXELS:,} 像素）")
                allowed_exts = _FORMAT_EXTENSIONS.get(image_format)
                if not allowed_exts or file_ext not in allowed_exts:
                    raise ValueError("图片扩展名与实际格式不一致")
                image.verify()
        return {"width": width, "height": height, "format": image_format}
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("文件不是有效或安全的图片") from exc


def _valid_audio_signature(data: bytes, file_ext: str) -> bool:
    head = data[:16]
    if file_ext in {".mp3", ".mpeg", ".mpga"}:
        return head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    if file_ext == ".wav":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if file_ext in {".m4a", ".mp4"}:
        return len(head) >= 12 and head[4:8] == b"ftyp"
    if file_ext == ".webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if file_ext == ".ogg":
        return head.startswith(b"OggS")
    return False


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
    selected = list(files or [])
    if len(selected) > MAX_IMAGES_PER_REQUEST:
        st.warning(f"单次最多上传 {MAX_IMAGES_PER_REQUEST} 张图片，其余文件已跳过")
        selected = selected[:MAX_IMAGES_PER_REQUEST]
    for f in selected:
        raw = bytes(f.getbuffer())
        # Validate file size
        file_size = len(raw)
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

        try:
            verified = validate_image_bytes(raw, file_ext)
        except ValueError as exc:
            st.warning(f"文件 {f.name} 未通过内容校验：{exc}，已跳过")
            continue

        # Secure filename - use timestamp + hash to prevent path traversal
        safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{hashlib.sha256(f.name.encode()).hexdigest()[:8]}{file_ext}"
        out = UPLOAD_DIR / safe_name
        _atomic_write_bytes(out, raw)
        image_meta = {
            "width": verified["width"],
            "height": verified["height"],
            "format": verified["format"],
            "mode": "",
        }
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

    width, height = int(pil_image.width), int(pil_image.height)
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"粘贴图片像素数超过限制（最多 {MAX_IMAGE_PIXELS:,} 像素）")
    name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    out = UPLOAD_DIR / name
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    _atomic_write_bytes(out, buffer.getvalue())
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
    raw = bytes(file.getbuffer())
    file_size = len(raw)
    if file_size > MAX_AUDIO_SIZE:
        raise ValueError(f"音频超过最大限制 {MAX_AUDIO_SIZE // (1024 * 1024)}MB")
    file_ext = Path(file.name).suffix.lower()
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("音频格式不支持")
    mime_type = getattr(file, "type", "")
    if mime_type and mime_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise ValueError(f"音频 MIME 类型 {mime_type} 不支持")
    if not _valid_audio_signature(raw, file_ext):
        raise ValueError("音频文件头与扩展名不匹配或文件已损坏")
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{hashlib.sha256(file.name.encode()).hexdigest()[:8]}{file_ext}"
    out = AUDIO_DIR / safe_name
    _atomic_write_bytes(out, raw)
    return str(out)
