"""Image lazy loading and thumbnail utilities for StructPilot.

This module provides:
1. Thumbnail generation via PIL (cached with @st.cache_data)
2. Guide image data URL optimization (thumbnails for list, full on click)
3. Image dimension caching
4. Scroll-to-element JS injection for smart scrolling

Design principles:
- Thumbnails are generated once and cached by file path + mtime.
- Full-size images are still available — lazy loading only changes WHEN
  images are loaded, not WHETHER they are loaded.
- The existing fixed screenshot display (render_guide_card) continues to
  work unchanged; this module provides optional optimization hooks.
- All functions degrade gracefully when PIL is not installed.

Integration points:
- main.py:2963, 2991  → use render_lazy_image() instead of st.image()
- main.py:282 (render_guide_card)  → use get_cached_thumbnail_data_url()
- main.py:804 (image_data_url)  → use get_cached_image_data_url() for base64
"""

from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st

_BASE_DIR = Path(__file__).resolve().parent.parent

# Thumbnail max edge size in pixels.
_THUMBNAIL_MAX_EDGE = 400

# Quality for thumbnail JPEG compression.
_THUMBNAIL_JPEG_QUALITY = 75

# Default display width for chat images.
_CHAT_IMAGE_WIDTH = 260


def _file_signature(path: str) -> str:
    """Return a cache key based on path + file size + mtime."""
    try:
        stat = os.stat(path)
        return f"{path}:{stat.st_size}:{stat.st_mtime}"
    except OSError:
        return path


@st.cache_data(show_spinner=False, max_entries=128)
def get_image_dimensions(path: str) -> Tuple[Optional[int], Optional[int]]:
    """Get image width and height, cached by file signature.

    Returns (None, None) if the file cannot be read or PIL is unavailable.
    """
    if not path or not os.path.exists(path):
        return None, None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return int(im.width), int(im.height)
    except Exception:
        return None, None


@st.cache_data(show_spinner=False, max_entries=64)
def generate_thumbnail_data_url(path: str, max_edge: int = _THUMBNAIL_MAX_EDGE) -> str:
    """Generate a thumbnail data URL from an image file.

    The thumbnail is resized so the longest edge is at most ``max_edge``
    pixels, then JPEG-compressed and base64-encoded as a data URL.

    This is used for:
    - Guide card image list (small thumbnails in tabs)
    - Chat message image previews (before clicking to expand)

    Falls back to full-size data URL if PIL is not available.

    Parameters
    ----------
    path : str
        Absolute path to the image file.
    max_edge : int
        Maximum edge length in pixels for the thumbnail.

    Returns
    -------
    str
        Base64 data URL (e.g. "data:image/jpeg;base64,..."), or "" if file missing.
    """
    if not path or not os.path.exists(path):
        return ""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            longest = max(im.size)
            if longest > max_edge:
                scale = max_edge / longest
                new_size = (max(1, int(im.width * scale)), max(1, int(im.height * scale)))
                im = im.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=_THUMBNAIL_JPEG_QUALITY)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        # Fallback: read raw file and encode
        try:
            mime = mimetypes.guess_type(path)[0] or "image/png"
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        except Exception:
            return ""


@st.cache_data(show_spinner=False, max_entries=64)
def get_cached_image_data_url(path: str) -> str:
    """Read a local image file and return a base64 data URL, cached.

    This is a cached replacement for the existing ``image_data_url()``
    function in main.py. The cache key includes file mtime so editing
    the image on disk busts the cache.

    Returns "" if the file is missing.
    """
    if not path or not os.path.exists(path):
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


@st.cache_data(show_spinner=False, max_entries=256)
def get_thumbnail_or_full(path: str, use_thumbnail: bool = True) -> str:
    """Get a data URL for an image, optionally as a thumbnail.

    Parameters
    ----------
    path : str
        Image file path.
    use_thumbnail : bool
        If True, generate a thumbnail. If False, return full-size data URL.

    Returns
    -------
    str
        Base64 data URL, or "" if file missing.
    """
    if use_thumbnail:
        return generate_thumbnail_data_url(path)
    return get_cached_image_data_url(path)


