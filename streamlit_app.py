"""最小测试版本 - 验证Streamlit Cloud环境"""
import streamlit as st

st.set_page_config(page_title="测试", page_icon="🔬")
st.title("🎉 应用启动成功！")
st.success("如果你看到这个页面，说明部署环境正常")

if st.button("测试按钮"):
    st.balloons()
    st.write("按钮正常工作！")
