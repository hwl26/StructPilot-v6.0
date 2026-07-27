"""测试 cryoSPARC workflow 生成器的脚本

用真实参数生成 workflow JSON，验证格式正确性。
"""

import json
import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.cryosparc_workflow import generate_cryosparc_workflow, workflow_to_json_str
from components.cryosparc_workflow_config import (
    BOX_SIZE_ALIGNMENT,
    _apply_quick_config,
    _calculate_derived_parameters,
    _initial_overrides,
    _partition_parameters,
    _quick_config_errors,
    _sync_derived_parameters,
    _template_validation_errors,
    _value_key,
    _workflow_validation_errors,
    _workflow_validation_warnings,
    _workflow_connector_markup,
    _workflow_lanes,
    _job_levels,
)


def test_onboarding_values_seed_real_workflow_jobs():
    overrides = _initial_overrides({
        "particle_diameter": 160,
        "mask_diameter": 190,
        "num_classes_2d": 80,
        "pixel_size": 1.12,
    })
    assert overrides["J1"]["psize_A"] == 1.12
    assert overrides["J4"]["diameter"] == 160
    assert overrides["J4"]["diameter_max"] == 160
    assert overrides["J6"]["class2D_K"] == 80
    assert overrides["J9"]["class2D_window_inner_A"] == 190


def test_workflow_rejects_invalid_particle_diameter_range():
    values = {"J4": {"diameter": 160, "diameter_max": 100}}
    assert _workflow_validation_errors(values) == ["J4 颗粒直径上限不能小于下限。"]


def test_workflow_parameters_are_partitioned_by_experiment_dependency():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    required, recommended = _partition_parameters(template["jobs"]["J1"])
    assert [key for key, _ in required] == ["blob_paths"]
    assert [key for key, _ in recommended] == [
        "psize_A", "accel_kv", "cs_mm", "total_dose_e_per_A2"
    ]

    required, recommended = _partition_parameters(template["jobs"]["J5"])
    assert required == []
    assert [key for key, _ in recommended] == [
        "compute_num_gpus", "box_size_pix", "bin_size_pix"
    ]


def test_workflow_visual_layout_keeps_branches_apart_and_draws_merges():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    jobs = template["jobs"]
    levels = _job_levels(jobs)
    lane_count, lanes = _workflow_lanes(jobs, levels)

    assert lane_count >= 3
    assert lanes["J3"] != lanes["J4"]
    assert lanes["J1"] == lane_count // 2
    split_markup = _workflow_connector_markup(
        jobs, levels, lanes, lane_count, levels["J2"]
    )
    merge_markup = _workflow_connector_markup(
        jobs, levels, lanes, lane_count, levels["J4"]
    )
    carry_markup = _workflow_connector_markup(
        jobs, levels, lanes, lane_count, levels["J7"]
    )
    assert split_markup.count("<path") == 2
    assert merge_markup.count("<path") == 2
    assert 'class="cswf-edge--carry"' in carry_markup
    assert ">J3</text>" in carry_markup


def test_linked_parameters_use_calibrated_formula_and_sixteen_pixel_alignment():
    calibrated = _calculate_derived_parameters(100, 0.96)
    assert calibrated["box_size_pix"] == 240

    derived = _calculate_derived_parameters(160, 0.96)
    assert derived["class2D_window_inner_A"] == 177.8
    assert derived["box_size_pix"] == 384
    assert derived["box_size_pix"] % BOX_SIZE_ALIGNMENT == 0
    assert derived["pixel_size_A"] == 0.96


def test_linked_parameters_are_written_to_all_matching_jobs():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    store = {
        "J1": {"psize_A": 0.96},
        "J4": {"diameter": 160, "diameter_max": 100},
    }
    derived = _sync_derived_parameters(template, store)
    assert derived["box_size_pix"] == 384
    assert store["J4"]["diameter_max"] == 160
    assert store["J5"]["box_size_pix"] == 384
    assert store["J8"]["box_size_pix"] == 384
    assert store["J6"]["class2D_window_inner_A"] == 177.8
    assert store["J9"]["class2D_window_inner_A"] == 177.8


