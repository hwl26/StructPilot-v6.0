# 🔍 StructPilot 写入操作完整审查

## 📊 概览

StructPilot 中有 **8 个主要数据存储位置**，**7 大类写入途径**，共计约 **30 个写入操作按钮/功能**。

---

## 📁 数据存储位置（8个）

### **1. 用户系统**
**文件：** `runtime/config/users.json`

**数据结构：**
```json
{
  "users": [
    {
      "username": "admin",
      "password_hash": "...",
      "display_name": "管理员",
      "role": "admin",  // admin / member / guest
      "lab": "labA",
      "created_at": "2025-01-20"
    }
  ]
}
```

**写入途径：**
- ❌ **当前没有注册功能**（用户由管理员预设）
- ⚠️ 未来可能需要：用户注册、修改密码、个人资料编辑

---

### **2. 个人笔记**
**文件：** `runtime/notes/{username}_notes.json`

**数据结构：**
```json
{
  "notes": [
    {
      "id": "note001",
      "title": "Motion Correction 参数设置",
      "content": "我的实验心得...",
      "step": "cp_02",
      "tags": ["motion", "parameters"],
      "created_at": "2025-01-20",
      "updated_at": "2025-01-21"
    }
  ]
}
```

**写入途径：**
1. **新建笔记** — `main.py` 第 3365-3395 行
   - 位置：设置 Tab → 📝 个人笔记 → ➕ 新建笔记
   - 权限：成员 + 管理员
   - 影响：`runtime/notes/{username}_notes.json`

2. **删除笔记** — `main.py` 第 3400-3410 行
   - 位置：设置 Tab → 📝 个人笔记 → 笔记列表 → 🗑️ 删除
   - 权限：笔记所有者 + 管理员
   - 影响：`runtime/notes/{username}_notes.json`

---

### **3. 实验室经验库（Lab Board）**
**文件：** `runtime/lab_board/posts.json`

**数据结构：**
```json
{
  "entries": [
    {
      "id": "exp001",
      "title": "Motion Correction 报错解决",
      "category": "troubleshooting",
      "step": "cp_02",
      "symptoms_text": "local motion too large",
      "solution": "将 B-factor 调高到 500-800",
      "author": "张三",
      "date": "2025-01-20",
      "source": "user_contributed",  // user_contributed / official
      "status": "pending"            // pending / approved / rejected
    }
  ]
}
```

**写入途径：**

3. **贡献经验** — `components/lab_board.py`
   - 位置：对话陪跑 Tab → 右侧边栏 → ✍️ 贡献经验
   - 权限：成员 + 管理员
   - 影响：`runtime/lab_board/posts.json`（添加 `status: "pending"` 条目）
   - 函数：`contribute_experience()`

4. **审核经验（批准）** — `components/lab_board.py`
   - 位置：设置 Tab → 📚 实验室共同知识库 → 🔍 待审核经验 → ✅ 批准
   - 权限：仅管理员
   - 影响：`runtime/lab_board/posts.json`（修改 `status: "pending"` → `"approved"`）
   - 函数：`approve_experience()`

5. **审核经验（驳回）** — `components/lab_board.py`
   - 位置：设置 Tab → 📚 实验室共同知识库 → 🔍 待审核经验 → ❌ 驳回
   - 权限：仅管理员
   - 影响：`runtime/lab_board/posts.json`（修改 `status: "pending"` → `"rejected"`）
   - 函数：`reject_experience()` ⚠️ **未实现**

6. **删除经验** — `components/lab_board.py`
   - 位置：设置 Tab → 📚 实验室共同知识库 → 经验列表 → 🗑️ 删除
   - 权限：仅管理员
   - 影响：`runtime/lab_board/posts.json`（删除指定条目）
   - 函数：`delete_experience()` ⚠️ **未实现**

