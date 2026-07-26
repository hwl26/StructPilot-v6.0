from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    r"C:\Users\17706\.codex\attachments\17d1bb21-af8d-47fa-9ae4-164fc74f25d9\pasted-text.txt"
)
TARGET = ROOT / "knowledge_base" / "lab_experience_kb.json"

AUTHOR_ROLES = {
    "王立群": "教授",
    "小玲": "博士三年级",
    "李明": "博士后",
    "张宇": "硕士二年级",
    "陈昊": "联合培养博士生",
}

# lab_029 is reserved for the requested 2D stripe-class verification case.
ID_BY_DATE = {
    "2024-03-15": "lab_012",
    "2024-09-22": "lab_013",
    "2025-06-08": "lab_014",
    "2026-02-14": "lab_015",
    "2024-05-20": "lab_016",
    "2024-11-03": "lab_017",
    "2025-03-18": "lab_018",
    "2025-12-10": "lab_019",
    "2026-06-05": "lab_020",
    "2024-07-12": "lab_021",
    "2024-12-05": "lab_022",
    "2025-04-20": "lab_023",
    "2025-08-31": "lab_024",
    "2026-03-07": "lab_025",
    "2024-10-18": "lab_026",
    "2025-02-09": "lab_027",
    "2025-11-22": "lab_028",
    "2025-07-29": "lab_029",
    "2025-01-30": "lab_030",
    "2025-09-14": "lab_031",
}