def test_quick_config_populates_every_real_template_target():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    store = {
        job_id: {
            key: parameter["value"]
            for key, parameter in job["parameters"].items()
        }
        for job_id, job in template["jobs"].items()
    }
    derived = _apply_quick_config(
        template,
        store,
        diameter_A=120,
        blob_paths=" /project/new/*.mrc ",
        gpu_count=3,
    )
    assert store["J1"]["blob_paths"] == "/project/new/*.mrc"
    assert store["J4"]["diameter"] == 120
    assert store["J4"]["diameter_max"] == 120
    assert derived["box_size_pix"] == 288
    for job_id, job in template["jobs"].items():
        if "compute_num_gpus" in job["parameters"]:
            assert store[job_id]["compute_num_gpus"] == 3


def test_quick_config_rejects_unsafe_or_invalid_inputs():
    assert _quick_config_errors(120, "/project/data/*.mrc", 4) == []
    errors = _quick_config_errors(0, "bad\npath", 0)
    assert "蛋白直径必须是大于 0 的数值。" in errors
    assert "数据路径不能包含换行或空字符。" in errors
    assert "GPU 数量必须是 1 到 64 之间的整数。" in errors


def test_template_structure_and_non_blocking_warnings_are_checked():
    malformed = {"jobs": {"J1": {"jobType": "x", "groups": [["J9.out", "in"]], "parameters": {}}}}
    assert "J1 引用了不存在的上游 Job。" in _template_validation_errors(malformed)
    warnings = _workflow_validation_warnings({"J1": {"blob_paths": "/project/one.mrc"}})
    assert warnings == ["数据路径未包含通配符；如果只需导入单个文件可以忽略此提示。"]


def test_quick_stage_shows_only_three_inputs_then_opens_editor():
    app_path = Path(__file__).resolve().parent / "workflow_quick_app.py"
    at = AppTest.from_file(app_path, default_timeout=10).run()
    assert not list(at.exception)
    assert [widget.label for widget in at.number_input] == ["蛋白直径 (Å) *", "GPU 数量 *"]
    assert [widget.label for widget in at.text_input] == ["数据路径 *"]
    next(button for button in at.button if button.label == "一键生成 Workflow").click().run()
    assert not list(at.exception)
    assert any(button.label == "J1" for button in at.button)


def test_required_workflow_values_are_validated_before_export():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    values = {
        "J1": {
            "blob_paths": "",
            "psize_A": None,
            "accel_kv": 300,
            "cs_mm": 2.7,
            "total_dose_e_per_A2": 50,
        },
        "J4": {"diameter": 160, "diameter_max": 160},
    }
    errors = _workflow_validation_errors(values, template)
    assert "J1 数据路径为必填项。" in errors
    assert "J1 像素大小必须是大于 0 的数值。" in errors


def test_manual_derived_overrides_are_validated_before_export():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    values = {
        "J1": {
            "blob_paths": "/project/data/*.mrc",
            "psize_A": 0.96,
            "accel_kv": 300,
            "cs_mm": 2.7,
            "total_dose_e_per_A2": 50,
        },
        "J4": {"diameter": 160, "diameter_max": 160},
        "J5": {"box_size_pix": 325},
        "J6": {"class2D_window_inner_A": None},
        "J8": {"box_size_pix": 326},
        "J9": {"class2D_window_inner_A": 178},
    }
    errors = _workflow_validation_errors(values, template)
    assert "J5 Extraction box size必须是偶数像素。" in errors
    assert "J6 Circular mask diameter必须是大于 0 的数值。" in errors


def test_workflow_editor_keeps_values_when_switching_job_cards():
    app_path = Path(__file__).resolve().parent / "workflow_editor_app.py"
    at = AppTest.from_file(app_path, default_timeout=10).run()
    assert not list(at.exception)
    next(button for button in at.button if button.label == "J4").click().run()
    assert not list(at.exception)
    values = {widget.label: widget.value for widget in at.number_input}
    assert values["颗粒直径下限 (A) *"] == 160
    diameter_widget = next(
        widget for widget in at.number_input if widget.label == "颗粒直径下限 (A) *"
    )
    assert diameter_widget.placeholder == "根据蛋白实际直径填写，例如 120"
    assert [tab.label for tab in at.tabs] == ["必填输入", "推荐与高级"]

    next(button for button in at.button if button.label == "J5").click().run()
    values = {widget.label: widget for widget in at.number_input}
    assert values["GPU 数量"].value == 4
    assert values["Extraction box size (pix)"].value == 384
    assert values["Extraction box size (pix)"].disabled is True

    next(button for button in at.button if button.label == "J6").click().run()
    values = {widget.label: widget for widget in at.number_input}
    assert values["2D 类别数"].value == 80
    assert values["Circular mask diameter (A)"].value == 177.8
    assert values["Circular mask diameter (A)"].disabled is True

    auto_toggle = next(
        widget for widget in at.checkbox
        if widget.label == "自动换算 box size 与 circular mask"
    )
    auto_toggle.set_value(False).run()
    values = {widget.label: widget for widget in at.number_input}
    assert values["Circular mask diameter (A)"].disabled is False


