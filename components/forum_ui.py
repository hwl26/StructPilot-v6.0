"""StructPilot 论坛 UI 组件

类似 Stack Overflow 的 Q&A 界面
"""

import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional
from utils.forum_data import (
    load_forum_data,
    create_question,
    create_answer,
    create_comment,
    upvote,
    accept_answer,
    get_question,
    get_answers,
    get_comments,
    search_posts,  # 修正函数名
    increment_views,
    has_user_upvoted
)


def render_forum_tab():
    """渲染论坛主页面"""
    st.markdown("## 💬 讨论区")

    # 顶部操作栏
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        search_query = st.text_input(
            "🔍 搜索问题",
            placeholder="输入关键词搜索...",
            label_visibility="collapsed",
            key="forum_search"
        )

    with col2:
        filter_tag = st.selectbox(
            "标签筛选",
            ["全部"] + ["cryosparc", "relion", "chimera", "error", "parameter", "workflow"],
            key="forum_filter_tag"
        )

    with col3:
        if st.button("➕ 提问", use_container_width=True, type="primary"):
            st.session_state["forum_show_ask"] = True

    st.markdown("---")

    # 提问表单
    if st.session_state.get("forum_show_ask", False):
        _render_ask_question_form()
        st.markdown("---")

    # 问题列表
    data = load_forum_data()
    questions = data.get("posts", [])

    # 过滤
    if search_query:
        questions = search_posts(keyword=search_query, tags=[filter_tag] if filter_tag != "全部" else None)
    elif filter_tag != "全部":
        questions = [q for q in questions if filter_tag in q.get("tags", [])]

    # 排序（最新在前）
    questions = sorted(questions, key=lambda x: x.get("created_at", ""), reverse=True)

    if not questions:
        st.info("🤔 还没有人提问，来做第一个提问者吧！")
        return

    # 显示问题列表
    for question in questions:
        _render_question_card(question)


def _render_ask_question_form():
    """渲染提问表单"""
    st.markdown("### 📝 提问")

    with st.form("ask_question_form"):
        title = st.text_input(
            "问题标题 *",
            placeholder="简洁描述你的问题（如：Motion Correction 报错如何解决？）",
            max_chars=200
        )

        content = st.text_area(
            "详细描述 *",
            placeholder="详细描述你遇到的问题、已尝试的方法、错误信息等...\n\n支持 Markdown 格式",
            height=200
        )

        col1, col2 = st.columns(2)

        with col1:
            software = st.selectbox(
                "相关软件",
                ["", "cryoSPARC", "RELION", "Chimera", "EMAN2", "cisTEM", "其他"],
                key="ask_software"
            )

        with col2:
            step = st.selectbox(
                "相关步骤",
                ["", "cp_01", "cp_02", "cp_03", "cp_04", "cp_05", "cp_06", "cp_07", "cp_08", "cp_09"],
                key="ask_step"
            )

        tags_input = st.text_input(
            "标签（用逗号分隔）",
            placeholder="如：cryosparc, error, motion_correction",
            key="ask_tags"
        )

        anonymous = st.checkbox("匿名提问", key="ask_anonymous")

        col_submit, col_cancel = st.columns(2)

        with col_submit:
            submitted = st.form_submit_button("✅ 发布问题", use_container_width=True, type="primary")

        with col_cancel:
            cancel = st.form_submit_button("❌ 取消", use_container_width=True)

        if cancel:
            st.session_state["forum_show_ask"] = False
            st.rerun()

        if submitted:
            if not title or not content:
                st.error("请填写问题标题和详细描述")
            else:
                # 解析标签
                tags = [t.strip() for t in tags_input.split(",") if t.strip()]
                if software and software != "其他":
                    tags.append(software.lower())

                # 获取当前用户信息
                user = st.session_state.get("username", "guest")
                user_display = st.session_state.get("display_name", user)
                user_lab = st.session_state.get("user_lab", "")

                # 创建问题
                question_id = create_question(
                    author=user,
                    author_display=user_display,
                    title=title,
                    content=content,
                    tags=tags,
                    software=software if software != "其他" else "",
                    step=step,
                    anonymous=anonymous,
                    author_lab=user_lab,
                    visibility="public"
                )

                st.success("✅ 问题已发布！")
                st.session_state["forum_show_ask"] = False
                st.session_state["forum_view_question"] = question_id
                st.rerun()


