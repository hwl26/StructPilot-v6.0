"""Regression tests for the current onboarding workflow recommender."""

import pytest

from components.onboarding_v2 import _confirmed_params_from_workflow, _generate_workflow_recommendation


@pytest.mark.parametrize(
    ("profile", "last_step", "voltage"),
    [
        ({"goal": "质检", "sample_type": "膜蛋白", "microscope": "Krios 300kV", "resolution_target": "粗筛"}, "cp_03", 300),
        ({"goal": "2D分类", "sample_type": "膜蛋白", "microscope": "Krios 300kV", "resolution_target": "中等"}, "cp_06", 300),
        ({"goal": "3D重构", "sample_type": "大型复合物", "microscope": "Krios 300kV", "resolution_target": "高分辨"}, "cp_11", 300),
        ({"goal": "2D分类", "sample_type": "小型蛋白", "microscope": "Arctica 200kV", "resolution_target": "中等"}, "cp_06", 200),
    ],
)
def test_workflow_recommendation_scenarios(profile, last_step, voltage):
    result = _generate_workflow_recommendation(profile)
    assert result["steps"][-1] == last_step
    assert result["params"]["voltage"] == voltage
    assert isinstance(result["skip_steps"], list)
    assert result["reason"]


def test_edited_onboarding_params_are_copied_to_formal_parameter_state():
    workflow = {"params": {"particle_diameter": 160, "mask_diameter": 190, "num_classes_2d": 80}}
    confirmed = _confirmed_params_from_workflow(workflow)
    assert confirmed["particle_diameter"] == 160
    assert confirmed["mask_diameter"] == 190
    assert confirmed["num_classes_2d"] == 80
    confirmed["particle_diameter"] = 200
    assert workflow["params"]["particle_diameter"] == 160
