"""Thread-safe, crash-resistant JSON persistence for local Streamlit runtime data."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Callable

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def path_lock(path: str | Path) -> threading.RLock:
    key = str(Path(path).resolve())
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


def atomic_write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=indent)
    with path_lock(target):
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def atomic_update_json(
    path: str | Path,
    default: Any,
    mutator: Callable[[Any], Any | None],
) -> Any:
    """Read-modify-replace one JSON file while holding its process-wide lock."""
    target = Path(path)
    with path_lock(target):
        try:
            data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else default
        except Exception:
            data = default
        replacement = mutator(data)
        if replacement is not None:
            data = replacement
        atomic_write_json(target, data)
        return data
