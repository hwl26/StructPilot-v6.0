# 🔧 权限修复完整方案

## ✅ 已完成（Commit: bc8f23f）

### **1. 论坛提问权限**
- ✅ 访客无法点击「➕ 提问」
- ✅ 提问表单权限检查

---

## ⏳ 待完成（剩余工作）

### **2. 论坛点赞权限（2处）**

#### **2a. 点赞问题 - `_render_question_detail()`**
**位置：** `components/forum_ui.py` 第 340-352 行

**修改前：**
```python
with col1:
    user = st.session_state.get("username", "guest")
    question_id = question["id"]
    upvotes = question.get("upvotes", 0)
    has_upvoted = has_user_upvoted(user, question_id, "question")

    if st.button(f"{'👍' if not has_upvoted else '✅'} {upvotes}", key=f"upvote_q_{question_id}"):
        if upvote(user, question_id, "question"):
            st.rerun()
```

**修改后：**
```python
with col1:
    from utils.user_manager import get_current_user
    current_user = get_current_user()
    user_role = current_user.get("role", "guest") if current_user else "guest"
    user = current_user.get("username", "guest") if current_user else "guest"

    question_id = question["id"]
    upvotes = question.get("upvotes", 0)
    has_upvoted = has_user_upvoted(user, question_id, "question")

    # 仅成员和管理员可以点赞
    if user_role in ["member", "admin"]:
        if st.button(f"{'👍' if not has_upvoted else '✅'} {upvotes}", key=f"upvote_q_{question_id}"):
            if upvote(user, question_id, "question"):
                st.rerun()
    else:
        st.button(f"👍 {upvotes}", key=f"upvote_q_{question_id}", disabled=True)
```

#### **2b. 点赞回答 - `_render_answer_card()`**
**位置：** `components/forum_ui.py` 第 398-407 行

**修改前：**
```python
with col_upvote:
    user = st.session_state.get("username", "guest")
    has_upvoted = has_user_upvoted(user, answer_id, "answer")

    if st.button(f"{'👍' if not has_upvoted else '✅'} 点赞", key=f"upvote_a_{answer_id}"):
        if upvote(user, answer_id, "answer"):
            st.rerun()
```

**修改后：**
```python
with col_upvote:
    from utils.user_manager import get_current_user
    current_user = get_current_user()
    user_role = current_user.get("role", "guest") if current_user else "guest"
    user = current_user.get("username", "guest") if current_user else "guest"

    has_upvoted = has_user_upvoted(user, answer_id, "answer")

    # 仅成员和管理员可以点赞
    if user_role in ["member", "admin"]:
        if st.button(f"{'👍' if not has_upvoted else '✅'} 点赞", key=f"upvote_a_{answer_id}"):
            if upvote(user, answer_id, "answer"):
                st.rerun()
    else:
        st.button("👍 点赞", key=f"upvote_a_{answer_id}", disabled=True)
```

---

### **3. 回答权限 - `_render_answer_form()`**
**位置：** `components/forum_ui.py` 第 420-452 行

**修改前：**
```python
def _render_answer_form(question_id: str):
    """渲染回答表单"""
    st.markdown("### 📝 写回答")

    with st.form(f"answer_form_{question_id}"):
        content = st.text_area(...)
        ...
        submitted = st.form_submit_button("✅ 发布回答", ...)

        if submitted:
            ...
```

**修改后：**
```python
def _render_answer_form(question_id: str):
    """渲染回答表单（仅成员和管理员）"""
    from utils.user_manager import get_current_user

    # 权限检查
    current_user = get_current_user()
    user_role = current_user.get("role", "guest") if current_user else "guest"

    if user_role not in ["member", "admin"]:
        st.info("💡 登录后可回答问题")
        return

    st.markdown("### 📝 写回答")

    with st.form(f"answer_form_{question_id}"):
        content = st.text_area(...)
        ...
        submitted = st.form_submit_button("✅ 发布回答", ...)

        if submitted:
            ...
            user = current_user.get("username", "guest")
            user_display = current_user.get("display_name", user)
            ...
```

---

### **4. 采纳答案权限 - `_render_answer_card()`**
**位置：** `components/forum_ui.py` 第 409-415 行

**修改前：**
```python
with col_accept:
    # 只有问题作者可以采纳
    if user == question.get("author") and not is_accepted:
        if st.button("✅ 采纳", key=f"accept_{answer_id}", type="primary"):
            if accept_answer(question["id"], answer_id):
                st.success("已采纳为最佳答案")
                st.rerun()
```

