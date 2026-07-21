"""
StructPilot v6.0 - Validation layer.

Provides lightweight guards for user inputs, checkpoint transitions, and
response sanity checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationResult:
    passed: bool
    summary: str
    concerns: List[str]
    suggestion: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "concerns": self.concerns,
            "suggestion": self.suggestion,
            "metadata": self.metadata or {},
        }


class InputValidator:
    """Rule-based validator for cryo-EM workflow inputs."""

    fail_keywords = [
        "失败", "报错", "error", "fail", "崩了", "exception", "crash",
        "很糊", "看不清", "没有颗粒", "分辨率很差",
    ]
    pass_keywords = [
        "完成", "ok", "没问题", "成功", "通过", "done", "跑完", "没报错",
        "pixel size", "resolution", "fsc", "3.5", "3.0", "2.5", "2.8", "3.2", "4.0",
    ]

    def validate_feedback(self, text: str) -> ValidationResult:
        if not text or not text.strip():
            return ValidationResult(False, "输入为空", ["用户没有提供有效内容"], "请补充一句当前结果或问题描述")

        lowered = text.lower()
        for kw in self.fail_keywords:
            if kw in lowered:
                return ValidationResult(
                    False,
                    f"检测到问题关键词：{kw}",
                    [f"文本包含 '{kw}'"],
                    "建议先排查具体报错、截图或日志，再决定是否推进",
                )

        if any(kw in lowered for kw in self.pass_keywords):
            return ValidationResult(True, "看起来已完成或可推进", [], "可以进入下一步")

        return ValidationResult(True, "中性输入，默认允许推进", [], "如有疑问，可补充更具体的参数或截图")

    def validate_checkpoint_id(self, cp_id: str, allowed: List[str]) -> ValidationResult:
        if cp_id in allowed:
            return ValidationResult(True, "检查站有效", [])
        return ValidationResult(False, "未知检查站", [f"{cp_id} 不在允许列表中"], "请先查看流程进度")

    def validate_params(self, params: Dict[str, Any]) -> ValidationResult:
        concerns = []
        if "pixel_size" in params:
            try:
                px = float(params["pixel_size"])
                if px <= 0 or px > 10:
                    concerns.append("pixel_size 数值异常")
            except Exception:
                concerns.append("pixel_size 不是数值")

        if "accelerating_voltage" in params:
            try:
                voltage = float(params["accelerating_voltage"])
                if voltage not in {80, 120, 200, 300}:
                    concerns.append("accelerating_voltage 不是常见冷冻电镜电压值")
            except Exception:
                concerns.append("accelerating_voltage 不是数值")

        if "spherical_aberration" in params:
            try:
                cs = float(params["spherical_aberration"])
                if cs <= 0 or cs > 5:
                    concerns.append("spherical_aberration 数值异常")
            except Exception:
                concerns.append("spherical_aberration 不是数值")

        if "box_size" in params:
            try:
                box = int(float(params["box_size"]))
                if box < 32 or box > 2048:
                    concerns.append("box_size 超出常见范围")
            except Exception:
                concerns.append("box_size 不是整数")

        if "total_dose" in params:
            try:
                dose = float(params["total_dose"])
                if dose <= 0 or dose > 200:
                    concerns.append("total_dose 数值异常")
            except Exception:
                concerns.append("total_dose 不是数值")

        if "ctf_fit" in params:
            try:
                fit = float(params["ctf_fit"])
                if fit <= 0 or fit > 20:
                    concerns.append("ctf_fit 数值异常")
            except Exception:
                concerns.append("ctf_fit 不是数值")

        if concerns:
            return ValidationResult(False, "参数校验未通过", concerns, "请检查参数单位和数值")
        return ValidationResult(True, "参数基本正常", [])


class ResponseValidator:
    """Simple response sanity check before UI rendering."""

    def validate_text(self, text: str) -> ValidationResult:
        if not text:
            return ValidationResult(False, "空回复", ["模型没有输出内容"], "请重试或查看日志")
        if len(text.strip()) < 2:
            return ValidationResult(False, "回复过短", ["内容太短，不足以展示"], "请补充完整解释")
        return ValidationResult(True, "回复可用", [])


def extract_params_from_text(text: str) -> Dict[str, Any]:
    """Extract common cryo-EM parameters from plain text."""
    params: Dict[str, Any] = {}
    patterns = {
        "pixel_size": r"(?:pixel\s*size|像素尺寸|像素大小)\s*(?:\([^)]*\))?\s*[:=：]?\s*([0-9]*\.?[0-9]+)",
        "accelerating_voltage": r"(?:accelerating\s*)?voltage\s*(?:\([^)]*\))?\s*[:=：]?\s*([0-9]+)|(?:加速电压|电压)\s*[:=：]?\s*([0-9]+)\s*kv?",
        "spherical_aberration": r"(?:spherical\s*aberration|球差)\s*(?:\([^)]*\))?\s*[:=：]?\s*([0-9]*\.?[0-9]+)",
        "amplitude_contrast": r"(?:amplitude\s*contrast|振幅衬度)\s*[:=：]?\s*([0-9]*\.?[0-9]+)",
        "ctf_fit": r"ctf\s*fit\s*[:=]?\s*([0-9]*\.?[0-9]+)",
        "box_size": r"box\s*size\s*[:=]?\s*([0-9]+)",
        "total_dose": r"(?:total\s*dose|总剂量)\s*[:=：]?\s*([0-9]*\.?[0-9]+)",
        "dose_per_frame": r"(?:dose\s*per\s*frame|每帧剂量)\s*[:=：]?\s*([0-9]*\.?[0-9]+)",
        "eer_fractionation": r"(?:eer\s*fractionation|eer\s*分帧数)\s*[:=：]?\s*([0-9]+)",
    }
    lowered = text.lower()
    for key, pattern in patterns.items():
        m = re.search(pattern, lowered)
        if m:
            value = next((g for g in m.groups() if g), "")
            parsed_value = float(value) if "." in value else int(value)
            params[key] = parsed_value
            if key == "accelerating_voltage":
                params.setdefault("voltage", parsed_value)
    return params
