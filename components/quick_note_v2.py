"""快速笔记组件 - 分屏笔记功能

架构设计：
1. sidebar 部分：显示触发按钮，控制分屏模式开关
2. 主区域部分：检测分屏模式，自动渲染双栏布局（内容区 + 笔记面板）

用法：
- 在 sidebar 调用 render_quick_note_sidebar() 显示触发按钮
- 在主区域调用 check_split_note_mode() 返回 SplitLayout 上下文管理器
- 使用 with check_split_note_mode() as layout: 包裹主内容

主要特性：
- 分屏模式下自动创建双栏布局
- 笔记面板固定在右侧，可独立滚动
- 支持笔记保存、清空、收起等操作
- 自动持久化笔记内容
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime
import uuid
from contextlib import contextmanager
from typing import Iterator


def render_quick_note_sidebar() -> None:
    """在sidebar显示分屏笔记触发按钮

    注意：高级模式下禁用分屏笔记，因为布局可能已使用columns，
    再嵌套columns会超过Streamlit的1层限制。
    """
    # 检查当前模式
    current_app_mode = st.session_state.get("app_mode", "beginner")

    # 高级模式下禁用分屏笔记
    if current_app_mode == "expert":
        st.markdown("### 📝 快速笔记")
        st.info("💡 高级模式下请使用「我的空间」→「个人笔记」功能", icon="ℹ️")
        return

    st.markdown("### 📝 快速笔记")

    # 初始化状态
    if "split_note_mode" not in st.session_state:
        st.session_state["split_note_mode"] = False

    # 显示当前状态
    current_mode = st.session_state["split_note_mode"]
    status_text = "🟢 分屏已开启" if current_mode else "⚪ 分屏已关闭"
    st.caption(status_text)

    # 切换按钮
    button_text = "📖 收起笔记" if current_mode else "📝 打开分屏笔记"
    if st.button(button_text, use_container_width=True, key="toggle_split_note"):
        st.session_state["split_note_mode"] = not current_mode
        st.rerun()

    # 使用提示
    with st.expander("💡 使用说明", expanded=False):
        st.markdown("""
        **分屏笔记模式**：
        - 点击"打开分屏笔记"后，主区域将分为左右两栏
        - 左侧显示原有内容，右侧显示笔记面板
        - 可以边浏览内容边记笔记
        - 笔记自动保存到"我的空间"

        ⚠️ 注意：此功能仅在快速/教学模式下可用
        """)


class SplitLayout:
    """分屏布局上下文管理器

    根据分屏模式状态，决定是否创建双栏布局。
    用法：
        with check_split_note_mode() as layout:
            with layout.main_area():
                # 主内容代码
    """

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.main_col = None
        self.note_col = None

    def __enter__(self):
        if self.enabled:
            # 检测是否已在 column 内部（避免嵌套超过1层）
            # Streamlit 不支持 columns 嵌套超过1层
            try:
                # 创建双栏布局：7:3 比例
                self.main_col, self.note_col = st.columns([7, 3])
            except Exception as e:
                # 如果创建失败（可能是嵌套问题），禁用分屏
                st.warning("⚠️ 当前界面布局不支持分屏笔记，请在主界面使用", icon="⚠️")
                self.enabled = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 如果分屏模式开启，渲染笔记面板
        if self.enabled and self.note_col is not None:
            with self.note_col:
                _render_note_panel()

    @contextmanager
    def main_area(self) -> Iterator[None]:
        """返回主内容区域的上下文"""
        if self.enabled and self.main_col is not None:
            with self.main_col:
                yield
        else:
            # 非分屏模式，直接使用整个区域
            yield


def check_split_note_mode() -> SplitLayout:
    """检查分屏模式并返回布局管理器

    Returns:
        SplitLayout: 分屏布局管理器

    用法：
        with check_split_note_mode() as layout:
            with layout.main_area():
                st.write("主内容")
                # ... 其他主内容代码
    """
    # 检查登录状态和权限
    if not st.session_state.get("logged_in", False):
        return SplitLayout(False)

    if st.session_state.get("role") not in ["member", "admin"]:
        return SplitLayout(False)

    username = st.session_state.get("username", "")
    if not username:
        return SplitLayout(False)

    # 获取分屏模式状态
    split_mode = st.session_state.get("split_note_mode", False)
    return SplitLayout(split_mode)


def _render_note_panel() -> None:
    """渲染右侧笔记面板（内部函数）"""
    st.markdown("### 📝 快速笔记")
    st.caption("边浏览边记录")

    # 初始化笔记内容状态
    if "quick_note_content" not in st.session_state:
        st.session_state["quick_note_content"] = ""

    if "quick_note_title" not in st.session_state:
        st.session_state["quick_note_title"] = ""

    # 笔记标题输入
    note_title = st.text_input(
        "标题（可选）",
        value=st.session_state["quick_note_title"],
        placeholder="如：参数调整记录",
        key="split_note_title_input",
        label_visibility="collapsed"
    )
    st.session_state["quick_note_title"] = note_title

    # 笔记内容输入
    note_content = st.text_area(
        "笔记内容",
        value=st.session_state["quick_note_content"],
        height=400,
        placeholder="在这里快速记录...\n\n例如：\n• 调整了XX参数从A到B\n• 发现XX现象\n• 待解决：XX问题",
        key="split_note_content_input",
        label_visibility="collapsed"
    )
    st.session_state["quick_note_content"] = note_content

    # 操作按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存", type="primary", use_container_width=True, key="save_split_note"):
            _save_note(note_title, note_content)

    with col2:
        if st.button("🗑️ 清空", use_container_width=True, key="clear_split_note"):
            st.session_state["quick_note_content"] = ""
            st.session_state["quick_note_title"] = ""
            st.rerun()

    # 显示当前用户
    username = st.session_state.get("username", "")
    st.caption(f"👤 {username}")

    # 快捷收起按钮
    if st.button("📖 收起笔记", use_container_width=True, key="close_split_note_inline"):
        st.session_state["split_note_mode"] = False
        st.rerun()


def _save_note(title: str, content: str) -> None:
    """保存笔记（内部函数）"""
    if not content.strip():
        st.warning("请输入笔记内容", icon="⚠️")
        return

    # 导入保存函数
    from utils.user_manager import save_user_note_dict

    username = st.session_state.get("username", "")
    if not username:
        st.error("未找到用户信息", icon="❌")
        return

    # 生成标题（如果用户未输入）
    if title.strip():
        final_title = title.strip()
    else:
        final_title = f"快速笔记 {datetime.now().strftime('%m-%d %H:%M')}"

    # 构造笔记对象
    new_note = {
        "id": str(uuid.uuid4())[:8],
        "title": final_title,
        "content": content.strip(),
        "step": "",
        "tags": ["快速笔记"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # 保存笔记
    if save_user_note_dict(username, new_note):
        # 清空输入框
        st.session_state["quick_note_content"] = ""
        st.session_state["quick_note_title"] = ""
        st.toast("✅ 笔记已保存", icon="✅")
        st.rerun()
    else:
        st.toast("❌ 保存失败", icon="❌")
