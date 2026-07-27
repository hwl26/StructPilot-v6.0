"""管理员区 Tab 渲染组件

提供管理员专用功能：
- 权限对比表
- 用户管理（创建、编辑、禁用）
- 经验审核
- 系统配置
"""

from __future__ import annotations
import json
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from utils.atomic_io import atomic_update_json

BASE_DIR = Path(__file__).resolve().parent.parent
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def _set_experience_status(exp_id: str, status: str, actor: str) -> None:
    def mutate(data):
        data = data if isinstance(data, dict) else {"entries": [], "meta": {}}
        for entry in data.setdefault("entries", []):
            if entry.get("id") == exp_id:
                entry["status"] = status
                entry[f"{status}_at"] = datetime.now().isoformat()
                entry[f"{status}_by"] = actor
                break
        return data
    atomic_update_json(_LAB_EXP_PATH, {"entries": [], "meta": {}}, mutate)


def render_admin_panel():
    """渲染管理员区主界面"""

    # 权限检查 - 使用 session_state 的 role
    user_role = st.session_state.get("role", "guest")

    # 调试信息（可选，帮助排查）
    # st.caption(f"Debug: role={user_role}, logged_in={st.session_state.get('logged_in')}")

    if user_role != "admin":
        st.warning("⚠️ 此功能仅管理员可用")
        st.info("💡 如需管理权限，请联系系统管理员")

        # 如果已登录但不是管理员，显示当前角色
        if st.session_state.get("logged_in"):
            st.caption(f"当前角色：{user_role}")
        return

    # 子Tab结构
    admin_tabs = st.tabs(["👥 权限管理", "👤 用户管理", "📋 经验审核", "⚙️ 系统配置"])

    with admin_tabs[0]:
        render_permissions_table()

    with admin_tabs[1]:
        render_user_management()

    with admin_tabs[2]:
        render_experience_review()

    with admin_tabs[3]:
        render_system_config()


def render_permissions_table():
    """渲染权限对比表"""
    st.markdown("### 👥 权限对比")
    st.caption("各角色的功能权限一览")

    # 权限数据
    permissions_data = {
        "查看知识库": {"admin": "✅", "member": "✅", "guest": "✅"},
        "AI对话提问": {"admin": "✅", "member": "✅", "guest": "❌"},
        "个人笔记": {"admin": "✅", "member": "✅", "guest": "❌"},
        "贡献经验": {"admin": "✅", "member": "✅", "guest": "❌"},
        "论坛发帖": {"admin": "✅", "member": "✅", "guest": "❌"},
        "论坛回答": {"admin": "✅", "member": "✅", "guest": "❌"},
        "审核经验": {"admin": "✅", "member": "❌", "guest": "❌"},
        "用户管理": {"admin": "✅", "member": "❌", "guest": "❌"},
        "系统配置": {"admin": "✅", "member": "❌", "guest": "❌"},
    }

    # 转换为DataFrame
    df = pd.DataFrame(permissions_data).T
    df.columns = ["管理员", "成员", "访客"]

    # 使用st.dataframe显示，支持列宽自动调整
    st.dataframe(
        df,
        use_container_width=True,
        height=350,
    )

    st.info("💡 **说明**：✅ 可用 | ❌ 不可用")


