"""StructPilot v6.0 — 独立性自检脚本（无需 Streamlit / LLM / 联网）。

验证范围：
  1. 配置层：config/settings + config/screenshot_map 可导入、路径解析正确；
  2. 截图映射：cp_01..cp_12 可从外部目录或内置兜底截图解析；
  3. 截图解析：resolve_screenshot 能从外部根解析 guide 截图路径；
  4. 官方文档：knowledge_index.json 含 13 条 [官方文档] 条目（B 阶段集成）；
  5. 检索内核：中文 tokenizer 修复 + lexical 去封顶（无 Key 模式命中官方文档）。

运行：cd StructPilot_v6 && python verify_v5.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 将工程根加入 sys.path，确保可导入 config / utils / knowledge_base
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


print("=" * 64)
print("StructPilot v6.0 自检")
print("=" * 64)

# ---------- 1. 配置层 ----------
print("\n[1] 配置层 (config/settings + config/screenshot_map)")
try:
    from config import settings, screenshot_map

    check("config 包可导入", True)
    check(
        "截图外部目录或内置兜底目录可用",
        settings.SCREENSHOT_ROOT.exists() or settings.BUNDLED_GUIDE_ROOT.exists(),
        f"external={settings.SCREENSHOT_ROOT.exists()} bundled={settings.BUNDLED_GUIDE_ROOT}",
    )
    covered = [f"cp_{i:02d}" for i in range(1, 13)]
    check(
        "映射覆盖 cp_01..cp_12",
        all(cp in screenshot_map.SCREENSHOT_FOLDERS for cp in covered),
        f"key 数={len(screenshot_map.SCREENSHOT_FOLDERS)}",
    )
    # cp_04 应有 3 个 picker 变体（映射规则关键特征）
    check(
        "cp_04 含 3 个 picker 变体",
        screenshot_map.SCREENSHOT_FOLDERS.get("cp_04", []) == [
            "cp_04_blob_picker",
            "cp_04_template_picker",
            "cp_04_topaz_picker",
        ],
    )
except Exception as exc:
    check("config 包可导入", False, f"异常: {exc}")

# ---------- 2. 截图映射（外部优先 / 内置降级） ----------
print("\n[2] 截图映射 — 外部优先 / 内置降级可达性")
if "screenshot_map" in dir() and "settings" in dir():
    for cp_id in [f"cp_{i:02d}" for i in range(1, 13)]:  # cp_01..cp_12
        folders = screenshot_map.SCREENSHOT_FOLDERS.get(cp_id, [])
        external_ok = any((settings.SCREENSHOT_ROOT / f).exists() for f in folders)
        bundled_ok = any((settings.BUNDLED_GUIDE_ROOT / f).exists() for f in folders)
        ok = external_ok or bundled_ok
        source = "external" if external_ok else "bundled" if bundled_ok else "missing"
        if ok:
            check(f"{cp_id} 截图可达", True, f"source={source} folders={folders}")
        else:
            try:
                from utils.assets import collect_checkpoint_screenshots

                shots = collect_checkpoint_screenshots(cp_id)
                check(f"{cp_id} 截图缺失时可降级", shots == [], f"source={source} folders={folders}")
            except Exception as exc:
                check(f"{cp_id} 截图缺失时可降级", False, f"异常: {exc}")

# ---------- 3. 截图解析 ----------
print("\n[3] 截图解析 (utils.assets.resolve_screenshot)")
try:
    from utils.assets import resolve_screenshot, collect_checkpoint_screenshots

    sample = "assets/guides/cp_01_import/01.1 relion import.png"
    resolved = resolve_screenshot(sample)
    check(
        "resolve_screenshot 命中外部或内置截图",
        resolved != "" and Path(resolved).exists(),
        f"-> {resolved}",
    )
    shots = collect_checkpoint_screenshots("cp_03")
    check("collect_checkpoint_screenshots(cp_03) 返回截图", len(shots) >= 1, f"n={len(shots)}")
    # 全部步骤汇总
    total = sum(len(collect_checkpoint_screenshots(cp)) for cp in [f"cp_{i:02d}" for i in range(1, 13)])
    check("cp_01..cp_12 累计截图 >= 12", total >= 12, f"total={total}")
except Exception as exc:
    check("utils.assets 解析", False, f"异常: {exc}")

# ---------- 4. 官方文档集成 ----------
print("\n[4] 官方文档集成 (B 阶段)")
idx_path = ROOT / "knowledge_base" / "knowledge_index.json"
if idx_path.exists():
    try:
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        docs = data if isinstance(data, list) else data.get("docs", [])
        official = [d for d in docs if str(d.get("doc_id", "")).startswith("[官方文档]")]
        check("knowledge_index 含 13 条官方文档", len(official) >= 13, f"n={len(official)}")
        # 覆盖检查：每个 cp 至少 1 条（checkpoint_id 或 tags 兜底）
        covered = set()
        for d in official:
            cid = d.get("checkpoint_id")
            if cid:
                covered.add(cid)
            for t in (d.get("tags") or []):
                if isinstance(t, str) and t.startswith("cp_"):
                    covered.add(t)
        missing = [f"cp_{i:02d}" for i in range(1, 13) if f"cp_{i:02d}" not in covered]
        check("官方文档覆盖全部 12 步（含 tags 兜底）", not missing, f"missing={missing}")
    except Exception as exc:
        check("官方文档统计", False, f"异常: {exc}")
else:
    check("knowledge_index 存在", False, "文件缺失")

# ---------- 5. 检索内核（中文修复 + lexical 去封顶） ----------
print("\n[5] 检索内核 — 中文 tokenizer 修复 + lexical 去封顶")
try:
    import numpy as np  # noqa: F401
    from knowledge_base.retriever import KnowledgeRetriever, _tokenize, _lexical_search

    # 5a. 中文 tokenizer：修复后"用户管理"应拆出中文 token
    toks = _tokenize("cryosparc 用户管理怎么创建")
    cn_hit = any(t in {"用户", "管理", "创建"} for t in toks)
    check("中文 tokenizer 提取中文词", cn_hit, f"tokens含中文={cn_hit}")

    # 5b. lexical 去封顶：单 token 命中的 checkpoint(权重1.0) 不再封顶挤占
    corpus = [
        ("cp_01", "数据导入 pixel size 电压", 1.0),
        ("[官方文档] RELION-SPA·Preprocessing (url)", "Preprocessing pixel size 0.885 dose 1.277 defocus 5000 50000", 0.95),
    ]
    res = _lexical_search(corpus, "Preprocessing pixel size dose", top_k=3)
    official_in = any("Preprocessing" in did for did, _, _ in res)
    check("lexical 检索命中官方文档（多 token 覆盖优先）", official_in, f"top={[d for d,_,_ in res]}")

    # 5c. 无 Key 模式：实际检索能命中官方文档（构建语料）
    class _FakeLLM:
        embedding_enabled = False
    retr = KnowledgeRetriever(_FakeLLM())
    hits = retr.search("RELION Preprocessing pixel size dose", top_k=5)
    official_hit = any("官方文档" in did for did, _, _ in hits)
    check("无 Key 模式检索命中官方文档", official_hit, f"hits={len(hits)}")
except ImportError:
    check("检索内核测试", False, "numpy 未安装，跳过（运行时需 pip install numpy）")
except Exception as exc:
    check("检索内核测试", False, f"异常: {exc}")

# ---------- 汇总 ----------
print("\n" + "=" * 64)
print(f"结果：PASS={PASS}  FAIL={FAIL}")
print("=" * 64)
sys.exit(1 if FAIL else 0)

