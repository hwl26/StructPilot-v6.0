import json
from pathlib import Path

from components import lab_board
from utils import forum_data
from utils.community_seed import (
    COMMUNITY_SEED_PATH,
    get_public_members,
    get_registered_user_count,
    load_community_seed,
)


def test_public_seed_contains_synced_community_without_private_credentials():
    raw = COMMUNITY_SEED_PATH.read_text(encoding="utf-8")
    lowered = raw.lower()
    assert '"email"' not in lowered
    assert "password_hash" not in lowered
    assert '"password"' not in lowered

    seed = load_community_seed()
    assert get_registered_user_count() == 6
    assert len(get_public_members()) == 5
    assert len(seed["forum"]["posts"]) == 20
    assert len(seed["forum"]["answers"]) == 26
    assert len(seed["forum"]["comments"]) == 18
    assert seed["forum"]["votes"] == []
    assert len(seed["lab_board"]) == 3


def test_forum_seed_merges_with_cloud_created_records(monkeypatch, tmp_path: Path):
    forum_path = tmp_path / "forum" / "forum_posts.json"
    monkeypatch.setattr(forum_data, "FORUM_DIR", forum_path.parent)
    monkeypatch.setattr(forum_data, "FORUM_DATA_PATH", forum_path)

    seeded = forum_data.load_forum_data()
    assert len(seeded["posts"]) == 20

    custom = {
        "id": "cloud-only-post",
        "title": "Cloud post",
        "created_at": "2026-07-29T00:00:00",
    }
    forum_path.parent.mkdir(parents=True, exist_ok=True)
    forum_path.write_text(
        json.dumps({"posts": [custom], "answers": [], "comments": [], "votes": []}),
        encoding="utf-8",
    )

    merged = forum_data.load_forum_data()
    assert len(merged["posts"]) == 21
    assert merged["posts"][0]["id"] == "cloud-only-post"


def test_board_seed_merges_with_cloud_created_records(monkeypatch, tmp_path: Path):
    board_path = tmp_path / "lab_board" / "posts.json"
    monkeypatch.setattr(lab_board, "_POSTS_PATH", board_path)

    seeded = lab_board.load_posts()
    assert len(seeded) == 3

    board_path.parent.mkdir(parents=True)
    board_path.write_text(
        json.dumps([{"id": "cloud-board", "timestamp": "2026-07-29T00:00:00"}]),
        encoding="utf-8",
    )
    merged = lab_board.load_posts()
    assert len(merged) == 4
    assert merged[0]["id"] == "cloud-board"
