# StructPilot v3 — A 域（自然语言理解 / 概念问答）重设计 · 落地报告

> 目标：让系统能正确回答「eer 是什么文件」等概念/术语/缩写问题，且不破坏 10 条铁律。
> 模式：纯增量改动，无重写；规则模式（无 API Key）零 LLM / 零 embedding 即可用。

## 一、根因（5 层断链）

| # | 断链点 | 原状 | 修复 |
|---|--------|------|------|
| ① | 术语库缺数据 | glossary 仅 3 条（CTF/pixel size/box size），无 EER，且缺 `stage_ids/software/related_file_formats` 字段 | 扩为 **17 条**种子术语，含完整 EER 条目 |
| ② | 概念匹配永不成立 | `retrieve()` 调 `_match_glossary(" ".join(expansion.keywords_cn+keywords_en))`，概念问题 expansion 关键词为空 → 传空串 → 匹配失败 | `_match_glossary` 改为接受 `raw_user_text` + `acronym_terms`，对**原始文本做子串匹配**，从源头修复 |
| ③ | 概念被错并到参数 | navigator `expert_triggers` 把「是什么/含义/定义/原理/作用」并入 `param_advice` | 在 `expert_triggers` **之前**插入 `concept_intro` 强信号 → 返回 `concept_explain` |
| ④ | 缺 LLM 自有知识兜底 | 未命中术语库只能答「不知道」 | AI 模式走 `llm.concept_answer()` 直答（1 次 LLM），注入术语库命中为权威事实 |
| ⑤ | 缩写无扩展 | "eer" 无法映射到 "EER" | `QueryExpansionAgent` 加载 `acronym_map.json` + 内置 `_DEFAULT_ACRONYM_MAP` 保底 |

## 二、改动文件清单（增量）

| 文件 | 改动 |
|------|------|
| `graph/state.py` | `ActionTag` 增加 `"concept_explain"`（类型安全） |
| `knowledge_base/terminology/glossary.json` | 3 → 17 条，补字段；EER 完整条目（Falcon 4i 超分辨计数模式原始文件格式，别名 `eer`） |
| `knowledge_base/terminology/acronym_map.json` | **新建**：常见 cryo-EM 缩写 → 全称映射 |
| `agents/navigator_agent.py` | `handle_input` 插入 `concept_intro` 路由（最高优先级，位于 `expert_triggers` 之前） |
| `agents/smart_qa_engine.py` | `QueryExpansion.acronym_terms` 字段；`QueryExpansionAgent` 缩写加载 + `_compute_acronym_terms`；`RAGRetrievalOptimizer` glossary 健壮加载；`_match_glossary` 子串匹配；`SmartQAEngine.answer_concept()` |
| `agents/llm_agent.py` | `concept_answer()` + `_concept_system_prompt()` + `_concept_user_prompt()` + `_chat_complete()`（openai/anthropic/gemini 统一单轮） |
| `graph/app.py` | `Route` 加 `"concept"`；`_ROUTING_TAGS` 加 `"concept_explain"`；`_route_from_navigator` 映射；`_build_graph` 加 concept 节点与边；新增 `_concept_node`；`_polish_reply` 对 `concept_explain` **早退** |

## 三、性能域两处「必须改」落实情况（perf-engineer 评审）

1. **概念路径 LLM 调用不翻倍**：`_concept_node` 由 `answer_concept()` 完整产出（规则模式术语卡 / AI 模式 1 次 LLM），随后 `_polish_reply` 对 `concept_explain` **直接早退**——不再二次运行 SmartQA `process()` 管线（understand+expand+reason+compose）、也不再末段 LLM 改写。概念路径 LLM 调用：规则模式 **0 次**、AI 模式 **1 次**（而非原评审预警的 6 次）。
   > 说明：评审最初建议用 `should_enhance` 加 `_skip_smart_qa_once` 开关来规避翻倍；本落地采用更稳健的 `action_tag == "concept_explain"` 早退，等效且更强地满足「不翻倍」硬约束。
2. **跳过 RAG refs 检索**：早退发生在 `_polish_reply` 内 `rag_search_cache` 检索之前，概念问答**不触发向量检索 / embedding 往返**，也避免「参考来源」噪音挂到术语卡上。

## 四、双软件 / 铁律校验

- 14 步工作流、SOP/参数/截图展示、当前步骤导航、报告日志、本地运行、Demo 点击路径：**均未改动**，保持可用。
- 双软件：概念卡读取 `state.software`；EER 条目 `software:"both"`，cryoSPARC（Patch Motion Correction (EER)）与 RELION（MotionCorr2+）均覆盖。
- 铁律 9（无 API Key 基础模式）：已验证 `llm=None` 下 `answer_concept` 走规则术语卡，**0 LLM / 0 embedding**。

## 五、验证结果（venv，`ast.parse` + 功能联调）

```
[PASS] ast.parse 全部 5 个 .py 文件
[PASS] glossary.json (17 条) / acronym_map.json 合法
[PASS] answer_concept("eer是什么文件") → 含 EER / Falcon 4i 术语卡（规则模式）
[PASS] 未收录词条 → 正确降级提示（建议启用 AI 模式）
[PASS] "ctf是什么" → 缩写扩展命中 CTF
[PASS] Navigator 路由 concept_explain；参数问题仍 param_advice；完成意图不误伤
[PASS] app.handle 全流程 → 产出 EER 卡，消息级 action_tag=concept_explain
==== 16/16 checks passed ====
```

## 六、已知限制 / 后续

- `state.action_tag` 顶层字段被 LangGraph 复位为 `"general"`（所有意图皆然，属预存行为），功能以 `message.action_tag` 为准，UI 读取消息级标签，无影响。
- AI 模式（有 Key）路径仅代码层验证，未做真实 API 联调；如用户配置 Key，建议现场确认一次概念直答效果。
- 术语库 17 条为种子数据，`review_status` 标 `seed_pending_expert_review`，可后续由领域专家补充。
