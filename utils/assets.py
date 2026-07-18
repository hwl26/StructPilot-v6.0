"""StructPilot v5.1 — 资源 / 截图解析工具。

相对 V3「直接 relative-to-BASE_DIR」的架构改进：
- 截图优先从「外部截图根」（上级目录 StructPilot_Visual_UI images）解析，
  缺失时回退到工程内 assets/guides（保留铁律 10 的 Demo 截图路径）；
- 提供 collect_checkpoint_screenshots()，按 cp_XX → 文件夹 映射规则扫描，
  避免逐文件硬编码，便于后续扩充截图；
- 所有路径解析失败都优雅降级，绝不抛异常中断会话。

调用方式：本模块被 main.resolve_guide_asset 懒加载调用，导入失败也不影响主流程。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    from config import screenshot_map
    from config import settings
except Exception:  # pragma: no cover - 防御性兜底
    screenshot_map = None
    settings = None

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def _image_files(folder: Path) -> List[Path]:
    if not folder or not folder.exists():
        return []
    files = [
        p
        for p in sorted(folder.iterdir())
        if p.suffix.lower() in _IMAGE_EXTS and p.is_file()
    ]
    return files


def _normalize_guide_rel(raw_path: str) -> str:
    """把 'assets/guides/cp_01_import/01.1 xxx.png' 归一为 'cp_01_import/01.1 xxx.png'。"""
    rel = Path(raw_path)
    parts = rel.as_posix().replace("\\", "/").split("/")
    norm = [p for p in parts if p not in ("", "assets", "guides", "user_guides")]
    return "/".join(norm)


def resolve_screenshot(raw_path: str) -> str:
    """解析 guide 截图路径：外部截图根优先，其次工程内 assets/guides，最后 BASE_DIR 相对。

    raw_path 形如 "assets/guides/cp_01_import/01.1 relion import.png"。
    提取其相对 assets/guides 的部分（cp_01_import/01.1 ...png），
    先在 SCREENSHOT_ROOT 下查找，再回退 BASE_DIR/assets/guides 下查找。
    """
    if not raw_path:
        return ""
    rel = Path(raw_path)
    if rel.is_absolute():
        return str(rel) if rel.exists() else ""

    rel_key = _normalize_guide_rel(raw_path)

    # 候选 1：外部截图根
    if settings is not None:
        ext_candidate = settings.SCREENSHOT_ROOT / rel_key
        if ext_candidate.exists():
            return str(ext_candidate)
        # 候选 2：工程内 assets/guides
        bundled = settings.BUNDLED_GUIDE_ROOT / rel_key
        if bundled.exists():
            return str(bundled)
    # 候选 3：相对 BASE_DIR（原行为兜底）
    base_candidate = Path(raw_path)
    if not base_candidate.is_absolute():
        base_candidate = Path(os.getcwd()) / raw_path
    if base_candidate.exists():
        return str(base_candidate)
    return ""


def collect_checkpoint_screenshots(
    cp_id: str, software: str = ""
) -> List[Dict[str, str]]:
    """返回某 checkpoint 的全部截图（外部优先，assets 兜底）。

    每条: {"path": str, "caption": str, "source": "external"|"bundled"}

    software 参数保留供将来按软件筛选（当前上级目录截图不区分软件）。
    """
    if screenshot_map is None or settings is None:
        return []
    folders = screenshot_map.folders_for(cp_id)
    results: List[Dict[str, str]] = []
    seen: set = set()
    for folder_name in folders:
        ext_folder = settings.SCREENSHOT_ROOT / folder_name
        bundled_folder = settings.BUNDLED_GUIDE_ROOT / folder_name
        if ext_folder.exists():
            source_folder = ext_folder
            source_tag = "external"
        elif bundled_folder.exists():
            source_folder = bundled_folder
            source_tag = "bundled"
        else:
            continue
        for f in _image_files(source_folder):
            if f in seen:
                continue
            seen.add(f)
            results.append(
                {
                    "path": str(f),
                    "caption": _caption_for(folder_name, f.name, cp_id),
                    "source": source_tag,
                }
            )
    return results


def _caption_for(folder_name: str, filename: str, cp_id: str) -> str:
    label = folder_name.replace("_", " ").replace(cp_id + " ", "").strip()
    return f"{label} · {filename}"


def screenshot_source_label() -> str:
    """返回当前截图来源，用于 UI 提示。"""
    if settings is not None and settings.SCREENSHOT_ROOT.exists():
        return f"外部目录：{settings.SCREENSHOT_ROOT}"
    return "工程内置（assets/guides）"
