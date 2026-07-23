# StructPilot v6.0 Final — 三模式架构版本

## 📋 概述

本版本在 v6.0 基础上实现了**三种交互模式**，满足不同用户需求：

| 模式 | 定位 | 适用场景 | 核心功能 |
|------|------|----------|----------|
| 🔧 **入门模式** | 傻瓜式 SOP 引导 | 零基础用户首次使用 | 极简操作指令、质检闭环、一键应用参数 |
| 🎓 **教学模式** | 原理学习+测验 | 理解每步的"为什么" | 5要素教学卡片、交互测验、知识验证 |
| ⚙️ **高级模式** | 效率工具+人机协作 | 有经验用户、批量操作 | 参数导出、预设管理、贡献经验 |

**核心原则**：底层12步工作流、知识库检索、LangGraph 编排**完全不变**——三模式只改变 UI 层渲染方式。

---

## 🏗️ 架构设计

```
StructPilot_v6 底层（不变）
├── graph/app.py（LangGraph 编排）
├── agents/（llm/expert/navigator等）
├── knowledge_base/（官方文档JSON）
└── ui/components/（参数卡片、截图渲染）

              ▼

         st.session_state.app_mode
         （控制UI层渲染方式）

         ┌────────┬────────┬────────┐
         ▼        ▼        ▼        ▼
   入门模式   教学模式   高级模式   (原v6双栏)
   beginner   teaching   expert     default
```

---

## 🆕 新增文件

### 1. 模式渲染层

```
modes/
├── __init__.py
├── beginner.py    # 入门模式：单栏简化布局
├── teaching.py    # 教学模式：教学卡片+测验
└── expert.py      # 高级模式：工具面板
```

### 2. UI 组件

```
components/
├── __init__.py
└── qa_card.py     # 质检卡片（评估+渲染）
```

### 3. 知识库（三个核心新增）

```
knowledge_base/
├── teaching_cards.json       # 教学卡片（5要素）
├── quiz_bank.json            # 测验题库
└── lab_experience_kb.json    # 课题组私有经验（🥇最高优先级）
```

---

## 📚 知识库四层架构

| 层级 | 来源 | 优先级 | 更新方式 |
|------|------|--------|----------|
| **L1: 课题组经验** | 师兄师姐实战踩坑记录 | ★★★★★ | 用户贡献→审核→生效 |
| **L2: 官方文档** | cryoSPARC/RELION Guide | ★★★★ | 定期同步 |
| **L3: GitHub经验** | Issues/Discussions 精选 | ★★★ | 手动收录 |
| **L4: AI推理** | LLM实时生成 | ★★ | 前三层无结果时兜底 |

**检索规则**：L1 → L2 → L3 → L4 逐层降级，课题组经验始终排在最前。

---

## 🎯 三模式功能清单

### 入门模式（Beginner）

- ✅ 每步展示"做什么 → 操作指令 → 截图 → 参数"
- ✅ 一键应用推荐参数（无需手动填写）
- ✅ 质检按钮：自动判断通过/警告/重做
- ✅ 质检不通过时优先展示课题组经验
- ✅ 引导按钮："去教学模式理解原理"
- ✅ 进度可视化（顶部进度条）

### 教学模式（Teaching）

- ✅ 5要素教学卡片：
  - 📚 这一步做什么
  - 🔑 关键参数含义
  - 📊 常见设置范围
  - ⚠️ 常见问题（优先课题组经验）
  - 🎯 判断标准
- ✅ 交互测验（每步3题，答对率≥67%通过）
- ✅ 教学进度追踪（st.session_state.teaching_progress）
- ✅ 测验通过后引导到高级模式

### 高级模式（Expert）

- ✅ 参数导出（CSV / JSON）
- ✅ 预设管理（保存/加载个人最佳实践）
- ✅ 贡献经验入口（录入课题组经验）
- ✅ 原有双栏布局保留（workspace + chat）
- 🔲 Workflow 文件生成（cryoSPARC 可导入）← 后续扩展

---

## 🚀 使用流程

### 首次使用

