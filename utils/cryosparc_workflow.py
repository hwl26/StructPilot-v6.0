"""StructPilot v6.0 — CryoSPARC Workflow JSON 生成器（官方格式）。

根据 CryoSPARC v4.4+ 官方 Workflow 格式生成可导入的 JSON。
参考官方示例结构并验证字段完整性。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
_CHECKPOINTS_PATH = BASE_DIR / "knowledge_base" / "flows" / "pipeline_checkpoints.json"

# CryoSPARC job_type 映射
_JOB_TYPE_MAP: dict[str, str] = {
    "cp_01": "import_movies",
    "cp_02": "patch_motion_correction_multi",
    "cp_03": "patch_ctf_estimation_multi",
    "cp_04": "blob_picker_gpu",
    "cp_05": "extract_micrographs_multi",
    "cp_06": "class_2D_new",
    "cp_07": "homo_abinit",
    "cp_08": "hetero_refine",
    "cp_09": "homo_refine_new",
    "cp_10": "ctf_refinement",
    "cp_11": "sharpen",
    "cp_12": "local_resolution",
}

# 数据流连接（source_job, output_slot → target_job, input_slot）
_CONNECTIONS: dict[str, list[tuple[str, str]]] = {
    "cp_02": [("cp_01", "imported_movies", "movies")],
    "cp_03": [("cp_02", "micrographs", "exposures")],
    "cp_04": [("cp_03", "exposures", "micrographs")],
    "cp_05": [
        ("cp_03", "exposures", "micrographs"),
        ("cp_04", "particles", "particles"),
    ],
    "cp_06": [("cp_05", "particles", "particles")],
    "cp_07": [("cp_06", "particles_selected", "particles")],
    "cp_08": [
        ("cp_06", "particles_selected", "particles"),
        ("cp_07", "volume_class_0", "volume"),
    ],
    "cp_09": [
        ("cp_08", "particles_class_0", "particles"),
        ("cp_08", "volume_class_0", "volume"),
    ],
    "cp_10": [
        ("cp_09", "particles", "particles"),
        ("cp_09", "volume", "volume"),
    ],
    "cp_11": [
        ("cp_10", "particles", "particles"),
        ("cp_10", "volume", "volume"),
    ],
    "cp_12": [("cp_11", "map_sharp", "volume")],
}


def _param(value: Any, locked: bool = False, visible: bool = True, flagged: bool = False) -> dict:
    """生成 CryoSPARC 参数对象格式。"""
    return {
        "value": value,
        "locked": locked,
        "visible": visible,
        "flagged": flagged,
        "notes": "",
    }


def _load_checkpoints() -> dict[str, dict]:
    """加载 checkpoint 元数据。"""
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
) -> dict | None:
    """生成 CryoSPARC v4.4+ 官方格式的 Workflow JSON。

    Parameters
    ----------
    workflow : dict
        StructPilot 推荐工作流，格式：{"steps": [...], "skip_steps": [...]}
    params : dict
        用户采集参数（pixel_size, voltage, Cs, particle_diameter, box_size等）
    workflow_name : str
        Workflow 显示名称
    software : str
        软件标识（非 cryosparc 时返回 None）

    Returns
    -------
    dict | None
        CryoSPARC Workflow JSON 对象，可直接序列化后导入 CryoSPARC GUI。
        格式兼容 CryoSPARC v4.4+
    """
    if software.lower() not in ("cryosparc", "cryosparc4", "cs"):
        return None

    steps = [s for s in workflow.get("steps", []) if s not in workflow.get("skip_steps", [])]
    if not steps:
        return None

    checkpoints = _load_checkpoints()
    jobs: dict[str, dict] = {}
    job_id_map: dict[str, str] = {}  # cp_id → J1/J2/...

    # 生成 Job 节点
    for idx, cp_id in enumerate(steps):
        job_type = _JOB_TYPE_MAP.get(cp_id)
        if not job_type:
            continue

        job_id = f"J{idx + 1}"
        job_id_map[cp_id] = job_id
        cp_meta = checkpoints.get(cp_id, {})

        # 构建 groups（数据流连接）
        groups: list[list[str]] = []
        if cp_id in _CONNECTIONS:
            for src_cp, src_slot, dst_slot in _CONNECTIONS[cp_id]:
                if src_cp in job_id_map:
                    groups.append([f"{job_id_map[src_cp]}.{src_slot}", dst_slot])

        # 构建 parameters
        job_params: dict[str, dict] = {}

        # cp_01: Import Movies
        if cp_id == "cp_01":
            job_params = {
                "blob_paths": _param(None, flagged=True),
                "gainref_path": _param(None, flagged=True),
                "psize_A": _param(params.get("pixel_size")),
                "accel_kv": _param(params.get("voltage")),
                "cs_mm": _param(params.get("Cs")),
                "total_dose_e_per_A2": _param(params.get("total_dose")),
            }

        # cp_02: Motion Correction
        elif cp_id == "cp_02":
            job_params = {
                "compute_num_gpus": _param(1),
                "bfactor": _param(params.get("bfactor", 150)),
            }

        # cp_03: CTF Estimation
        elif cp_id == "cp_03":
            job_params = {
                "compute_num_gpus": _param(1),
            }

        # cp_04: Blob Picker
        elif cp_id == "cp_04":
            diameter = params.get("particle_diameter", 150)
            job_params = {
                "diameter": _param(diameter),
                "diameter_max": _param(diameter * 1.5),
                "min_distance": _param(0.6),
                "use_ellipse": _param(True),
            }

        # cp_05: Extract
        elif cp_id == "cp_05":
            box_size = params.get("box_size", 256)
            job_params = {
                "compute_num_gpus": _param(2),
                "box_size_pix": _param(box_size),
                "bin_size_pix": _param(min(box_size // 2, 120)),
            }

        # cp_06: 2D Classification
        elif cp_id == "cp_06":
            job_params = {
                "class2D_K": _param(100),
                "class2D_max_res": _param(5),
                "compute_num_gpus": _param(2),
                "compute_use_ssd": _param(False),
            }

        # cp_07: Ab-Initio
        elif cp_id == "cp_07":
            job_params = {
                "abinit_K": _param(3),
                "abinit_max_res": _param(10),
                "compute_use_ssd": _param(False),
            }

        # cp_08: Hetero Refine
        elif cp_id == "cp_08":
            job_params = {
                "compute_use_ssd": _param(False),
            }

        # cp_09: Homogeneous Refine
        elif cp_id == "cp_09":
            job_params = {
                "compute_use_ssd": _param(False),
                "refine_res_align_max": _param(3),
            }

        # cp_10: CTF Refinement
        elif cp_id == "cp_10":
            job_params = {}

        # cp_11: Sharpen
        elif cp_id == "cp_11":
            job_params = {}

        # cp_12: Local Resolution
        elif cp_id == "cp_12":
            job_params = {}

        jobs[job_id] = {
            "title": "",
            "description": "",
            "jobType": job_type,
            "groups": groups,
            "individualResults": [],
            "parameters": job_params,
        }

    # 组装 Workflow 对象（CryoSPARC 官方格式）
    workflow_json = {
        "_id": uuid.uuid4().hex[:24],  # 24位16进制字符串
        "category": "Default",  # 使用 Default 而不是自定义分类
        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",  # 毫秒精度
        "createdBy": "000000000000000000000000",  # 假用户ID（导入后CryoSPARC会替换）
        "csVersion": "v4.4.1",
        "description": (
            f"Generated by StructPilot v6.0. "
            f"Steps: {len(jobs)}. "
            f"Params: pixel_size={params.get('pixel_size')}A, "
            f"voltage={params.get('voltage')}kV, "
            f"Cs={params.get('Cs')}mm."
        ),
        "jobs": jobs,
        "parents": {},
        "title": workflow_name,
        "workflowVersion": "1.0.0",
    }

    return workflow_json


def workflow_to_json_str(workflow_json: dict, indent: int = 2) -> str:
    """序列化为 JSON 字符串。"""
    return json.dumps(workflow_json, ensure_ascii=False, indent=indent)
