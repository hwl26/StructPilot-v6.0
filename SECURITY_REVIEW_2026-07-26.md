# StructPilot 公开部署安全与可靠性复核

更新日期：2026-07-27
审查范围：当前本地工作树、Streamlit 公开部署配置、认证与会话、外部 API、上传、知识库/RAG、cryoSPARC Workflow 编辑与导出。

## 执行结论

当前版本已完成此前 Critical/High 问题的代码修复，未在 Git 跟踪文件中发现真实 API Key、访问令牌、私钥或默认弱口令。源码编译、配置解析、健康检查和完整测试均通过：`88 passed`。

在遵守以下发布条件时，本版本适合决赛公开体验：

1. 真实 API Key、管理员密码和机器人 Token 只保存在 Streamlit Cloud Secrets，不进入 Git。
2. 在模型服务商后台设置日/月预算、速率限制和异常告警。
3. 公开课题组署名经验前确认作者已同意公开。
4. 公开体验数据不作为唯一科研记录；Streamlit Community Cloud 的本地运行目录可能随重启丢失。

安全审查不能证明软件绝对“零漏洞”，但当前已覆盖本项目最主要的凭证泄露、越权、SSRF、路径穿越、上传伪装、共享会话串读和 Workflow 结构损坏风险。

## 已关闭问题

### SEC-01：访客读取或替换服务凭证 — 已关闭

原严重度：Critical。

证据：

- `main.py:3205` 在进入完整设置页面前同时检查高级模式和管理员角色。
- `main.py:3383`、`main.py:4224` 的 API Key/Bot Token 输入框始终为空，不再把已保存密钥回填到前端组件。
- `utils/network_security.py:10-45` 要求远程服务使用 HTTPS，并限制服务主机名；私网、回环、链路本地和保留 IP 被拒绝。
- `agents/llm_agent.py:226-239` 支持从服务端环境变量读取密钥；状态文本不显示密钥片段，并有回归测试覆盖。

结果：普通访客可以使用服务端代理的 AI 能力，但不能从 UI 读取、覆盖或把 Authorization 请求引向任意主机。

### SEC-02：新部署自动创建已知默认弱口令 — 已关闭

原严重度：Critical。

证据：

- `utils/auth.py:38-79` 仅在私有环境变量 `STRUCTPILOT_BOOTSTRAP_ADMIN_PASSWORD` 存在时创建管理员；未配置时保持纯访客部署。
- 仓库文档和启动脚本已移除已知默认弱口令，统一改为私有 Secrets 初始化。
- 密码哈希优先使用 bcrypt，回退为带随机盐的 PBKDF2；比较使用常量时间函数。

结果：公开部署不会产生可预测的管理员凭证。

### SEC-03：URL/浏览器存储中的登录会话 — 已关闭

原严重度：High。

证据：

- 当前 `main.py` 不再从查询参数读取或写入 `sid`。
- `utils/session_persistence.py` 的旧保存/恢复 API 已改为安全空操作，只保留清理历史 localStorage/cookie 的兼容函数。
- 登录状态仅存在于当前 Streamlit 服务端会话；刷新后可能需要重新登录，这是当前安全取舍。

结果：分享 URL、浏览器历史和前端脚本不再携带可复用的登录令牌。

### SEC-04：会话文件路径穿越 — 已关闭

原严重度：Medium。

证据：

- `utils/server_session.py:17-34` 在保存、读取和删除前要求规范 UUID。
- `tests/test_security_hardening.py` 验证 `../outside` 不能创建、读取或删除文件。

结果：外部字符串不能逃逸 `runtime/sessions`。

### SEC-05：上传伪装和资源耗尽 — 已关闭

原严重度：High。

证据：

- `utils/file_upload.py:49-50` 限制单次图片数量与最大像素数。
- `utils/file_upload.py:79-103` 使用 Pillow 解码真实内容并核对扩展名，拒绝伪装图片和超大解压图。
- `.streamlit/config.toml` 将 Streamlit 单文件上传限制为 25 MB。

结果：仅凭文件扩展名绕过校验和常见图片解压炸弹风险得到控制。

### SEC-06：多访客数据串读和 API 滥用 — 已关闭/缓解

原严重度：High。

证据：

