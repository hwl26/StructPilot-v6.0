# StructPilot v6.0 Final — 启动和使用指南

## 🚀 快速启动

### Windows 用户（推荐）

**双击运行**：`start.bat`

该脚本会自动：
1. 检查 Python 和 Streamlit 是否安装
2. 启动应用
3. 在浏览器中打开 http://localhost:8501

---

### 命令行启动（所有平台）

```bash
# 1. 打开终端/命令提示符
# 2. 进入项目目录
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\final_struct

# 3. 启动应用
streamlit run main.py
```

**首次启动**：浏览器会自动打开应用  
**后续启动**：如浏览器未自动打开，手动访问 http://localhost:8501

**停止应用**：在终端按 `Ctrl+C`

---

## 📋 环境要求

### 必需软件

- **Python**：3.8 或更高版本
- **Streamlit**：1.35 或更高版本

### 安装依赖

```bash
# 进入项目目录
cd final_struct

# 安装所有依赖
pip install -r requirements.txt
```

**核心依赖清单**：
```
streamlit>=1.35
langgraph>=0.2.0
langchain-core>=0.2.0
python-dotenv>=1.0
requests>=2.31
loguru>=0.7
numpy>=1.24
Pillow>=10.0
```

---

## 🎯 首次使用流程

### 1. 启动应用

运行 `start.bat` 或 `streamlit run main.py`

### 2. 需求问答（入门模式）

首次启动会弹出 5 个问题：

```
🎯 欢迎使用 StructPilot
让我们先了解你的需求，为你定制最合适的流程路线。

1️⃣ 你的研究目标是什么？
   ○ 初步质检（到 CTF Estimation 即可）
   ● 2D 分类筛选颗粒
   ○ 3D 重构（完整流程）

2️⃣ 你的样品类型？
   ● 膜蛋白（~200-400 kDa）
   ○ 大分子复合体（>500 kDa）
   ○ 小蛋白（<200 kDa）

3️⃣ 使用的电镜设备？
   ● Titan Krios 300kV
   ○ Talos Arctica 200kV
   ○ 其他

4️⃣ 目标分辨率？
   ○ 粗筛（>10Å）
   ● 中等（5-10Å）
   ○ 高分辨（<5Å）

5️⃣ 有经验师兄师姐带吗？
   ● 有
   ○ 独立探索

[✅ 生成我的专属流程]
```

### 3. 确认定制方案

系统会根据你的回答生成定制化流程：

```
✨ 根据你的需求，推荐以下路线：

✓ Import Movies
✓ Motion Correction
✓ CTF Estimation
✓ Blob Picker
✓ Extract Particles
✓ 2D Classification
⊗ Initial Model（跳过）
⊗ 3D Refinement（跳过）
...（共跳过 5 步）

📋 预填充参数：
· Pixel size: 0.86 Å/pix
· Voltage: 300 kV
· Particle diameter: ~150 Å
· 2D classes: 50

💡 原因：你的目标是 2D 分类筛选，
   完成颗粒提取和分类后即可。

[确认并开始] [重新问答]
```

### 4. 开始使用

点击"确认并开始"后，进入简化版流程，只显示你需要的步骤。

---

## 🎨 三种交互模式

### 🔧 入门模式（默认）

**适合**：零基础用户、首次使用

**特点**：
- 傻瓜式操作指令
- 参数已预填充
- 质检结果自动评估
- 课题组经验优先展示

**切换方式**：侧边栏 → 交互模式 → 🔧 入门模式

---

### 🎓 教学模式

**适合**：想理解原理、准备考试/答辩

**特点**：
- 5 要素教学卡片（做什么/参数含义/常见问题/判断标准）
- 交互测验（每步 3 题，答对 ≥67% 通过）
- 学习进度追踪

**切换方式**：侧边栏 → 交互模式 → 🎓 教学模式

**示例**：

```
📖 CTF Estimation 原理学习

📚 这一步做什么
CTF 描述了电镜如何将样品信息转化为图像...

🔑 关键参数含义
· CTF estimation method: CTFFIND4
  最通用的 CTF 估算算法...

⚠️ 常见问题
🥇 课题组经验：CTF 拟合率低（王师兄）
  → 检查像素尺寸是否正确...

🎯 判断标准
CTF 拟合率 > 70%...

[我已理解，开始测验 →]
```

