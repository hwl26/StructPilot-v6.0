from pathlib import Path

import streamlit as st

from components.cryosparc_workflow_config import render_workflow_config


st.session_state.setdefault("cswf_quick_ready", True)
render_workflow_config(
    Path(__file__).resolve().parent.parent / "knowledge_base" / "workflows" / "2d_classification.json",
    initial_params={
        "particle_diameter": 160,
        "micrographs_path": "/project/data/*.mrc",
        "gpu_count": 4,
        "mask_diameter": 190,
        "num_classes_2d": 80,
    },
)