DETAILS = {
    "2024-03-15": {
        "title": "统一组内 CTF 曝光筛选标准",
        "software": "cryoSPARC",
        "step": "cp_03",
        "symptoms": ["CTF 合格标准不一致", "组内数据质量参差", "曝光筛选口径不同"],
        "related_params": {"ctf_fit_resolution": "≤ 5 Å", "astigmatism": "< 2000 Å", "retention_rate": "≥ 80%"},
        "success_rate": "",
        "tags": ["CTF", "曝光筛选", "质量标准", "组内协作"],
    },
    "2024-09-22": {
        "title": "2D 分类质量差时优先回查上游颗粒挑选",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["2D 好类比例低", "过度调整 2D 参数", "Topaz 训练集过小"],
        "related_params": {"topaz_training_particles": 200, "good_class_ratio": "8%"},
        "success_rate": "定位到 Topaz 训练集仅 200 颗粒导致过拟合",
        "tags": ["2D 分类", "Topaz", "上游排查", "过拟合"],
    },
    "2025-06-08": {
        "title": "box size 过大导致 2D 条纹类",
        "software": "cryoSPARC",
        "step": "cp_05",
        "symptoms": ["box size 过大", "2D 分类条纹类", "经验参数硬搬"],
        "related_params": {"box_size": "约 256 px", "particle_diameter": "约 110 Å", "box_to_particle_ratio": "1.2~1.5", "particle_box_occupancy": "≤ 60%"},
        "success_rate": "box size 从 320 px 调至约 256 px 后条纹类明显改善",
        "tags": ["box size", "box size 怎么选", "颗粒提取", "2D 条纹类", "像素尺寸"],
    },
    "2026-02-14": {
        "title": "Falcon4 数据未启用 ePT 导致高频信息损失",
        "software": "cryoSPARC",
        "step": "cp_03",
        "symptoms": ["Falcon4 分辨率偏差", "ePT 未启用", "高频信息损失"],
        "related_params": {"ept_enabled": True, "detector": "Falcon4"},
        "success_rate": "启用 ePT 后拟合分辨率提升约 0.3~0.5 Å",
        "tags": ["Falcon4", "ePT", "CTF", "高频信息"],
    },
    "2024-05-20": {
        "title": "EER 导入时混淆 super-res 与 counting 像素",
        "software": "cryoSPARC",
        "step": "cp_01",
        "symptoms": ["导入像素尺寸错误", "super-res/counting 混淆", "后续参数连锁错误"],
        "related_params": {"pixel_size_mode": "super-res/counting", "pixel_size": "读取采集元数据"},
        "success_rate": "定位导入像素错误后重新处理，避免继续沿用错误 box 和 mask",
        "tags": ["EER", "数据导入", "像素尺寸", "元数据"],
    },
    "2024-11-03": {
        "title": "运动校正漂移过大时先排查采集硬件状态",
        "software": "RELION",
        "step": "cp_02",
        "symptoms": ["微图漂移过大", "调参无改善", "采集批次异常"],
        "related_params": {"total_motion_median": "12 Å", "b_factor": "多组测试", "patch_size": "多组测试"},
        "success_rate": "确认液氮液面异常并剔除不可挽救批次",
        "tags": ["运动校正", "漂移", "采集日志", "硬件状态"],
    },
    "2025-03-18": {
        "title": "Topaz 训练集分布偏差导致跨 defocus 泛化差",
        "software": "cryoSPARC",
        "step": "cp_04",
        "symptoms": ["Topaz 泛化差", "训练集 defocus 单一", "不同微图挑选差异大"],
        "related_params": {"topaz_training_particles": 1000, "defocus_range": "1.0~2.5 µm", "sampling": "按 defocus 和冰厚分层"},
        "success_rate": "覆盖 1.0~2.5 µm defocus 后模型泛化明显提高",
        "tags": ["Topaz", "训练集", "defocus", "分层抽样"],
    },
    "2025-07-29": {
        "title": "2D 分类大量条纹类的组合参数排查",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["2D 分类条纹类", "颗粒 average 不清晰", "Force max 影响收敛"],
        "related_params": {"box_size": "320→256 px", "mask_diameter": "300→240 px", "force_max_over_poses": False, "num_iterations": "40→80"},
        "success_rate": "关闭 Force max、缩小 mask/box 并增加迭代后问题解决",
        "tags": ["2D 分类", "条纹类", "Force max", "mask diameter", "box size"],
    },
    "2025-12-10": {
        "title": "手动 B-factor 过激导致锐化假密度",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["手动 B-factor 过激", "椒盐状假密度", "锐化结果不可靠"],
        "related_params": {"manual_b_factor": -80, "auto_b_factor": -45, "resolution": "7.2→5.8 Å"},
        "success_rate": "自动 B-factor（约 -45）比手动 -80 更可靠",
        "tags": ["B-factor", "锐化", "假密度", "参数边界"],
    },
    "2026-06-05": {
        "title": "用检查清单减少新人重复踩坑",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["新人重复犯错", "经验分散", "合格标准不统一"],
        "related_params": {},
        "success_rate": "形成导入到 2D 分类检查清单后，重复犯错明显减少",
        "tags": ["检查清单", "知识沉淀", "新人培训", "流程标准化"],
    },
    "2024-07-12": {
        "title": "用对照实验确定 EER grouping",
        "software": "cryoSPARC",
        "step": "cp_01",
        "symptoms": ["EER grouping 缺少依据", "担心分组损失信息", "计算效率低"],
        "related_params": {"eer_grouping": [4, 6, 8, 12], "recommended_grouping": 8},
        "success_rate": "grouping=8 与 grouping=4 分辨率差 <0.1 Å，计算约快一倍",
        "tags": ["EER", "grouping", "对照实验", "计算效率"],
    },
    "2024-12-05": {
        "title": "用矩阵测试选择运动校正 B-factor 与 patch",
        "software": "RELION",
        "step": "cp_02",
        "symptoms": ["运动校正参数凭感觉", "B-factor 与 patch 组合不稳定", "低颗粒密度数据"],
        "related_params": {"b_factor": "150~200", "patch_size": "5×5", "tested_b_factor": [100, 150, 200, 300], "tested_patch": ["3×3", "5×5", "7×7"]},
        "success_rate": "矩阵测试显示 B-factor 150~200、patch 5×5 对多数数据更稳定",
        "tags": ["运动校正", "B-factor", "patch", "矩阵测试"],
    },
    "2025-04-20": {
        "title": "按信噪比与成本选择 Blob Picker 或 Topaz",
        "software": "cryoSPARC",
        "step": "cp_04",
        "symptoms": ["挑选策略缺少量化依据", "Blob 假阳性高", "Topaz 有训练成本"],
        "related_params": {"topaz_training_particles": 2000, "blob_false_positive_rate": "约 45%", "topaz_false_positive_rate": "约 22%", "topaz_training_time": "约 20 分钟"},
        "success_rate": "同批数据中 Topaz 假阳性率约 22%，Blob Picker 约 45%",
        "tags": ["Blob Picker", "Topaz", "假阳性率", "策略选择"],
    },
    "2025-08-31": {
        "title": "两轮 bin 策略降低大数据集 2D 分类成本",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["2D 分类计算成本高", "大颗粒数数据集", "一次性全量处理低效"],
        "related_params": {"round_1": "bin4 + crop 128 px", "round_2": "bin2"},
        "success_rate": "两轮策略节省约 65% 计算时间，并保留更多好类",
        "tags": ["2D 分类", "bin", "crop", "计算成本"],
    },
    "2026-03-07": {
        "title": "CTF 精修应在颗粒富集和模型稳定后进行",
        "software": "cryoSPARC",
        "step": "cp_03",
        "symptoms": ["CTF 精修时机不明", "过早精修分辨率下降", "小数据集收益不明显"],
        "related_params": {"global_ctf_refinement": "3D 初始模型后", "local_ctf_particle_threshold": "≥ 50000"},
        "success_rate": "在模型稳定后执行通常提升约 0.2~0.3 Å；少于 5 万颗粒时 Local CTF 收益不明显",
        "tags": ["CTF 精修", "Global CTF", "Local CTF", "时机选择"],
    },
    "2024-10-18": {
        "title": "Blob Picker 直径范围过宽导致假阳性过高",
        "software": "cryoSPARC",
        "step": "cp_04",
        "symptoms": ["Blob Picker 假阳性高", "冰晶碎片被挑选", "碳膜边缘被挑选"],
        "related_params": {"particle_diameter_range": "真实尺寸 ±20%", "min_separation": "按粒径调整", "max_local_maxima": "按微图密度调整"},
        "success_rate": "假阳性率由目测超过 60% 降至约 25%",
        "tags": ["Blob Picker", "粒径范围", "假阳性", "Min separation"],
    },
    "2025-02-09": {
        "title": "2D class 数不足导致好类被垃圾颗粒淹没",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["class 数过少", "好类不清晰", "垃圾颗粒混入好类"],
        "related_params": {"num_classes": "20→50", "particle_count": "5~20 万"},
        "success_rate": "class 数从 20 增至 50 后好类明显变清晰",
        "tags": ["2D 分类", "num classes", "好类筛选", "颗粒数量"],
    },
    "2025-11-22": {
        "title": "2D 取向覆盖差可能源于样品制备而非参数",
        "software": "cryoSPARC",
        "step": "cp_06",
        "symptoms": ["2D 取向覆盖差", "优先取向", "误判为参数问题"],
        "related_params": {"orientation_coverage": "检查类别投影方向", "grid_preparation": "优化冷冻/载网条件"},
        "success_rate": "优化载网制备条件后取向覆盖明显改善",
        "tags": ["2D 分类", "优先取向", "样品制备", "问题归因"],
    },
    "2025-01-30": {
        "title": "不同探测器数据格式混用导致导入失败",
        "software": "cryoSPARC",
        "step": "cp_01",
        "symptoms": ["K3 与 Falcon4 格式混用", "数据导入失败", "mdoc 元数据未解析"],
        "related_params": {"k3_format": ".tiff + .mdoc", "falcon4_format": "EER", "project_isolation": "按探测器/格式分项目"},
        "success_rate": "按格式单独建项目并提取 mdoc 关键字段后成功导入",
        "tags": ["K3", "Falcon4", "数据格式", "mdoc", "导入"],
    },
    "2025-09-14": {
        "title": "导入像素与 bin 后像素混淆导致粒子截断",
        "software": "cryoSPARC",
        "step": "cp_05",
        "symptoms": ["粒子密度截断", "box size 不匹配", "导入像素与 bin 后像素混淆"],
        "related_params": {"import_pixel_size": "counting 值", "box_size": "按 bin 后像素重新计算", "binning": "全链路一致"},
        "success_rate": "重新导入并按 bin 后像素计算 box 后解决粒子截断",
        "tags": ["像素尺寸", "bin", "box size", "颗粒提取"],
    },
}


