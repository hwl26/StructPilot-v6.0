"""我的空间 Tab 渲染组件

提供个人专属功能：
- 个人笔记管理
- LLM 润色笔记转经验
- 我的贡献审核状态
"""

from __future__ import annotations
import json
import streamlit as st
from pathlib import Path
from datetime import datetime
import uuid

BASE_DIR = Path(__file__).resolve().parent.parent


def render_my_space():
    """渲染我的空间主界面"""

    # 获取当前用户
    from utils.user_manager import get_current_user, load_user_notes, save_user_note, delete_user_note
    current_user = get_current_user()

    if not current_user:
        st.warning("⚠️ 请先登录才能使用此功能")
        st.info("💡 在左侧边栏「👤 用户笔记」中登录")
        st.caption("**提示**：如果已登录但仍显示此消息，请刷新页面")
        return

    # 显示当前用户信息
    st.caption(f"👤 当前用户：**{current_user.get('display_name', current_user.get('username'))}**")

    # 子Tab结构
    space_tabs = st.tabs(["📝 个人笔记", "✨ 笔记润色", "📤 我的贡献"])

    with space_tabs[0]:
        render_personal_notes(current_user)

    with space_tabs[1]:
        render_note_polish(current_user)

    with space_tabs[2]:
        render_my_contributions(current_user)


