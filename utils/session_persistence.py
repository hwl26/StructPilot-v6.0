"""Session 持久化工具

使用 localStorage 保持用户登录状态，防止刷新后退出登录。
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
import json
from datetime import datetime, timedelta


def save_session_to_storage(username: str, role: str, display_name: str):
    """保存登录状态到 localStorage

    Parameters
    ----------
    username : str
        用户名
    role : str
        角色 (admin/member/guest)
    display_name : str
        显示名称
    """
    session_data = {
        "username": username,
        "role": role,
        "display_name": display_name,
        "timestamp": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat()  # 7天有效期
    }

    # 使用 JavaScript 保存到 localStorage
    html = f"""
    <script>
        try {{
            localStorage.setItem('structpilot_session', JSON.stringify({json.dumps(session_data)}));
            console.log('Session saved to localStorage');
        }} catch (e) {{
            console.error('Failed to save session:', e);
        }}
    </script>
    """
    components.html(html, height=0)


def restore_session_from_storage():
    """从 localStorage 恢复登录状态

    Returns
    -------
    dict or None
        恢复的session数据，如果不存在或已过期则返回None
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
        function restoreSession() {
            try {
                const sessionStr = localStorage.getItem('structpilot_session');
                if (!sessionStr) {
                    parent.postMessage({type: 'session', data: null}, '*');
                    return;
                }

                const session = JSON.parse(sessionStr);

                // 检查是否过期
                const expiresAt = new Date(session.expires_at);
                const now = new Date();

                if (now > expiresAt) {
                    // 已过期，清除
                    localStorage.removeItem('structpilot_session');
                    parent.postMessage({type: 'session', data: null}, '*');
                    return;
                }

                // 未过期，返回数据
                parent.postMessage({type: 'session', data: session}, '*');
            } catch (e) {
                console.error('Failed to restore session:', e);
                parent.postMessage({type: 'session', data: null}, '*');
            }
        }

        // 立即执行
        restoreSession();
        </script>
    </head>
    <body></body>
    </html>
    """

    # 使用 iframe 通信
    return components.html(html, height=0)


def clear_session_from_storage():
    """清除 localStorage 中的登录状态"""
    html = """
    <script>
        try {
            localStorage.removeItem('structpilot_session');
            console.log('Session cleared from localStorage');
        } catch (e) {
            console.error('Failed to clear session:', e);
        }
    </script>
    """
    components.html(html, height=0)


def init_session_persistence():
    """初始化 session 持久化

    在应用启动时调用，尝试从 localStorage 恢复登录状态
    """
    # 如果已经登录，不需要恢复
    if st.session_state.get("logged_in"):
        return

    # 尝试从 localStorage 恢复
    # 注意：由于 Streamlit 的限制，我们使用一个标记来判断是否需要恢复
    if "_session_restore_attempted" not in st.session_state:
        st.session_state._session_restore_attempted = True

        # 使用隐藏组件尝试恢复（需要在侧边栏或主界面调用）
        # 实际恢复逻辑在 main.py 中通过 JavaScript 实现
        pass


# ==================== 简化版：使用 Cookie ====================

def save_session_cookie(username: str, role: str, display_name: str):
    """使用 Cookie 保存 session（简化版）

    注意：这个方法更简单但安全性较低，仅用于本地部署
    """
    session_data = f"{username}|{role}|{display_name}|{datetime.now().isoformat()}"

    html = f"""
    <script>
        // 设置 Cookie（7天有效期）
        const expiresDate = new Date();
        expiresDate.setDate(expiresDate.getDate() + 7);
        document.cookie = "structpilot_session={session_data}; expires=" + expiresDate.toUTCString() + "; path=/";
        console.log('Session saved to cookie');
    </script>
    """
    components.html(html, height=0)


def restore_session_cookie():
    """从 Cookie 恢复 session

    Returns
    -------
    dict or None
    """
    html = """
    <script>
        function getCookie(name) {
            const value = "; " + document.cookie;
            const parts = value.split("; " + name + "=");
            if (parts.length === 2) {
                return parts.pop().split(";").shift();
            }
            return null;
        }

        const sessionCookie = getCookie("structpilot_session");
        if (sessionCookie) {
            const parts = sessionCookie.split("|");
            if (parts.length >= 3) {
                const session = {
                    username: parts[0],
                    role: parts[1],
                    display_name: parts[2],
                    timestamp: parts[3] || ""
                };
                parent.postMessage({type: 'session_cookie', data: session}, '*');
            } else {
                parent.postMessage({type: 'session_cookie', data: null}, '*');
            }
        } else {
            parent.postMessage({type: 'session_cookie', data: null}, '*');
        }
    </script>
    """
    return components.html(html, height=0)


def clear_session_cookie():
    """清除 Cookie"""
    html = """
    <script>
        document.cookie = "structpilot_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        console.log('Session cookie cleared');
    </script>
    """
    components.html(html, height=0)
