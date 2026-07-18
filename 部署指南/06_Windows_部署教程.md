# Windows 笔记本部署到 Streamlit Cloud 完整教程

> 专为 Windows 用户设计，无需 Linux 知识

---

## 前置条件检查

### ✅ 你需要的（都很简单）

1. **GitHub 账号**（免费）
   - 没有？访问 [github.com](https://github.com/signup) 注册

2. **Git 工具**（免费）
   - 检查是否已安装：
   ```cmd
   git --version
   ```
   - 如果显示版本号 → 已安装 ✅
   - 如果报错 → 需要安装（见下方）

3. **网络连接**
   - 能访问 GitHub 和 Streamlit Cloud

### 🔧 安装 Git（如果还没有）

**方式 1：下载安装包（推荐）**

1. 访问 [git-scm.com/download/win](https://git-scm.com/download/win)
2. 下载 64-bit Git for Windows Setup
3. 双击安装，**全部使用默认选项**（一路 Next）
4. 安装完成后，重新打开命令提示符测试：
   ```cmd
   git --version
   ```

**方式 2：通过 Winget（Windows 11）**

```powershell
winget install Git.Git
```

---

## 第一步：准备代码（在你的笔记本上）

### 1.1 打开命令提示符

- 按 `Win + R`
- 输入 `cmd`
- 回车

### 1.2 进入项目目录

```cmd
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6
```

### 1.3 检查文件

```cmd
dir
```

确认看到：
- `main.py` ✅
- `requirements.txt` ✅
- `.env.example` ✅

---

## 第二步：创建 .gitignore 文件

### 2.1 创建文件

在记事本中创建一个新文件，内容如下：

```
.env
runtime/
.venv/
__pycache__/
*.pyc
*.log
.DS_Store
Thumbs.db
.pytest_cache/
*.sqlite3
```

### 2.2 保存文件

- **文件名**：`.gitignore`（注意前面有个点）
- **保存位置**：`D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6\`
- **编码**：UTF-8
- **重要**：保存类型选择 "所有文件"，不要是 `.gitignore.txt`

**快捷方式**（在命令提示符中）：

```cmd
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6

echo .env > .gitignore
echo runtime/ >> .gitignore
echo .venv/ >> .gitignore
echo __pycache__/ >> .gitignore
echo *.pyc >> .gitignore
echo *.log >> .gitignore
echo .pytest_cache/ >> .gitignore
echo *.sqlite3 >> .gitignore
```

---

## 第三步：上传到 GitHub

### 3.1 初始化 Git

```cmd
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6

git init
```

看到 `Initialized empty Git repository` → 成功 ✅

### 3.2 配置 Git（首次使用）

```cmd
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

### 3.3 添加文件

```cmd
git add .
```

### 3.4 提交

```cmd
git commit -m "Initial commit for Streamlit Cloud"
```

### 3.5 创建 GitHub 仓库

**在浏览器中操作**：

1. 访问 [github.com/new](https://github.com/new)
2. 填写信息：
   - **Repository name**：`StructPilot`
   - **Description**：`冷冻电镜数据处理智能陪跑助手`
   - **Public**（必须选择 Public，免费版要求）
   - **不要**勾选 "Add a README file"
   - **不要**勾选 "Add .gitignore"
3. 点击 "Create repository"
4. 复制页面显示的仓库地址（类似 `https://github.com/你的用户名/StructPilot.git`）

### 3.6 关联并推送

```cmd
# 关联远程仓库（替换为你的实际地址）
git remote add origin https://github.com/你的用户名/StructPilot.git

# 推送代码
git branch -M main
git push -u origin main
```

**如果提示输入用户名和密码**：
- 用户名：你的 GitHub 用户名
- 密码：需要使用 **Personal Access Token**（不是 GitHub 密码）

**生成 Token**：
1. 访问 [github.com/settings/tokens](https://github.com/settings/tokens)
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 Token
5. 把 Token 作为密码粘贴

---

## 第四步：部署到 Streamlit Cloud

### 4.1 访问 Streamlit Cloud

打开浏览器，访问：[share.streamlit.io](https://share.streamlit.io)

### 4.2 登录

点击 "Sign in with GitHub"，授权登录

### 4.3 创建新应用

1. 点击右上角 "New app"
2. 填写信息：
   - **Repository**：`你的用户名/StructPilot`
   - **Branch**：`main`
   - **Main file path**：`main.py`
   - **App URL**：随便起个名字（如 `structpilot-demo`）

### 4.4 配置环境变量

点击 "Advanced settings"，添加环境变量：

```
STRUCTPILOT_LLM_PROVIDER = openai_compatible

STRUCTPILOT_LLM_API_KEY = 你的实际API密钥

STRUCTPILOT_LLM_MODEL = Qwen/Qwen3-VL-32B-Instruct

STRUCTPILOT_LLM_BASE_URL = https://api.siliconflow.cn/v1

STRUCTPILOT_EMBEDDING_MODEL = BAAI/bge-m3

STRUCTPILOT_EMBEDDING_API_KEY = 你的实际Embedding密钥

STRUCTPILOT_AUDIO_MODEL = FunAudioLLM/SenseVoiceSmall

STRUCTPILOT_AUDIO_API_KEY = 你的实际Audio密钥
```

**⚠️ 注意**：不要有多余的引号，直接填值

### 4.5 部署

点击 "Deploy!"

等待 3-5 分钟，部署完成后会自动打开应用。

---

## 第五步：访问和分享

### 你的应用地址

```
https://你的应用名.streamlit.app
```

例如：`https://structpilot-demo.streamlit.app`

### 分享给他人

直接把这个链接发给任何人，他们无需登录就能访问！

---

## 常见问题

### Q1: Git 推送时提示认证失败

**解决**：使用 Personal Access Token 而不是密码

1. 生成 Token：[github.com/settings/tokens](https://github.com/settings/tokens)
2. 在弹出的密码框中粘贴 Token

### Q2: 命令提示符中文乱码

**解决**：

```cmd
chcp 65001
```

### Q3: 找不到 .gitignore 文件

**原因**：Windows 资源管理器默认隐藏以 `.` 开头的文件

**解决**：
- 打开资源管理器
- 点击 "查看" → 勾选 "隐藏的项目"
- 或者直接在命令提示符创建（见上文）

### Q4: 部署失败，提示找不到模块

**检查**：`requirements.txt` 是否完整

**修复**：确保包含所有依赖：

```txt
streamlit>=1.35,<2.0
langgraph>=0.2.0
langchain-core>=0.2.0
python-dotenv>=1.0
requests>=2.31
loguru>=0.7
numpy>=1.24
streamlit-paste-button>=0.1.2
Pillow>=10.0
```

### Q5: 应用显示 "Sleeping"

**原因**：免费版不活跃时会睡眠

**解决**：首次访问等待 10-30 秒唤醒即可

---

## 更新代码（以后修改后）

### 本地修改后推送

```cmd
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6

git add .
git commit -m "更新描述"
git push
```

Streamlit Cloud 会自动检测并重新部署（约 2-3 分钟）

---

## 完整流程总结

```
1. 安装 Git
   ↓
2. 创建 .gitignore
   ↓
3. Git 初始化和提交
   ↓
4. GitHub 创建仓库
   ↓
5. 推送代码到 GitHub
   ↓
6. Streamlit Cloud 部署
   ↓
7. 完成！获得公开访问链接
```

**总耗时**：15-30 分钟（首次）

---

## 图形界面方式（如果不想用命令行）

### 使用 GitHub Desktop

1. **下载安装**
   - 访问 [desktop.github.com](https://desktop.github.com/)
   - 下载并安装

2. **添加项目**
   - 打开 GitHub Desktop
   - File → Add Local Repository
   - 选择 `D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\StructPilot_v6`

3. **发布到 GitHub**
   - 点击 "Publish repository"
   - 取消勾选 "Keep this code private"
   - 点击 "Publish"

4. **后续更新**
   - 修改代码后，GitHub Desktop 会自动检测
   - 填写 Summary，点击 "Commit to main"
   - 点击 "Push origin"

---

## 需要帮助？

如果遇到问题：

1. **检查错误信息**：仔细阅读红色提示
2. **查看文档**：重新阅读对应章节
3. **搜索问题**：复制错误信息到百度/Google
4. **截图提问**：把错误截图发给我

---

**恭喜！你现在知道如何在 Windows 上部署了！** 🎉

**下一步**：按照上面的步骤，15 分钟内完成部署！