def test_workflow_editor_recalculates_linked_jobs_after_diameter_change():
    app_path = Path(__file__).resolve().parent / "workflow_editor_app.py"
    at = AppTest.from_file(app_path, default_timeout=10).run()
    next(button for button in at.button if button.label == "J4").click().run()
    diameter_widget = next(
        widget for widget in at.number_input if widget.label == "颗粒直径下限 (A) *"
    )
    diameter_widget.set_value(180).run()
    values = {widget.label: widget.value for widget in at.number_input}
    assert values["颗粒直径上限 (A)"] == 180

    next(button for button in at.button if button.label == "J5").click().run()
    values = {widget.label: widget.value for widget in at.number_input}
    assert values["Extraction box size (pix)"] == 432

    next(button for button in at.button if button.label == "J6").click().run()
    values = {widget.label: widget.value for widget in at.number_input}
    assert values["Circular mask diameter (A)"] == 200


def test_template_export_preserves_cryoSPARC_2d_topology_and_edits():
    """The visual editor must export the supplied workflow, not a simplified clone."""
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    overrides = {
        "J1": {"psize_A": 1.12},
        "J4": {"diameter": 135},
        "J5": {"box_size_pix": 288},
        "J6": {"class2D_K": 160},
    }

    result = generate_cryosparc_workflow(
        workflow={"steps": []},
        params={"_workflow_template": template, "_workflow_values": overrides},
        workflow_name="Edited 2D workflow",
        software="cryosparc",
    )

    assert result is not None
    assert result["title"] == "Edited 2D workflow"
    assert set(result["jobs"]) == set(template["jobs"])
    assert result["jobs"]["J5"]["groups"] == template["jobs"]["J5"]["groups"]
    assert result["jobs"]["J1"]["parameters"]["psize_A"]["value"] == 1.12
    assert result["jobs"]["J4"]["parameters"]["diameter"]["value"] == 135
    assert result["jobs"]["J5"]["parameters"]["box_size_pix"]["value"] == 288
    assert result["jobs"]["J6"]["parameters"]["class2D_K"]["value"] == 160
    assert result["createdBy"] == ""

    required_fields = {"value", "locked", "visible", "flagged", "notes"}
    for job in result["jobs"].values():
        for parameter in job["parameters"].values():
            assert required_fields <= set(parameter)
            assert parameter["locked"] is False


def test_template_export_rejects_type_confusion_and_broken_topology():
    template_path = Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    try:
        generate_cryosparc_workflow(
            workflow={"steps": []},
            params={
                "_workflow_template": template,
                "_workflow_values": {"J5": {"box_size_pix": "not-an-integer"}},
            },
            software="cryosparc",
        )
    except ValueError as exc:
        assert "J5.box_size_pix must be an integer" in str(exc)
    else:
        raise AssertionError("invalid parameter type was accepted")

    broken = json.loads(json.dumps(template))
    broken["jobs"]["J5"]["groups"] = [["J99.particles", "particles"]]
    try:
        generate_cryosparc_workflow(
            workflow={"steps": []},
            params={"_workflow_template": broken, "_workflow_values": {}},
            software="cryosparc",
        )
    except ValueError as exc:
        assert "references a missing source" in str(exc)
    else:
        raise AssertionError("broken workflow topology was accepted")