- `agents/memory_agent.py` 的会话读写、重命名和删除绑定 `owner_id`，测试验证不同 owner 不能读取同一会话。
- `agents/memory_agent.py:492-501` 对访客设置默认每小时 20、每日 100、全局每日 1000 次 AI 请求限制，均可通过 Secrets 调低。
- 原子文件写入与路径锁用于共享 JSON/会话配置，降低并发写坏文件的概率。

结果：应用层已经限制单访客和全局消耗，但仍必须配合供应商侧预算上限，见 RISK-01。

### SEC-07：Git 密钥与开发者路径泄露 — 已关闭

原严重度：High。

证据：

- `.gitignore:4-9` 忽略 `.env*` 和 `.streamlit/secrets.toml`，仅允许安全的 `.env.example`。
- `.streamlit/secrets.toml.example` 只包含根级变量名和占位符，与 `os.getenv` 的读取方式一致。
- RELION/经验导入脚本改用项目相对路径或显式环境变量；测试与文档中的开发者用户名路径已清理。
- 已对 Git 跟踪文件扫描 OpenAI/GitHub/AWS/Google/Telegram/PEM 等高风险模式，未发现真实凭证。

结果：仓库可公开包含代码、知识库、经验库与 Workflow 模板，但不包含可用凭证。

## Workflow 可靠性结论

- 参数编辑器使用真实 cryoSPARC JSON 模板，不生成简化伪结构。
- 导出前校验 Job 类型、参数类型和上游拓扑。
- 导出时重新生成 `_id`、清空原 `createdBy`，所有参数 `locked=false`，避免固定值焊死。
- 蛋白直径联动自动写入 J5/J8 的 box size 和 J6/J9 的 mask，同时允许关闭自动换算后手动编辑。
- 右侧节点与左侧参数卡双向联动，切换 Job 后参数状态不丢失。

上述行为由 `tests/test_cryosparc_workflow.py` 的单元测试和 Streamlit AppTest 覆盖。

## 仍需接受或运营控制的风险

### RISK-01：公开访客会消耗共享 API 额度

严重度：Medium（运营风险）。

应用内配额能降低滥用，但不能替代服务商计费保护。部署前应为专用演示 Key 设置硬预算、速率限制和告警；不要复用个人主账号高额度 Key。发生异常流量时应立即禁用/轮换 Key。

### RISK-02：Community Cloud 本地数据不是持久数据库

严重度：Medium（可靠性风险）。

访客会话、投稿和配置位于运行时目录，实例重建时可能丢失。公开演示可接受；若正式推广，需要外置数据库/对象存储、备份和恢复演练。

### RISK-03：经验库包含真实作者署名

严重度：Medium（隐私与合规风险）。

经验库按需求保留王立群、小玲、李明、张宇、陈昊等署名与日期。推送前应确认所有作者授权公开；未授权时应改为角色化或匿名署名。

### RISK-04：仓库内存在未接入主 Web 的旧演示组件

严重度：Low。

`components/split_view.py` 与 `video-slides/` 含独立 iframe/postMessage/HTML 演示逻辑，但未被主 Streamlit 应用导入。若未来将其接入公开路由，应单独增加严格 origin 校验和不可信 HTML 清洗。

## 验证记录

- Python 改动文件 `py_compile`：通过。
- `.streamlit/secrets.toml.example` TOML 解析：通过。
- 经验库与 Workflow JSON 解析：通过。
- `python -m pytest -q`：`88 passed in 24.85s`。
- `python healthcheck.py`：依赖、源码语法、运行目录、SQLite、知识库全部 `[OK]`。
- `git diff --check`：提交前再次执行。

## Streamlit Cloud 发布要求

在 App settings → Secrets 中粘贴 `.streamlit/secrets.toml.example` 的结构并替换占位符。至少配置：

```toml
STRUCTPILOT_LLM_PROVIDER = "openai_compatible"
STRUCTPILOT_LLM_API_KEY = "仅放在 Streamlit Secrets 的专用演示 Key"
STRUCTPILOT_LLM_MODEL = "Qwen/Qwen3-VL-32B-Instruct"
STRUCTPILOT_LLM_BASE_URL = "https://api.siliconflow.cn/v1"
```

Embedding/Audio 若复用同一服务可使用各自的专用变量；管理员功能不是公开体验必需项，可不配置 `STRUCTPILOT_BOOTSTRAP_ADMIN_PASSWORD`。