def parse_source(text: str):
    appendix_marker = "附录：关键参数速查"
    body = text.split(appendix_marker, 1)[0]
    pattern = re.compile(
        r"(?ms)^([0-9]{4}-[0-9]{2}-[0-9]{2})\s*·\s*(王立群|小玲|李明|张宇|陈昊)\s*\n"
        r"(.*?)(?=^[0-9]{4}-[0-9]{2}-[0-9]{2}\s*·\s*(?:王立群|小玲|李明|张宇|陈昊)\s*$|\Z)"
    )
    parsed = []
    for match in pattern.finditer(body):
        item_date, author, block = match.group(1), match.group(2), match.group(3).strip()
        parts = re.match(r"(?ms)^(.*?)\s*问题：(.*?)\s*解决思路：(.*?)\s*心得：(.*?)\s*$", block)
        if not parts:
            raise ValueError(f"无法解析三段式经验：{item_date} {author}")
        parsed.append(
            {
                "date": item_date,
                "author": author,
                "symptoms_text": parts.group(1).strip(),
                "problem": parts.group(2).strip(),
                "solution": parts.group(3).strip(),
                "lesson": parts.group(4).strip(),
            }
        )
    return parsed


def build_entry(raw):
    detail = DETAILS[raw["date"]]
    return {
        "id": ID_BY_DATE[raw["date"]],
        "title": detail["title"],
        "source": "lab_experience",
        "source_type": "lab_exp",
        "author": raw["author"],
        "author_role": AUTHOR_ROLES[raw["author"]],
        "date": raw["date"],
        "status": "approved",
        "reviewer": "王立群",
        "software": detail["software"],
        "step": detail["step"],
        "category": "postmortem",
        "symptoms": detail["symptoms"],
        "symptoms_text": raw["symptoms_text"],
        "solution": raw["solution"],
        "lesson": raw["lesson"],
        "related_params": detail["related_params"],
        "success_rate": detail["success_rate"],
        "tags": detail["tags"],
        "tier": "lab",
        "verified": True,
        "last_verified": "2026-07-26",
    }