def test_full_workflow(tmp_path):
    """测试完整的 cryoSPARC workflow（从导入到 2D 分类）"""
    # 真实参数（对照你提供的样本）
    params = {
        "movies_path": "/project/data/movies/*.tif",
        "gainref_path": "/project/data/gain_reference.mrc",
        "pixel_size": 0.41,
        "voltage": 300,
        "Cs": 2.7,
        "total_dose": 60,
        "particle_diameter": 110,
        "particle_diameter_max": 160,
        "box_size": 320,
        "class2d_num_classes": 100,
    }

    # 推荐工作流（完整流程）
    workflow = {
        "steps": [
            "cp_01",  # Import Movies
            "cp_02",  # Motion Correction
            "cp_03",  # CTF Estimation
            "cp_03b", # Curate Exposures
            "cp_04",  # Blob Picker
            "cp_04c", # Inspect Picks
            "cp_05",  # Extract
            "cp_06",  # 2D Classification
            "cp_06b", # Select 2D
        ],
        "skip_steps": [],
    }

    # 生成 workflow
    workflow_json = generate_cryosparc_workflow(
        workflow=workflow,
        params=params,
        workflow_name="StructPilot_Test_Workflow",
        software="cryosparc",
    )

    assert workflow_json, "Workflow 生成失败"

    # 验证必需字段
    required_top_level = ["_id", "title", "workflowVersion", "jobs", "parents"]
    for field in required_top_level:
        assert field in workflow_json, f"缺少顶层字段：{field}"
    assert workflow_json["createdBy"] == ""

    # 验证 jobs 结构
    jobs = workflow_json.get("jobs", {})
    assert jobs, "jobs 字典为空"

    # 验证每个 job 的必需字段
    for job_id, job_data in jobs.items():
        required_job_fields = ["title", "description", "jobType", "groups", "individualResults", "parameters"]
        for field in required_job_fields:
            assert field in job_data, f"Job {job_id} 缺少字段：{field}"

        # 验证参数格式
        for param_name, param_obj in job_data["parameters"].items():
            required_param_fields = ["value", "locked", "visible", "flagged", "notes"]
            for field in required_param_fields:
                assert field in param_obj, f"Job {job_id} 参数 {param_name} 缺少字段：{field}"

    # 输出 JSON
    json_str = workflow_to_json_str(workflow_json, indent=2)
    output_path = tmp_path / "test_workflow.json"
    output_path.write_text(json_str, encoding="utf-8")

    print("✅ Workflow 生成成功！")
    print(f"📁 已保存到：{output_path}")
    print(f"📊 生成了 {len(jobs)} 个 job")
    print("\n--- 生成的 job 列表 ---")
    for job_id, job_data in jobs.items():
        job_type = job_data["jobType"]
        num_params = len(job_data["parameters"])
        print(f"  {job_id}: {job_type} ({num_params} 个参数)")



def test_relion_handoff(tmp_path):
    """测试 RELION→cryoSPARC 接力路线"""
    params = {
        "micrographs_path": "/fs/pool/pool-train/EM_data/20260702_CHL_MUNC13D_STXBP2_STX/MotionCorr/job002/Movies/*EER.mrc",
        "pixel_size": 0.96,
        "voltage": 300,
        "Cs": 2.7,
        "total_dose": 50,
        "particle_diameter": 220,
        "box_size": 382,
    }

    workflow = {
        "steps": [
            "cp_01b",  # Import Micrographs（RELION输出）
            "cp_03",   # CTF Estimation
            "cp_03b",  # Curate
            "cp_04b",  # Template Picker
            "cp_05",   # Extract
            "cp_06",   # 2D Class
        ],
        "skip_steps": [],
    }

    workflow_json = generate_cryosparc_workflow(
        workflow=workflow,
        params=params,
        workflow_name="StructPilot_RELION_Handoff",
        software="cryosparc",
    )

    assert workflow_json, "RELION 接力 workflow 生成失败"

    json_str = workflow_to_json_str(workflow_json, indent=2)
    output_path = tmp_path / "test_workflow_relion.json"
    output_path.write_text(json_str, encoding="utf-8")

    print("✅ RELION 接力 workflow 生成成功！")
    print(f"📁 已保存到：{output_path}")


if __name__ == "__main__":
    import tempfile
    print("=" * 60)
    print("测试 1：完整 cryoSPARC workflow（从 Movies 开始）")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as _tmp:
        _out = Path(_tmp)
        test_full_workflow(_out)
        print("\n" + "=" * 60)
        print("测试 2：RELION→cryoSPARC 接力 workflow")
        print("=" * 60)
        test_relion_handoff(_out)

    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)
