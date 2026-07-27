from pathlib import Path

from components.cryosparc_workflow_config import render_workflow_config


render_workflow_config(
    Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json",
    initial_params={
        "particle_diameter": 120,
        "micrographs_path": "/project/data/*.mrc",
        "gpu_count": 4,
    },
)
