# StructPilot v2.0 架构说明

> 冷冻电镜（cryo-EM）数据处理「陪跑教练」——把标准处理流程拆成检查站，
> 用户每完成一步就汇报，系统给下一步指导、参数建议、故障诊断，并全程记忆、可导出报告。

---

## 一、定位

StructPilot 把一条 cryo-EM 单颗粒处理流程拆成若干「检查站」（checkpoint）。用户以对话方式逐站推进：

- 汇报「开始 / 完成 / 跳过 / 进度 / 报错」，系统据此流转状态机、给出对应指导；
- 可上传或粘贴软件界面截图，由支持视觉的模型给出图文指导；
- 全程对话与进度落库，可恢复会话、导出报告，并把有价值的经验「沉淀」进知识库。

设计目标：**代码能力与知识内容解耦**——空知识库也能跑通流程，导入实验室经验后能力自动增强。

---

## 二、分层架构

```
┌──────────────────────────────────────────────────────┐
│  表现层  Streamlit UI (main.py)                            │
│  对话陪跑 / 报告导出 / 设置  三 Tab + 侧边栏会话管理          │
├──────────────────────────────────────────────────────┤
│  编排层  LangGraph (graph/app.py)                          │
│  StructPilotApp：navigator 条件路由 → expert/sop/fault/...   │
│  挂载点 _polish_reply：RAG 检索 + vision 图片 + LM 改写       │
├──────────────────────────────────────────────────────┤
│  智能体层  agents/                                          │
│  NavigatorAgent（状态机，关键词路由 + 状态流转）              │
│  ExpertAgent / SOPAgent（已接入条件路由，分别在               │
│    param_advice / stage_guide_sop 触发）                       │
│  LLMAgent（改写 / embedding / 图文 / 经验抽取，多 provider）  │
│  MemoryAgent（SQLite 持久化）                               │
├──────────────────────────────────────────────────────┤
│  知识层  knowledge_base/（6 个 JSON） + retriever.py        │
│  流程站点 / 故障库 / 专家规则 / SOP / QC 标准 / 教练话术       │
│  + RAG 检索器（numpy 余弦相似度 + sha256 缓存 + 阈值过滤）     │
├──────────────────────────────────────────────────────┤
│  持久层  state.py（运行时） + SQLite（memory.sqlite3）       │
│  4 张表：sessions / messages / message_images / checkpoints │
└──────────────────────────────────────────────────────┘
```

---

## 三、核心数据流

一次对话内部发生的事：

```
用户输入（可带截图）
  │
  ▼
NavigatorAgent.handle_input
  关键词路由 + 状态机流转
  （开始 / 完成 / 跳过 / 进度 / 报错 各走不同分支，产出「规则层结论」）
  │
  ▼
_polish_reply（graph/app.py）
  ① RAG 检索 top-k 知识片段（余弦相似度，阈值 ≥ 0.30 才注入）
  ② 取本轮截图路径（压缩到长边 ≤ 1024px）
  ③ LLMAgent.rewrite：三层 prompt
       规则层结论（权威，不可改） / 检索参考（可引用，非事实） / 用户输入
  │
  ▼
MemoryAgent.capture_state
  整个 PipelineState 落 SQLite
  │
  ▼
UI 渲染 + 自动滚动到底部
```

---

## 四、关键设计决策

### 1. 单一权威应答者
`_route_from_navigator` 依据 `action_tag` 将流程条件路由到 expert / sop / fault / plot_interp /
concept / casual 等下游节点（`param_advice` → expert、`stage_guide_sop` → sop、`fault_diagnosis` →
fault、`plot_interpretation` → plot_interp、`concept_explain` → concept、`casual` → casual），
但同一轮对话只会有一个下游节点产出回复：navigator 在识别到路由标签时仅缓存前缀文本（`_nav_prefix`），
由下游节点消费前缀并调用 `_polish_reply` 生成唯一助手回复。这根治了早期「一次输入产生两条回复」的 bug，
RAG / vision 全部挂在这条单线的 `_polish_reply` 上，不引入并发追加。

### 2. 全链路优雅降级
- 未配 embedding → RAG 检索返回 `[]`，对话照常；
- 未配 vision 模型 → 图片被忽略，走纯文本；
- 未配 LLM → 退回纯规则模式。

任何一环缺失都不报错，系统始终可用。

### 3. 内容无关骨架
代码能力与知识内容解耦。空知识库能跑通流程；导入实验室 SOP / 经验后，
RAG 检索与改写的质量自动提升，无需改代码。

### 4. RAG 检索器要点
- 纯 numpy 手写余弦相似度，不引入 Chroma / FAISS（简单、Windows 友好）；
- 语料向量按 `sha256(text)` 缓存到 `config/embeddings_cache.json`，可复用；
- query 向量当场计算、**不落盘**（每次提问都不同，缓存它只会让缓存无限膨胀）；
- 相似度低于阈值（默认 0.30）的片段丢弃，避免低相关内容混入上下文误导模型。

---

## 五、关键模块与文件

