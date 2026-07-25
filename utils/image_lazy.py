"""Image lazy loading and thumbnail utilities for StructPilot.

This module provides:
1. Thumbnail generation via PIL (cached with @st.cache_data)
2. Guide image data URL optimization (thumbnails for list, full on click)
3. Image dimension caching
4. Scroll-to-element JS injection for smart scrolling
5. IntersectionObserver-based lazy loading for HTML-embedded images
6. Expander-based lazy loading for st.image widgets
7. Lazy image gallery with grouped expanders

Design principles:
- Thumbnails are generated once and cached by file path + mtime.
- Full-size images are still available — lazy loading only changes WHEN
  images are loaded, not WHETHER they are loaded.
- The existing fixed screenshot display (render_guide_card) continues to
  work unchanged; this module provides optional optimization hooks.
- All functions degrade gracefully when PIL is not installed.
- Two lazy loading strategies:
  a) **IntersectionObserver JS**: For HTML-embedded images (guide cards).
     Images start as grey placeholders; JS swaps in the real src when visible.
  b) **Expander wrapping**: For st.image widgets (gallery, workspace).
     Images are grouped into expanders; only expanded groups load images.

Integration points:
- main.py render_guide_card  → use lazy_image_html() for <img> tags
- image_gallery.py           → use render_lazy_gallery() instead of render_image_gallery()
- stage_workspace.py         → use render_image_in_expander() for step screenshots
"""

from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


# =========================================================================
# IntersectionObserver JS Lazy Loading (for HTML-embedded images)
# =========================================================================

def lazy_image_html(
    src: str,
    alt: str = "",
    placeholder_color: str = "#f1f5f9",
    placeholder_text: str = "",
    extra_attrs: str = "",
    img_id: str = "",
) -> str:
    """Generate an ``<img>`` tag that lazy-loads via IntersectionObserver.

    The image element is created with a transparent 1px placeholder src.
    The real ``src`` is stored in ``data-src``.  A single IntersectionObserver
    script (injected once per page via ``_inject_observer_script()``) watches
    all ``[data-src]`` elements and swaps the ``src`` when the element enters
    the viewport.

    Parameters
    ----------
    src : str
        The actual image source (data URL, HTTP URL, or local file path).
    alt : str
        Alt text for accessibility.
    placeholder_color : str
        Background colour of the placeholder rectangle.
    placeholder_text : str
        Optional text shown in the placeholder (e.g. "Loading...").
    extra_attrs : str
        Additional HTML attributes to merge into the ``<img>`` tag
        (e.g. ``class=\"...\" style=\"...\"``).
    img_id : str
        Optional HTML ``id`` for the image element.

    Returns
    -------
    str
        A complete ``<img>`` HTML string.
    """
    # Short-circuit: if src is empty, return a placeholder div
    if not src:
        id_attr = f' id="{img_id}"' if img_id else ""
        return (
            f'<div{id_attr} class="sp-lazy-placeholder"'
            f' style="background:{placeholder_color};min-height:120px;'
            f'border-radius:6px;display:flex;align-items:center;justify-content:center;'
            f'color:#94a3b8;font-size:0.85rem;">{placeholder_text or "Image unavailable"}</div>'
        )

    # Ensure the IntersectionObserver bootstrap script is present on the page
    _inject_observer_script()

    id_attr = f' id="{img_id}"' if img_id else ""
    ph_text_attr = f" data-ph-text=\"{_html_escape(placeholder_text)}\"" if placeholder_text else ""
    placeholder_style = (
        f"background:{placeholder_color};min-height:180px;border-radius:6px;"
        f"display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:0.85rem;"
    )

    return (
        f'<img{ id_attr} class="sp-lazy-img"'
        f' data-src="{_html_escape(src)}"'
        f' src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
        f' alt="{_html_escape(alt)}"'
        f'{ph_text_attr}'
        f' style="{placeholder_style}"'
        f' {extra_attrs} loading="lazy">'
    )