def _render_question_card(question: Dict):
    """渲染问题卡片"""
    question_id = question["id"]

    # 状态标识
    status_emoji = {
        "open": "🟢",
        "answered": "🟡",
        "closed": "🔴"
    }
    status_label = {
        "open": "待解答",
        "answered": "已回答",
        "closed": "已关闭"
    }

    with st.container():
        col1, col2 = st.columns([1, 10])

        with col1:
            # 点赞数
            upvotes = question.get("upvotes", 0)
            st.markdown(f"<div style='text-align:center;padding:10px;'>"
                       f"<div style='font-size:1.5rem;'>👍</div>"
                       f"<div style='font-size:1.2rem;font-weight:bold;'>{upvotes}</div>"
                       f"</div>", unsafe_allow_html=True)

        with col2:
            # 标题
            title = question.get("title", "无标题")
            if st.button(
                f"{status_emoji.get(question.get('status', 'open'), '🟢')} {title}",
                key=f"q_{question_id}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state["forum_view_question"] = question_id
                st.rerun()

            # 元信息
            author = question.get("author_display", "未知")
            created_at = question.get("created_at", "")
            answers_count = question.get("answers_count", 0)
            views = question.get("views", 0)

            # 解析时间（显示相对时间）
            try:
                dt = datetime.fromisoformat(created_at)
                time_diff = datetime.now() - dt
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}天前"
                elif time_diff.seconds >= 3600:
                    time_str = f"{time_diff.seconds // 3600}小时前"
                else:
                    time_str = f"{time_diff.seconds // 60}分钟前"
            except:
                time_str = "未知时间"

            meta = f"👤 {author} · 🕒 {time_str} · 💬 {answers_count}个回答 · 👁️ {views}次浏览"
            st.caption(meta)

            # 标签
            tags = question.get("tags", [])
            if tags:
                tag_html = " ".join([f"<span style='background:#e0e7ff;color:#4338ca;padding:2px 8px;border-radius:4px;font-size:0.85rem;margin-right:4px;'>{tag}</span>" for tag in tags])
                st.markdown(tag_html, unsafe_allow_html=True)

        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)


def render_question_detail():
    """渲染问题详情页"""
    question_id = st.session_state.get("forum_view_question")
    if not question_id:
        render_forum_tab()
        return

    question = get_question(question_id)
    if not question:
        st.error("问题不存在")
        if st.button("← 返回列表"):
            del st.session_state["forum_view_question"]
            st.rerun()
        return

    # 增加浏览量
    increment_views(question_id)

    # 返回按钮
    if st.button("← 返回讨论区"):
        del st.session_state["forum_view_question"]
        st.rerun()

    st.markdown("---")

    # 问题主体
    _render_question_detail(question)

    st.markdown("---")

    # 回答列表
    answers = get_answers(question_id)
    if answers:
        st.markdown(f"## 💡 {len(answers)} 个回答")
        for answer in sorted(answers, key=lambda x: (not x.get("is_accepted", False), -x.get("upvotes", 0))):
            _render_answer_card(answer, question)
    else:
        st.info("还没有人回答，来抢沙发吧！")

    st.markdown("---")

    # 回答表单
    _render_answer_form(question_id)


