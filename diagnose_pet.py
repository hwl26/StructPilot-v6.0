"""桌宠诊断脚本 - 检查为什么主程序中看不到桌宠"""
import streamlit as st

st.set_page_config(page_title="桌宠诊断", layout="wide")

st.title("🔍 桌宠诊断工具")

st.markdown("## 检查 1：Session State 配置")

pet_enabled = st.session_state.get("pet_enabled", "未设置，默认True")
pet_type = st.session_state.get("pet_type", "未设置，默认penguin")
pet_size = st.session_state.get("pet_size", "未设置，默认64")

col1, col2 = st.columns(2)
with col1:
    st.metric("pet_enabled", pet_enabled)
    st.metric("pet_type", pet_type)
    st.metric("pet_size", pet_size)

with col2:
    if st.button("强制启用桌宠"):
        st.session_state["pet_enabled"] = True
        st.success("已设置 pet_enabled = True")
        st.rerun()

    if st.button("强制禁用桌宠"):
        st.session_state["pet_enabled"] = False
        st.warning("已设置 pet_enabled = False")
        st.rerun()

st.markdown("---")
st.markdown("## 检查 2：UI Settings 文件")

import os
import json

# 查找 UI settings 文件
settings_paths = [
    "C:\\Users\\17706\\Documents\\struct\\StructPilot_v2_runtime\\config\\ui_settings.json",
    "config/ui_settings.json",
    "runtime/ui_settings.json",
]

st.write("**检查配置文件位置：**")
for path in settings_paths:
    exists = os.path.exists(path)
    st.write(f"- `{path}`: {'✅ 存在' if exists else '❌ 不存在'}")

    if exists:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            st.json(settings)
        except Exception as e:
            st.error(f"读取失败: {e}")

st.markdown("---")
st.markdown("## 检查 3：渲染测试")

st.write("点击下面的按钮，强制渲染一个测试桌宠：")

if st.button("🐧 渲染测试桌宠", type="primary"):
    from ui.components.simple_desk_pet import render_simple_desk_pet

    st.info("正在渲染桌宠...")
    render_simple_desk_pet(
        pet_type="penguin",
        pet_size=80,  # 更大以便看到
        pet_mood="bounce"  # 弹跳动画
    )
    st.success("桌宠渲染完成！请查看右下角。")

st.markdown("---")
st.markdown("## 检查 4：导入测试")

try:
    from ui.components.simple_desk_pet import render_simple_desk_pet, update_pet_mood
    st.success("✅ 简化版桌宠模块导入成功")
    st.code(f"render_simple_desk_pet: {render_simple_desk_pet}")
    st.code(f"update_pet_mood: {update_pet_mood}")
except Exception as e:
    st.error(f"❌ 简化版桌宠模块导入失败: {e}")

try:
    from ui.components.desk_pet import render_desk_pet
    st.success("✅ 完整版桌宠模块导入成功")
except Exception as e:
    st.warning(f"⚠️ 完整版桌宠模块导入失败: {e}")

st.markdown("---")
st.markdown("## 💡 诊断建议")

if pet_enabled == False:
    st.error("**问题：** pet_enabled 被设置为 False，桌宠已禁用")
    st.markdown("**解决方案：** 点击上面的「强制启用桌宠」按钮")
elif pet_enabled == True or pet_enabled == "未设置，默认True":
    st.success("**配置正常：** pet_enabled 已启用")
    st.markdown("**如果主程序还是看不到桌宠，可能原因：**")
    st.markdown("1. 主程序的渲染代码位置不对")
    st.markdown("2. 某个条件判断阻止了渲染")
    st.markdown("3. 桌宠被其他元素遮挡（z-index 问题）")