| 层 | 文件 | 职责 |
|----|------|------|
| 表现层 | `main.py` | Streamlit 入口：三 Tab + 侧边栏，对话 / 报告 / 设置 / 会话管理 |
| 编排层 | `graph/app.py` | `StructPilotApp`，LangGraph 条件路由图，`_polish_reply` 挂载 RAG/vision/改写 |
| 状态 | `graph/state.py` | `PipelineState` / `Message` / `CheckpointRecord` 运行时数据结构 |
| 智能体 | `agents/navigator_agent.py` | 状态机流转、关键词路由、故障诊断、进度/报告生成 |
| 智能体 | `agents/llm_agent.py` | LLM 改写 / embedding / 图文多模态 / 经验抽取，多 provider 适配 |
| 智能体 | `agents/memory_agent.py` | SQLite 持久化，会话存取 / 列表 / 重命名 / 删除 |
| 智能体 | `agents/expert_agent.py` `agents/sop_agent.py` | 已接入条件路由：`param_advice` → expert，`stage_guide_sop` → sop |
| 知识层 | `knowledge_base/pipeline_checkpoints.json` | 流程检查站定义（步骤 / 参数 / QC / 常见坑） |
| 知识层 | `knowledge_base/retriever.py` | RAG 检索器（numpy 余弦 + 缓存 + 阈值） |
| 知识层 | `knowledge_base/importer.py` | 知识文档读写（`KnowledgeDoc` / 索引读写 / 文本平铺） |
| 校验 | `validator/validator.py` | 反馈通过/失败判定、参数抽取 |
| 配置 | `utils/ui_settings.py` | UI 偏好持久化（主题 / 背景 / 历史条数） |

---

## 六、持久层数据结构

### 运行时（`graph/state.py`）

- **PipelineState**：核心状态对象
  - 会话标识：`session_id` / `created_at` / `last_updated`
  - 工作流进度：`current_cp_id` / `software`（cryosparc / relion）
  - 状态追踪：`completed[]` / `failed[]` / `skipped[]` 三个列表维护检查站流转
  - 消息队列：`messages: List[Message]`
  - 检查点记录：`checkpoint_records: Dict[cp_id, CheckpointRecord]`
  - 待处理图片：`pending_images`
- **Message**：`role` / `content` / `timestamp` / `action_tag` / `metadata` / `image_refs`
- **CheckpointStatus 状态机**：`pending → in_progress → {passed | failed | skipped}`

### SQLite（`memory/memory.sqlite3`）

| 表 | 关键字段 |
|----|----------|
| `sessions` | session_id(PK) / software / current_cp_id / completed_json / failed_json / skipped_json / params_json / last_qc_result_json |
| `messages` | session_id / role / content / timestamp / action_tag / metadata_json |
| `message_images` | session_id / message_id / image_path / sha256 / width / height / caption |
| `checkpoint_records` | (session_id, cp_id)(PK) / status / qc_summary / qc_passed / params_captured_json / notes |

数据流：`PipelineState` → JSON 序列化 → SQLite 入库；反向查询 → 反序列化 → 重建 `PipelineState`，支持完整会话复现。

---

## 七、能力实现度

| 能力 | 工程实现 | 真实可用度 | 卡点 |
|------|----------|-----------|------|
| 状态机陪跑 | 完整 | 仅 cp_01 内容完整 | 知识库 |
| RAG 检索 | 完整（numpy 余弦 + 缓存 + 阈值） | 待配 embedding key | 配置 + 内容 |
| 图文指导（vision） | openai 兼容完整（含图片压缩） | 待配 vision 模型 | 配置 |
| 多 Agent 决策 | expert/sop/fault 等多节点条件路由 | 可用 | — |
| 记忆库 - 模式 1（代码预写） | 完整 | 可用 | — |
| 记忆库 - 模式 2（交互沉淀） | 完整（「沉淀经验」按钮） | 可用 | — |

---

## 八、已知瓶颈与后续方向

**当前瓶颈不在代码，在内容。** 工程骨架（分层 / 降级 / 持久化 / RAG / vision 管线）已较扎实，
真正拖后腿的是知识库内容。

- **P0 知识库填充（最高优先级，非写代码）**：`pipeline_checkpoints.json` 的 cp_02~cp_12
  步骤 / QC / 常见坑均为空；故障库、专家规则各仅 1 条。RAG 检索的质量直接取决于这些内容。
  建议用「沉淀经验」按钮 + 文档导入管线，把实验室 SOP 逐步灌入。
- **P1 工程健壮性**：`tests/` 已有 6 个测试文件（`conftest.py` / `test_core.py` / `test_dynamic_tabs.py` /
  `test_modes_architecture.py` / `test_onboarding.py` / `test_response_profiles.py`），建议继续补状态机流转、
  RAG 降级、序列化往返的单元测试；ExpertAgent / SOPAgent 已通过 `_route_from_navigator` 接入条件路由
  （`param_advice` / `stage_guide_sop`），可随知识库充实持续增强专业能力。
- **P2 体验 / 运维**：补部署使用文档；为 embedding 缓存增加基于内容 hash 的自动失效；
  对长会话引入检索 / 发图的成本控制策略。

---

## 九、一句话结论（汇报用）

> 软件工程层已成熟——分层清晰、全链路优雅降级、RAG / 图文 / 记忆三条能力线全部「通电」。
> 当前唯一核心瓶颈是知识库内容（12 站仅 1 站完整、故障 / 规则库各仅 1 条），
> 属于内容工程问题而非代码问题。下一步重心应从「写代码」转向「灌知识」。