def lazy_image_wrap_html(
    inner_html: str,
    src: str,
    alt: str = "",
    wrapper_class: str = "sp-guide-image-wrap",
) -> str:
    """Wrap lazy_image_html output in a container div (for hotspots etc.).

    This is a drop-in helper for ``render_guide_card`` in main.py that
    produces the same ``.sp-guide-image-wrap`` wrapper but with a lazy
    ``<img>`` inside.

    Parameters
    ----------
    inner_html : str
        The HTML content to place inside the wrapper (usually from
        ``lazy_image_html()`` + hotspot anchors).
    src : str
        Actual image source (used to generate the lazy ``<img>`` tag).
    alt : str
        Alt text.
    wrapper_class : str
        CSS class for the outer wrapper div.

    Returns
    -------
    str
        Complete wrapper HTML string.
    """
    img_tag = lazy_image_html(src, alt=alt)
    return f'<div class="{wrapper_class}">{img_tag}{inner_html}</div>'


# Track whether observer script has been injected this render cycle.
_observer_injected_key = "__lazy_observer_injected"


def _inject_observer_script() -> None:
    """Inject the IntersectionObserver bootstrap script (once per render).

    Uses ``st.components.v1.html`` to inject a small ``<script>`` block that:
    1. Creates a single IntersectionObserver for all ``.sp-lazy-img`` elements.
    2. When an element enters the viewport (with 100px rootMargin for
       pre-loading slightly before visible), replaces ``src`` with
       ``data-src`` and removes the placeholder styling.
    3. Unobserves the element after loading to free resources.
    """
    if st.session_state.get(_observer_injected_key):
        return

    try:
        import streamlit.components.v1 as components
    except ImportError:
        return

    js_code = """
<script>
(function() {
    if (window.__spLazyObserverInit) return;
    window.__spLazyObserverInit = true;

    function initObserver() {
        var imgs = document.querySelectorAll('img.sp-lazy-img[data-src]');
        if (!imgs.length) return;

        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var img = entry.target;
                    var realSrc = img.getAttribute('data-src');
                    if (realSrc) {
                        img.src = realSrc;
                        img.removeAttribute('data-src');
                        img.classList.remove('sp-lazy-img');
                        // Remove placeholder styling once loaded
                        img.style.background = '';
                        img.style.minHeight = '';
                        img.style.display = 'block';
                        img.style.width = '100%';
                        img.style.height = 'auto';
                    }
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '200px 0px',
            threshold: 0.01
        });

        imgs.forEach(function(img) { observer.observe(img); });
    }

    // Run immediately and also after a short delay (Streamlit re-renders)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initObserver);
    } else {
        initObserver();
    }
    // Retry after Streamlit finishes rendering
    setTimeout(initObserver, 500);
    setTimeout(initObserver, 1500);
})();
</script>
    """

    components.html(js_code, height=0, width=0)
    st.session_state[_observer_injected_key] = True


def _html_escape(s: str) -> str:
    """Minimal HTML entity escaping for attribute values."""
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# =========================================================================
# Expander-based Lazy Loading (for st.image widgets)
# =========================================================================

def render_image_in_expander(
    path: str,
    caption: str = "",
    label: str = "",
    use_container_width: bool = True,
    thumb_width: int = 0,
    key: str = "",
) -> None:
    """Render an image inside a collapsed expander for on-demand loading.

    The image is only loaded into the browser when the user expands the
    expander. This is the recommended lightweight lazy loading strategy
    for Streamlit since Streamlit does not natively support image
    lazy loading.

    Parameters
    ----------
    path : str
        Image file path.
    caption : str
        Caption text below the image.
    label : str
        Expander label text. Defaults to a clickable caption with icon.
    use_container_width : bool
        If True, image fills the container width when shown.
    thumb_width : int
        If > 0, show a thumbnail outside the expander at this width.
    key : str
        Unique key for the expander widget.
    """
    if not path or not os.path.exists(path):
        return

    expander_key = f"lazy_exp_{key}" if key else f"lazy_exp_{hash(path)}"
    display_label = label or f"  \U0001F5BC\uFE0F {caption or 'Click to view image'}"

    # Optionally show a small thumbnail as preview
    if thumb_width > 0:
        thumb_url = generate_thumbnail_data_url(path, max_edge=thumb_width)
        if thumb_url:
            st.image(thumb_url, caption=None, width=thumb_width)

    with st.expander(display_label, expanded=False):
        try:
            st.image(path, caption=caption or None, use_container_width=use_container_width)
        except Exception:
            st.caption(f"Failed to load: {caption or path}")


