"""智能参数推荐引擎

根据用户问卷和实验需求，生成个性化的 cryoSPARC 参数推荐。

设计原则：
- 基于用户问卷（样品类型、目标分辨率、设备型号）
- 使用经验规则 + AI 优化
- 生成推荐理由
- 支持参数关联验证（如 box_size 应大于 particle_diameter * 1.5）

用法：
    from utils.param_recommender import recommend_parameters

    params, reasons = recommend_parameters(
        user_profile={
            "sample_type": "virus",
            "target_resolution": 3.0,
            "microscope": "Titan Krios 300kV",
            "particle_size": "large",
            "data_amount": "high"
        }
    )
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
import math


def recommend_parameters(
    user_profile: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """根据用户画像推荐参数

    Parameters
    ----------
    user_profile : dict
        用户问卷信息，包含：
        - sample_type: 样品类型 (virus, protein_complex, membrane_protein, etc.)
        - target_resolution: 目标分辨率 (Å)
        - microscope: 设备型号 (Titan Krios 300kV, Glacios 200kV, etc.)
        - particle_size: 颗粒大小 (small < 150kDa, medium 150-500kDa, large > 500kDa)
        - data_amount: 数据量 (low, medium, high)

    Returns
    -------
    tuple[dict, dict]
        (推荐参数, 推荐理由)
    """
    params = {}
    reasons = {}

    # 1. 显微镜参数推荐
    microscope = user_profile.get("microscope", "Titan Krios 300kV")

    # 加速电压
    if "300" in microscope or "Krios" in microscope:
        params["voltage"] = 300
        reasons["voltage"] = "您的设备为 Titan Krios，标配 300kV 加速电压"
    elif "200" in microscope or "Glacios" in microscope:
        params["voltage"] = 200
        reasons["voltage"] = "您的设备为 Glacios，标配 200kV 加速电压"
    else:
        params["voltage"] = 300
        reasons["voltage"] = "默认使用 300kV（最常见配置）"

    # 球差系数
    if "Krios" in microscope:
        params["Cs"] = 2.7
        reasons["Cs"] = "Titan Krios 标准球差系数为 2.7mm"
    elif "Glacios" in microscope:
        params["Cs"] = 2.7
        reasons["Cs"] = "Glacios 标准球差系数为 2.7mm"
    else:
        params["Cs"] = 2.7
        reasons["Cs"] = "现代电镜标准球差系数"

    # 2. 像素大小推荐（基于目标分辨率）
    target_res = user_profile.get("target_resolution", 3.0)

    # 经验规则：pixel_size ≈ target_resolution / 2.5 ~ 3.0
    # 高分辨率需要更小的像素
    if target_res <= 2.5:
        params["pixel_size"] = 0.85
        reasons["pixel_size"] = f"目标 {target_res}Å 高分辨率，推荐 0.85Å/px 高采样"
    elif target_res <= 3.5:
        params["pixel_size"] = 1.0
        reasons["pixel_size"] = f"目标 {target_res}Å，推荐 1.0Å/px 平衡采样与计算量"
    elif target_res <= 5.0:
        params["pixel_size"] = 1.3
        reasons["pixel_size"] = f"目标 {target_res}Å 中等分辨率，1.3Å/px 可减少数据量"
    else:
        params["pixel_size"] = 1.5
        reasons["pixel_size"] = f"目标 {target_res}Å，1.5Å/px 快速处理"

    # 3. 总剂量推荐
    sample_type = user_profile.get("sample_type", "protein_complex")

    if sample_type == "virus" or "virus" in sample_type.lower():
        params["total_dose"] = 60.0
        reasons["total_dose"] = "病毒样品较耐辐照，推荐 60 e⁻/Å²"
    elif "membrane" in sample_type.lower():
        params["total_dose"] = 50.0
        reasons["total_dose"] = "膜蛋白对辐照敏感，推荐 50 e⁻/Å² 保护结构"
    else:
        params["total_dose"] = 60.0
        reasons["total_dose"] = "标准蛋白复合物，推荐 60 e⁻/Å²"

    # 4. 颗粒直径推荐
    particle_size = user_profile.get("particle_size", "medium")

    if particle_size == "small" or "< 150" in str(particle_size):
        params["particle_diameter"] = 100
        reasons["particle_diameter"] = "小颗粒（< 150kDa），直径约 100Å"
    elif particle_size == "large" or "> 500" in str(particle_size):
        params["particle_diameter"] = 300
        reasons["particle_diameter"] = "大颗粒（> 500kDa），直径约 300Å"
    else:  # medium
        params["particle_diameter"] = 150
        reasons["particle_diameter"] = "中等颗粒（150-500kDa），直径约 150Å"

    # 5. Box size 推荐
    # 经验规则：box_size 应为 particle_diameter 的 1.5-2.0 倍，且为 2 的幂次
    min_box = params["particle_diameter"] * 1.5 / params["pixel_size"]
    ideal_box = _round_to_power_of_2(min_box)

    # 确保 box size 在合理范围内
    if ideal_box < 128:
        params["box_size"] = 128
    elif ideal_box > 512:
        params["box_size"] = 512
    else:
        params["box_size"] = ideal_box

    reasons["box_size"] = (
        f"基于颗粒直径 {params['particle_diameter']}Å 和像素大小 {params['pixel_size']}Å/px，"
        f"推荐 {params['box_size']}px（包含足够背景）"
    )

    # 6. B-factor 推荐
    if target_res <= 3.0:
        params["bfactor"] = -100
        reasons["bfactor"] = "高分辨率结构，使用轻度锐化 -100Å²"
    elif target_res <= 5.0:
        params["bfactor"] = -150
        reasons["bfactor"] = "中等分辨率，使用标准锐化 -150Å²"
    else:
        params["bfactor"] = -200
        reasons["bfactor"] = "低分辨率结构，使用强锐化 -200Å² 增强细节"

    # 7. 数据处理策略
    data_amount = user_profile.get("data_amount", "medium")
    if data_amount == "high":
        reasons["_strategy"] = "💡 数据量大，建议启用 GPU 加速和并行处理"
    elif data_amount == "low":
        reasons["_strategy"] = "💡 数据量较少，建议谨慎筛选颗粒质量"

    return params, reasons


def _round_to_power_of_2(value: float) -> int:
    """将数值向上取整到最近的 2 的幂次

    Examples:
        150 -> 256
        300 -> 512
        80 -> 128
    """
    return 2 ** math.ceil(math.log2(value))


def validate_parameters(params: Dict[str, Any]) -> Tuple[bool, list[str]]:
    """验证参数合理性

    Returns:
        (是否通过, 警告信息列表)
    """
    warnings = []

    # 1. Box size 应大于 particle_diameter 的 1.2 倍
    if "box_size" in params and "particle_diameter" in params and "pixel_size" in params:
        min_box_angstrom = params["particle_diameter"] * 1.2
        actual_box_angstrom = params["box_size"] * params["pixel_size"]

        if actual_box_angstrom < min_box_angstrom:
            warnings.append(
                f"⚠️ Box size 可能太小：当前 {params['box_size']}px "
                f"（{actual_box_angstrom:.0f}Å）< 颗粒直径 {params['particle_diameter']}Å 的 1.2 倍"
            )

    # 2. 像素大小与目标分辨率的匹配
    if "pixel_size" in params and "target_resolution" in params:
        nyquist = params["pixel_size"] * 2  # Nyquist 极限
        if params["target_resolution"] < nyquist:
            warnings.append(
                f"⚠️ 目标分辨率 {params['target_resolution']}Å 超过 Nyquist 极限 "
                f"{nyquist:.1f}Å，建议减小像素或降低分辨率预期"
            )

    # 3. 总剂量检查
    if "total_dose" in params:
        if params["total_dose"] > 100:
            warnings.append("⚠️ 总剂量 > 100 e⁻/Å²，可能造成严重辐照损伤")
        elif params["total_dose"] < 30:
            warnings.append("⚠️ 总剂量 < 30 e⁻/Å²，信噪比可能不足")

    passed = len(warnings) == 0
    return passed, warnings


# 预设参数模板（用于快速开始）
PARAM_TEMPLATES = {
    "high_res_small_particle": {
        "name": "高分辨率小颗粒（< 150kDa, 目标 < 3Å）",
        "params": {
            "voltage": 300,
            "Cs": 2.7,
            "pixel_size": 0.85,
            "total_dose": 60.0,
            "particle_diameter": 100,
            "box_size": 256,
            "bfactor": -100,
        }
    },
    "standard_protein": {
        "name": "标准蛋白复合物（150-500kDa, 目标 3-4Å）",
        "params": {
            "voltage": 300,
            "Cs": 2.7,
            "pixel_size": 1.0,
            "total_dose": 60.0,
            "particle_diameter": 150,
            "box_size": 320,
            "bfactor": -150,
        }
    },
    "large_virus": {
        "name": "大病毒颗粒（> 500kDa, 目标 4-6Å）",
        "params": {
            "voltage": 300,
            "Cs": 2.7,
            "pixel_size": 1.3,
            "total_dose": 60.0,
            "particle_diameter": 300,
            "box_size": 384,
            "bfactor": -150,
        }
    },
}


def get_template(template_name: str) -> Dict[str, Any]:
    """获取预设参数模板"""
    return PARAM_TEMPLATES.get(template_name, PARAM_TEMPLATES["standard_protein"])
