"""Import the curated RELION knowledge package into StructPilot's runtime index.

Only runtime_allowed formal answers are imported. Items waiting for expert
review remain outside the runtime answer surface.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

BASE_DIR = Path(__file__).resolve().parents[1]
# 支持通过环境变量 RELION_KB_DIR 覆盖 KB 包路径，便于测试和沙箱环境
DEFAULT_PACKAGE_DIR = Path(
    os.environ.get(
        "RELION_KB_DIR",
        r"C:\Users\17706\Documents\struct\relion_kb_task\output\structpilot_relion_kb_package_v0",
    )
)
INDEX_PATH = BASE_DIR / "knowledge_base" / "knowledge_index.json"
STAGE_CARDS_PATH = BASE_DIR / "knowledge_base" / "relion_stage_cards.json"
CORPUS_CACHE_PATH = BASE_DIR / "config" / "corpus_cache.json"
# 新增：runtime answer index 和 stage navigation index 路径
RUNTIME_ANSWER_INDEX_PATH = BASE_DIR / "knowledge_base" / "runtime_answer_index.json"
STAGE_NAVIGATION_INDEX_PATH = BASE_DIR / "knowledge_base" / "stage_navigation_index.json"
GOVERNED_STAGE_CARDS_PATH = BASE_DIR / "knowledge_base" / "flows" / "relion_stage_cards.json"
GOVERNED_RUNTIME_ANSWER_INDEX_PATH = BASE_DIR / "knowledge_base" / "qa" / "runtime_answer_index.json"
GOVERNED_STAGE_NAVIGATION_INDEX_PATH = BASE_DIR / "knowledge_base" / "flows" / "stage_navigation_index.json"
GOVERNED_FORMAL_ANSWERS_PATH = BASE_DIR / "knowledge_base" / "qa" / "formal_answers.jsonl"


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                yield item


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _stage_lookup(package_dir: Path) -> Dict[str, Dict[str, Any]]:
    cards = _read_json(package_dir / "stage_cards.json")
    if not isinstance(cards, list):
        return {}
    return {str(card.get("id", "")): card for card in cards if isinstance(card, dict)}


def _formal_answer_to_doc(item: Dict[str, Any], stage: Dict[str, Any]) -> Dict[str, Any]:
    checkpoint_id = str(item.get("checkpoint_id") or stage.get("id") or "")
    source_urls = _as_list(item.get("source_urls"))
    guardrails = _as_list(item.get("guardrails"))
    question = str(item.get("question") or "").strip()
    answer = str(item.get("answer") or "").strip()

    summary_parts = [
        f"Q: {question}" if question else "",
        f"A: {answer}" if answer else "",
        f"Evidence grade: {item.get('evidence_grade', '')}".strip(),
        f"Risk grade: {item.get('risk_grade', '')}".strip(),
    ]
    if source_urls:
        summary_parts.append("Sources: " + "; ".join(source_urls))

    return {
        "doc_id": str(item.get("id") or f"relion_{checkpoint_id}_{abs(hash(question))}"),
        "software": "RELION",
        "version": "5.0",
        "module": str(stage.get("name") or checkpoint_id),
        "screen_name": ", ".join(_as_list(stage.get("relion_jobs"))),
        "checkpoint_id": checkpoint_id,
        "title_cn": question,
        "title_en": "",
        "summary": "\n".join(part for part in summary_parts if part),
        "ui_keywords": _as_list(stage.get("key_parameters")) + _as_list(stage.get("relion_jobs")),
        "ui_elements": _as_list(stage.get("relion_jobs")),
        "action_steps": [answer] if answer else [],
        "qc_checks": _as_list(stage.get("qc_checks")),
        "common_errors": _as_list(stage.get("common_pitfalls")) + guardrails,
        "rollback_nodes": [],
        "image_refs": [],
        "tags": [
            "relion",
            "formal_ready_v0",
            str(item.get("evidence_grade") or "").lower(),
            str(item.get("risk_grade") or "").lower(),
            checkpoint_id,
        ],
    }


def _formal_answer_to_runtime_item(item: Dict[str, Any], stage: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve package QA as governed runtime JSONL with review metadata."""
    checkpoint_id = str(item.get("checkpoint_id") or stage.get("id") or "")
    return {
        "doc_id": str(item.get("id") or f"relion_{checkpoint_id}"),
        "checkpoint_id": checkpoint_id,
        "software": "RELION",
        "version": "5.0",
        "question": str(item.get("question") or "").strip(),
        "answer": str(item.get("answer") or "").strip(),
        "source": _as_list(item.get("source_urls")),
        "evidence_grade": item.get("evidence_grade", ""),
        "risk_grade": item.get("risk_grade", ""),
        "guardrails": _as_list(item.get("guardrails")),
        "status": "formal_ready",
        "review_status": "expert_approved",
        "runtime_allowed": True,
        "tags": [
            "relion",
            "formal_runtime",
            str(item.get("evidence_grade") or "").lower(),
            str(item.get("risk_grade") or "").lower(),
            checkpoint_id,
        ],
    }


