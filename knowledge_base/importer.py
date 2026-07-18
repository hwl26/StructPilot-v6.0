"""Knowledge importer skeleton for structured cryo-EM experience docs."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import json

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

TIER_WEIGHTS = {
    "builtin": 1.0,
    "sop": 0.95,
    "note": 0.7,
    "draft": 0.4,
}

TIER_LABELS = {
    "builtin": "内置",
    "sop": "正式SOP",
    "note": "个人笔记",
    "draft": "草稿",
}

STR_LIST_KEYS = {
    "ui_keywords", "ui_elements", "action_steps", "qc_checks",
    "common_errors", "rollback_nodes", "image_refs", "tags",
}
STR_SCALAR_DEFAULTS = {
    "doc_id", "software", "version", "module", "screen_name", "checkpoint_id",
    "title_cn", "title_en", "summary", "tier", "status", "source", "imported_at",
    "source_url", "source_grade", "evidence_grade", "risk_grade", "review_status",
}


@dataclass
class KnowledgeDoc:
    doc_id: str
    software: str
    version: str = ""
    module: str = ""
    screen_name: str = ""
    checkpoint_id: str = ""
    title_cn: str = ""
    title_en: str = ""
    summary: str = ""
    ui_keywords: List[str] = field(default_factory=list)
    ui_elements: List[str] = field(default_factory=list)
    action_steps: List[str] = field(default_factory=list)
    qc_checks: List[str] = field(default_factory=list)
    common_errors: List[str] = field(default_factory=list)
    rollback_nodes: List[str] = field(default_factory=list)
    image_refs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    tier: str = "note"
    status: str = "formal_ready"
    source: str = "import"
    imported_at: str = ""
    source_url: str = ""
    source_grade: str = ""
    evidence_grade: str = ""
    risk_grade: str = ""
    review_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for k, v in list(data.items()):
            if v is None:
                if k in STR_LIST_KEYS:
                    data[k] = []
                else:
                    data[k] = ""
        if not data.get("tier"):
            data["tier"] = "note"
        if not data.get("status"):
            data["status"] = "formal_ready"
        if not data.get("source"):
            data["source"] = "import"
        if not data.get("imported_at"):
            data["imported_at"] = datetime.now().isoformat(timespec="seconds")
        return data

    @property
    def weight(self) -> float:
        w = TIER_WEIGHTS.get(self.tier, 0.6)
        if self.status != "formal_ready":
            w *= 0.5
        return w


def load_knowledge_doc(path: str) -> KnowledgeDoc:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Knowledge document must be a mapping/object")
    return doc_from_dict(data)


def doc_from_dict(data: Dict[str, Any]) -> KnowledgeDoc:
    clean: Dict[str, Any] = {}
    for fobj in KnowledgeDoc.__dataclass_fields__.values():
        k = fobj.name
        if k in data:
            v = data[k]
            if fobj.type == List[str] or k in STR_LIST_KEYS:
                if v is None:
                    v = []
                elif not isinstance(v, list):
                    v = [str(v)]
                else:
                    v = [str(x) for x in v if x is not None and str(x).strip()]
            else:
                v = "" if v is None else str(v)
            clean[k] = v
    if "doc_id" not in clean or "software" not in clean:
        raise ValueError("doc_id and software are required fields")
    return KnowledgeDoc(**clean)


def update_knowledge_index(doc: KnowledgeDoc, index_path: str) -> None:
    p = Path(index_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing: List[Dict[str, Any]] = []
    if p.exists():
        existing = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    existing = [item for item in existing if item.get("doc_id") != doc.doc_id]
    existing.append(doc.to_dict())
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_knowledge_doc(doc_id: str, index_path: str) -> bool:
    p = Path(index_path)
    if not p.exists():
        return False
    try:
        existing = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(existing, list):
        return False
    new_list = [item for item in existing if item.get("doc_id") != doc_id]
    if len(new_list) == len(existing):
        return False
    p.write_text(json.dumps(new_list, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def update_doc_status(doc_id: str, index_path: str, status: str, tier: Optional[str] = None) -> bool:
    p = Path(index_path)
    if not p.exists():
        return False
    try:
        existing = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(existing, list):
        return False
    found = False
    for item in existing:
        if item.get("doc_id") == doc_id:
            item["status"] = status
            if tier is not None:
                item["tier"] = tier
            found = True
            break
    if not found:
        return False
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def load_knowledge_index(index_path: str) -> List[Dict[str, Any]]:
    """Read the knowledge index written by ``update_knowledge_index``.

    Returns an empty list when the file is missing or malformed, so callers can
    degrade gracefully.
    """
    p = Path(index_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def doc_to_text(doc: Any) -> str:
    """Flatten a knowledge doc (dict or ``KnowledgeDoc``) into retrieval text.

    Concatenates the human-meaningful fields (title / summary / steps / QC /
    errors). Used both as the RAG corpus source and as model context.
    """
    if isinstance(doc, KnowledgeDoc):
        data = doc.to_dict()
    elif isinstance(doc, dict):
        data = doc
    else:
        return ""

    parts: List[str] = []
    title = (data.get("title_cn") or data.get("title_en") or "").strip()
    if title:
        parts.append(title)
    summary = (data.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    def _add_list(label: str, key: str) -> None:
        items = data.get(key) or []
        if isinstance(items, list):
            cleaned = [str(x).strip() for x in items if str(x).strip()]
            if cleaned:
                parts.append(f"{label}：" + "；".join(cleaned))

    _add_list("操作步骤", "action_steps")
    _add_list("质控要点", "qc_checks")
    _add_list("常见错误", "common_errors")
    return "\n".join(parts)


def detect_conflicts(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect potentially conflicting knowledge docs within the same checkpoint.

    Returns a list of conflict groups, each containing docs that share a
    checkpoint_id but have significantly different qc_checks or action_steps
    (simple keyword overlap heuristic).
    """
    by_cp: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        cp = (d.get("checkpoint_id") or "").strip()
        if not cp:
            continue
        by_cp.setdefault(cp, []).append(d)

    conflicts: List[Dict[str, Any]] = []
    for cp, group in by_cp.items():
        if len(group) < 2:
            continue
        formal = [d for d in group if d.get("status") == "formal_ready"]
        if len(formal) < 2:
            continue
        for i in range(len(formal)):
            for j in range(i + 1, len(formal)):
                a, b = formal[i], formal[j]
                if (a.get("tier") or "") == "builtin" and (b.get("tier") or "") == "builtin":
                    continue
                a_steps = set((a.get("qc_checks") or []) + (a.get("common_errors") or []))
                b_steps = set((b.get("qc_checks") or []) + (b.get("common_errors") or []))
                if a_steps and b_steps:
                    overlap = len(a_steps & b_steps) / max(len(a_steps | b_steps), 1)
                    if overlap < 0.2 and (len(a_steps) >= 2 or len(b_steps) >= 2):
                        conflicts.append({
                            "checkpoint_id": cp,
                            "docs": [a.get("doc_id"), b.get("doc_id")],
                            "titles": [a.get("title_cn") or a.get("doc_id", ""),
                                       b.get("title_cn") or b.get("doc_id", "")],
                            "reason": "质控要点/常见错误重叠度低，可能存在矛盾",
                        })
    return conflicts
