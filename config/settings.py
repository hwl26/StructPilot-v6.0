"""StructPilot v5.1 — 集中化配置（路径 / 运行参数）。

相对 V3 的架构改进：
- 所有关键路径集中管理，支持环境变量覆盖，便于跨盘 / 跨机部署；
- 截图根目录默认指向「上级目录」StructPilot_Visual_UI 的 images 目录
  （即用户提供的各步骤截图存放位置），不再要求把截图复制进工程内；
- 运行态目录默认独立为 StructPilot_v4_runtime，与 V3 互不污染。
"""

from __future__ import annotations

import os
from pathlib import Path

# 工程根目录：config/ -> 上一级即项目根
BASE_DIR = Path(__file__).resolve().parent.parent

# 运行态目录（会话记忆 / 上传 / OCR 缓存等），保持 V3 的多级回退策略
RUNTIME_ROOT = Path(
    os.getenv(
        "STRUCTPILOT_RUNTIME_DIR",
        str(BASE_DIR / "runtime"),
    )
)


def _default_screenshot_root() -> Path:
    """上级目录提供的视觉 UI 截图根（各步骤截图存放位置）。"""
    return (
        BASE_DIR.parent
        / "StructPilot_Visual_UI"
        / "StructPilot_Visual_UI"
        / "images"
    )


# 截图根目录：默认指向上级目录 StructPilot_Visual_UI images，
# 可被环境变量 STRUCTPILOT_SCREENSHOTS_DIR（绝对路径）覆盖。
SCREENSHOT_ROOT = Path(
    os.getenv("STRUCTPILOT_SCREENSHOTS_DIR", str(_default_screenshot_root()))
).expanduser()

# 工程内兜底截图目录（assets/guides），外部缺失时回退（铁律 10）。
BUNDLED_GUIDE_ROOT = BASE_DIR / "assets" / "guides"

# 指南卡片 / 知识库等路径
GUIDE_CARDS_PATH = BASE_DIR / "knowledge_base" / "guides" / "guide_cards.json"
CORRECTIONS_PATH = BASE_DIR / "knowledge_base" / "review" / "user_corrections.jsonl"

# 运行态可写目录
UPLOAD_DIR = RUNTIME_ROOT / "memory" / "uploads"
AUDIO_DIR = RUNTIME_ROOT / "memory" / "audio"
MEMORY_DIR = RUNTIME_ROOT / "memory"


def is_external_screenshots_available() -> bool:
    """外部截图根是否可访问（用于 UI 提示与回退判断）。"""
    return SCREENSHOT_ROOT.exists()


def resolve_screenshot_root() -> Path:
    """返回实际可用的截图根：外部优先，否则工程内兜底。"""
    if SCREENSHOT_ROOT.exists():
        return SCREENSHOT_ROOT
    return BUNDLED_GUIDE_ROOT