7. **重置经验库（从头开始）** — `utils/knowledge_manager.py`
   - 位置：设置 Tab → 高级功能 → 🔧 知识库管理 → 🔄 从头开始
   - 权限：仅管理员
   - 影响：`runtime/lab_board/posts.json`（删除所有 `source: "user_contributed"` 条目，保留 `source: "official"`）
   - 函数：`reset_knowledge_base()`

---

### **4. 论坛（Forum）**
**文件：** `runtime/forum/forum_posts.json`

**数据结构：**
```json
{
  "posts": [
    {
      "id": "q001",
      "type": "question",
      "author": "张三",
      "author_display": "张三",
      "author_lab": "labA",
      "title": "Motion Correction 报错如何解决？",
      "content": "详细描述...",
      "tags": ["cryosparc", "error"],
      "software": "cryoSPARC",
      "step": "cp_02",
      "upvotes": 5,
      "views": 120,
      "answers_count": 2,
      "accepted_answer_id": "a001",
      "status": "answered",  // open / answered
      "created_at": "2025-01-20"
    }
  ],
  "answers": [
    {
      "id": "a001",
      "question_id": "q001",
      "author": "李四",
      "content": "解决方案...",
      "upvotes": 8,
      "is_accepted": true,
      "created_at": "2025-01-20"
    }
  ],
  "comments": [
    {
      "id": "c001",
      "parent_id": "a001",
      "parent_type": "answer",  // question / answer
      "author": "王五",
      "content": "补充说明...",
      "created_at": "2025-01-20"
    }
  ],
  "votes": [
    {
      "user": "张三",
      "target_id": "q001",
      "target_type": "question",
      "vote_type": "up"  // up / down
    }
  ]
}
```

**写入途径：**

8. **提问** — `components/forum_ui.py` → `render_forum_tab()`
   - 位置：讨论区 Tab → ➕ 提问
   - 权限：成员 + 管理员（⚠️ 当前访客也可以，待限制）
   - 影响：`runtime/forum/forum_posts.json`（添加 `posts` 条目）
   - 函数：`create_question()`

9. **回答** — `components/forum_ui.py` → `render_question_detail()`
   - 位置：讨论区 Tab → 问题详情 → 💬 回答这个问题
   - 权限：成员 + 管理员（⚠️ 当前访客也可以，待限制）
   - 影响：`runtime/forum/forum_posts.json`（添加 `answers` 条目）
   - 函数：`create_answer()`

10. **评论** — `components/forum_ui.py` → `render_question_detail()`
    - 位置：讨论区 Tab → 问题/回答 → 💬 添加评论
    - 权限：成员 + 管理员（⚠️ 当前访客也可以，待限制）
    - 影响：`runtime/forum/forum_posts.json`（添加 `comments` 条目）
    - 函数：`create_comment()`

11. **点赞** — `components/forum_ui.py` → `_render_question_card()`
    - 位置：讨论区 Tab → 问题/回答卡片 → 👍 点赞
    - 权限：成员 + 管理员（⚠️ 当前访客也可以，待限制）
    - 影响：`runtime/forum/forum_posts.json`（添加 `votes` 条目，增加 `upvotes` 计数）
    - 函数：`upvote()`

12. **采纳答案** — `components/forum_ui.py` → `render_question_detail()`
    - 位置：讨论区 Tab → 问题详情 → 回答卡片 → ✅ 采纳
    - 权限：问题作者 + 管理员
    - 影响：`runtime/forum/forum_posts.json`（设置 `accepted_answer_id`，标记 `is_accepted`）
    - 函数：`accept_answer()`

13. **删除问题/回答/评论** — ⚠️ **未实现**
    - 应该位置：讨论区 Tab → 内容卡片 → 🗑️ 删除
    - 应有权限：作者（自己的内容）+ 管理员（任何内容）
    - 影响：`runtime/forum/forum_posts.json`

---

### **5. 配置文件**

#### **5a. LLM 配置**
**文件：** `runtime/config/llm_config.json`

