# StructPilot 运行性能优化说明

> 本文档记录 StructPilot 已实施的运行性能优化措施，覆盖缓存架构、流式响应、
> 快速路径、图片优化、会话状态管理、LLM 重试与热路径 I/O 等方面。
> 所有优化均遵循「全链路优雅降级」原则——无 API Key / 无 embedding 时缓存照常工作。

---

## 一、缓存架构

缓存是本项目最大的性能杠杆。`utils/perf_cache.py` 集中实现了 Streamlit 原生缓存与进程内 LRU 缓存，
所有缓存都是透明包装：调用方拿到的数据类型与未缓存时完全一致。

### 1. App / LLM 单例缓存（`@st.cache_resource`）

| 函数 | 位置 | 作用 |
|------|------|------|
| `get_cached_app` | `utils/perf_cache.py` | 单例化 `StructPilotApp`，避免每次 Streamlit rerun 重建 LangGraph、`KnowledgeRetriever` 及全部 Agent（合计加载 10+ 个 JSON） |
| `get_cached_llm_agent` | `utils/perf_cache.py` | 单例化 `LLMAgent`，避免每次 rerun 重读 `config/llm_config.json` 等配置 |

- `get_cached_app` 的缓存键含 `app_api_version` 参数，公共编排接口变更时递增该版本号即可让在线进程弃用旧实例。
- `get_cached_app` 内部会确保 `app.llm` 与 `app.retriever.llm` 指向同一个缓存单例，避免配置漂移。
- 注意：`st.cache_resource` 的对象在整个 Streamlit 进程内共享，**不应**在每次知识库变更时清除——仅由 `clear_app_cache()` 在用户显式「重置」时调用。

### 2. JSON 加载缓存（`@st.cache_data`）

| 函数 | `max_entries` | 位置 | 用途 |
|------|---------------|------|------|
| `cached_load_json` | 64 | `utils/perf_cache.py` | 加载 `knowledge_base/` 下的 JSON（`load_json_with_fallback` 的缓存版） |
| `cached_load_json_by_path` | 16 | `utils/perf_cache.py` | 按绝对路径加载任意 JSON（如 `config/llm_config.json`） |
| `cached_load_jsonl` | 32 | `utils/perf_cache.py` | 加载 JSONL 文件（逐行解析，返回 `List[Dict]`） |

- 缓存键包含文件 mtime，编辑磁盘上的 JSON 后下一次 rerun 自动失效（详见第九节「已修复问题」）。
- `NavigatorAgent` / `SOPAgent` / `ExpertAgent` 的 `__init__` 均改用 `cached_load_json`，避免每个 Agent 重复读盘。

### 3. RAG 检索 LRU 缓存

| 项 | 值 |
|----|----|
| 函数 | `rag_search_cache` |
| 位置 | `utils/perf_cache.py` |
| 容量 | `max_entries=100`（`_RAG_CACHE_MAX_SIZE`） |
| 复合键 | `(software, cp_id, query_hash, top_k)`，其中 `query_hash = sha256(query)[:16]` |
| 淘汰策略 | LRU（`OrderedDict.move_to_end` / `popitem(last=False)`） |
| 线程安全 | `threading.Lock`（`_rag_cache_lock`） |

- `graph/app.py` 的 `_polish_reply` 优先调用 `rag_search_cache(self.retriever, ...)`，未命中才回退到 `retriever.search`。
- 知识库被标记为 dirty（`mark_kb_dirty()`）时，下一次查询会先清空 LRU 缓存再放行。

### 4. Embedding 磁盘缓存

| 项 | 值 |
|----|----|
| 文件 | `config/embeddings_cache.json` |
| 键 | `sha256(text)` |
| 位置 | `knowledge_base/retriever.py`（`_CACHE_PATH`、`_sha256`） |

- 语料向量按 `sha256(text)` 落盘，命中即跳过 embedding API 调用。
- query 向量当场计算、不落盘（每次提问都不同，缓存只会让缓存无限膨胀）。

### 5. Corpus 缓存

| 项 | 值 |
|----|----|
| 文件 | `config/corpus_cache.json` |
| 版本号 | `_CORPUS_CACHE_VERSION = 2`（`knowledge_base/retriever.py`） |
| 位置 | `retriever.py`：`_load_corpus_cache` / `_save_corpus_cache` / `_invalidate_corpus_cache` |

- 首次构建语料矩阵后写入 `corpus_cache.json`，含 `cache_version` 字段；下次启动直接加载。
- 版本号不匹配（如检索算法升级）时自动作废旧缓存并重建，避免命中过期向量。

