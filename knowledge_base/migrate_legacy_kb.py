"""Migrate legacy flat knowledge files into the governed KB layout.

This script is intentionally conservative: it copies approved/formal runtime
knowledge into the new folders while leaving the old flat files in place for
compatibility.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


KB_DIR = Path(__file__).resolve().parent


COPIES: List[Tuple[str, str]] = [
    ("pipeline_checkpoints.json", "flows/pipeline_checkpoints.json"),
    ("relion_stage_cards.json", "flows/relion_stage_cards.json"),
    ("stage_navigation_index.json", "flows/stage_navigation_index.json"),
    ("runtime_answer_index.json", "qa/runtime_answer_index.json"),
    ("tier2_rules.json", "rules/tier2_rules.json"),
    ("fault_trouble.json", "faults/fault_trouble.json"),
    ("qc_standard.json", "faults/qc_standard.json"),
]


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _is_formal(doc: Dict[str, Any]) -> bool:
    status = str(doc.get("status") or "").strip()
    if status == "formal_ready":
        return True
    tags = doc.get("tags") or []
    return isinstance(tags, list) and "formal_ready" in " ".join(str(tag) for tag in tags)


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _legacy_doc_to_formal_answer(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "doc_id": str(doc.get("doc_id") or ""),
        "checkpoint_id": str(doc.get("checkpoint_id") or ""),
        "software": str(doc.get("software") or ""),
        "version": str(doc.get("version") or ""),
        "question": str(doc.get("title_cn") or doc.get("title_en") or ""),
        "answer": str(doc.get("summary") or ""),
        "action_steps": _as_list(doc.get("action_steps")),
        "qc_checks": _as_list(doc.get("qc_checks")),
        "common_errors": _as_list(doc.get("common_errors")),
        "rollback_nodes": _as_list(doc.get("rollback_nodes")),
        "source": str(doc.get("source") or "legacy_knowledge_index"),
        "tier": str(doc.get("tier") or "note"),
        "status": "formal_ready",
        "review_status": "legacy_formal_ready",
        "runtime_allowed": True,
        "tags": _as_list(doc.get("tags")) + ["migrated_from_legacy_index"],
    }


def migrate_copies() -> int:
    copied = 0
    for source_rel, dest_rel in COPIES:
        source = KB_DIR / source_rel
        dest = KB_DIR / dest_rel
        if not source.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied += 1
    return copied


def migrate_formal_answers() -> int:
    docs = _read_json(KB_DIR / "knowledge_index.json", [])
    if not isinstance(docs, list):
        docs = []
    formal_items = [
        _legacy_doc_to_formal_answer(doc)
        for doc in docs
        if isinstance(doc, dict) and _is_formal(doc)
    ]
    out_path = KB_DIR / "qa" / "formal_answers.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in formal_items),
        encoding="utf-8",
    )
    return len(formal_items)


def ensure_empty_files() -> None:
    for relpath in (
        "qa/review_queue.jsonl",
        "qa/rejected_or_deprecated.jsonl",
        "review/review_log.jsonl",
    ):
        path = KB_DIR / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")


def migrate() -> Dict[str, int]:
    ensure_empty_files()
    return {
        "copied_files": migrate_copies(),
        "formal_answers": migrate_formal_answers(),
    }


if __name__ == "__main__":
    print(json.dumps(migrate(), ensure_ascii=False, indent=2))
