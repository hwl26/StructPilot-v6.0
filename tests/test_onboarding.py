#!/usr/bin/env python
"""需求问答功能快速测试。

模拟用户选择不同选项，验证工作流生成逻辑。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from components.onboarding import _generate_workflow_recommendation


def test_scenario(name: str, profile: dict) -> None:
    """测试一个场景。"""
    print(f"\n{'=' * 60}")
    print(f"场景：{name}")
    print(f"{'=' * 60}")
    print(f"用户画像：{profile}")

    result = _generate_workflow_recommendation(profile)

    print(f"\n推荐流程：")
    print(f"  需要步骤：{result['steps']}")
    print(f"  跳过步骤：{result['skip_steps']}")
    print(f"\n预填参数：")
    for k, v in result['params'].items():
        print(f"  {k}: {v}")
    print(f"\n推荐理由：")
    print(f"  {result['reason']}")


def main():
    print("=" * 60)
    print("StructPilot 需求问答功能测试")
    print("=" * 60)

    # 场景1：初学者，只做质检
    test_scenario(
        "初学者-仅质检",
        {
            "goal": "质检",
            "sample_type": "膜蛋白",
            "microscope": "Krios 300kV",
            "resolution_target": "粗筛",
            "has_mentor": "有",
        },
    )

    # 场景2：常见场景，2D分类
    test_scenario(
        "常见场景-2D分类",
        {
            "goal": "2D分类",
            "sample_type": "膜蛋白",
            "microscope": "Krios 300kV",
            "resolution_target": "中等",
            "has_mentor": "有",
        },
    )

    # 场景3：完整3D重构
    test_scenario(
        "完整流程-3D重构",
        {
            "goal": "3D重构",
            "sample_type": "大分子复合体",
            "microscope": "Krios 300kV",
            "resolution_target": "高分辨",
            "has_mentor": "有",
        },
    )

    # 场景4：不同设备（Arctica）
    test_scenario(
        "不同设备-Arctica",
        {
            "goal": "2D分类",
            "sample_type": "小蛋白",
            "microscope": "Arctica 200kV",
            "resolution_target": "中等",
            "has_mentor": "独立探索",
        },
    )

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有场景测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