---

## 二、流式响应

### 1. LLM 流式输出

| 函数 | 位置 | 说明 |
|------|------|------|
| `_openai_compatible_rewrite_stream` | `agents/llm_agent.py`（约 520 行） | OpenAI 兼容接口的流式改写，逐 chunk 产出 |
| `rewrite_with_metadata_stream` | `agents/llm_agent.py`（约 568 行） | 流式改写入口，内部调用 `_openai_compatible_rewrite_stream` 并按 provider 分发 |

### 2. UI 实时更新

| 项 | 位置 |
|----|------|
| `_stream_sink` | `main.py`（约 2993 行） |

- `_polish_reply`（`graph/app.py`）在检测到 `self._stream_sink` 与 `rewrite_with_metadata_stream` 同时可用时，
  改走流式分支：每收到一个 chunk 即 `stream_sink(_chunk)` 推送给 UI，实现「首字 < 2s」的体感。
- 流式产物累计完毕后仍会落库为完整 `agent_reply`，不影响记忆与报告导出。

---

## 三、本地快速路径

| 项 | 值 |
|----|----|
| 函数 | `handle_local_flow_command` |
| 位置 | `main.py`（约 1201 行） |

- 对「进度 / 报告 / 下一步」等流程命令走**零 LLM、零 RAG** 的纯规则路径，直接产出 `PipelineState`。
- `_polish_reply` 中 `skip_llm = state.action_tag in _LOCAL_ONLY_ACTIONS and not image_paths`，
  命中时 `trace["fallback_reason"] = "local_fast_path"`，`timings_ms["llm"] = 0`。
- 仅有图片附件时仍会触发 LLM（多模态解读），避免错过截图诊断。

---

## 四、概念问答快速通道

| 项 | 值 |
|----|----|
| 入口 | `SmartQAEngine.answer_concept` |
| 位置 | `agents/smart_qa_engine.py`（约 1796 行） |
| 触发条件 | `action_tag == "concept_explain"` |

- `concept_explain` 意图直接调用 `llm.concept_answer` 生成完整术语卡，**跳过 `_polish_reply` 中的二次 RAG 检索与 LLM 改写管线**。
- `_polish_reply`（`graph/app.py` 约 348 行）对 `concept_explain` 早退：仅做 `format_response_for_profile` 包装，
  不再运行 SmartQA 二次管线、RAG refs 检索与 LLM 改写，避免概念路径 LLM 调用翻倍与「参考来源」噪音。
- `answer_concept` 内部自行完成术语库匹配（glossary）+ LLM 直答（1 次调用），满足性能域「概念路径不翻倍」的硬约束。

---

## 五、图片优化

### 1. 缩略图生成

| 项 | 值 |
|----|----|
| 模块 | `utils/image_lazy.py` |
| 函数 | `generate_thumbnail_data_url` |
| 算法 | PIL `Image.LANCZOS` 重采样 |
| 压缩 | JPEG `quality=75` |
| 最大边 | `_THUMBNAIL_MAX_EDGE = 400` px |
| 缓存 | `@st.cache_data(max_entries=64)`，键含文件 size + mtime |

- 长边超过 400px 时按比例缩放，base64 编码为 data URL，显著降低列表 / 聊天预览的传输体积。
- 配套 `render_lazy_image` / `render_image_with_expand`：缩略图内联 + 展开查看原图。

### 2. 多模态图片压缩

| 项 | 值 |
|----|----|
| 模块 | `agents/llm_agent.py` |
| 最大边 | `_MAX_IMAGE_EDGE = 768`（环境变量 `STRUCTPILOT_MAX_IMAGE_EDGE` 可覆盖） |
| 压缩 | JPEG `quality=85` |
| 算法 | PIL `Image.LANCZOS` |

- 发往 vision 模型的截图统一压缩到长边 ≤ 768px + JPEG q85，兼顾识别精度与上行带宽。

---

## 六、会话状态管理

### 1. 聊天历史折叠

| 项 | 值 |
|----|----|
| 函数 | `get_chat_display_window` |
| 位置 | `agent/ui_state_manager.py`（约 264 行） |

- 渲染聊天区时只取最近 N 条消息窗口，避免长会话一次性渲染上百条气泡导致卡顿。

### 2. 历史窗口可控

| 项 | 值 |
|----|----|
| 窗口大小 | 10 条消息 |
| 单条字符 | 200 字符 |
| 摘要上限 | 1500 字符 |

- `_build_context`（`graph/app.py`）注入最近 10 条消息、每条 200 字符；`_update_session_summary` 维护 1500 字符摘要。
- 上下文既保留近期细节，又通过摘要覆盖更早的关键进度，控制 LLM prompt 体积。