1. 启动应用 → 默认进入**入门模式**
2. 侧边栏选择软件（RELION / cryoSPARC）
3. 按照操作指令逐步完成 12 步
4. 遇到质检不通过 → 查看课题组经验 → 点击"去教学模式"

### 理解原理

1. 切换到**教学模式**
2. 阅读5要素教学卡片
3. 完成交互测验（3题，答对≥2题通过）
4. 测验通过 → 标记"已学习"

### 高效操作

1. 切换到**高级模式**
2. 导出当前步骤参数为 CSV/JSON
3. 保存预设供后续项目复用
4. 贡献经验到课题组知识库

---

## 🛠️ 开发说明

### 模式切换逻辑

```python
# main.py:1327-1332
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "beginner"

# main.py:3939-3955（路由器）
if _app_mode == "beginner":
    from modes import render_beginner_view
    render_beginner_view(_current_cp, state, app, run_command)
    st.stop()
elif _app_mode == "teaching":
    from modes import render_teaching_view
    render_teaching_view(_current_cp, state, app)
    st.stop()
# else: 保留原有双栏布局（高级模式+原有用户）
```

### 状态管理

| session_state 键 | 作用 | 初始值 |
|---|---|---|
| `app_mode` | 当前模式 | `"beginner"` |
| `mode_history` | 切换历史 | `[]` |
| `teaching_progress` | 教学进度 | `{}` |

### 知识库扩展

#### 添加新步骤的教学内容

**文件**：`knowledge_base/teaching_cards.json`

```json
{
  "cp_XX": {
    "step_name": "步骤名称",
    "beginner_instructions": ["①...", "②..."],
    "teaching_card": {
      "what": "做什么",
      "key_params": [{"name": "参数名", "meaning": "含义", "range": "范围"}],
      "common_problems": ["问题1", "问题2"],
      "success_criteria": "判断标准"
    },
    "quality_check": {
      "rules": [{"condition": "...", "status": "pass/warn/fail", "message": "..."}]
    }
  }
}
```

#### 添加测验题

**文件**：`knowledge_base/quiz_bank.json`

```json
{
  "cp_XX": {
    "questions": [
      {
        "question": "题目",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "correct": 1,  // 索引从0开始
        "explanation": "解释"
      }
    ]
  }
}
```

#### 贡献课题组经验

**方式1**：用户在高级模式中通过"贡献经验"表单提交

**方式2**：直接编辑 `knowledge_base/lab_experience_kb.json`

```json
{
  "entries": [
    {
      "id": "lab_XXX",
      "title": "简短标题",
      "step": "cp_XX",
      "symptoms": ["症状1", "症状2"],
      "solution": "解决方案详细描述",
      "author": "作者",
      "date": "2026-XX-XX",
      "status": "approved",  // pending / approved
      "tags": ["标签1", "标签2"]
    }
  ]
}
```

---

## ✅ 已完成清单

- [x] 三模式路由器（main.py）
- [x] 入门模式渲染（modes/beginner.py）
- [x] 教学模式渲染（modes/teaching.py）
- [x] 高级模式渲染（modes/expert.py）
- [x] 质检卡片组件（components/qa_card.py）
- [x] 教学卡片数据（4个核心步骤）
- [x] 测验题库（3个步骤×3题）
- [x] 课题组经验库（5条种子数据）
- [x] 侧边栏模式切换器
- [x] 模式状态管理
- [x] 语法验证通过

---

## 🔜 后续扩展方向

1. **完善教学内容**：补充剩余8个步骤的教学卡片和测验题
2. **质检规则引擎**：实现基于输出文件的自动质检（目前为兜底规则）
3. **Workflow 导出**：生成 cryoSPARC 可导入的 workflow JSON
4. **预设共享**：团队成员间预设文件导入/导出
5. **知识库审核UI**：管理员审核待验证经验的界面
6. **GitHub经验爬取**：自动收录 cryoSPARC/RELION 高质量 Issue
7. **用户行为追踪**：模式切换频率、学习进度统计

---

## 📞 联系方式

如有问题或建议，请联系项目组。

---

**版本**：v6.0-final  
**更新时间**：2026-07-22  
**架构设计**：基于原有 v6.0 + 三模式扩展
