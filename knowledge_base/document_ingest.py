"""Document ingestion helpers for image-heavy operation documents.

The module is intentionally local and deterministic: it can turn plain text,
Markdown, JSON/YAML-like text exports, or image batches into reviewable
KnowledgeDoc drafts without requiring network OCR or an LLM call. Rich PDF/DOCX
parsing can be added later behind the same draft contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from knowledge_base.importer import KnowledgeDoc


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".json", ".yaml", ".yml"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

CHECKPOINT_KEYWORDS = {
    "cp_01": ["import", "movies", "micrograph", "star", "导入"],
    "cp_02": ["motion", "motioncorr", "patch motion", "drift", "运动"],
    "cp_03": ["ctf", "defocus", "ctffind"],
    "cp_04": ["pick", "picking", "blob", "template"],
    "cp_05": ["extract", "particles", "box size"],
    "cp_06": ["2d", "class2d", "classification"],
    "cp_07": ["initial model", "ab initio", "3d"],
    "cp_08": ["refine", "homogeneous", "non-uniform"],
    "cp_09": ["polish", "bayesian"],
}


@dataclass
class ImageAssetDraft:
    source_name: str
    stored_path: str
    caption: str = ""
    ocr_text: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: str = ""


@dataclass
class IngestDraft:
    doc: KnowledgeDoc
    images: List[ImageAssetDraft] = field(default_factory=list)
    raw_text_preview: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc": self.doc.to_dict(),
            "images": [image.__dict__ for image in self.images],
            "raw_text_preview": self.raw_text_preview,
            "warnings": self.warnings,
        }


def _safe_slug(text: str, default: str = "doc") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (text or "").strip()).strip("._")
    return (slug or default)[:80]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _lines(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", line).strip(" -\t") for line in (text or "").splitlines() if line.strip()]


def _guess_software(text: str, default: str = "relion") -> str:
    lower = text.lower()
    if "cryosparc" in lower or "cryo-sparc" in lower:
        return "cryosparc"
    if "relion" in lower:
        return "relion"
    return default


def _guess_checkpoint(text: str, filename: str = "") -> str:
    haystack = f"{filename}\n{text}".lower()
    explicit = re.search(r"\bcp[_-]?(\d{1,2})\b", haystack)
    if explicit:
        return f"cp_{int(explicit.group(1)):02d}"
    scores = []
    for cp_id, keywords in CHECKPOINT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in haystack)
        if score:
            scores.append((score, cp_id))
    return max(scores)[1] if scores else ""


def _guess_problem_type(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("error", "failed", "exception", "报错", "失败")):
        return "error"
    if any(token in lower for token in ("parameter", "参数", "box size", "pixel", "dose")):
        return "parameter"
    if any(token in lower for token in ("sop", "step", "步骤", "workflow", "流程")):
        return "sop"
    return "operation"


def _extract_sections(text: str) -> Dict[str, List[str]]:
    lines = _lines(text)
    action_steps: List[str] = []
    qc_checks: List[str] = []
    common_errors: List[str] = []
    ui_terms: List[str] = []
    for line in lines:
        lower = line.lower()
        if re.match(r"^(\d+[.)、]|step\s+\d+|步骤\s*\d+)", lower):
            action_steps.append(line)
        elif any(token in lower for token in ("check", "qc", "确认", "检查", "质控", "should be")):
            qc_checks.append(line)
        elif any(token in lower for token in ("error", "failed", "warning", "报错", "失败", "警告")):
            common_errors.append(line)
        if any(token in line for token in ("I/O", "Motion", "CTF", "Extract", "2D", "3D", "Import")):
            ui_terms.append(line[:120])
    if not action_steps:
        action_steps = lines[:8]
    return {
        "action_steps": action_steps[:20],
        "qc_checks": qc_checks[:12],
        "common_errors": common_errors[:12],
        "ui_keywords": ui_terms[:20],
    }


def _copy_image_assets(image_paths: Iterable[Path], asset_root: Path, doc_id: str) -> List[ImageAssetDraft]:
    target_dir = asset_root / _safe_slug(doc_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    result: List[ImageAssetDraft] = []
    for idx, src in enumerate(image_paths, start=1):
        if not src.exists() or src.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        digest = _file_sha256(src)
        out_name = f"{idx:02d}_{_safe_slug(src.stem, 'image')}_{digest[:8]}{src.suffix.lower()}"
        dst = target_dir / out_name
        if not dst.exists():
            shutil.copy2(src, dst)
        width = height = None
        try:
            from PIL import Image

            with Image.open(dst) as im:
                width, height = int(im.width), int(im.height)
        except Exception:
            pass
        result.append(ImageAssetDraft(
            source_name=src.name,
            stored_path=str(dst),
            caption=src.stem,
            width=width,
            height=height,
            sha256=digest,
        ))
    return result


def build_ingest_draft(
    source_path: Path,
    asset_root: Path,
    *,
    default_software: str = "relion",
    tier: str = "note",
    status: str = "draft",
    extra_image_paths: Optional[List[Path]] = None,
) -> IngestDraft:
    source_path = Path(source_path)
    warnings: List[str] = []
    text = ""
    if source_path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS:
        text = _read_text_file(source_path)
    elif source_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        extra_image_paths = [source_path] + list(extra_image_paths or [])
        warnings.append("Image-only input: add OCR text or a short summary before approving.")
    else:
        warnings.append(f"Unsupported rich document extension {source_path.suffix}; saved as metadata-only draft.")

    doc_id_seed = f"{source_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    doc_id = "doc_" + _safe_slug(doc_id_seed)
    software = _guess_software(text or source_path.name, default_software)
    checkpoint_id = _guess_checkpoint(text, source_path.name)
    problem_type = _guess_problem_type(text or source_path.name)
    sections = _extract_sections(text)
    title = _lines(text)[0][:80] if _lines(text) else source_path.stem
    summary_lines = [line for line in _lines(text) if line not in sections["action_steps"]][:3]
    summary = " ".join(summary_lines)[:500] if summary_lines else f"Draft imported from {source_path.name}."
    images = _copy_image_assets(extra_image_paths or [], asset_root, doc_id)
    image_refs = [image.stored_path for image in images]
    tags = [tag for tag in [software, checkpoint_id, problem_type, source_path.suffix.lower().lstrip(".")] if tag]
    doc = KnowledgeDoc(
        doc_id=doc_id,
        software=software,
        checkpoint_id=checkpoint_id,
        title_cn=title,
        summary=summary,
        ui_keywords=sections["ui_keywords"],
        action_steps=sections["action_steps"],
        qc_checks=sections["qc_checks"],
        common_errors=sections["common_errors"],
        image_refs=image_refs,
        tags=tags,
        tier=tier,
        status=status,
        source="document_ingest",
        imported_at=datetime.now().isoformat(timespec="seconds"),
    )
    if not checkpoint_id:
        warnings.append("No checkpoint detected; set checkpoint_id before approving if this should affect guided UI/RAG ranking.")
    return IngestDraft(doc=doc, images=images, raw_text_preview=text[:2000], warnings=warnings)
