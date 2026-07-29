"""Load and merge the repository-backed public community seed."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parent.parent
COMMUNITY_SEED_PATH = BASE_DIR / "config" / "community_seed.json"

_EMPTY_SEED: dict[str, Any] = {
    "stats": {"registered_users": 0},
    "members": [],
    "forum": {"posts": [], "answers": [], "comments": [], "votes": []},
    "lab_board": [],
}


def load_community_seed() -> dict[str, Any]:
    """Return a validated public seed without raising on deployment startup."""
    try:
        payload = json.loads(COMMUNITY_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return deepcopy(_EMPTY_SEED)
    if not isinstance(payload, dict):
        return deepcopy(_EMPTY_SEED)

    seed = deepcopy(_EMPTY_SEED)
    stats = payload.get("stats")
    members = payload.get("members")
    forum = payload.get("forum")
    lab_board = payload.get("lab_board")
    if isinstance(stats, dict):
        seed["stats"].update(stats)
    if isinstance(members, list):
        seed["members"] = [item for item in members if isinstance(item, dict)]
    if isinstance(forum, dict):
        for key in seed["forum"]:
            records = forum.get(key)
            if isinstance(records, list):
                seed["forum"][key] = [item for item in records if isinstance(item, dict)]
    if isinstance(lab_board, list):
        seed["lab_board"] = [item for item in lab_board if isinstance(item, dict)]
    return seed


def _merge_records(
    current: Any,
    seeded: Any,
    identity: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    current_records = [item for item in current if isinstance(item, dict)] if isinstance(current, list) else []
    seeded_records = [item for item in seeded if isinstance(item, dict)] if isinstance(seeded, list) else []
    merged = deepcopy(current_records)
    seen = {identity(item) for item in current_records}
    for item in seeded_records:
        record_id = identity(item)
        if record_id not in seen:
            merged.append(deepcopy(item))
            seen.add(record_id)
    return merged


def merge_forum_seed(current: Any) -> dict[str, list[dict[str, Any]]]:
    """Add missing seeded forum records while preserving cloud-created data."""
    current_data = current if isinstance(current, dict) else {}
    seeded = load_community_seed()["forum"]
    return {
        "posts": _merge_records(current_data.get("posts"), seeded.get("posts"), lambda item: item.get("id")),
        "answers": _merge_records(current_data.get("answers"), seeded.get("answers"), lambda item: item.get("id")),
        "comments": _merge_records(current_data.get("comments"), seeded.get("comments"), lambda item: item.get("id")),
        "votes": _merge_records(
            current_data.get("votes"),
            seeded.get("votes"),
            lambda item: (item.get("user"), item.get("target_id"), item.get("target_type")),
        ),
    }


def merge_lab_board_seed(current: Any) -> list[dict[str, Any]]:
    """Add missing seeded board posts while preserving cloud-created posts."""
    return _merge_records(current, load_community_seed()["lab_board"], lambda item: item.get("id"))


def get_public_members() -> list[dict[str, Any]]:
    return deepcopy(load_community_seed()["members"])


def get_registered_user_count() -> int:
    value = load_community_seed()["stats"].get("registered_users", 0)
    return value if isinstance(value, int) and value >= 0 else 0