**写入途径：**

14. **保存 LLM 配置** — `main.py` 第 3520-3527 行
    - 位置：设置 Tab（高级模式）→ LLM 设置 → 💾 保存 LLM 配置
    - 权限：所有用户（⚠️ 建议限制为管理员）
    - 影响：`runtime/config/llm_config.json`
    - 函数：`app.llm.save_config()`

15. **保存 Embedding 配置** — `main.py` 第 3554-3560 行
    - 位置：设置 Tab（高级模式）→ 向量检索 → 💾 保存 Embedding 配置
    - 权限：所有用户（⚠️ 建议限制为管理员）
    - 影响：`runtime/config/llm_config.json`
    - 函数：`app.llm.save_embedding_config()`

16. **保存语音配置** — `main.py` 第 3630-3640 行
    - 位置：设置 Tab（高级模式）→ 语音转写 → 💾 保存语音转写配置
    - 权限：所有用户（⚠️ 建议限制为管理员）
    - 影响：`runtime/config/llm_config.json`
    - 函数：`app.llm.save_audio_config()`

#### **5b. UI 配置**
**文件：** `runtime/config/ui_settings.json` 和 `runtime/ui_settings.json`

**写入途径：**

17. **保存界面设置** — `main.py` 第 3337-3347 行（入门模式）
    - 位置：设置 Tab（入门/教学模式）→ 🎨 界面设置 → 💾 保存界面设置
    - 权限：所有用户
    - 影响：`runtime/ui_settings.json`
    - 函数：`save_ui_settings()`

18. **保存界面设置** — `main.py` 第 3690-3710 行（高级模式）
    - 位置：设置 Tab（高级模式）→ 界面设置 → 💾 保存设置
    - 权限：所有用户
    - 影响：`runtime/config/ui_settings.json`
    - 函数：`save_ui_settings()`

#### **5c. 用户配置**
**文件：** `runtime/config/users.json`

**写入途径：**
- ⚠️ **当前没有用户注册/修改功能**
- 用户数据由管理员手动管理或通过初始化脚本创建

---

### **6. 对话历史**
**文件：** `runtime/conversations/{user_id}_{session_id}.json`

**写入途径：**

19. **AI 对话** — `main.py` 对话陪跑 Tab → 发送消息
    - 位置：对话陪跑 Tab → 输入框 → 发送
    - 权限：所有用户
    - 影响：`runtime/conversations/` 目录下的对话历史文件
    - 函数：`state.add_message()` → 自动持久化

20. **清除会话数据** — `main.py` 第 3458-3464 行
    - 位置：设置 Tab（入门/教学模式）→ 🔄 数据管理 → 清除会话数据
    - 权限：所有用户
    - 影响：`st.session_state`（会话状态），不影响文件
    - 函数：清除 session_state 变量

---

### **7. Workflow 导出**
**文件：** 用户下载的 JSON 文件（不存储在服务器）

**写入途径：**

21. **生成 cryoSPARC Workflow** — `modes/beginner_wizard.py`
    - 位置：入门模式 → 参数向导 → 填写完参数 → ✅ 完成 → 🚀 生成 Workflow
    - 权限：所有用户
    - 影响：生成 JSON 文件供用户下载，**不写入服务器文件**
    - 函数：`generate_cryosparc_workflow()`

---

### **8. 知识库检索统计**
**文件：** `runtime/knowledge_hit_counts.json`

**数据结构：**
```json
{
  "doc_001": 5,
  "doc_002": 12,
  "exp_001": 3
}
```

**写入途径：**

22. **自动记录检索命中** — `knowledge_base/retriever.py`
    - 触发条件：AI 对话时，RAG 检索命中某个文档
    - 权限：自动（无需用户操作）
    - 影响：`runtime/knowledge_hit_counts.json`（增加命中计数）
    - 函数：`KnowledgeRetriever.search()` 内部自动记录

