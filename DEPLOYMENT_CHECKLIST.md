# Streamlit Cloud 部署检查清单

## ✅ 已完成

### 1. 依赖修复
- ✅ 添加 `anthropic>=0.25.0` 到 `requirements.txt`
- ✅ 添加 `langchain-anthropic>=0.1.0` 到 `requirements.txt`
- ✅ Commit: `fe8d652`

---

## 🔧 需要在Streamlit Cloud后台配置

### 2. Secrets配置（必须）

访问：https://share.streamlit.io/ → 你的应用 → Settings → Secrets

添加以下配置：

```toml
# AI API配置
[llm]
provider = "anthropic"  # 或 "openai" / "compatible"
api_key = "sk-ant-xxx..."  # 你的Claude API密钥
base_url = ""  # 如果使用兼容API则填写
model_name = "claude-3-5-sonnet-20241022"  # 或其他模型

# 可选：OpenAI配置
[openai]
api_key = "sk-xxx..."
base_url = "https://api.openai.com/v1"

# 管理员密码
[auth]
admin_password = "your_secure_password"
```

**重要**：
- `llm.api_key` 必须配置，否则AI功能无法使用
- `llm.provider` 决定使用的模型（anthropic/openai/compatible）

---

### 3. 环境变量（可选）

如果使用 `.env` 文件，需要在Secrets中添加：

```toml
ANTHROPIC_API_KEY = "sk-ant-xxx..."
OPENAI_API_KEY = "sk-xxx..."
```

---

## 🚀 部署后验证

### 步骤1：检查应用状态
1. 访问应用URL（图中显示一直转圈）
2. 查看右下角"Manage app" → "Logs"
3. 查找错误信息：
   - `ModuleNotFoundError` → 依赖缺失
   - `KeyError: 'llm'` → Secrets未配置
   - `ImportError` → 版本冲突

### 步骤2：查看详细日志

常见错误及解决方案：

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `No module named 'anthropic'` | requirements.txt缺失 | 已修复（commit fe8d652） |
| `KeyError: 'api_key'` | Secrets未配置 | 在后台添加secrets |
| `API key not found` | .env未加载 | 改用Secrets配置 |
| `Memory limit exceeded` | 应用太大 | 优化资源占用 |
| `Timeout after 600s` | 启动超时 | 减少启动时加载的内容 |

### 步骤3：测试核心功能
- ✅ 登录功能
- ✅ AI对话
- ✅ 智能问卷
- ✅ 参数配置
- ✅ Session持久化

---

## 📝 故障排查步骤

如果应用仍然转圈：

### 1. 查看实时日志
```bash
# 在Streamlit Cloud后台
Manage app → Logs → 查看最新错误
```

### 2. 常见问题

#### 问题A：依赖安装失败
**症状**：日志显示 `ERROR: Could not find a version that satisfies the requirement xxx`

**解决**：
- 检查 `requirements.txt` 版本号是否合理
- 尝试放宽版本限制（如 `>=0.25.0` 改为 `>=0.20.0`）

#### 问题B：API密钥未配置
**症状**：应用启动但AI功能报错 `API key not found`

**解决**：
1. Settings → Secrets → 添加API密钥
2. 重启应用（Reboot app）

#### 问题C：内存不足
**症状**：日志显示 `MemoryError` 或 `Killed`

**解决**：
- 减少启动时加载的数据
- 优化图片/资源文件大小
- 考虑升级到付费计划（更多内存）

#### 问题D：文件路径错误
**症状**：`FileNotFoundError: runtime/sessions/xxx.json`

**解决**：
- 确保 `runtime/` 目录存在且被Git跟踪
- 或在代码中动态创建目录：
```python
SESSION_DIR.mkdir(parents=True, exist_ok=True)
```

---

## 🔄 重新部署

修改后需要触发重新部署：

### 方法1：推送代码（自动触发）
```bash
git add .
git commit -m "fix: xxx"
git push origin main
```

### 方法2：手动重启
1. Manage app → Reboot app
2. 等待3-5分钟

---

## 📞 需要帮助？

如果仍然无法部署，请提供以下信息：

1. **Streamlit Cloud日志**（完整错误信息）
2. **应用URL**
3. **是否配置了Secrets**（不要发送真实API密钥）

截图或复制日志后，我可以进一步诊断。

---

## 🎯 下一步

- ✅ 依赖已修复，等待Streamlit Cloud重新构建
- ⏳ 预计3-5分钟后应用启动
- 🔍 如果仍失败，查看日志并反馈错误信息