def build_summary_entry(source_text: str):
    appendix = source_text.split("附录：关键参数速查", 1)[1]
    table_text = appendix.split("本文档由课题组成员", 1)[0].strip()
    return {
        "id": "lab_032",
        "title": "cp_01~cp_06 关键参数速查",
        "source": "lab_experience",
        "source_type": "lab_exp",
        "author": "王立群",
        "author_role": "教授",
        "date": "2026-07-26",
        "status": "approved",
        "reviewer": "王立群",
        "software": "cryoSPARC",
        "step": "cp_01~cp_06",
        "category": "summary",
        "symptoms": ["参数速查", "流程检查清单", "组内经验值"],
        "symptoms_text": "课题组从数据导入到 2D 分类的关键参数速查附录。",
        "solution": table_text,
        "lesson": "速查值用于建立检查起点，实际设置仍须结合探测器、像素尺寸、粒径、冰厚和数据质量复核。",
        "related_params": {
            "eer_grouping": "4~8（Falcon4 建议 8）",
            "motion_b_factor": "150~200",
            "motion_patch": "5×5",
            "ctf_fit_resolution": "≤ 5 Å",
            "astigmatism": "< 2000 Å",
            "blob_diameter": "粒径 ±20%",
            "topaz_training_particles": "≥ 2000",
            "box_size": "粒径 1.2~1.5 倍，粒径占比 ≤ 60%",
            "num_classes": ">20万→100；5~20万→50；<5万→20~30",
            "num_iterations": "60~80，并关闭 Force max",
        },
        "success_rate": "",
        "tags": ["参数速查", "cp_01~cp_06", "组内标准", "质量控制", "检查清单"],
        "tier": "lab",
        "verified": True,
        "last_verified": "2026-07-26",
    }


def main():
    source_text = SOURCE.read_text(encoding="utf-8")
    parsed = parse_source(source_text)
    if len(parsed) != 20:
        raise ValueError(f"预期 20 条经验，实际解析到 {len(parsed)} 条")
    dates = {item["date"] for item in parsed}
    if dates != set(DETAILS) or dates != set(ID_BY_DATE):
        raise ValueError("日期映射与解析结果不一致")

    data = json.loads(TARGET.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) < 11:
        raise ValueError("现有经验库结构不符合预期")
    original_entries = entries[:11]
    original_ids = [entry.get("id") for entry in original_entries]
    if original_ids != [f"lab_{i:03d}" for i in range(1, 12)]:
        raise ValueError("现有 lab_001~lab_011 不连续，停止导入")

    new_entries = [build_entry(item) for item in parsed]
    new_entries.sort(key=lambda item: int(item["id"].split("_")[1]))
    all_entries = original_entries + new_entries + [build_summary_entry(source_text)]
    ids = [entry.get("id") for entry in all_entries]
    if ids != [f"lab_{i:03d}" for i in range(1, 33)]:
        raise ValueError("最终 ID 必须为 lab_001~lab_032")

    data["entries"] = all_entries
    meta = data.setdefault("meta", {})
    meta["total_entries"] = len(all_entries)
    meta["last_updated"] = "2026-07-26"
    meta["pending_review"] = 0
    meta["description"] = "课题组私有经验库；原有 11 条保持不变，新增 20 条复盘经验和 1 条 cp_01~cp_06 参数速查汇总。"
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"imported={len(new_entries)} total={len(all_entries)} target={TARGET}")


if __name__ == "__main__":
    main()