def _render_question_detail(question: Dict):
    """渲染问题详情"""
    # 标题
    st.markdown(f"# {question.get('title', '无标题')}")

    # 元信息
    author = question.get("author_display", "未知")
    created_at = question.get("created_at", "")
    status = question.get("status", "open")

    try:
        dt = datetime.fromisoformat(created_at)
        time_str = dt.strftime("%Y-%m-%d %H:%M")
    except:
        time_str = "未知时间"

    st.caption(f"👤 {author} · 🕒 {time_str}")

    # 标签
    tags = question.get("tags", [])
    if tags:
        tag_html = " ".join([f"<span style='background:#e0e7ff;color:#4338ca;padding:4px 12px;border-radius:6px;font-size:0.9rem;margin-right:6px;'>{tag}</span>" for tag in tags])
        st.markdown(tag_html, unsafe_allow_html=True)

    st.markdown("---")

    # 内容
    st.markdown(question.get("content", ""))

    # 操作栏
    col1, col2, col3 = st.columns([1, 1, 8])

    with col1:
        user = st.session_state.get("username", "guest")
        question_id = question["id"]
        upvotes = question.get("upvotes", 0)

        has_upvoted = has_user_upvoted(user, question_id, "question")

        if st.button(f"{'👍' if not has_upvoted else '✅'} {upvotes}", key=f"upvote_q_{question_id}"):
            if upvote(user, question_id, "question"):
                st.rerun()

    with col2:
        answers_count = question.get("answers_count", 0)
        st.button(f"💬 {answers_count}", key=f"answers_{question_id}", disabled=True)


def _render_answer_card(answer: Dict, question: Dict):
    """渲染回答卡片"""
    answer_id = answer["id"]
    is_accepted = answer.get("is_accepted", False)

    with st.container():
        # 采纳标记
        if is_accepted:
            st.success("✅ 已采纳为最佳答案")

        col1, col2 = st.columns([1, 10])

        with col1:
            # 点赞数
            upvotes = answer.get("upvotes", 0)
            st.markdown(f"<div style='text-align:center;padding:10px;'>"
                       f"<div style='font-size:1.3rem;'>👍</div>"
                       f"<div style='font-size:1.1rem;font-weight:bold;'>{upvotes}</div>"
                       f"</div>", unsafe_allow_html=True)

        with col2:
            # 作者和时间
            author = answer.get("author_display", "未知")
            created_at = answer.get("created_at", "")

            try:
                dt = datetime.fromisoformat(created_at)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = "未知时间"

            st.caption(f"👤 {author} · 🕒 {time_str}")

            # 内容
            st.markdown(answer.get("content", ""))

            # 操作栏
            col_upvote, col_accept, col_comment = st.columns([1, 1, 8])

            with col_upvote:
                user = st.session_state.get("username", "guest")
                has_upvoted = has_user_upvoted(user, answer_id, "answer")

                if st.button(
                    f"{'👍' if not has_upvoted else '✅'} 点赞",
                    key=f"upvote_a_{answer_id}"
                ):
                    if upvote(user, answer_id, "answer"):
                        st.rerun()

            with col_accept:
                # 只有问题作者可以采纳
                if user == question.get("author") and not is_accepted:
                    if st.button("✅ 采纳", key=f"accept_{answer_id}", type="primary"):
                        if accept_answer(question["id"], answer_id):
                            st.success("已采纳为最佳答案")
                            st.rerun()

        st.markdown("<hr style='margin:10px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)


def _render_answer_form(question_id: str):
    """渲染回答表单"""
    st.markdown("### 📝 写回答")

    with st.form(f"answer_form_{question_id}"):
        content = st.text_area(
            "你的回答",
            placeholder="分享你的经验和解决方案...\n\n支持 Markdown 格式",
            height=200,
            key=f"answer_content_{question_id}"
        )

        anonymous = st.checkbox("匿名回答", key=f"answer_anonymous_{question_id}")

        submitted = st.form_submit_button("✅ 发布回答", use_container_width=True, type="primary")

        if submitted:
            if not content.strip():
                st.error("请填写回答内容")
            else:
                user = st.session_state.get("username", "guest")
                user_display = st.session_state.get("display_name", user)

                answer_id = create_answer(
                    question_id=question_id,
                    author=user,
                    author_display=user_display,
                    content=content,
                    anonymous=anonymous
                )

                st.success("✅ 回答已发布！")
                st.rerun()
