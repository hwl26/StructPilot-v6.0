# StructPilot v5.1 — Cryo-EM 流程导航 Copilot

StructPilot 是一个本地可运行的 cryo-EM 单颗粒处理流程导航助手。它按 12 个检查点（cp_01 数据导入到 cp_12 模型构建与验证）引导用户完成处理，提供 SOP、参数建议、故障排查、概念解释、图像/语音输入和可选 LLM 增强。

v5.1 的重点是让回答更可靠、更对应用户问题：回答深度分为简洁、教学、专家；每条新回答会记录生成时的深度和回答焦点；LLM prompt 会按参数建议、质控判断、故障排查、操作指导、决策建议、概念解释、图像/语音证据判断等问题类型调整侧重点。

## v5.1 主要能力

- **真实回答深度**：简洁、教学、专家三种模式分别控制结构、解释密度、QC 标准、回退路径、证据等级和不确定性。
- **LLM 回复灵活化**：系统会识别用户问题焦点，避免所有问题都套同一模板；参数问题重参数边界，截图问题重可见证据，故障问题重排查路径。
- **证据优先回答**：关键建议绑定规则层、知识库/RAG、用户图像/OCR/语音、LLM 推断或不确定性说明。
- **多模态反馈**：上传图片或语音后显示处理状态、识别摘要、置信度和原始输入引用。
- **知识库闭环**：支持正式、草稿、废弃、来源等级、证据等级、风险等级和命中信息管理。
- **稳定运行态**：运行数据默认写入 `runtime/`，可用 `STRUCTPILOT_RUNTIME_DIR` 改到统一可写目录。
- **截图内置兜底**：`assets/guides` 已内置 cp_01 到 cp_12 的兜底截图，共 22 个文件；外部截图目录缺失时不会导致自检失败。

## Quick Start（Windows）

双击：

```bat
start.bat
```

首次运行会创建 `.venv`、安装依赖、执行健康检查，并在本机启动 Streamlit：

```text
http://127.0.0.1:8501/
```

如需手动启动：

```bat
.venv\Scripts\python.exe -m streamlit run main.py --server.port 8501
```

## 自检与测试

交付或给他人使用前建议运行：

```bat
.venv\Scripts\python.exe verify_v5.py
.venv\Scripts\python.exe healthcheck.py
.venv\Scripts\python.exe -m pytest -q
```

`verify_v4.py` 仍保留为兼容入口，推荐新文档和交付包使用 `verify_v5.py`。

## 运行模式

- **基础模式**：不配置 API Key，使用本地规则、SOP、知识库检索和截图兜底。适合离线演示和教学。
- **AI 增强模式**：配置 LLM/Embedding/视觉/语音 API 后，启用语义检索、LLM 改写、图像理解和语音转写。
- **回答深度**：简洁用于快速判断，教学用于带新手操作，专家用于科研审核和复杂决策。

## 配置

复制 `.env.example` 为 `.env`，按需填写：

- `STRUCTPILOT_LLM_PROVIDER`
- `STRUCTPILOT_LLM_API_KEY`
- `STRUCTPILOT_LLM_MODEL`
- `STRUCTPILOT_LLM_BASE_URL`
- `STRUCTPILOT_EMBEDDING_MODEL`
- `STRUCTPILOT_AUDIO_MODEL`
- `STRUCTPILOT_SCREENSHOTS_DIR`
- `STRUCTPILOT_RUNTIME_DIR`

不要把 `.env`、API Key、`runtime/`、SQLite 数据库、用户上传图片/音频、日志、缓存或 `.venv/` 提交给他人。

## Project Layout

```text
main.py                  Streamlit UI 入口
version.py               v5.1 版本与显示名
graph/                   LangGraph 编排与运行时状态
agents/                  Navigator / LLM / Memory / SOP / Expert / SmartQA
knowledge_base/          检查点、规则、SOP、QA、检索、官方文档
assets/guides/           cp_01..cp_12 内置兜底截图
config/                  settings.py + screenshot_map.py
utils/                   资源解析、缓存、多模态辅助
validator/               输入与参数校验
tests/                   pytest 自动化测试
eval_cases/              评测样例
healthcheck.py           交付前健康检查
verify_v5.py             v5.1 自检入口
start.bat                Windows 启动器
```

## 交付文档

给他人使用时，请优先提交由 `build_release.ps1` 生成的 `dist/StructPilot_v5.1.zip`，并附带：

- `DELIVERY_AND_USER_GUIDE_V5.1.md`
- `CHANGELOG_V5.1.md`
- `StructPilot_v5.1.zip.sha256`

内部运行目录名如果仍出现 `StructPilot_v4_runtime`，只表示历史兼容路径，不代表当前软件版本。对外展示版本以 `StructPilot v5.1` 为准。
