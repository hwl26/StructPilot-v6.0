# Streamlit Community Cloud 免费部署教程

> 完全免费，5 分钟上线

---

## 第一步：准备 GitHub 仓库

### 1.1 创建仓库

访问 [GitHub](https://github.com) 并创建新仓库：
- 仓库名：`StructPilot`
- 可见性：Public（免费版必须公开）

### 1.2 上传代码

```bash
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6

# 初始化 Git
git init

# 创建 .gitignore
cat > .gitignore << 'EOF'
.env
runtime/
.venv/
__pycache__/
*.pyc
*.log
.DS_Store
Thumbs.db
.pytest_cache/
EOF

# 提交代码
git add .
git commit -m "Initial commit for Streamlit Cloud deployment"

# 推送到 GitHub
git remote add origin https://github.com/你的用户名/StructPilot.git
git branch -M main
git push -u origin main
```

---

## 第二步：配置 Streamlit Cloud

### 2.1 注册账号

访问 [share.streamlit.io](https://share.streamlit.io)，使用 GitHub 账号登录。

### 2.2 部署应用

1. 点击 "New app"
2. 填写信息：
   - **Repository**：选择 `你的用户名/StructPilot`
   - **Branch**：`main`
   - **Main file path**：`main.py`
   - **App URL**：`structpilot-你的名字`（会生成为 `structpilot-你的名字.streamlit.app`）

3. 点击 "Advanced settings"，配置环境变量：

```
STRUCTPILOT_LLM_PROVIDER = openai_compatible
STRUCTPILOT_LLM_API_KEY = 你的API密钥
STRUCTPILOT_LLM_MODEL = Qwen/Qwen3-VL-32B-Instruct
STRUCTPILOT_LLM_BASE_URL = https://api.siliconflow.cn/v1

STRUCTPILOT_EMBEDDING_MODEL = BAAI/bge-m3
STRUCTPILOT_EMBEDDING_API_KEY = 你的Embedding密钥

STRUCTPILOT_AUDIO_MODEL = FunAudioLLM/SenseVoiceSmall
STRUCTPILOT_AUDIO_API_KEY = 你的Audio密钥
```

4. 点击 "Deploy"

### 2.3 等待部署

- 初次部署约需 3-5 分钟
- 部署成功后会显示应用 URL
- URL 格式：`https://structpilot-你的名字.streamlit.app`

---

## 第三步：访问和分享

### 访问地址

```
https://你的应用名.streamlit.app
```

### 分享给他人

直接把 URL 分享给其他人即可，无需任何配置。

---

## 管理应用

### 查看日志

在 Streamlit Cloud 控制台可以查看：
- 实时日志
- 错误信息
- 资源使用情况

### 更新代码

只需推送到 GitHub：

```bash
git add .
git commit -m "Update"
git push

# Streamlit Cloud 会自动检测并重新部署
```

### 重启应用

在 Streamlit Cloud 控制台点击 "Reboot app"

### 删除应用

在控制台点击 "Delete app"

---

## 常见问题

### Q1: 部署失败

**检查**：
- `requirements.txt` 是否完整
- 是否有语法错误
- 查看部署日志

### Q2: 应用睡眠（Sleeping）

免费版不活跃时会进入睡眠状态，首次访问需要等待几秒唤醒。

**解决**：升级到付费版或使用定时任务保持活跃。

### Q3: 资源限制

免费版限制：
- 1GB RAM
- 1 CPU core
- 每月使用时长限制

**解决**：优化代码减少内存使用，或升级到付费版。

---

## 优化建议

### 1. 减少依赖大小

```txt
# requirements.txt 中只保留必需的包
streamlit>=1.35,<2.0
langgraph>=0.2.0
langchain-core>=0.2.0
python-dotenv>=1.0
requests>=2.31
loguru>=0.7
numpy>=1.24,<2.0
streamlit-paste-button>=0.1.2
Pillow>=10.0,<11.0
```

### 2. 使用缓存

```python
@st.cache_resource
def get_llm_client():
    # 初始化一次，复用
    pass

@st.cache_data
def load_knowledge_base():
    # 加载一次，缓存
    pass
```

### 3. 设置资源限制

在 `.streamlit/config.toml` 中：

```toml
[server]
maxUploadSize = 200
maxMessageSize = 200

[runner]
magicEnabled = false
```

---

## 成本

**完全免费**！无需信用卡。

---

## 升级选项

如果免费版不够用，可以考虑：

| 方案 | 价格 | 资源 |
|------|------|------|
| Community | 免费 | 1GB RAM, 1 CPU |
| Starter | $20/月 | 4GB RAM, 2 CPU |
| Team | $250/月 | 团队协作功能 |

---

## 总结

**优点**：
- ✅ 完全免费
- ✅ 部署超简单
- ✅ 自动 HTTPS
- ✅ 无需运维

**缺点**：
- ⚠️ 必须公开代码
- ⚠️ 资源有限
- ⚠️ 不活跃会睡眠

**适合**：
- 演示和测试
- 小规模使用
- 教学和学习

---

**部署时间**：5 分钟  
**成本**：完全免费
