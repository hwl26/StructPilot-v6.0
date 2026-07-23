"""StructPilot v6.0 — 三模式渲染层。

beginner / teaching / expert 三个模块各自暴露一个顶层 render 函数，
由 main.py 根据 st.session_state.app_mode 路由调用。

底层12步工作流、知识库检索、LangGraph 编排完全不受影响。
"""

from modes.beginner import render_beginner_view
from modes.teaching import render_teaching_view
from modes.expert import render_expert_view

__all__ = ["render_beginner_view", "render_teaching_view", "render_expert_view"]
