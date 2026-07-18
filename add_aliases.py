#!/usr/bin/env python3
"""
为 guide_cards.json 中的参数添加别名，解决参数显示问题
"""
import json
from pathlib import Path

# 参数别名映射表
ALIASES = {
    "pixel_size": ["apix", "angpix", "pixel_spacing"],
    "voltage": ["accelerating_voltage", "acceleration_voltage", "kv"],
    "spherical_aberration": ["cs", "cs_value"],
    "dose_per_frame": ["total_dose", "dose"],
    "b_factor": ["bfactor", "b_factor_motioncorr"],
    "box_size": ["boxsize"],
    "defocus_range_min": ["defocus_range", "min_defocus"],
    "defocus_range_max": ["max_defocus"],
    "num_classes": ["number_of_classes", "n_classes"],
    "num_iterations": ["number_of_iterations", "n_iterations"],
    "circular_mask_diameter": ["mask_diameter", "particle_diameter"],
    "min_separation": ["min_separation_dist"],
    "max_diameter": ["max_particle_diameter"],
    "min_diameter": ["min_particle_diameter"],
    "fourier_crop": ["fourier_crop_box_size"],
    "use_gpu": ["num_gpus"],
}

def add_aliases_to_guide_cards(input_path: str, output_path: str):
    """为 guide_cards.json 添加别名"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cards = data.get('cards', [])
    modified_count = 0

    for card in cards:
        for substep in card.get('substeps', []):
            for param in substep.get('parameters', []):
                param_id = param.get('id', '')
                if param_id in ALIASES:
                    # 添加 aliases 字段
                    param['aliases'] = ALIASES[param_id]
                    modified_count += 1
                    print(f"[OK] Added aliases for '{param_id}': {ALIASES[param_id]}")

    # 保存修改后的文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] Modified {modified_count} parameters")
    print(f"[SUCCESS] Saved to: {output_path}")

if __name__ == "__main__":
    import shutil
    input_file = "knowledge_base/guides/guide_cards.json"
    output_file = "knowledge_base/guides/guide_cards.json"
    backup_file = "knowledge_base/guides/guide_cards.json.backup"

    # 备份原文件
    shutil.copy(input_file, backup_file)
    print(f"[BACKUP] Created: {backup_file}")

    # 添加别名
    add_aliases_to_guide_cards(input_file, output_file)