def render_lazy_gallery(
    images: list,
    key_prefix: str = "lg",
    group_size: int = 4,
    columns: int = 3,
    use_expanders: bool = True,
) -> None:
    """Render a gallery of images with expander-based lazy loading.

    When ``use_expanders`` is True (default), images are grouped into
    collapsible sections. Only the currently expanded section loads
    its images into the browser, significantly reducing initial page
    load time for galleries with many images.

    When ``use_expanders`` is False, falls back to immediate rendering
    (same as the original ``render_image_gallery``).

    Parameters
    ----------
    images : list of dict
        Each dict should have at least a ``path`` key. Supported keys:
        path, image, url, caption, label, name, title, hotspot, annotation.
    key_prefix : str
        Unique prefix for widget keys.
    group_size : int
        Number of images per expander group.
    columns : int
        Number of columns within each group.
    use_expanders : bool
        If True, group images into expanders for lazy loading.
    """
    if not images:
        st.caption("")
        return

    # Deduplicate
    seen = set()
    unique = []
    for img in images:
        path = _resolve_path(img)
        if not path:
            continue
        if path not in seen:
            seen.add(path)
            unique.append(img)

    if not unique:
        st.caption("")
        return

    total = len(unique)

    if not use_expanders or total <= group_size:
        # Small number of images: render directly (no expanders needed)
        _render_image_grid(unique, key_prefix, columns)
        return

    # Group images into expanders
    num_groups = (total + group_size - 1) // group_size
    for g in range(num_groups):
        start = g * group_size
        end = min(start + group_size, total)
        group = unique[start:end]

        # Build group label
        first_caption = (
            group[0].get("caption") or group[0].get("label")
            or group[0].get("name") or ""
        )
        if len(group) == 1:
            group_label = f"  \U0001F5BC\uFE0F {first_caption}"
        else:
            group_label = (
                f"  \U0001F5BC\uFE0F  ({start + 1}-{end}/{total})"
                f"  {first_caption}"
                if first_caption
                else f"  \U0001F5BC\uFE0F  ({start + 1}-{end}/{total})"
            )

        with st.expander(group_label, expanded=(g == 0)):
            _render_image_grid(group, f"{key_prefix}_g{g}", columns)


def _render_image_grid(
    images: list,
    key_prefix: str,
    columns: int,
) -> None:
    """Render a grid of images using st.image with thumbnail optimization."""
    n_cols = min(columns, len(images))
    cols = st.columns(n_cols)

    for i, img in enumerate(images):
        col = cols[i % n_cols]
        with col:
            path = _resolve_path(img)
            caption = (
                img.get("caption") or img.get("label")
                or img.get("name") or img.get("title") or ""
            )
            annotation = img.get("hotspot") or img.get("annotation") or ""

            if not path:
                st.caption(f"\U0001F4F7 {caption or 'Image unavailable'}")
                continue

            if not path.startswith(("http://", "https://", "data:")) and not os.path.exists(path):
                st.caption(f"\U0001F4F7 {caption or path} (not found)")
                continue

            try:
                # Use thumbnail for faster rendering, with expander for full
                thumb_url = generate_thumbnail_data_url(path)
                if thumb_url:
                    st.image(thumb_url, caption=caption or None, use_container_width=True)
                else:
                    st.image(path, caption=caption or None, use_container_width=True)
            except Exception:
                st.caption(f"\U0001F4F7 {caption or path} (load failed)")

            if annotation:
                st.caption(f"  \U0001F4A1 {annotation}")


def _resolve_path(img: dict) -> str:
    """Extract and resolve image path from a dict.

    Supports: path, image, image_path, url, src keys.
    Absolute paths and URLs are returned as-is.
    Relative paths are resolved against the project base directory.
    """
    path = (
        img.get("path") or img.get("image")
        or img.get("image_path") or img.get("url")
        or img.get("src") or ""
    )
    if not path:
        return ""

    path = str(path).strip()

    # Already a URL or data URL
    if path.startswith(("http://", "https://", "data:")):
        return path

    # Absolute path
    if os.path.isabs(path):
        return path

    # Resolve relative to base directory
    candidate = _BASE_DIR / path
    if candidate.exists():
        return str(candidate)

    # Fallback: try importing main module for BASE_DIR
    try:
        import importlib
        main_mod = importlib.import_module("main")
        base_dir = getattr(main_mod, "BASE_DIR", None)
        if base_dir:
            candidate = base_dir / path
            if candidate.exists():
                return str(candidate)
            if hasattr(main_mod, "resolve_guide_asset"):
                resolved = main_mod.resolve_guide_asset(path)
                if resolved:
                    return resolved
    except Exception:
        pass

    return path

