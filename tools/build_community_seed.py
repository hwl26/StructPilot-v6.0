"""Build the public community seed from local ignored runtime data.

The output intentionally excludes email addresses, password hashes, and
per-user vote history. Run this script before publishing updated demo data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
IMPORT_PATH = BASE_DIR / "forum_import_data.json"
USERS_PATH = BASE_DIR / "runtime" / "config" / "users.json"
BOARD_PATH = BASE_DIR / "runtime" / "lab_board" / "posts.json"
OUTPUT_PATH = BASE_DIR / "config" / "community_seed.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_forum(imported: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    answers_raw = imported.get("answers", [])
    answer_counts: dict[str, int] = {}
    accepted_ids: dict[str, str] = {}
    for answer in answers_raw:
        post_id = answer["post_id"]
        answer_counts[post_id] = answer_counts.get(post_id, 0) + 1
        if answer.get("accepted"):
            accepted_ids[post_id] = answer["id"]

    posts = []
    for post in imported.get("posts", []):
        answer_count = answer_counts.get(post["id"], 0)
        posts.append({
            "id": post["id"],
            "type": post["type"],
            "author": post["author"],
            "author_display": post["display"],
            "author_lab": "",
            "anonymous": False,
            "created_at": post["date"],
            "title": post["title"],
            "content": post["content"],
            "tags": post["tags"],
            "software": post["software"],
            "step": post["step"],
            "upvotes": post["upvotes"],
            "views": post["views"],
            "answers_count": answer_count,
            "accepted_answer_id": accepted_ids.get(post["id"]),
            "status": "answered" if answer_count else "open",
            "visibility": "public",
        })

    answers = [{
        "id": answer["id"],
        "question_id": answer["post_id"],
        "author": answer["author"],
        "author_display": answer["display"],
        "anonymous": False,
        "created_at": answer["date"],
        "content": answer["content"],
        "upvotes": answer["upvotes"],
        "is_accepted": answer.get("accepted", False),
    } for answer in answers_raw]

    comments = [{
        "id": comment["id"],
        "parent_id": comment["parent_id"],
        "parent_type": comment["parent_type"],
        "author": comment["author"],
        "author_display": comment["display"],
        "created_at": comment["date"],
        "content": comment["content"],
    } for comment in imported.get("comments", [])]
    return {"posts": posts, "answers": answers, "comments": comments, "votes": []}


def build_seed() -> dict[str, Any]:
    imported = _read_json(IMPORT_PATH)
    users = _read_json(USERS_PATH).get("users", [])
    board_data = _read_json(BOARD_PATH)
    board_posts = board_data if isinstance(board_data, list) else board_data.get("posts", [])

    members = []
    for member in imported.get("members", []):
        members.append({
            key: member.get(key, "")
            for key in ("username", "display_name", "title", "bio")
        })

    # Aggregate upvote counts remain on posts/answers; voter identities do not.
    public_forum = _normalize_forum(imported)
    public_board = []
    for post in board_posts:
        clean_post = dict(post)
        clean_post["images"] = []
        public_board.append(clean_post)

    return {
        "schema_version": 1,
        "stats": {
            "registered_users": len(users),
            "public_members": len(members),
            "forum_posts": len(public_forum["posts"]),
            "forum_answers": len(public_forum["answers"]),
            "forum_comments": len(public_forum["comments"]),
            "board_posts": len(public_board),
        },
        "members": members,
        "forum": public_forum,
        "lab_board": public_board,
    }


def main() -> None:
    payload = build_seed()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    forbidden = ('"email"', 'password_hash', 'password', 'api_key')
    lowered = serialized.lower()
    if any(token in lowered for token in forbidden):
        raise ValueError("community seed contains a forbidden private field")
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(json.dumps(payload["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
