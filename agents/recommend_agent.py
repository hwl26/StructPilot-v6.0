"""RecommendAgent — 上下文感知参数推荐引擎。

根据用户实验条件（显微镜、样品、数据量等），为关键参数计算个性化推荐值。
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional


# 官方 Guide 的高效 box size 列表
EFFICIENT_BOX_SIZES = [
    32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 80, 88, 96, 104, 112, 120,
    128, 144, 160, 176, 192, 208, 224, 240, 256, 288, 320, 352, 384, 416,
    448, 480, 512, 576, 640, 1280,
]


class RecommendAgent:
    def __init__(self, rules_path: Optional[str] = None):
        if rules_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(base, "knowledge_base", "rules", "recommendation_rules.json")
        self.rules: Dict[str, Any] = {}
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
        except Exception:
            pass

    def recommend(self, param_name: str, user_context: Dict[str, Any], round_number: int = 1) -> Optional[Dict[str, Any]]:
        """为指定参数计算推荐值。返回 {value, reason, formula} 或 None。"""
        ctx = user_context or {}

        if param_name in ("box_size", "extraction_box_size"):
            return self._recommend_box_size(ctx)
        elif param_name in ("num_classes", "num_2d_classes", "number_of_2d_classes"):
            return self._recommend_num_classes(ctx)
        elif param_name in ("max_resolution", "maximum_resolution"):
            return self._recommend_max_resolution(round_number)
        elif param_name in ("accelerating_voltage", "voltage_kv", "voltage"):
            return self._recommend_voltage(ctx)
        elif param_name in ("pixel_size", "pixel_size_a"):
            return self._recommend_pixel_size(ctx)
        elif param_name in ("spherical_aberration", "cs", "cs_mm"):
            return self._recommend_cs(ctx)

        return None

    def _estimate_diameter(self, mass_kda: float) -> float:
        """分子量 → 估算球状蛋白直径 (Å)。V ≈ mass × 1210 Å³/kDa。"""
        volume = mass_kda * 1210.0
        diameter = 2.0 * (3.0 * volume / (4.0 * math.pi)) ** (1.0 / 3.0)
        return round(diameter)

    def _recommend_box_size(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mass = ctx.get("estimated_mass_kda")
        pixel = ctx.get("pixel_size_A")
        if not mass or not pixel:
            return None

        try:
            mass = float(mass)
            pixel = float(pixel)
        except (ValueError, TypeError):
            return None

        diameter = self._estimate_diameter(mass)
        raw_box = diameter / pixel * 1.8

        # 向上取整到高效 box size
        recommended = raw_box
        for size in EFFICIENT_BOX_SIZES:
            if size >= raw_box:
                recommended = size
                break

        return {
            "value": int(recommended),
            "reason": f"基于你的 {mass:.0f} kDa 蛋白（~{diameter}Å 直径）+ {pixel} Å/px 像素尺寸",
            "formula": f"{diameter}Å / {pixel}Å/px × 1.8 ≈ {raw_box:.0f}px → 向上取整为 {int(recommended)}px",
        }

    def _recommend_num_classes(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        particles = ctx.get("estimated_particles")
        if not particles:
            return None
        try:
            particles = int(particles)
        except (ValueError, TypeError):
            return None

        if particles > 200000:
            value = 100
            reason = f"基于你的 {particles:,} 颗粒量（>20 万 → 100 类充分分离）"
        elif particles > 50000:
            value = 50
            reason = f"基于你的 {particles:,} 颗粒量（5-20 万 → 50 类平衡速度与精度）"
        else:
            value = 30
            reason = f"基于你的 {particles:,} 颗粒量（<5 万 → 30 类避免信号稀释）"

        return {"value": value, "reason": reason, "formula": "颗粒数 → 类别数映射规则"}

    def _recommend_max_resolution(self, round_number: int = 1) -> Optional[Dict[str, Any]]:
        if round_number <= 1:
            return {"value": 5, "reason": "第一轮 bin2 快速粗筛，低频轮廓即可", "formula": ""}
        else:
            return {"value": 3, "reason": "第二轮 bin1 精挑，push 高频信号", "formula": ""}

    def _recommend_voltage(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        microscope = str(ctx.get("microscope", "")).lower()
        if "titan krios" in microscope or "krios" in microscope:
            return {"value": 300, "reason": "Titan Krios 标准电压 300kV", "formula": ""}
        if "arctica" in microscope or "glacios" in microscope:
            return {"value": 200, "reason": "Arctica/Glacios 标准电压 200kV", "formula": ""}
        return None

    def _recommend_pixel_size(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        detector = str(ctx.get("detector", "")).lower()
        if "k3" in detector:
            return {"value": "物理像素/2（超分辨率模式）", "reason": "K3 超分辨率模式需除以 2", "formula": ""}
        return None

    def _recommend_cs(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        microscope = str(ctx.get("microscope", "")).lower()
        if "titan krios" in microscope or "krios" in microscope:
            return {"value": 2.7, "reason": "Titan Krios 标准球差 2.7mm", "formula": ""}
        if "arctica" in microscope or "glacios" in microscope:
            return {"value": 2.0, "reason": "200kV 设备常用球差 2.0mm", "formula": ""}
        return None

    def recommend_all(self, param_names: List[str], user_context: Dict[str, Any], round_number: int = 1) -> Dict[str, Dict[str, Any]]:
        """批量推荐。"""
        results: Dict[str, Dict[str, Any]] = {}
        for name in param_names:
            rec = self.recommend(name, user_context, round_number)
            if rec:
                results[name] = rec
        return results

    def auto_recommend_from_state(self, state_params: Dict[str, Any], round_number: int = 1) -> Dict[str, Dict[str, Any]]:
        """改动6：从state.params自动推荐相关参数，用于对话中智能提示。

        例如用户提到 estimated_mass_kda=150, pixel_size_A=1.5，自动推荐 box_size。
        """
        results: Dict[str, Dict[str, Any]] = {}

        # 若有分子量+像素尺寸，推荐 box_size
        if state_params.get("estimated_mass_kda") and state_params.get("pixel_size_A"):
            rec = self._recommend_box_size(state_params)
            if rec:
                results["box_size"] = rec

        # 若有颗粒数，推荐 num_classes
        if state_params.get("estimated_particles"):
            rec = self._recommend_num_classes(state_params)
            if rec:
                results["num_2d_classes"] = rec

        # 若有显微镜型号，推荐电压
        if state_params.get("microscope"):
            rec = self._recommend_voltage(state_params)
            if rec:
                results["accelerating_voltage"] = rec
            cs_rec = self._recommend_cs(state_params)
            if cs_rec:
                results["spherical_aberration"] = cs_rec

        # 根据轮次推荐分辨率
        max_res_rec = self._recommend_max_resolution(round_number)
        if max_res_rec:
            results["maximum_resolution"] = max_res_rec

        return results
