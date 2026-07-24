"""StructPilot v6.0 — CryoSPARC Workflow JSON 生成器。

根据用户的推荐工作流和采集参数，生成可直接导入 CryoSPARC 的 Workflow JSON。
CryoSPARC v4 Workflow 格式：Nodes（Job定义）+ Connections（数据流）+ Params（参数预填）

导入方式：CryoSPARC GUI → 右侧 Workflows → Import Workflow → 上传 JSON 文件
导入后：一键 Apply 批量创建所有 Job 并自动连线，省去每步手动操作。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
_CHECKPOINTS_PATH = BASE_DIR / "knowledge_base" / "flows" / "pipeline_checkpoints.json"

# --------------------------------------------------------------------------- #
# CryoSPARC job_type 映射（checkpoint_id → cryoSPARC job type string）
# 来源：cryoSPARC v4 文档，confirmed job type names
# --------------------------------------------------------------------------- #
_JOB_TYPE_MAP: dict[str, str] = {
    "cp_01": "import_movies",
    "cp_02": "patch_motion_correction",
    "cp_03": "patch_ctf_estimation",
    "cp_04": "blob_picker",
    "cp_05": "extract_micrographs",
    "cp_06": "class_2D",
    "cp_07": "ab_initio_reconstruction",
    "cp_08": "hetero_refine",
    "cp_09": "homogeneous_refine",
    "cp_10": "ctf_refinement",
    "cp_11": "sharpening",
    "cp_12": "local_resolution_estimation",
}

# 数据流连接：(source_cp_id, output_slot) → (target_cp_id, input_slot)
# 描述 CryoSPARC 中各 Job 的数据依赖关系
_CONNECTIONS = [
    ("cp_01", "imported_movies",       "cp_02", "movies"),
    ("cp_02", "micrographs",           "cp_03", "micrographs"),
    ("cp_03", "exposures",             "cp_04", "micrographs"),
    ("cp_04", "picked_particles",      "cp_05", "particles"),
    ("cp_03", "exposures",             "cp_05", "micrographs"),
    ("cp_05", "particles",             "cp_06", "particles"),
    ("cp_06", "particles_selected",    "cp_07", "particles"),
    ("cp_07", "volume_map",            "cp_08", "volume"),
    ("cp_06", "particles_selected",    "cp_08", "particles"),
    ("cp_08", "particles",             "cp_09", "particles"),
    ("cp_08", "volume",                "cp_09", "volume_refmap"),
    ("cp_09", "particles",             "cp_10", "particles"),
    ("cp_09", "volume",                "cp_10", "volume"),
    ("cp_10", "particles",             "cp_11", "particles"),
    ("cp_10", "volume",                "cp_11", "volume"),
    ("cp_11", "map_sharp",             "cp_12", "volume"),
]

# CryoSPARC 参数名映射：StructPilot 内部 key → cryoSPARC param name
_PARAM_MAP: dict[str, dict[str, str]] = {
    "cp_01": {
        "pixel_size": "psize_A",
        "voltage": "accel_kv",
        "Cs": "cs_mm",
        "total_dose": "total_dose_e_per_A2",
        "gain_reference": "gainref_path",
    },
    "cp_02": {
        "bfactor": "bfactor",
        "patch_size": "patch_size_x",
        "dose_weighting": "dose_weight_enable",
        "group_n_frames": "group_n_frames",
    },
    "cp_03": {
        "max_resolution_ctf": "res_max_fit",
        "min_resolution_ctf": "res_min_fit",
        "ctf_fit_range_low": "df_search_min",
        "ctf_fit_range_high": "df_search_max",
    },
    "cp_04": {
        "particle_diameter": "diameter",
        "min_separation": "min_dist",
        "low_threshold": "lowpass_res",
    },
    "cp_05": {
        "box_size": "box_size_pix",
        "particle_diameter": "cs_particle_diam_A",
        "fourier_crop": "fourier_crop_to_box_size_pix",
    },
    "cp_06": {
        "num_classes_2d": "num_classes",
        "particle_diameter": "diam_A",
        "max_resolution_2d": "class2D_K",
        "num_iterations": "class2D_num_iterations",
    },
    "cp_07": {
        "num_ab_initio": "num_classes",
        "initial_resolution": "abinit_init_res",
        "symmetry": "abinit_sym",
    },
    "cp_08": {
        "num_classes_3d": "num_classes",
        "mask_diameter": "ref_mask_radius_A",
    },
    "cp_09": {
        "mask_diameter": "ref_mask_radius_A",
        "refine_res_init": "refine_res_init",
        "refine_res_gsfsc_split": "refine_res_gsfsc_split",
    },
    "cp_10": {
        "refine_defocus_per_group": "refine_defocus_per_group",
        "refine_ctf_global_refine": "refine_ctf_global_refine",
    },
    "cp_11": {
        "sharpening_bfactor": "sharpen_bfactor",
    },
    "cp_12": {
        "locres_sampling": "locres_sampling",
    },
}


def _load_checkpoints() -> dict[str, dict]:
    """加载 checkpoint 元数据，按 id 索引。"""
    try:
        data = json.loads(_CHECKPOINTS_PATH.read_text(encoding="utf-8"))
        return {cp["checkpoint_id"]: cp for cp in data}
    except Exception:
        return {}


def generate_cryosparc_workflow(
    workflow: dict,
    params: dict,
    workflow_name: str = "StructPilot_Workflow",
    software: str = "cryosparc",
) -> dict:
    """生成 CryoSPARC Workflow JSON。

    Parameters
    ----------
    workflow
        StructPilot 推荐工作流：{"steps": [...], "skip_steps": [...]}
    params
        用户采集参数（pixel_size, voltage, particle_diameter 等）
    workflow_name
        Workflow 名称（显示在 CryoSPARC 右侧面板）
    software
        当前软件（非 cryosparc 时返回空，因为 RELION 格式不同）

    Returns
    -------
    dict
        可序列化为 JSON 的 CryoSPARC Workflow 对象。
    """
    if software.lower() not in ("cryosparc", "cryosparc4", "cs"):
        return {}

    steps = [s for s in workflow.get("steps", []) if s not in workflow.get("skip_steps", [])]
    checkpoints = _load_checkpoints()

    nodes = []
    job_uid_map: dict[str, str] = {}  # cp_id → uid

    # ── 生成 Job 节点 ──────────────────────────────────────
    for idx, cp_id in enumerate(steps):
        job_type = _JOB_TYPE_MAP.get(cp_id, "")
        if not job_type:
            continue

        uid = f"J{idx + 1}"
        job_uid_map[cp_id] = uid
        cp_meta = checkpoints.get(cp_id, {})
        cp_cn = cp_meta.get("checkpoint_cn", cp_id)

        # 构建参数覆盖（只填 StructPilot 知道的值）
        param_overrides: dict[str, Any] = {}
        param_name_map = _PARAM_MAP.get(cp_id, {})
        for sp_key, cs_key in param_name_map.items():
            if sp_key in params and params[sp_key] is not None:
                param_overrides[cs_key] = params[sp_key]

        node = {
            "uid": uid,
            "job_type": job_type,
            "title": f"{uid} {cp_meta.get('checkpoint_cn', job_type).replace(' ', '_')}",
            "description": cp_cn,
            "params_override": param_overrides,
            "connections": [],
        }
        nodes.append(node)

    # ── 生成连接 ───────────────────────────────────────────
    connections = []
    for src_cp, src_slot, dst_cp, dst_slot in _CONNECTIONS:
        if src_cp not in job_uid_map or dst_cp not in job_uid_map:
            continue  # 跳过不在本次工作流中的连接
        connections.append({
            "src_job_uid": job_uid_map[src_cp],
            "src_output_group_name": src_slot,
            "dest_job_uid": job_uid_map[dst_cp],
            "dest_input_group_name": dst_slot,
        })

    # ── 组装 Workflow 对象 ─────────────────────────────────
    workflow_json = {
        "workflow_type": "template",
        "title": workflow_name,
        "description": (
            f"由 StructPilot v6.0 自动生成。\n"
            f"包含 {len(nodes)} 个 Job。\n"
            f"参数预设：pixel_size={params.get('pixel_size', '?')} Å, "
            f"voltage={params.get('voltage', '?')} kV, "
            f"particle_diameter={params.get('particle_diameter', '?')} Å"
        ),
        "jobs": nodes,
        "connections": connections,
    }

    return workflow_json


def workflow_to_json_str(workflow_json: dict, indent: int = 2) -> str:
    return json.dumps(workflow_json, ensure_ascii=False, indent=indent)