---

## 🎯 按权限分类

### **访客（Guest）— 0 个写入权限**
- ❌ **不能写入任何数据**
- ⚠️ 但当前论坛未限制，访客可以提问/回答/点赞（待修复）

---

### **成员（Member）— 11 个写入权限**

| # | 功能 | 影响的文件 | 位置 |
|---|------|-----------|------|
| 1 | 新建个人笔记 | `runtime/notes/{user}_notes.json` | 设置 → 个人笔记 |
| 2 | 删除个人笔记 | `runtime/notes/{user}_notes.json` | 设置 → 个人笔记 |
| 3 | 贡献经验 | `runtime/lab_board/posts.json` | 对话陪跑 → 贡献经验 |
| 4 | 论坛提问 | `runtime/forum/forum_posts.json` | 讨论区 → 提问 |
| 5 | 论坛回答 | `runtime/forum/forum_posts.json` | 讨论区 → 回答 |
| 6 | 论坛评论 | `runtime/forum/forum_posts.json` | 讨论区 → 评论 |
| 7 | 论坛点赞 | `runtime/forum/forum_posts.json` | 讨论区 → 点赞 |
| 8 | 采纳答案（自己的问题） | `runtime/forum/forum_posts.json` | 讨论区 → 采纳 |
| 9 | AI 对话 | `runtime/conversations/` | 对话陪跑 → 发送 |
| 10 | 保存界面设置 | `runtime/ui_settings.json` | 设置 → 界面设置 |
| 11 | 生成 Workflow | 下载文件（不存储） | 参数向导 → 生成 |

---

### **管理员（Admin）— 22 个写入权限**

**包含成员的所有权限 +：**

| # | 功能 | 影响的文件 | 位置 |
|---|------|-----------|------|
| 12 | 审核经验（批准） | `runtime/lab_board/posts.json` | 设置 → 知识库 → 批准 |
| 13 | 审核经验（驳回） | `runtime/lab_board/posts.json` | 设置 → 知识库 → 驳回 ⚠️ 未实现 |
| 14 | 删除经验 | `runtime/lab_board/posts.json` | 设置 → 知识库 → 删除 ⚠️ 未实现 |
| 15 | 重置经验库（从头开始） | `runtime/lab_board/posts.json` | 设置 → 高级功能 → 从头开始 |
| 16 | 删除论坛内容 | `runtime/forum/forum_posts.json` | 讨论区 → 删除 ⚠️ 未实现 |
| 17 | 采纳答案（任何问题） | `runtime/forum/forum_posts.json` | 讨论区 → 采纳 |
| 18 | 查看/删除他人笔记 | `runtime/notes/*.json` | ⚠️ 未实现 |
| 19 | 保存 LLM 配置 | `runtime/config/llm_config.json` | 设置 → LLM 设置 |
| 20 | 保存 Embedding 配置 | `runtime/config/llm_config.json` | 设置 → 向量检索 |
| 21 | 保存语音配置 | `runtime/config/llm_config.json` | 设置 → 语音转写 |
| 22 | 生成领域模板 | `runtime/domain_templates/` | 设置 → 高级功能 → 抽象框架 ⚠️ 未实现 UI |

---

## ⚠️ 权限问题汇总

### **高优先级（P0）— 必须修复**

1. **论坛权限未限制** ❌
   - 问题：访客可以提问、回答、评论、点赞
   - 影响文件：`runtime/forum/forum_posts.json`
   - 修复：在 `components/forum_ui.py` 中添加权限检查

2. **LLM 配置所有人可修改** ❌
   - 问题：普通成员可以修改 LLM/Embedding/语音配置
   - 影响文件：`runtime/config/llm_config.json`
   - 修复：限制为仅管理员可修改

---

### **中优先级（P1）— 应该实现**

