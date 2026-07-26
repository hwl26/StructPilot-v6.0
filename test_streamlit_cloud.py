"""Streamlit Cloud启动测试页面

用于验证部署环境是否正常，无需加载完整应用
"""
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="StructPilot启动测试", page_icon="🔬", layout="wide")

st.title("🔬 StructPilot 启动测试")
st.success("✅ Streamlit应用已成功启动！")

st.markdown(f"""
## 环境信息

- **当前时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Python版本**: {st.__version__}
- **Streamlit版本**: {st.__version__}

## 下一步

如果你看到这个页面，说明：
1. ✅ 代码已成功推送到GitHub
2. ✅ Streamlit Cloud已成功构建
3. ✅ 应用可以正常启动

现在可以访问完整应用：`main.py`
""")

# 测试session state
if st.button("测试Session State"):
    if "counter" not in st.session_state:
        st.session_state.counter = 0
    st.session_state.counter += 1
    st.write(f"点击次数: {st.session_state.counter}")

# 测试导入
st.markdown("---")
st.markdown("### 依赖检查")

try:
    import langgraph
    st.success(f"✅ langgraph {langgraph.__version__}")
except Exception as e:
    st.error(f"❌ langgraph 导入失败: {e}")

try:
    import streamlit_paste_button
    st.success(f"✅ streamlit_paste_button")
except Exception as e:
    st.error(f"❌ streamlit_paste_button 导入失败: {e}")

try:
    from graph.app import StructPilotApp
    st.success("✅ StructPilotApp 导入成功")
except Exception as e:
    st.error(f"❌ StructPilotApp 导入失败: {e}")

st.markdown("---")
st.info("💡 如果所有检查都通过，说明完整应用应该可以正常运行")
