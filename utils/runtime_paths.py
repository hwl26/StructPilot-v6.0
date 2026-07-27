"""Runtime path constants and shared low-level helpers.

Extracted from main.py to break circular imports: modules under utils/ that
need UPLOAD_DIR / file_sha256 / etc. must import them from here, never from
main.py (which would trigger Streamlit's set_page_config on re-import).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RUNTIME_ROOT = Path(
    os.getenv(
        "STRUCTPILOT_RUNTIME_DIR",
        str(BASE_DIR / "runtime"),
    )
)
os.environ.setdefault("STRUCTPILOT_RUNTIME_DIR", str(RUNTIME_ROOT))


def ensure_runtime_dir(preferred: Path, fallback_name: str) -> Path:
    """Return a writable runtime directory from several locations.

    Tries multiple roots so the app works on Windows, Linux, and read-only
    cloud environments (Streamlit Community Cloud).  Never raises — falls
    back to the system temp dir if every candidate fails.
    """
    roots = [preferred]
    if os.getenv("STRUCTPILOT_RUNTIME_DIR"):
        runtime = Path(os.getenv("STRUCTPILOT_RUNTIME_DIR", ""))
        roots.append(runtime / "memory" / fallback_name)
        roots.append(runtime / fallback_name)
    roots.extend(
        [
            BASE_DIR / "runtime" / "memory" / fallback_name,
            Path.home() / "Documents" / "struct" / "StructPilot_v4_runtime" / "memory" / fallback_name,
            Path(tempfile.gettempdir()) / "StructPilot_v4" / fallback_name,
        ]
    )
    tried = []
    for path in roots:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("", encoding="utf-8")
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
            return path
        except OSError as exc:
            tried.append(f"{path} ({exc})")
    # Last-resort fallback: system temp dir (always writable on all platforms)
    fallback = Path(tempfile.gettempdir()) / "StructPilot_v4" / fallback_name
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# ---------------------------------------------------------------------------
# Runtime directories — resolved at import time but with guaranteed fallback
# so that read-only environments (Streamlit Cloud) never crash on import.
# ---------------------------------------------------------------------------
MEMORY_DIR = ensure_runtime_dir(RUNTIME_ROOT / "memory", "memory")
UPLOAD_DIR = ensure_runtime_dir(RUNTIME_ROOT / "memory" / "uploads", "uploads")
AUDIO_DIR = ensure_runtime_dir(RUNTIME_ROOT / "memory" / "audio", "audio")
CACHE_DIR = ensure_runtime_dir(RUNTIME_ROOT / "cache", "cache")
IMAGE_OCR_CACHE_DIR = ensure_runtime_dir(CACHE_DIR / "image_ocr", "image_ocr")
AUDIO_CACHE_DIR = ensure_runtime_dir(CACHE_DIR / "audio_transcripts", "audio_transcripts")

GUIDE_CARDS_PATH = BASE_DIR / "knowledge_base" / "guides" / "guide_cards.json"
CORRECTIONS_PATH = BASE_DIR / "knowledge_base" / "review" / "user_corrections.jsonl"
INGEST_ASSET_ROOT = BASE_DIR / "assets" / "user_guides"


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json_cache(path: Path) -> dict | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        return None
    return None


def _write_json_cache(path: Path, data: dict) -> None:
    try:
        from utils.atomic_io import atomic_write_json
        atomic_write_json(path, data)
    except Exception:
        pass