---

### ⚙️ 高级模式

**适合**：有经验用户、批量操作

**特点**：
- 参数导出（CSV / JSON）
- 预设管理（保存/加载）
- 贡献课题组经验
- 完整参数面板

**切换方式**：侧边栏 → 交互模式 → ⚙️ 高级模式

**高级功能**（页面底部折叠区）：

```
⚙️ 高级功能

[📥 导出参数] [💾 预设管理] [💡 贡献经验]

导出参数：
  [📄 CSV 格式] [📋 JSON 格式]

预设管理：
  保存为预设：[TRPV1 标准流程]
  备注：适用于 300kDa 膜蛋白
  [💾 保存]

贡献经验：
  标题：Motion Correction 报错 local motion...
  分类：报错解决方案
  症状：...
  解决：增大 B-factor 到 500...
  [提交经验]
```

---

## 🔧 常见问题

### Q1: 启动时报错 "ModuleNotFoundError: No module named 'streamlit'"

**原因**：Streamlit 未安装

**解决**：
```bash
pip install streamlit
```

---

### Q2: 应用启动后浏览器未自动打开

**解决**：手动在浏览器中访问 `http://localhost:8501`

---

### Q3: 端口 8501 被占用

**解决**：指定其他端口
```bash
streamlit run main.py --server.port 8888
```

---

### Q4: 想重新做需求问答

**解决方式 1**：刷新浏览器页面，清除缓存
**解决方式 2**：删除 `.streamlit/` 目录（如存在）
**解决方式 3**：代码中暂时不支持"重新问答"按钮，需手动清除 session_state

---

### Q5: 如何在入门模式中查看被跳过的步骤？

**方式 1**：侧边栏步骤列表中，跳过的步骤显示为 `⊗ ~~步骤名~~`
**方式 2**：切换到"高级模式"，可查看完整 12 步流程

---

## 📊 文件结构说明

```
final_struct/
├── main.py                        # 主入口
├── start.bat                      # Windows 启动脚本
├── requirements.txt               # 依赖清单
├── modes/                         # 三模式渲染层
│   ├── beginner.py                # 入门模式
│   ├── teaching.py                # 教学模式
│   └── expert.py                  # 高级模式
├── components/                    # UI 组件
│   ├── onboarding.py              # 需求问答
│   └── qa_card.py                 # 质检卡片
├── knowledge_base/                # 知识库
│   ├── teaching_cards.json        # 教学卡片
│   ├── quiz_bank.json             # 测验题库
│   ├── lab_experience_kb.json     # 课题组经验
│   └── ...                        # 其他知识文件
├── agents/                        # LLM agent 体系
├── graph/                         # LangGraph 编排
├── ui/                            # UI 组件库
└── docs/                          # 文档
```

---

## 🔐 数据隐私

### 本地存储

- **教学进度**：存储在浏览器 session，关闭标签页后清除
- **课题组经验**：存储在本地 `knowledge_base/lab_experience_kb.json`
- **预设文件**：存储在本地 `runtime/presets/`

### 网络请求

- **LLM 调用**：如启用 AI 模式，会调用配置的 LLM API（OpenAI / Anthropic / 本地）
- **无外部追踪**：不向第三方发送用户数据

---

## 📞 技术支持

### 文档

- [三模式架构说明](README_MODES.md)
- [需求问答优化说明](ONBOARDING_OPTIMIZATION.md)
- [构建报告](BUILD_REPORT.md)

### 问题反馈

如遇到问题，请提供：
1. 启动命令
2. 终端报错信息
3. 浏览器控制台错误（F12 → Console）
4. 操作步骤复现

---

## 🎓 使用建议

### 新手推荐路径

1. **首次使用**：使用入门模式，完成需求问答
2. **遇到质检不通过**：查看课题组经验，点击"去教学模式"
3. **完成一轮流程后**：切换到教学模式，做测验验证理解
4. **熟练后**：切换到高级模式，导出预设、贡献经验

### 团队协作建议

1. **师兄师姐**：通过高级模式"贡献经验"，积累课题组知识库
2. **新生**：入门模式 + 教学模式，快速上手
3. **预设共享**：高级模式导出预设文件，团队成员直接导入

---

**版本**：v6.0-final  
**更新时间**：2026-07-22  
**当前状态**：✅ 运行中 (http://localhost:8501)
