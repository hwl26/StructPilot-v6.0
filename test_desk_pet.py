"""测试桌宠组件是否能正常渲染"""
import streamlit as st
from ui.components.desk_pet import render_desk_pet

st.set_page_config(page_title="桌宠测试", layout="wide")

st.title("🐧 桌宠渲染测试")

# 简单的桌宠配置
pet_type = "penguin"
pet_svg = """<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <circle cx="32" cy="32" r="28" fill="#e0f2fe"/>
  <circle cx="24" cy="28" r="4" fill="#1e293b"/>
  <circle cx="40" cy="28" r="4" fill="#1e293b"/>
  <path d="M 20 38 Q 32 42 44 38" stroke="#f59e0b" stroke-width="2" fill="none"/>
</svg>"""

ctx_msgs = ["你好～我是测试桌宠！"]
pet_msgs = ["陪你做实验～"]
body_msgs = ["需要帮忙吗？"]
tail_msgs = ["加油！"]
quick_qs = ["测试问题1", "测试问题2"]

theme = {
    "sidebar": "#f8fafc",
    "sidebar_border": "#e2e8f0",
    "app": "#ffffff",
    "text": "#0f172a",
    "accent": "#2563eb",
}

st.info("如果右下角出现小企鹅，说明桌宠组件正常。")

# 渲染桌宠
action = render_desk_pet(
    pet_type=pet_type,
    pet_svg=pet_svg,
    ctx_msgs=ctx_msgs,
    pet_msgs=pet_msgs,
    body_msgs=body_msgs,
    tail_msgs=tail_msgs,
    quick_qs=quick_qs,
    theme=theme,
    is_dark=False,
    pet_mood="idle",
    pet_size=64,
)

if action:
    st.success(f"桌宠动作：{action}")

st.markdown("---")
st.caption("💡 如果桌宠未显示，请查看浏览器 Console（F12）中的错误信息。")