### 3. 命名空间前缀与向后兼容

| 项 | 值 |
|----|----|
| 前缀 | `sp_*` |
| 常量 | `_PREFIX = "sp_"`（`agent/ui_state_manager.py` 约 32 行） |
| 兼容策略 | 双写（新键 `sp_*` 与旧键并存），平滑迁移历史会话 |

- 所有 session_state 键统一加 `sp_` 命名空间，避免与 Streamlit 内部键冲突；旧键双写保证存量会话不丢状态。

---

## 七、LLM 重试机制（新实施）

| 项 | 值 |
|----|----|
| 模块 | `agents/llm_agent.py` |
| 库 | tenacity（指数退避重试） |
| 重试状态码 | 429 / 500 / 502 / 503 |
| 最大重试次数 | 3 次 |

- 对 LLM 改写 / 概念问答等调用引入 tenacity 指数退避重试，针对服务商限流（429）与临时服务端异常（5xx）自动重试 3 次。
- 重试仅覆盖瞬时错误，鉴权失败（401/403）、模型不存在（400）等永久性错误不重试，直接走 `_format_connection_error` 给出可操作的设置页诊断。

---

## 八、热路径 I/O 优化（规划中）

| 项 | 值 |
|----|----|
| 函数 | `_record_hits` |
| 位置 | `knowledge_base/retriever.py`（约 107 行） |
| 命中落盘文件 | `_HIT_COUNTS_PATH`（检索命中遥测） |

**当前状态**：`_record_hits` 每次检索仍执行同步 read-modify-write 文件 I/O，虽有 `try/except` 兜底不阻塞主路径，但高频问答时会产生频繁磁盘写入。

**优化方向**（待实施）：
- 改为**内存累积 + 定时落盘**：检索命中计数先在内存中累加，按时间阈值批量写入磁盘，
  避免每次检索都触发同步文件 I/O。
- 落盘失败静默兜底（`except Exception: pass`），遥测丢失不影响检索主路径。

---

## 九、已修复的性能问题

### 1. `cached_load_json` mtime 失效问题

- 早期 `@st.cache_data` 仅以参数为键，磁盘上 JSON 改动后缓存不会自动失效。
- 修复后缓存键纳入文件 mtime（`_file_mtime_key`），编辑 JSON 即在下次 rerun 自动失效，
  与 `mark_kb_dirty()` / `clear_all_caches()` 形成双层失效保障。

### 2. `preload_next_step_images` 预加载能力已启用

| 项 | 值 |
|----|----|
| 函数 | `preload_next_step_images` |
| 位置 | `utils/image_lazy.py`（约 247 行） |

- 用户处于检查站 N 时，后台预生成 N+1 站引导图的缩略图（命中 `@st.cache_data`）。
- 当用户真正推进到 N+1 时，图片瞬时加载，消除首屏等待。

---

## 十、性能测试建议

### 1. 单用户场景目标

| 指标 | 目标 |
|------|------|
| 首屏渲染 | < 3s |
| LLM 首字延迟（流式） | < 2s |
| RAG 检索（含缓存命中） | < 500ms |

- 验证方法：清空 `config/embeddings_cache.json` 后冷启动测一次（含首次 embedding），
  再测第二次（命中缓存），对比 `trace.timings_ms` 中的 `retrieval` 与 `llm` 字段。

### 2. 多用户场景注意点

| 风险 | 说明 |
|------|------|
| `session_state` 膨胀 | 长会话消息 / 图片引用累积，建议定期调用 `get_chat_display_window` 截断渲染窗口并归档旧消息 |
| SQLite 并发写入 | 多会话并发落库时 `memory.sqlite3` 写锁竞争，建议启用 WAL 模式或对写入做批处理 |
| `@st.cache_resource` 全局共享 | App / LLM 单例跨会话共享是优势，但修改 LLM 配置后需显式 `clear_app_cache()` 才能生效 |

---

## 附：缓存一键清理

| 函数 | 位置 | 作用 |
|------|------|------|
| `clear_all_caches` | `utils/perf_cache.py` | 清空 JSON / JSONL / RAG LRU 缓存（保留 App / LLM 单例） |
| `clear_app_cache` | `utils/perf_cache.py` | 强制重建 `StructPilotApp` 与 `LLMAgent` 单例（改 LLM 配置后调用） |
| `mark_kb_dirty` | `utils/perf_cache.py` | 标记知识库已变更，下次 RAG 查询前清空 LRU 并失效 JSON 缓存 |
