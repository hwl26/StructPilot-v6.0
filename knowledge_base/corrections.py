"""User correction and query normalization helpers.

Corrections are stored as append-only JSONL so every UI/user fix is auditable
before it is promoted into the formal knowledge index.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


SOFTWARE_ALIASES = {
    "relion": "relion",
    "relion5": "relion",
    "relion 5": "relion",
    "cryosparc": "cryosparc",
    "cryo-sparc": "cryosparc",
    "csparc": "cryosparc",
}

CHECKPOINT_ALIASES = {
    "import": "cp_01",
    "导入": "cp_01",
    "motion": "cp_02",
    "motion correction": "cp_02",
    "motioncorr": "cp_02",
    "运动校正": "cp_02",
    "ctf": "cp_03",
    "pick": "cp_04",
    "picking": "cp_04",
    "extract": "cp_05",
    "2d": "cp_06",
    "class2d": "cp_06",
    "3d": "cp_07",
    "refine": "cp_08",
    "polish": "cp_09",
}

TYPO_MAP = {
    "corection": "correction",
    "corect": "correct",
    "moton": "motion",
    "motoin": "motion",
    "relain": "relion",
    "reloin": "relion",
    "ctff": "ctf",
    "clasification": "classification",
    "partical": "particle",
}


@dataclass
class NormalizedQuery:
    original: str
    normalized: str
    software: str = ""
    checkpoint_id: str = ""
    problem_type: str = "general"
    corrections: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserCorrection:
    correction_id: str
    session_id: str
    created_at: str
    kind: str
    original_query: str = ""
    normalized_query: str = ""
    corrected_query: str = ""
    answer_excerpt: str = ""
    user_note: str = ""
    checkpoint_id: str = ""
    software: str = ""
    status: str = "pending_review"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _replace_typos(text: str) -> tuple[str, List[str]]:
    fixed = text
    applied: List[str] = []
    for wrong, right in TYPO_MAP.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", flags=re.I)
        if pattern.search(fixed):
            fixed = pattern.sub(right, fixed)
            applied.append(f"{wrong}->{right}")
    fixed = re.sub(r"\s+", " ", fixed).strip()
    return fixed, applied


def _detect_software(text: str, default: str = "") -> str:
    lower = text.lower()
    for alias, canonical in SOFTWARE_ALIASES.items():
        if alias in lower:
            return canonical
    return default or ""


def _detect_checkpoint(text: str, default: str = "") -> str:
    lower = text.lower()
    explicit = re.search(r"\bcp[_-]?(\d{1,2})\b", lower)
    if explicit:
        return f"cp_{int(explicit.group(1)):02d}"
    matches = []
    for alias, cp_id in CHECKPOINT_ALIASES.items():
        if alias in lower:
            matches.append((len(alias), cp_id))
    if matches:
        return max(matches)[1]
    return default or ""


def _detect_problem_type(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("报错", "失败", "error", "failed", "cannot", "exception")):
        return "error"
    if any(token in lower for token in ("参数", "parameter", "box", "pixel", "dose", "threshold")):
        return "parameter"
    if any(token in lower for token in ("进度", "完成", "下一步", "progress", "next")):
        return "workflow"
    if any(token in lower for token in ("截图", "图", "image", "screen")):
        return "screenshot"
    return "general"


def normalize_query(text: str, *, default_software: str = "", default_checkpoint: str = "") -> NormalizedQuery:
    original = (text or "").strip()
    normalized, corrections = _replace_typos(original)
    software = _detect_software(normalized, default_software)
    checkpoint_id = _detect_checkpoint(normalized, default_checkpoint)
    problem_type = _detect_problem_type(normalized)
    tags = []
    if software:
        tags.append(software)
    if checkpoint_id:
        tags.append(checkpoint_id)
    if problem_type != "general":
        tags.append(problem_type)
    if tags and normalized:
        normalized = f"[{', '.join(tags)}] {normalized}"
    confidence = 0.35 + (0.2 if software else 0) + (0.25 if checkpoint_id else 0) + (0.1 if corrections else 0)
    return NormalizedQuery(
        original=original,
        normalized=normalized,
        software=software,
        checkpoint_id=checkpoint_id,
        problem_type=problem_type,
        corrections=corrections,
        confidence=min(confidence, 0.95),
    )


def append_correction(path: Path, correction: UserCorrection) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(correction.to_dict(), ensure_ascii=False) + "\n")


def load_corrections(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return rows[:limit] if limit else rows


def make_correction(
    *,
    session_id: str,
    kind: str,
    original_query: str = "",
    normalized_query: str = "",
    corrected_query: str = "",
    answer_excerpt: str = "",
    user_note: str = "",
    checkpoint_id: str = "",
    software: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> UserCorrection:
    created_at = datetime.now().isoformat(timespec="seconds")
    seed = f"{session_id}|{created_at}|{kind}|{original_query}|{corrected_query}"
    readable_tail = re.sub(r"[^a-zA-Z0-9]+", "", seed)[-10:]
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    correction_id = f"corr_{readable_tail}_{digest}"
    return UserCorrection(
        correction_id=correction_id,
        session_id=session_id,
        created_at=created_at,
        kind=kind,
        original_query=original_query,
        normalized_query=normalized_query,
        corrected_query=corrected_query,
        answer_excerpt=answer_excerpt[:1200],
        user_note=user_note,
        checkpoint_id=checkpoint_id,
        software=software,
        metadata=metadata or {},
    )