**修改后：**
```python
with col_accept:
    from utils.user_manager import get_current_user
    current_user = get_current_user()
    user_role = current_user.get("role", "guest") if current_user else "guest"
    user = current_user.get("username", "guest") if current_user else "guest"

    # 问题作者和管理员可以采纳
    is_author = (user == question.get("author"))
    can_accept = (user_role == "admin" or is_author) and not is_accepted

    if can_accept:
        if st.button("✅ 采纳", key=f"accept_{answer_id}", type="primary"):
            if accept_answer(question["id"], answer_id):
                st.success("已采纳为最佳答案")
                st.rerun()
```

---

### **5. 评论权限（待定位）**
**需要查找：** `create_comment()` 调用位置

**预计位置：** `_render_comment_section()` 或类似函数

**修改思路：** 同样添加权限检查，仅成员和管理员可以评论

---

### **6. 删除功能（需新增）**

#### **6a. 删除问题 - 新增函数**
**文件：** `utils/forum_data.py`

**新增函数：**
```python
def delete_question(question_id: str, user: str, user_role: str) -> bool:
    """删除问题（作者或管理员）"""
    data = load_forum_data()

    # 查找问题
    question = next((q for q in data["posts"] if q["id"] == question_id), None)
    if not question:
        return False

    # 权限检查
    is_author = (user == question["author"])
    can_delete = (user_role == "admin" or is_author)

    if not can_delete:
        return False

    # 删除问题
    data["posts"] = [q for q in data["posts"] if q["id"] != question_id]

    # 同时删除该问题的所有回答和评论
    data["answers"] = [a for a in data.get("answers", []) if a["question_id"] != question_id]
    data["comments"] = [c for c in data.get("comments", []) 
                       if not (c.get("parent_type") == "question" and c["parent_id"] == question_id)]

    # 保存
    save_forum_data(data)
    return True
```

#### **6b. 删除回答 - 新增函数**
```python
def delete_answer(answer_id: str, user: str, user_role: str) -> bool:
    """删除回答（作者或管理员）"""
    data = load_forum_data()

    # 查找回答
    answer = next((a for a in data.get("answers", []) if a["id"] == answer_id), None)
    if not answer:
        return False

    # 权限检查
    is_author = (user == answer["author"])
    can_delete = (user_role == "admin" or is_author)

    if not can_delete:
        return False

    # 删除回答
    data["answers"] = [a for a in data.get("answers", []) if a["id"] != answer_id]

    # 同时删除该回答的所有评论
    data["comments"] = [c for c in data.get("comments", []) 
                       if not (c.get("parent_type") == "answer" and c["parent_id"] == answer_id)]

    # 更新问题的回答计数
    question_id = answer["question_id"]
    for q in data["posts"]:
        if q["id"] == question_id:
            q["answers_count"] = max(0, q.get("answers_count", 0) - 1)
            break

    # 保存
    save_forum_data(data)
    return True
```

#### **6c. UI 添加删除按钮**
在 `_render_question_detail()` 和 `_render_answer_card()` 中添加删除按钮

---

## 📋 修复顺序建议

1. ✅ **已完成：** 提问权限（commit bc8f23f）
2. ⏳ **下一步：** 点赞权限（2处）- 最简单
3. ⏳ **之后：** 回答权限 - 较简单
4. ⏳ **然后：** 采纳答案权限 - 简单修改
5. ⏳ **最后：** 删除功能 - 需新增代码

---

## 🧪 测试清单

完成所有修复后，需要测试：

### **访客身份测试：**
- [ ] 无法点击「➕ 提问」
- [ ] 无法点赞问题
- [ ] 无法点赞回答
- [ ] 无法回答问题
- [ ] 无法评论
- [ ] 无法采纳答案
- [ ] 无法删除任何内容

### **成员身份测试：**
- [ ] 可以提问
- [ ] 可以点赞
- [ ] 可以回答
- [ ] 可以评论
- [ ] 可以采纳自己问题的答案
- [ ] 可以删除自己的问题/回答/评论
- [ ] 无法删除他人的内容

### **管理员身份测试：**
- [ ] 所有成员权限
- [ ] 可以采纳任何答案
- [ ] 可以删除任何问题/回答/评论

---

**预计工作量：** 剩余 4 处修改（点赞2处 + 回答1处 + 采纳1处）+ 删除功能（3个函数 + UI）
**总计：** 约 200-300 行代码

**是否继续修复？** 我可以一次性完成所有修复！
