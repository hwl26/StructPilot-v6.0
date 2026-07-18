"""Validate StructPilot's governed knowledge-base layout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


KB_DIR = Path(__file__).resolve().parent

REQUIRED_DIRS = (
    "flows",
    "qa",
    "terminology",
    "rules",
    "faults",
    "guides",
    "sources",
    "review",
)

REQUIRED_JSON_FILES = (
    "flows/pipeline_checkpoints.json",
    "flows/relion_stage_cards.json",
    "flows/cryosparc_stage_cards.json",
    "rules/tier2_rules.json",
    "rules/risk_gating_rules.json",
    "faults/fault_trouble.json",
    "faults/qc_standard.json",
    "terminology/glossary.json",
    "terminology/software_ui_terms.json",
    "terminology/parameter_aliases.json",
    "guides/guide_cards.json",
    "sources/source_registry.json",
    "review/review_policy.json",
)

REQUIRED_JSONL_FILES = (
    "qa/formal_answers.jsonl",
    "qa/review_queue.jsonl",
    "qa/rejected_or_deprecated.jsonl",
    "review/review_log.jsonl",
)

FORMAL_STATUSES = {"formal_ready", "approved", "expert_approved", "legacy_formal_ready"}


def _load_json(path: Path) -> Tuple[bool, Any, str]:
    try:
        return True, json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return False, None, str(exc)


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Dict[str, Any]]]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"line {line_no}: expected object")
        yield line_no, item


def validate(root: Path = KB_DIR) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    for relpath in REQUIRED_DIRS:
        if not (root / relpath).is_dir():
            errors.append(f"missing directory: {relpath}")

    for relpath in REQUIRED_JSON_FILES:
        path = root / relpath
        if not path.exists():
            errors.append(f"missing JSON file: {relpath}")
            continue
        ok, data, message = _load_json(path)
        if not ok:
            errors.append(f"invalid JSON: {relpath}: {message}")
            continue
        if relpath == "flows/pipeline_checkpoints.json" and not isinstance(data, list):
            errors.append("flows/pipeline_checkpoints.json must be a list")
        if relpath == "flows/relion_stage_cards.json" and not isinstance(data, list):
            errors.append("flows/relion_stage_cards.json must be a list")

    formal_count = 0
    for relpath in REQUIRED_JSONL_FILES:
        path = root / relpath
        if not path.exists():
            errors.append(f"missing JSONL file: {relpath}")
            continue
        try:
            rows = list(_iter_jsonl(path))
        except Exception as exc:
            errors.append(f"invalid JSONL: {relpath}: {exc}")
            continue

        for line_no, item in rows:
            if relpath == "qa/formal_answers.jsonl":
                formal_count += 1
                status = str(item.get("status") or item.get("review_status") or "")
                if status not in FORMAL_STATUSES:
                    errors.append(f"formal answer {line_no} has non-formal status: {status}")
                if item.get("runtime_allowed", True) is False:
                    warnings.append(f"formal answer {line_no} is marked runtime_allowed=false")
                if not item.get("source"):
                    warnings.append(f"formal answer {line_no} has no source")
            if relpath == "qa/review_queue.jsonl" and item.get("runtime_allowed") is True:
                errors.append(f"review queue item {line_no} must not be runtime_allowed=true")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "formal_answers": formal_count,
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
