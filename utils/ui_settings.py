"""UI settings persistence.

Stores lightweight UI preferences (theme, mascot, history display count) in a
local JSON file so they survive page refresh and restart.

Automatically probes writable directories to handle sandboxed environments
(e.g. TRAE) where the project directory may be read-only.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dir_is_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except Exception:
        return False


def _resolve_settings_path() -> str:
    """Return the first writable settings path from a prioritized candidate list."""
    filename = "ui_settings.json"

    candidates = []

    env_path = os.getenv("STRUCTPILOT_UI_CONFIG_PATH")
    if env_path:
        candidates.append(env_path)

    runtime_dir = os.getenv(
        "STRUCTPILOT_RUNTIME_DIR",
        os.path.join(os.path.expanduser("~"), "Documents", "struct", "StructPilot_v2_runtime"),
    )
    candidates.append(os.path.join(runtime_dir, "config", filename))

    candidates.append(os.path.join(_BASE_DIR, "config", filename))

    try:
        workspace_root = os.path.dirname(os.path.dirname(_BASE_DIR))
        candidates.append(os.path.join(workspace_root, "trae_more", "runtime", "config", filename))
    except Exception:
        pass

    candidates.append(os.path.join(tempfile.gettempdir(), f"structpilot_{filename}"))

    for path in candidates:
        parent = os.path.dirname(path) or "."
        if path and _dir_is_writable(parent):
            return path

    return os.path.join(_BASE_DIR, "config", filename)


_SETTINGS_PATH = _resolve_settings_path()

DEFAULTS: Dict[str, Any] = {
    "ui_theme": "静谧蓝",
    "mascot_url": "",
    "history_limit": 8,
    "bg_image": "",
    "bg_opacity": 0.12,
    "pet_enabled": True,
    "pet_type": "penguin",
    "pet_size": 64,
}


def load_ui_settings() -> Dict[str, Any]:
    """Load UI settings, falling back to defaults for missing keys."""
    settings = dict(DEFAULTS)
    if not os.path.exists(_SETTINGS_PATH):
        return settings
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in DEFAULTS:
                if key in data:
                    settings[key] = data[key]
    except Exception:
        pass
    return settings


def save_ui_settings(**kwargs: Any) -> Dict[str, Any]:
    """Merge given keys into the stored settings and persist them."""
    settings = load_ui_settings()
    for key, value in kwargs.items():
        if key in DEFAULTS:
            settings[key] = value
    parent = os.path.dirname(_SETTINGS_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    return settings