def import_package(package_dir: Path = DEFAULT_PACKAGE_DIR) -> Dict[str, int]:
    package_dir = package_dir.resolve()
    stage_by_id = _stage_lookup(package_dir)
    stage_cards = list(stage_by_id.values())
    formal_items = [
        item
        for item in _read_jsonl(package_dir / "formal_answers.jsonl")
        if item.get("runtime_allowed") is True
        and str(item.get("status") or "").startswith("formal_ready")
    ]

    existing: List[Dict[str, Any]] = []
    if INDEX_PATH.exists():
        loaded = _read_json(INDEX_PATH)
        if isinstance(loaded, list):
            existing = [item for item in loaded if isinstance(item, dict)]

    imported_ids = {str(item.get("id")) for item in formal_items}
    kept = [doc for doc in existing if str(doc.get("doc_id")) not in imported_ids]
    docs = [
        _formal_answer_to_doc(item, stage_by_id.get(str(item.get("checkpoint_id")), {}))
        for item in formal_items
    ]

    INDEX_PATH.write_text(json.dumps(kept + docs, ensure_ascii=False, indent=2), encoding="utf-8")
    STAGE_CARDS_PATH.write_text(json.dumps(stage_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    GOVERNED_STAGE_CARDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOVERNED_STAGE_CARDS_PATH.write_text(json.dumps(stage_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    governed_items = [
        _formal_answer_to_runtime_item(item, stage_by_id.get(str(item.get("checkpoint_id")), {}))
        for item in formal_items
    ]
    GOVERNED_FORMAL_ANSWERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOVERNED_FORMAL_ANSWERS_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in governed_items),
        encoding="utf-8",
    )
    if CORPUS_CACHE_PATH.exists():
        CORPUS_CACHE_PATH.unlink()
    # P1-C7: 加载 runtime_answer_index.json 和 stage_navigation_index.json
    runtime_index = None
    runtime_path = package_dir / "runtime_answer_index.json"
    if runtime_path.exists():
        try:
            runtime_index = _read_json(runtime_path)
            RUNTIME_ANSWER_INDEX_PATH.write_text(
                json.dumps(runtime_index, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            GOVERNED_RUNTIME_ANSWER_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOVERNED_RUNTIME_ANSWER_INDEX_PATH.write_text(
                json.dumps(runtime_index, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            print(f"WARNING: failed to load runtime_answer_index.json: {exc}")

    stage_nav = None
    stage_nav_path = package_dir / "stage_navigation_index.json"
    if stage_nav_path.exists():
        try:
            stage_nav = _read_json(stage_nav_path)
            STAGE_NAVIGATION_INDEX_PATH.write_text(
                json.dumps(stage_nav, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            GOVERNED_STAGE_NAVIGATION_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOVERNED_STAGE_NAVIGATION_INDEX_PATH.write_text(
                json.dumps(stage_nav, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            print(f"WARNING: failed to load stage_navigation_index.json: {exc}")

    return {
        "imported": len(docs),
        "imported_stage_cards": len(stage_cards),
        "kept_existing": len(kept),
        "total": len(kept + docs),
        "runtime_index_loaded": runtime_index is not None,
        "stage_nav_loaded": stage_nav is not None,
    }


if __name__ == "__main__":
    print(json.dumps(import_package(), ensure_ascii=False, indent=2))
