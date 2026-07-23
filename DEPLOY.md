# StructPilot v6.0 部署指南

## 🌐 Streamlit Cloud 部署（推荐）

### 前置准备
1. GitHub 账号
2. Streamlit Cloud 账号（使用 GitHub 登录：[share.streamlit.io](https://share.streamlit.io)）

---

## 📋 部署步骤

### 1. Fork 仓库
访问 [github.com/hwl26/StructPilot-v6.0](https://github.com/hwl26/StructPilot-v6.0)，点击右上角 **Fork** 按钮。

### 2. 登录 Streamlit Cloud
1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 使用 GitHub 账号登录
3. 授权 Streamlit Cloud 访问你的 GitHub 仓库

### 3. 创建新应用
1. 点击 **New app**
2. 选择你 Fork 的仓库：`<your-username>/StructPilot-v6.0`
3. **Branch**: `main`
4. **Main file path**: `main.py`
5. **App URL**（可选）：自定义子域名，如 `structpilot-demo`

### 4. 配置环境（可选）

点击 **Advanced settings** → **Secrets**，添加以下内容（如果需要启用 LLM 功能）：

```toml
[llm]
provider = "openai_compatible"
api_key = "your-api-key-here"
model = "gpt-4o-mini"
base_url = "https://api.openai.com/v1"
timeout = 30

[embedding]
model = "BAAI/bge-m3"
api_key = "your-embedding-api-key"
base_url = "https://your-embedding-service.com"
```

**注意**：
- 不配置 Secrets 也能运行，入门/教学模式不依赖 LLM
- 静态知识库检索功能正常工作

### 5. 部署应用
点击 **Deploy** 按钮，等待 3-5 分钟构建完成。

---

## ✅ 部署完成

应用部署成功后，你会得到一个 URL，格式如：
```
https://<your-app-name>.streamlit.app
```

分享链接给同事、学生，无需本地安装即可使用！

---

## 🔧 本地开发

如果需要本地调试或二次开发：

### 克隆仓库
```bash
git clone https://github.com/hwl26/StructPilot-v6.0.git
cd StructPilot-v6.0
```

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行应用
```bash
streamlit run main.py
```

浏览器打开 http://localhost:8501

---

## 📦 更新应用

当你更新了代码（本地或通过 GitHub 网页编辑）：

1. 提交更改到 GitHub
2. Streamlit Cloud 会**自动检测并重新部署**（约 2-3 分钟）
3. 无需手动操作

---

## ❓ 常见问题

### Q1: 部署后界面空白？
**A**: 检查浏览器控制台（F12）是否有报错。通常是 Secrets 配置格式错误，或者依赖版本冲突。

### Q2: 应用启动慢？
**A**: Streamlit Cloud 免费版有冷启动时间（~30秒），首次访问较慢属正常现象。付费版可消除冷启动。

### Q3: 如何关闭应用？
**A**: 进入 Streamlit Cloud 管理面板 → 选择应用 → Settings → Delete app。

### Q4: 可以私有部署吗？
**A**: 可以。Streamlit Cloud 支持私有应用（仅特定邮箱可访问），或者使用 Docker 容器化后部署到自己的服务器。

---

## 📞 技术支持

- GitHub Issues: [github.com/hwl26/StructPilot-v6.0/issues](https://github.com/hwl26/StructPilot-v6.0/issues)
- 邮件：hwl26@shanghaitech.edu.cn

---

**版本**: v6.0  
**更新时间**: 2026-03-01
