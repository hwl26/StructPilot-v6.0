"""测试动态Tab渲染。

验证入门/教学模式下设置Tab是否正常显示。
"""

import streamlit as st

st.set_page_config(page_title="Tab Test", layout="wide")

st.title("动态Tab测试")

# 模拟app_mode
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "beginner"

# 模式选择器
mode = st.selectbox("选择模式", ["beginner", "teaching", "expert"])
if mode != st.session_state.app_mode:
    st.session_state.app_mode = mode
    st.rerun()

st.markdown(f"**当前模式**: {st.session_state.app_mode}")
st.markdown("---")

# 动态Tab
_app_mode = st.session_state.get("app_mode", "beginner")
if _app_mode in ["beginner", "teaching"]:
    tab_chat, tab_settings = st.tabs(["对话陪跑", "设置"])
    tab_report = None
else:
    tab_chat, tab_report, tab_settings = st.tabs(["对话陪跑", "报告导出", "设置"])

# Tab 1: 对话陪跑
with tab_chat:
    st.markdown("### 对话陪跑")
    st.success("✅ 对话陪跑Tab内容正常显示")
    st.write(f"当前模式：{_app_mode}")

# Tab 2: 报告导出（仅高级模式）
if tab_report is not None:
    with tab_report:
        st.markdown("### 报告导出")
        st.success("✅ 报告导出Tab内容正常显示（仅高级模式）")

# Tab 3: 设置
with tab_settings:
    st.markdown("### 设置")
    st.success("✅ 设置Tab内容正常显示")
    st.write(f"当前模式：{_app_mode}")

    st.markdown("#### LLM 设置")
    provider = st.selectbox("选择LLM提供商", ["不启用", "OpenAI", "本地Ollama"])
    st.text_input("API Key", type="password")

    st.markdown("#### 桌宠设置")
    pet_size = st.slider("桌宠大小", 50, 200, 100)
    st.checkbox("显示桌宠")

    st.markdown("#### 主题设置")
    theme = st.selectbox("配色方案", ["静谧蓝", "墨竹绿", "雅致紫", "深邃黑"])

st.markdown("---")
st.caption("💡 测试说明：切换模式后，检查各Tab是否正常显示内容")
