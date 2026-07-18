# StructPilot V4 变更日志

> 日期：2026-07-10
> 基线：StructPilot_v3（成熟可运行核心，已含 A 域双轨路由 / B 域 UI / B 阶段官方文档集成 / C 域性能优化）
> 目标：从零重建为 V4，在架构设计、代码质量、功能完整性三方面提升，并保留全部既有交互路径与「上级目录」截图映射规则。

## 新增模块（V4 架构改进核心）

- `config/__init__.py`：配置包标识。
- `config/settings.py`：集中化路径与运行参数。
  - `BASE_DIR` / `RUNTIME_ROOT`（独立 `StructPilot_v4_runtime`）。
  - `SCREENSHOT_ROOT`：默认指向上级目录 `StructPilot_Visual_UI/StructPilot_Visual_UI/images`，可被 `STRUCTPILOT_SCREENSHOTS_DIR` 覆盖。
  - `BUNDLED_GUIDE_ROOT`（`assets/guides` 兜底）。
  - 提供 `is_external_screenshots_available()` / `resolve_screenshot_root()`。
- `config/screenshot_map.py`：`cp_NN → [文件夹名]` 映射规则单一事实来源（固化上级目录命名约定，cp_04 含 3 个 picker 变体）。
- `utils/assets.py`：`resolve_screenshot()`（外部根优先 → 工程内兜底 → BASE_DIR 相对）与 `collect_checkpoint_screenshots(cp_id)`（按映射扫描文件夹），全程优雅降级。
- `verify_v4.py`：独立性自检（无需 Streamlit / LLM / 联网），覆盖配置、截图映射、官方文档、检索内核。

## 修改文件

- `main.py`
  - `resolve_guide_asset()`：改为委托 `utils.assets.resolve_screenshot`，外部截图优先、原 `assets/guides` 兜底（保留铁律 10）。
  - `RUNTIME_ROOT` 默认目录由 `StructPilot_v2_runtime` 调整为 `StructPilot_v4_runtime`，与 V3 隔离。
- `.env.example`：新增 `STRUCTPILOT_SCREENSHOTS_DIR` / `STRUCTPILOT_RUNTIME_DIR` 说明。
- `start.bat`：标题与提示更新为 v4.0。
- `README.md`：重写为 V4 权威文档（含 10 铁律兼容性、截图映射表、V4 改进、自检说明）。

## 保留 / 未改动（确保功能完整性）

- 12 步工作流 `pipeline_checkpoints.json`（cp_01..cp_12）、cryoSPARC / RELION 双软件切换。
- LangGraph 编排（`graph/app.py`、`graph/state.py`）、各 agent（Navigator / LLM / Memory / SOP / Expert / SmartQA）。
- 检索内核 RAG（`knowledge_base/retriever.py`）：中文 tokenizer 修复 + lexical 去封顶保留，无 Key 模式命中官方文档已验证。
- 13 条官方文档集成（`knowledge_base/ingest_official_docs.py` + `knowledge_index.json` + `config/corpus_cache.json` 含 13 条官方文档）。
- 聊天卡片 / 截图画廊 / 参数面板 / 阶段工作区（`ui/components/`）。
- 报告导出、会话记忆、健康自检等既有能力。

## 验证结果

`python verify_v4.py` → **PASS=24 / FAIL=0**
- 配置层导入与路径解析 ✓
- cp_01..cp_11 外部截图全部可达（保留映射规则）✓
- `resolve_screenshot` / `collect_checkpoint_screenshots` 命中外部目录（累计 31 张）✓
- 官方文档 13 条、覆盖全部 12 步（含 tags 兜底）✓
- 检索内核：中文 tokenizer 修复 ✓、lexical 去封顶（多 token 官方文档优先）✓、无 Key 模式检索命中官方文档 ✓
- 全部 45 个 Python 模块 `py_compile` 通过 ✓