def render_user_management():
    """渲染用户管理界面"""
    st.markdown("### 👤 用户管理")

    from utils.auth import load_users, save_users, _hash_password

    users_data = load_users()
    users = users_data.get("users", [])

    st.caption(f"📊 共 {len(users)} 个用户")

    # 创建新用户
    with st.expander("➕ 创建新用户", expanded=False):
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("用户名 *", placeholder="如：zhangsan")
                new_role = st.selectbox(
                    "角色 *",
                    options=["member", "admin"],
                    format_func=lambda x: {"member": "成员", "admin": "管理员"}[x]
                )
            with col2:
                new_display_name = st.text_input("显示名称", placeholder="如：张三")
                new_email = st.text_input("邮箱（可选）", placeholder="user@example.com")

            new_initial_password = st.text_input(
                "初始密码 *",
                value="123456",
                type="password",
                help="用户首次登录时必须修改密码"
            )

            submitted = st.form_submit_button("创建账号", use_container_width=True, type="primary")

            if submitted:
                if not new_username or not new_initial_password:
                    st.error("❌ 用户名和初始密码不能为空")
                elif any(u.get("username") == new_username for u in users):
                    st.error(f"❌ 用户名 '{new_username}' 已存在")
                else:
                    # 创建新用户
                    new_user = {
                        "username": new_username,
                        "password_hash": _hash_password(new_initial_password),
                        "role": new_role,
                        "display_name": new_display_name or new_username,
                        "email": new_email or "",
                        "force_change_password": True,  # 强制首次登录修改密码
                        "created_at": datetime.now().isoformat(),
                    }
                    users.append(new_user)
                    users_data["users"] = users

                    if save_users(users_data):
                        st.success(
                            f"✅ 账号创建成功！\n\n"
                            f"**请将以下信息告知用户：**\n"
                            f"- 用户名：`{new_username}`\n"
                            f"- 初始密码：`{new_initial_password}`\n\n"
                            f"⚠️ 用户首次登录时将被要求修改密码"
                        )
                        st.rerun()
                    else:
                        st.error("❌ 保存失败，请重试")

    st.divider()
    st.markdown("#### 用户列表")

    # 显示用户列表
    for idx, user in enumerate(users):
        username = user.get("username", "")
        display_name = user.get("display_name", username)
        role = user.get("role", "member")
        email = user.get("email", "未设置")

        role_badge = "🔧 管理员" if role == "admin" else "👤 成员"

        with st.expander(f"{role_badge} {display_name} (@{username})", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**用户名**：{username}")
                st.markdown(f"**显示名称**：{display_name}")
                st.markdown(f"**角色**：{role_badge}")
                st.markdown(f"**邮箱**：{email}")

                if user.get("force_change_password"):
                    st.warning("⚠️ 首次登录需修改密码")

            with col2:
                # 防止删除最后一个管理员
                if username == "admin":
                    st.caption("🔒 默认管理员\n不可删除")
                else:
                    if st.button("🗑️ 删除", key=f"delete_user_{idx}", use_container_width=True):
                        # 确认删除
                        if st.session_state.get(f"confirm_delete_{username}"):
                            users.remove(user)
                            users_data["users"] = users
                            save_users(users_data)
                            st.success(f"✅ 已删除用户：{username}")
                            st.session_state.pop(f"confirm_delete_{username}", None)
                            st.rerun()
                        else:
                            st.session_state[f"confirm_delete_{username}"] = True
                            st.warning("再次点击确认删除")


def render_experience_review():
    """渲染经验审核界面"""
    st.markdown("### 📋 经验审核")
    st.caption("审核用户贡献的经验，通过后全员可见")

    # 审核状态筛选
    review_filter = st.radio(
        "显示条目",
        options=["待审核", "已驳回", "全部"],
        horizontal=True,
        key="admin_exp_review_filter",
    )

    try:
        if not _LAB_EXP_PATH.exists():
            st.info("💡 还没有待审核的经验")
            return

        exp_data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        all_entries = exp_data.get("entries", [])

        # 根据筛选器过滤
        if review_filter == "待审核":
            filtered_exps = [e for e in all_entries if e.get("status") == "pending"]
        elif review_filter == "已驳回":
            filtered_exps = [e for e in all_entries if e.get("status") == "rejected"]
        else:  # 全部
            filtered_exps = [e for e in all_entries if e.get("status") in ("pending", "rejected")]

        if not filtered_exps:
            st.info(f"💡 没有{review_filter}的经验")
            return

        st.info(f"📝 {review_filter}：{len(filtered_exps)} 条")

        for exp in filtered_exps[:20]:  # 最多显示20条
            status_badge = "⏳ 待审核" if exp.get("status") == "pending" else "❌ 已驳回"

            with st.expander(f"{status_badge} | {exp.get('title', '无标题')}", expanded=False):
                st.markdown(f"**分类**：{exp.get('category', '')}")
                st.markdown(f"**步骤**：{exp.get('step', '')}")
                st.markdown(f"**症状**：{exp.get('symptoms_text', '')}")
                st.markdown("---")
                st.markdown(f"**解决方案**：")
                st.markdown(exp.get('solution', ''))
                st.caption(f"提交者：{exp.get('author', '')} · {exp.get('date', '')}")

                st.divider()
                col_approve, col_reject = st.columns(2)

                with col_approve:
                    if st.button("✅ 通过", key=f"admin_approve_{exp.get('id')}", use_container_width=True):
                        _set_experience_status(exp.get("id", ""), "approved", st.session_state.get("username", "admin"))

                        # 企业微信推送通知（可选）
                        try:
                            from utils.wework_bot import load_wework_config, send_wework_message
                            ww_cfg = load_wework_config()
                            if ww_cfg.get("enabled") and ww_cfg.get("webhook_url"):
                                notify_content = (
                                    f"✅ **新经验已审核通过**\n\n"
                                    f"**标题**：{exp.get('title', '')}\n"
                                    f"**作者**：{exp.get('author', '')}\n"
                                    f"**步骤**：{exp.get('step', '')}\n"
                                )
                                send_wework_message(ww_cfg["webhook_url"], notify_content)
                        except Exception:
                            pass  # 推送失败不影响审核

                        st.success("✅ 已通过审核")
                        st.rerun()

                with col_reject:
                    if st.button("❌ 驳回", key=f"admin_reject_{exp.get('id')}", use_container_width=True):
                        _set_experience_status(exp.get("id", ""), "rejected", st.session_state.get("username", "admin"))

                        st.success("❌ 已驳回")
                        st.rerun()

    except json.JSONDecodeError as e:
        st.error(f"❌ JSON 解析错误：{e}")
        st.caption("请检查 knowledge_base/lab_experience_kb.json 文件格式")
    except Exception as e:
        st.error(f"❌ 加载失败：{e}")


def render_system_config():
    """渲染系统配置界面"""
    st.markdown("### ⚙️ 系统配置")
    st.caption("LLM、向量检索、语音转写等高级配置")

    st.info("💡 系统配置功能已在「设置」Tab中提供，此处为快捷入口")

    if st.button("📝 前往设置页面", use_container_width=True):
        st.info("请点击顶部「设置」Tab 查看完整配置")