3. **缺少经验驳回功能** ⚠️
   - 问题：管理员只能批准，不能驳回
   - 影响文件：`runtime/lab_board/posts.json`
   - 修复：添加 `reject_experience()` 函数和 UI 按钮

4. **缺少删除论坛内容功能** ⚠️
   - 问题：无法删除垃圾/违规问题/回答/评论
   - 影响文件：`runtime/forum/forum_posts.json`
   - 修复：添加删除功能（作者删除自己的，管理员删除任何）

5. **缺少删除经验功能** ⚠️
   - 问题：审核通过的经验无法删除（如发现错误）
   - 影响文件：`runtime/lab_board/posts.json`
   - 修复：添加 `delete_experience()` 函数

6. **管理员查看所有用户笔记** ⚠️
   - 问题：管理员无法查看/管理其他用户的笔记
   - 影响文件：`runtime/notes/*.json`
   - 修复：添加管理员视图

---

### **低优先级（P2）— 可以考虑**

7. **用户注册功能**
   - 当前：用户由管理员预设
   - 未来：支持用户自助注册（需要审核）

8. **用户修改密码/资料**
   - 当前：无法修改
   - 未来：用户可以修改密码、显示名称

9. **对话历史管理**
   - 当前：对话自动保存，无法管理
   - 未来：用户可以查看、删除自己的对话历史
   - 管理员可以查看所有对话（审计需求）

---

## 📊 数据文件依赖关系图

```
┌────────────────────────────────────────────────────────────┐
│                  StructPilot 数据存储                       │
└────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┼─────────────────┐
                    │         │                 │
        ┌───────────▼──┐  ┌───▼────────┐  ┌────▼──────────┐
        │ 用户系统     │  │ 内容数据   │  │  配置文件      │
        │ users.json   │  │            │  │                │
        └──────┬───────┘  └─────┬──────┘  └─────┬──────────┘
               │                │               │
        ┌──────▼──────┐  ┌──────▼──────┐  ┌────▼──────────┐
        │ 认证/授权   │  │ 笔记        │  │ LLM/UI 配置   │
        │             │  │ notes/      │  │ llm_config.json│
        └─────────────┘  │ {user}.json │  │ ui_settings.json│
                         └──────┬──────┘  └────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
            ┌───────▼──┐  ┌─────▼────┐  ┌─▼──────────┐
            │ 经验库   │  │ 论坛     │  │ 对话历史   │
            │lab_board │  │forum     │  │conversations/│
            │posts.json│  │posts.json│  │            │
            └──────────┘  └──────────┘  └────────────┘
```

---

## ✅ 建议的修复优先级

### **立即修复（本次对话）**
1. ✅ 论坛访客权限限制
2. ✅ LLM 配置限制为管理员
3. ✅ 经验库驳回按钮

### **决赛前完成**
4. 论坛删除功能
5. 经验库删除功能
6. 管理员查看所有笔记

### **后续优化**
7. 用户注册/修改密码
8. 对话历史管理

---

## 🎯 总结

**StructPilot 写入操作统计：**
- **数据存储位置：** 8 个
- **写入途径：** 22 个
- **待实现功能：** 6 个
- **权限问题：** 2 个高优先级 + 4 个中优先级

**核心数据文件：**
1. `runtime/config/users.json` — 用户系统
2. `runtime/notes/{user}_notes.json` — 个人笔记
3. `runtime/lab_board/posts.json` — **经验库（可重置）**
4. `runtime/forum/forum_posts.json` — 论坛
5. `runtime/config/llm_config.json` — LLM 配置
6. `runtime/config/ui_settings.json` — UI 配置
7. `runtime/conversations/` — 对话历史
8. `runtime/knowledge_hit_counts.json` — 检索统计

**「从头开始」按钮影响：**
- ✅ **仅影响**：`runtime/lab_board/posts.json`（删除 `source: "user_contributed"` 条目）
- ❌ **不影响**：其他所有文件

---

**完整审查文档已创建！** 📋✨
