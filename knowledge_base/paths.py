"""Knowledge-base path helpers.

The project is moving from a flat ``knowledge_base/*.json`` layout to a
governed layout with flows, qa, terminology, rules, faults, guides, sources,
and review folders.  These helpers keep runtime code conservative: read the
new location first and fall back to the legacy flat file when needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class KnowledgeBasePaths:
    root: str

    def path(self, relpath: str) -> str:
        return os.path.join(self.root, *relpath.replace("\\", "/").split("/"))

    def first_existing(self, *relpaths: str) -> Optional[str]:
        for relpath in relpaths:
            path = self.path(relpath)
            if os.path.exists(path):
                return path
        return None


def load_json_with_fallback(
    knowledge_dir: str,
    primary_relpath: str,
    legacy_filename: Optional[str] = None,
    default: Any = None,
) -> Any:
    """Load JSON from the governed path, falling back to the legacy file."""
    paths = KnowledgeBasePaths(knowledge_dir)
    candidates = [primary_relpath]
    if legacy_filename:
        candidates.append(legacy_filename)
    path = paths.first_existing(*candidates)
    if not path:
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file, skipping blank lines and malformed rows."""
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def iter_runtime_allowed_docs(knowledge_dir: str) -> Iterable[Dict[str, Any]]:
    """Yield formally approved QA docs that are allowed in runtime answers."""
    formal_path = KnowledgeBasePaths(knowledge_dir).path("qa/formal_answers.jsonl")
    for doc in load_jsonl(formal_path):
        if doc.get("runtime_allowed", True) is False:
            continue
        status = doc.get("status") or doc.get("review_status")
        if status and status not in {"formal_ready", "approved", "expert_approved"}:
            continue
        yield doc


def source_label(doc: Dict[str, Any]) -> str:
    source = doc.get("source") or doc.get("sources") or ""
    if isinstance(source, list):
        return "; ".join(str(item) for item in source if item)
    return str(source)
