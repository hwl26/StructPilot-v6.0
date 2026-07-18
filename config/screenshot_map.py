"""Screenshot folder mapping for StructPilot guide assets.

This is the single source of truth used by ``utils.assets``. External screenshots
are preferred when ``STRUCTPILOT_SCREENSHOTS_DIR`` points to a full image set;
otherwise StructPilot falls back to the bundled ``assets/guides`` folders.
"""

from __future__ import annotations

from typing import Dict, List


SCREENSHOT_FOLDERS: Dict[str, List[str]] = {
    "cp_01": ["cp_01_import"],
    "cp_02": ["cp_02_motion_correction"],
    "cp_03": ["cp_03_ctf_estimation"],
    "cp_04": [
        "cp_04_blob_picker",
        "cp_04_template_picker",
        "cp_04_topaz_picker",
    ],
    "cp_05": ["cp_05_extract"],
    "cp_06": ["cp_06_2d_classification"],
    "cp_07": ["cp_07_select_2d"],
    "cp_08": ["cp_08_ab_initio"],
    "cp_09": ["cp_09_heterogeneous"],
    "cp_10": ["cp_10_homogeneous"],
    "cp_11": ["cp_11_non_uniform"],
    "cp_12": ["cp_12_model_validation"],
}

ALL_CHECKPOINT_IDS: List[str] = [f"cp_{i:02d}" for i in range(1, 13)]


def folders_for(cp_id: str) -> List[str]:
    """Return screenshot folders for one checkpoint."""
    return list(SCREENSHOT_FOLDERS.get(cp_id, []))


def has_screenshots(cp_id: str) -> bool:
    """Return whether the checkpoint has configured screenshot folders."""
    return bool(SCREENSHOT_FOLDERS.get(cp_id))