def render_personal_notes(current_user):
    """渲染个人笔记管理"""
    st.markdown("### 📝 个人笔记")
    st.caption("记录你的实验心得、参数设置、问题解决方案")

    from utils.user_manager import load_user_notes, save_user_note, delete_user_note

    username = current_user.get("username")
    notes = load_user_notes(username)

    st.info(f"📊 共 {len(notes)} 条笔记")

    # 新建笔记
    with st.expander("➕ 新建笔记", expanded=False):
        with st.form("new_note_form"):
            note_title = st.text_input("笔记标题 *", placeholder="如：Motion Correction 参数设置")
            note_content = st.text_area(
                "笔记内容 *",
                placeholder="记录你的实验心得、参数设置、遇到的问题和解决方案...",
                height=150
            )

            col1, col2 = st.columns(2)
            with col1:
                note_step = st.selectbox(
                    "相关步骤（可选）",
                    [""] + [
                        "cp_01 数据导入", "cp_02 运动校正", "cp_03 CTF估计",
                        "cp_04 颗粒挑选", "cp_05 颗粒提取", "cp_06 2D分类",
                        "cp_07 Ab-initio", "cp_08 3D分类", "cp_09 3D精修"
                    ]
                )
            with col2:
                note_tags = st.text_input("标签（可选）", placeholder="用逗号分隔，如：参数,问题,解决方案")

            submitted = st.form_submit_button("保存笔记", use_container_width=True, type="primary")

            if submitted:
                if not note_title.strip() or not note_content.strip():
                    st.error("❌ 标题和内容不能为空")
                else:
                    note_id = str(uuid.uuid4())[:8]
                    new_note = {
                        "id": note_id,
                        "title": note_title.strip(),
                        "content": note_content.strip(),
                        "step": note_step.split()[0] if note_step else "",
                        "tags": [t.strip() for t in note_tags.split(",") if t.strip()],
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    }

                    if save_user_note(username, new_note):
                        st.success("✅ 笔记已保存")
                        st.rerun()
                    else:
                        st.error("❌ 保存失败，请重试")

    # 笔记列表
    if notes:
        st.divider()
        st.markdown("#### 📋 我的笔记")

        # 步骤筛选
        all_steps = ["全部"] + [
            "cp_01", "cp_02", "cp_03", "cp_04", "cp_05",
            "cp_06", "cp_07", "cp_08", "cp_09"
        ]
        step_filter = st.selectbox("按步骤筛选", all_steps, key="note_step_filter")

        # 过滤笔记
        if step_filter != "全部":
            filtered_notes = [n for n in notes if n.get("step") == step_filter]
        else:
            filtered_notes = notes

        st.caption(f"显示 {len(filtered_notes)} / {len(notes)} 条笔记")

        # 显示笔记
        for note in sorted(filtered_notes, key=lambda x: x.get("updated_at", ""), reverse=True):
            note_id = note.get("id", "")
            title = note.get("title", "无标题")
            content = note.get("content", "")
            step = note.get("step", "")
            tags = note.get("tags", [])
            created_at = note.get("created_at", "")[:10]

            with st.expander(f"📄 {title}", expanded=False):
                st.markdown(f"**创建时间**：{created_at}")
                if step:
                    st.markdown(f"**相关步骤**：{step}")
                if tags:
                    st.markdown(f"**标签**：{', '.join(tags)}")

                st.markdown("---")
                st.markdown(content)

                st.markdown("---")
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✏️ 编辑", key=f"edit_note_{note_id}", use_container_width=True):
                        st.session_state[f"editing_note_{note_id}"] = True
                        st.rerun()

                with col2:
                    if st.button("✨ 润色", key=f"polish_note_{note_id}", use_container_width=True):
                        st.session_state["polish_note_id"] = note_id
                        st.session_state["active_space_tab"] = 1  # 切换到润色Tab
                        st.rerun()

                with col3:
                    if st.button("🗑️ 删除", key=f"delete_note_{note_id}", use_container_width=True):
                        if delete_user_note(username, note_id):
                            st.success("✅ 笔记已删除")
                            st.rerun()
                        else:
                            st.error("❌ 删除失败")

                # 编辑模式
                if st.session_state.get(f"editing_note_{note_id}"):
                    st.markdown("---")
                    st.markdown("**编辑笔记**")
                    with st.form(f"edit_note_form_{note_id}"):
                        edit_title = st.text_input("标题", value=note.get("title", ""))
                        edit_content = st.text_area("内容", value=note.get("content", ""), height=150)

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_edit = st.form_submit_button("💾 保存", use_container_width=True)
                        with col_cancel:
                            cancel_edit = st.form_submit_button("❌ 取消", use_container_width=True)

                        if save_edit:
                            note["title"] = edit_title.strip()
                            note["content"] = edit_content.strip()
                            note["updated_at"] = datetime.now().isoformat()

                            if save_user_note(username, note, update=True):
                                st.session_state.pop(f"editing_note_{note_id}", None)
                                st.success("✅ 笔记已更新")
                                st.rerun()

                        if cancel_edit:
                            st.session_state.pop(f"editing_note_{note_id}", None)
                            st.rerun()
    else:
        st.info("💡 还没有笔记，点击上方「➕ 新建笔记」开始记录")


