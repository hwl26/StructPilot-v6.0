"""测试 cryoSPARC workflow 生成器的脚本

用真实参数生成 workflow JSON，验证格式正确性。
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.cryosparc_workflow import generate_cryosparc_workflow, workflow_to_json_str


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

    required_fields = {"value", "locked", "visible", "flagged", "notes"}
    for job in result["jobs"].values():
        for parameter in job["parameters"].values():
            assert required_fields <= set(parameter)
            assert parameter["locked"] is False


def test_full_workflow():
    """测试完整的 cryoSPARC workflow（从导入到 2D 分类）"""
    # 真实参数（对照你提供的样本）
    params = {
        "movies_path": "/home/wangjiangyun/EM_data/20251116_wtx2/*.tif",
        "gainref_path": "/home/wangjiangyun/EM_data/20251116_wtx2/SuperRef_20251116_wtx2_0001_usable.mrc",
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

    if not workflow_json:
        print("❌ Workflow 生成失败")
        return False

    # 验证必需字段
    required_top_level = ["_id", "title", "workflowVersion", "jobs", "parents"]
    for field in required_top_level:
        if field not in workflow_json:
            print(f"❌ 缺少顶层字段：{field}")
            return False

    # 验证 jobs 结构
    jobs = workflow_json.get("jobs", {})
    if not jobs:
        print("❌ jobs 字典为空")
        return False

    # 验证每个 job 的必需字段
    for job_id, job_data in jobs.items():
        required_job_fields = ["title", "description", "jobType", "groups", "individualResults", "parameters"]
        for field in required_job_fields:
            if field not in job_data:
                print(f"❌ Job {job_id} 缺少字段：{field}")
                return False

        # 验证参数格式
        for param_name, param_obj in job_data["parameters"].items():
            required_param_fields = ["value", "locked", "visible", "flagged", "notes"]
            for field in required_param_fields:
                if field not in param_obj:
                    print(f"❌ Job {job_id} 参数 {param_name} 缺少字段：{field}")
                    return False

    # 输出 JSON
    json_str = workflow_to_json_str(workflow_json, indent=2)
    output_path = Path(__file__).parent / "test_workflow.json"
    output_path.write_text(json_str, encoding="utf-8")

    print("✅ Workflow 生成成功！")
    print(f"📁 已保存到：{output_path}")
    print(f"📊 生成了 {len(jobs)} 个 job")
    print("\n--- 生成的 job 列表 ---")
    for job_id, job_data in jobs.items():
        job_type = job_data["jobType"]
        num_params = len(job_data["parameters"])
        print(f"  {job_id}: {job_type} ({num_params} 个参数)")

    return True


def test_relion_handoff():
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

    if not workflow_json:
        print("❌ RELION 接力 workflow 生成失败")
        return False

    json_str = workflow_to_json_str(workflow_json, indent=2)
    output_path = Path(__file__).parent / "test_workflow_relion.json"
    output_path.write_text(json_str, encoding="utf-8")

    print("✅ RELION 接力 workflow 生成成功！")
    print(f"📁 已保存到：{output_path}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("测试 1：完整 cryoSPARC workflow（从 Movies 开始）")
    print("=" * 60)
    test1_ok = test_full_workflow()

    print("\n" + "=" * 60)
    print("测试 2：RELION→cryoSPARC 接力 workflow")
    print("=" * 60)
    test2_ok = test_relion_handoff()

    print("\n" + "=" * 60)
    if test1_ok and test2_ok:
        print("🎉 所有测试通过！")
        print("\n📖 接下来，请将生成的 JSON 文件导入 cryoSPARC 进行实际验证：")
        print("  1. 登录 cryoSPARC Web 界面")
        print("  2. 进入 Projects → Import Workflow")
        print("  3. 上传 test_workflow.json 或 test_workflow_relion.json")
        print("  4. 检查 workflow 是否正确加载、job 连接是否正确")
    else:
        print("❌ 部分测试失败，请检查错误信息")
    print("=" * 60)
