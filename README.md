# StructPilot v6.0 Final

**cryo-EM 数据处理流程智能陪跑系统 · 三模式交互版**

---

## 🚀 快速开始

### 启动应用

**Windows 用户（推荐）**：
```bash
双击运行 start.bat
```

**命令行**：
```bash
cd final_struct
streamlit run main.py
```

浏览器自动打开 http://localhost:8501

---

## 📌 三种交互模式

### 🔧 入门模式（默认）
- 需求问答定制流程
- 参数自动预填充
- 质检结果评估
- 课题组经验优先

### 🎓 教学模式
- 5要素教学卡片
- 交互测验验证
- 学习进度追踪

### ⚙️ 高级模式
- 参数导出（CSV/JSON）
- 预设管理
- 贡献经验

**切换方式**：侧边栏 → 交互模式

---

## 📚 文档

- [完整使用指南](USAGE_GUIDE.md)
- [三模式架构](README_MODES.md)
- [需求问答优化](ONBOARDING_OPTIMIZATION.md)

---

## 📊 知识库优先级

```
🥇 课题组经验 > 官方文档 > GitHub > AI推理
```

---

## 🌐 在线部署（Streamlit Cloud）

### 一键部署到 Streamlit Cloud

1. **Fork 本仓库**到你的 GitHub 账号
2. 访问 [share.streamlit.io](https://share.streamlit.io)
3. 点击「New app」→ 选择你的仓库 → 主文件选择 `main.py`
4. 点击「Deploy」

### 配置 Secrets（可选，启用 LLM 功能）

部署后，进入 App Settings → Secrets，添加：

```toml
[llm]
provider = "openai_compatible"
api_key = "your-api-key"
model = "gpt-4o-mini"
base_url = "https://api.openai.com/v1"

[embedding]
model = "BAAI/bge-m3"
api_key = "your-embedding-key"
base_url = "https://your-service.com"
```

**不配置也能用**：入门模式和教学模式不依赖 LLM，静态知识库照常检索。

---

**版本**：v6.0-final  
**状态**：✅ 运行中
