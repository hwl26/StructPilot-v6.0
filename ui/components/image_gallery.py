"""Image gallery component for StructPilot.

Renders a thumbnail grid of reference screenshots with click-to-expand.
Supports lazy loading via Streamlit's native image rendering.

Images can come from:
  - Local file paths (resolved via resolve_guide_asset)
  - Data URLs (base64-encoded)
  - Remote URLs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# Performance: lazy import image utilities
try:
    from utils.image_lazy import render_lazy_image, generate_thumbnail_data_url
    _HAS_LAZY = True
except ImportError:
    _HAS_LAZY = False


def render_image_gallery(
    images: List[Dict[str, Any]],
    key_prefix: str = "ig",
    columns: int = 3,
    thumbnail_width: Optional[int] = None,
) -> None:
    """Render a grid of image thumbnails.

    Parameters
    ----------
    images : list of dict
        Each dict should have:
          - path / image / url: image source
          - caption / label / name: display caption
          - hotspot / annotation: optional annotation text
    key_prefix : str
        Unique prefix for widget keys.
    columns : int
        Number of columns in the thumbnail grid.
    thumbnail_width : int, optional
        Width in pixels for thumbnails. If None, uses container width.
    """
    if not images:
        st.caption("暂无截图。")
        return

    # Deduplicate by resolved path; skip entries whose paths cannot be resolved
    seen_paths = set()
    unique_images = []
    for img in images:
        path = _resolve_image_path(img)
        if not path:
            continue  # Skip unresolvable images silently
        if path not in seen_paths:
            seen_paths.add(path)
            unique_images.append(img)

    if not unique_images:
        st.caption("暂无截图。")
        return

    # Render thumbnail grid
    n_cols = min(columns, len(unique_images))
    cols = st.columns(n_cols)

    for i, img in enumerate(unique_images):
        col = cols[i % n_cols]
        with col:
            _render_thumbnail(img, f"{key_prefix}_{i}", thumbnail_width)


def _render_thumbnail(
    img: Dict[str, Any],
    key: str,
    thumbnail_width: Optional[int],
) -> None:
    """Render a single thumbnail with expand-on-click."""
    path = _resolve_image_path(img)
    caption = (
        img.get("caption")
        or img.get("label")
        or img.get("name")
        or img.get("title")
        or ""
    )
    annotation = img.get("hotspot") or img.get("annotation") or ""

    if not path:
        st.caption(f"📷 {caption or '图片不可用'}")
        return

    # Check file exists for local paths
    if not path.startswith(("http://", "https://", "data:")) and not os.path.exists(path):
        st.caption(f"📷 {caption or path}（文件未找到）")
        return

    try:
        if thumbnail_width:
            st.image(path, caption=caption, width=thumbnail_width)
        else:
            st.image(path, caption=caption, use_container_width=True)
    except Exception:
        st.caption(f"📷 {caption or path}（加载失败）")
        return

    # Show annotation if present
    if annotation:
        st.caption(f"💡 {annotation}")


def _resolve_image_path(img: Dict[str, Any]) -> str:
    """Extract and resolve image path from various dict formats.

    Resolution strategy (ordered by reliability):
      1. Direct BASE_DIR from main module (preferred)
      2. Path relative to this file's parent chain (fallback)
      3. resolve_guide_asset from main module
      4. Raw path as-is (last resort)
    """
    path = (
        img.get("path")
        or img.get("image")
        or img.get("image_path")
        or img.get("url")
        or img.get("src")
        or ""
    )
    if not path:
        return ""

    path = str(path).strip()

    # Already a URL or data URL
    if path.startswith(("http://", "https://", "data:")):
        return path

    # Absolute path — return as-is (caller checks os.path.exists)
    if os.path.isabs(path):
        return path

    # --- Strategy 1: import main module for BASE_DIR ---
    resolved = None
    try:
        import importlib
        main_mod = importlib.import_module("main")
        base_dir = getattr(main_mod, "BASE_DIR", None)
        if base_dir:
            candidate = base_dir / path
            if candidate.exists():
                resolved = str(candidate)

        # Try resolve_guide_asset as secondary check
        if not resolved and hasattr(main_mod, "resolve_guide_asset"):
            resolved = main_mod.resolve_guide_asset(path)
    except Exception:
        pass

    # --- Strategy 2: Resolve relative to this component file (import-free fallback) ---
    if not resolved:
        try:
            _component_dir = Path(__file__).resolve().parent.parent.parent  # ui/components → project root
            candidate = _component_dir / path
            if candidate.exists():
                resolved = str(candidate)
        except Exception:
            pass

    return resolved if resolved else path


def render_image_lightbox(
    images: List[Dict[str, Any]],
    key_prefix: str = "lb",
) -> None:
    """Render images in a lightbox-style expandable layout.

    Shows thumbnails; clicking opens the full image in an expander below.
    """
    if not images:
        st.caption("暂无截图。")
        return

    # Show thumbnail row
    thumb_cols = st.columns(min(len(images), 5))
    selected_idx = None

    for i, img in enumerate(images):
        col = thumb_cols[i % len(thumb_cols)]
        with col:
            path = _resolve_image_path(img)
            caption = img.get("caption") or img.get("label") or f"图 {i+1}"
            if path and os.path.exists(path):
                if st.button(f"🔍 {caption}", key=f"{key_prefix}_btn_{i}", use_container_width=True):
                    selected_idx = i
            else:
                st.caption(f"📷 {caption}")

    # Show selected image in full
    if selected_idx is not None:
        img = images[selected_idx]
        path = _resolve_image_path(img)
        caption = img.get("caption") or img.get("label") or ""
        if path:
            try:
                # Performance: use cached full-size data URL for lightbox
                if _HAS_LAZY:
                    from utils.image_lazy import get_cached_image_data_url
                    full_url = get_cached_image_data_url(path)
                    if full_url:
                        st.image(full_url, caption=caption, use_container_width=True)
                    else:
                        st.image(path, caption=caption, use_container_width=True)
                else:
                    st.image(path, caption=caption, use_container_width=True)
            except Exception:
                st.caption(f"无法加载: {caption}")