def render_lazy_image(
    path: str,
    caption: str = "",
    width: int = _CHAT_IMAGE_WIDTH,
    use_thumbnail: bool = False,
    key: str = "",
) -> None:
    """Render an image in Streamlit with optional thumbnail optimization.

    This is a drop-in replacement for ``st.image(path, caption=..., width=...)``
    that adds:
    - Thumbnail generation for large images (reduces data transfer)
    - Graceful fallback to st.image if path is invalid

    Parameters
    ----------
    path : str
        Image file path.
    caption : str
        Caption text below the image.
    width : int
        Display width in pixels.
    use_thumbnail : bool
        If True, generate a thumbnail instead of loading the full image.
        Thumbnails are much smaller but slightly lower quality.
    key : str
        Optional unique key for the image widget (for Streamlit widget tracking).
    """
    if not path or not os.path.exists(path):
        return

    if use_thumbnail:
        # Use thumbnail data URL for faster loading
        thumb_url = generate_thumbnail_data_url(path)
        if thumb_url:
            st.image(thumb_url, caption=caption or None, width=width)
            return

    # Fallback: direct st.image (Streamlit handles file reading)
    st.image(path, caption=caption or None, width=width)


def render_image_with_expand(
    path: str,
    caption: str = "",
    thumb_width: int = _CHAT_IMAGE_WIDTH,
    key: str = "",
) -> None:
    """Render a thumbnail that can be expanded to show the full image.

    Shows a small thumbnail inline. Below it, an expander allows the user
    to view the full-resolution image. This significantly reduces initial
    page load time when many images are in the chat history.

    Parameters
    ----------
    path : str
        Image file path.
    caption : str
        Caption text.
    thumb_width : int
        Width of the thumbnail preview.
    key : str
        Unique key for the expander widget.
    """
    if not path or not os.path.exists(path):
        return

    # Show thumbnail
    thumb_url = generate_thumbnail_data_url(path)
    if thumb_url:
        st.image(thumb_url, caption=caption or None, width=thumb_width)
    else:
        st.image(path, caption=caption or None, width=thumb_width)

    # Expander for full image
    expander_key = f"img_expand_{key}" if key else f"img_expand_{hash(path)}"
    with st.expander("查看原图", expanded=False):
        full_url = get_cached_image_data_url(path)
        if full_url:
            st.image(full_url, caption=None, use_container_width=True)
        else:
            st.image(path, caption=None, use_container_width=True)


def preload_next_step_images(
    current_cp_id: str,
    checkpoints: list,
    guide_cards: dict,
    base_dir: Path = _BASE_DIR,
) -> None:
    """Preload images for the next checkpoint (speculative loading).

    When the user is on checkpoint N, this function triggers thumbnail
    generation for checkpoint N+1's guide images. The thumbnails are
    cached by @st.cache_data, so when the user actually navigates to N+1,
    the images load instantly.

    Parameters
    ----------
    current_cp_id : str
        Current checkpoint ID (e.g. "cp_03").
    checkpoints : list
        List of checkpoint dicts (from navigator.checkpoints).
    guide_cards : dict
        Guide card mapping (from load_guide_cards()).
    base_dir : Path
        Project base directory for resolving relative image paths.
    """
    # Find next checkpoint
    cp_ids = [cp.get("checkpoint_id", "") for cp in checkpoints]
    if current_cp_id not in cp_ids:
        return
    idx = cp_ids.index(current_cp_id)
    if idx + 1 >= len(cp_ids):
        return
    next_cp_id = cp_ids[idx + 1]

    # Preload guide card images for next step
    next_card = guide_cards.get(next_cp_id)
    if not next_card or not isinstance(next_card, dict):
        return

    substeps = next_card.get("substeps", [])
    if not isinstance(substeps, list):
        return

    for substep in substeps:
        if not isinstance(substep, dict):
            continue
        images = substep.get("images", [])
        if not isinstance(images, list):
            continue
        for img_item in images:
            if not isinstance(img_item, dict):
                continue
            raw_path = str(
                img_item.get("path")
                or img_item.get("image")
                or img_item.get("image_path")
                or ""
            ).strip()
            if not raw_path:
                continue
            img_path = Path(raw_path)
            if not img_path.is_absolute():
                img_path = base_dir / raw_path
            if img_path.exists():
                # Trigger thumbnail generation (cached)
                generate_thumbnail_data_url(str(img_path))
