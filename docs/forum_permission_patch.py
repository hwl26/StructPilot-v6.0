"""
论坛权限修复补丁

需要在以下位置添加权限检查：
1. 点赞（问题和回答）
2. 回答问题
3. 添加评论
4. 采纳答案（保留原有逻辑：问题作者可以采纳）
"""

# 第 1 步：修改点赞按钮（问题） - 在 _render_question_detail 函数中
# 第 340-352 行

OLD_CODE_1 = '''
    with col1:
        user = st.session_state.get("username", "guest")
        question_id = question["id"]
        upvotes = question.get("upvotes", 0)

        has_upvoted = has_user_upvoted(user, question_id, "question")

        if st.button(f"{'👍' if not has_upvoted else '✅'} {upvotes}", key=f"upvote_q_{question_id}"):
            if upvote(user, question_id, "question"):
                st.rerun()
'''

NEW_CODE_1 = '''
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
            st.caption("登录后可点赞")
'''

# 第 2 步：修改点赞按钮（回答） - 在 _render_answer_card 函数中
# 第 398-407 行

OLD_CODE_2 = '''
            with col_upvote:
                user = st.session_state.get("username", "guest")
                has_upvoted = has_user_upvoted(user, answer_id, "answer")

                if st.button(
                    f"{'👍' if not has_upvoted else '✅'} 点赞",
                    key=f"upvote_a_{answer_id}"
                ):
                    if upvote(user, answer_id, "answer"):
                        st.rerun()
'''

NEW_CODE_2 = '''
            with col_upvote:
                from utils.user_manager import get_current_user
                current_user = get_current_user()
                user_role = current_user.get("role", "guest") if current_user else "guest"
                user = current_user.get("username", "guest") if current_user else "guest"

                has_upvoted = has_user_upvoted(user, answer_id, "answer")

                # 仅成员和管理员可以点赞
                if user_role in ["member", "admin"]:
                    if st.button(
                        f"{'👍' if not has_upvoted else '✅'} 点赞",
                        key=f"upvote_a_{answer_id}"
                    ):
                        if upvote(user, answer_id, "answer"):
                            st.rerun()
                else:
                    st.button("👍 点赞", key=f"upvote_a_{answer_id}", disabled=True)
'''

# 第 3 步：修改采纳答案按钮 - 在 _render_answer_card 函数中
# 第 409-415 行

OLD_CODE_3 = '''
            with col_accept:
                # 只有问题作者可以采纳
                if user == question.get("author") and not is_accepted:
                    if st.button("✅ 采纳", key=f"accept_{answer_id}", type="primary"):
                        if accept_answer(question["id"], answer_id):
                            st.success("已采纳为最佳答案")
                            st.rerun()
'''

NEW_CODE_3 = '''
            with col_accept:
                from utils.user_manager import get_current_user
                current_user = get_current_user()
                user_role = current_user.get("role", "guest") if current_user else "guest"
                user = current_user.get("username", "guest") if current_user else "guest"

                # 只有问题作者和管理员可以采纳
                is_author = (user == question.get("author"))
                can_accept = (user_role == "admin" or is_author) and not is_accepted

                if can_accept:
                    if st.button("✅ 采纳", key=f"accept_{answer_id}", type="primary"):
                        if accept_answer(question["id"], answer_id):
                            st.success("已采纳为最佳答案")
                            st.rerun()
'''

# 第 4 步：修改回答表单 - 需要找到 _render_answer_form 函数
# 预计在第 420-450 行左右

print("论坛权限修复补丁已准备好")
print("需要手动修改的位置：")
print("1. _render_question_detail() - 第 340-352 行（点赞问题）")
print("2. _render_answer_card() - 第 398-407 行（点赞回答）")
print("3. _render_answer_card() - 第 409-415 行（采纳答案）")
print("4. _render_answer_form() - 待定位（回答表单权限）")