def render_note_polish(current_user):
    """渲染笔记润色功能"""
    st.markdown("### ✨ 笔记润色")
    st.caption("使用 AI 将口语化笔记润色为结构化的技术经验")

    from utils.user_manager import load_user_notes

    username = current_user.get("username")
    notes = load_user_notes(username)

    if not notes:
        st.info("💡 还没有笔记，先去「个人笔记」Tab 创建笔记吧")
        return

    # 选择要润色的笔记
    polish_note_id = st.session_state.get("polish_note_id")

    if polish_note_id:
        # 找到指定笔记
        note = next((n for n in notes if n.get("id") == polish_note_id), None)
        if note:
            st.success(f"✅ 已选择笔记：**{note.get('title')}**")
        else:
            polish_note_id = None
            st.session_state.pop("polish_note_id", None)

    if not polish_note_id:
        note_options = {n.get("id"): n.get("title", "无标题") for n in notes}
        selected_id = st.selectbox(
            "选择要润色的笔记",
            options=list(note_options.keys()),
            format_func=lambda x: note_options[x],
            key="select_polish_note"
        )
        note = next((n for n in notes if n.get("id") == selected_id), None)

    if not note:
        st.warning("⚠️ 未找到笔记")
        return

    # 显示原始笔记
    with st.expander("📄 原始笔记", expanded=True):
        st.markdown(f"**标题**：{note.get('title')}")
        st.markdown(f"**内容**：")
        st.text_area("", value=note.get("content", ""), height=200, disabled=True, label_visibility="collapsed")

    st.divider()

    # 润色选项
    st.markdown("#### 润色选项")
    col1, col2 = st.columns(2)
    with col1:
        polish_style = st.selectbox(
            "润色风格",
            options=["standard", "detailed", "concise"],
            format_func=lambda x: {"standard": "标准（平衡）", "detailed": "详细（完整）", "concise": "简洁（精炼）"}[x]
        )
    with col2:
        include_code = st.toggle("包含代码块格式", value=True)

    if st.button("✨ 开始润色", use_container_width=True, type="primary"):
        with st.spinner("正在使用 AI 润色..."):
            from utils.note_to_experience import polish_note

            polished = polish_note(
                note.get("content", ""),
                style=polish_style,
                include_code=include_code
            )

            if polished:
                st.session_state["polished_result"] = polished
                st.success("✅ 润色完成！")
                st.rerun()
            else:
                st.error("❌ 润色失败，请检查 LLM 配置")

    # 显示润色结果
    if st.session_state.get("polished_result"):
        st.divider()
        st.markdown("#### ✨ 润色结果")

        polished_text = st.session_state["polished_result"]
        st.text_area("", value=polished_text, height=300, disabled=True, label_visibility="collapsed")

        st.divider()
        st.markdown("#### 📤 下一步")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 保存为新笔记", use_container_width=True):
                # TODO: 实现保存逻辑
                st.info("功能开发中...")

        with col2:
            if st.button("📤 提交为经验", use_container_width=True):
                # TODO: 实现提交逻辑
                st.info("功能开发中...")

        with col3:
            if st.button("🔄 重新润色", use_container_width=True):
                st.session_state.pop("polished_result", None)
                st.rerun()


def render_my_contributions(current_user):
    """渲染我的贡献列表"""
    st.markdown("### 📤 我的贡献")
    st.caption("查看你提交的经验审核状态")

    username = current_user.get("username")

    # 加载经验库
    exp_path = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"

    try:
        exp_data = json.loads(exp_path.read_text(encoding="utf-8"))
        my_exps = [e for e in exp_data.get("entries", []) if e.get("author") == username]

        if my_exps:
            st.info(f"📊 共提交 {len(my_exps)} 条经验")

            # 按状态分组
            pending = [e for e in my_exps if e.get("status") == "pending"]
            approved = [e for e in my_exps if e.get("status") == "approved"]
            rejected = [e for e in my_exps if e.get("status") == "rejected"]

            st.markdown(f"⏳ 待审核：{len(pending)} | ✅ 已通过：{len(approved)} | ❌ 已驳回：{len(rejected)}")

            st.divider()

            # 显示经验列表
            for exp in sorted(my_exps, key=lambda x: x.get("date", ""), reverse=True):
                status = exp.get("status", "pending")
                status_badge = {"pending": "⏳ 待审核", "approved": "✅ 已通过", "rejected": "❌ 已驳回"}[status]

                with st.expander(f"{status_badge} {exp.get('title', '')}", expanded=False):
                    st.markdown(f"**分类**：{exp.get('category', '')}")
                    st.markdown(f"**步骤**：{exp.get('step', '')}")
                    st.markdown(f"**提交时间**：{exp.get('date', '')}")

                    if status == "approved":
                        st.markdown(f"**通过时间**：{exp.get('approved_at', '')[:10]}")

                    st.markdown("---")
                    st.markdown(f"**解决方案**：")
                    st.markdown(exp.get("solution", ""))
        else:
            st.info("💡 还没有提交任何经验，去「笔记润色」Tab 将笔记转为经验吧")

    except Exception as e:
        st.error(f"❌ 加载失败：{e}")
