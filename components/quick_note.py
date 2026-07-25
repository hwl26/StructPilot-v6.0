"""右侧快速笔记面板

提供浮动的笔记快速记录功能：
- 悬浮按钮
- 快速笔记表单
- 分屏模式切换
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components


def render_quick_note_button():
    """渲染右下角的快速笔记按钮（浮动）"""

    # 检查登录状态
    if not st.session_state.get("logged_in", False):
        return

    # CSS + JS 实现浮动按钮和快速笔记面板
    html = """
    <style>
    /* 快速笔记浮动按钮 */
    #quick-note-btn {
        position: fixed;
        bottom: 100px;
        right: 20px;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 24px;
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9998;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    #quick-note-btn:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 16px rgba(0,0,0,0.25);
    }

    #quick-note-btn.active {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }

    /* 快速笔记面板 */
    #quick-note-panel {
        position: fixed;
        top: 0;
        right: -400px;
        width: 400px;
        height: 100vh;
        background: white;
        box-shadow: -4px 0 12px rgba(0,0,0,0.15);
        z-index: 9999;
        transition: right 0.3s ease;
        overflow-y: auto;
        padding: 20px;
    }

    #quick-note-panel.open {
        right: 0;
    }

    #quick-note-panel h3 {
        margin-top: 0;
        color: #333;
        font-size: 18px;
        border-bottom: 2px solid #667eea;
        padding-bottom: 10px;
    }

    #quick-note-panel textarea {
        width: 100%;
        min-height: 200px;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
        font-family: 'Segoe UI', sans-serif;
        resize: vertical;
    }

    #quick-note-panel input[type="text"] {
        width: 100%;
        padding: 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
        margin-bottom: 10px;
    }

    #quick-note-panel button {
        width: 100%;
        padding: 10px;
        margin-top: 10px;
        border: none;
        border-radius: 4px;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s;
    }

    #quick-note-panel .btn-save {
        background: #667eea;
        color: white;
    }

    #quick-note-panel .btn-save:hover {
        background: #5568d3;
    }

    #quick-note-panel .btn-split {
        background: #10b981;
        color: white;
    }

    #quick-note-panel .btn-split:hover {
        background: #059669;
    }

    #quick-note-panel .btn-close {
        background: #6b7280;
        color: white;
    }

    #quick-note-panel .btn-close:hover {
        background: #4b5563;
    }

    /* 遮罩层 */
    #quick-note-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.3);
        z-index: 9997;
        display: none;
    }

    #quick-note-overlay.open {
        display: block;
    }

    /* 深色模式适配 */
    @media (prefers-color-scheme: dark) {
        #quick-note-panel {
            background: #1f2937;
            color: #f3f4f6;
        }

        #quick-note-panel h3 {
            color: #f3f4f6;
        }

        #quick-note-panel textarea,
        #quick-note-panel input[type="text"] {
            background: #374151;
            color: #f3f4f6;
            border-color: #4b5563;
        }
    }
    </style>

    <!-- 浮动按钮 -->
    <button id="quick-note-btn" onclick="toggleQuickNote()">
        📝
    </button>

    <!-- 遮罩层 -->
    <div id="quick-note-overlay" onclick="closeQuickNote()"></div>

    <!-- 快速笔记面板 -->
    <div id="quick-note-panel">
        <h3>📝 快速笔记</h3>

        <input type="text" id="note-title" placeholder="笔记标题（可选）" />

        <textarea id="note-content" placeholder="在这里快速记录你的想法、参数设置、遇到的问题...

支持 Markdown 格式
"></textarea>

        <button class="btn-save" onclick="saveQuickNote()">💾 保存笔记</button>
        <button class="btn-split" onclick="enableSplitMode()">🔀 分屏模式</button>
        <button class="btn-close" onclick="closeQuickNote()">✖️ 关闭</button>

        <div id="note-status" style="margin-top: 10px; font-size: 12px; color: #10b981;"></div>
    </div>

    <script>
    let panelOpen = false;

    function toggleQuickNote() {
        panelOpen = !panelOpen;
        const panel = document.getElementById('quick-note-panel');
        const overlay = document.getElementById('quick-note-overlay');
        const btn = document.getElementById('quick-note-btn');

        if (panelOpen) {
            panel.classList.add('open');
            overlay.classList.add('open');
            btn.classList.add('active');
        } else {
            panel.classList.remove('open');
            overlay.classList.remove('open');
            btn.classList.remove('active');
        }
    }

    function closeQuickNote() {
        panelOpen = false;
        document.getElementById('quick-note-panel').classList.remove('open');
        document.getElementById('quick-note-overlay').classList.remove('open');
        document.getElementById('quick-note-btn').classList.remove('active');
    }

    function saveQuickNote() {
        const title = document.getElementById('note-title').value.trim();
        const content = document.getElementById('note-content').value.trim();

        if (!content) {
            alert('笔记内容不能为空');
            return;
        }

        // 通过 Streamlit 的 session_state 保存
        const noteData = {
            title: title || '快速笔记',
            content: content,
            timestamp: new Date().toISOString()
        };

        // 发送消息到 Streamlit
        parent.postMessage({
            type: 'quick_note_save',
            data: noteData
        }, '*');

        // 显示保存成功提示
        const status = document.getElementById('note-status');
        status.textContent = '✅ 笔记已保存！';
        setTimeout(() => {
            status.textContent = '';
            document.getElementById('note-title').value = '';
            document.getElementById('note-content').value = '';
        }, 2000);
    }

    function enableSplitMode() {
        // 通知 Streamlit 启用分屏模式
        parent.postMessage({
            type: 'enable_split_mode'
        }, '*');

        closeQuickNote();
    }
    </script>
    """

    components.html(html, height=0)


def handle_quick_note_events():
    """处理快速笔记事件（保存、分屏模式）"""

    # 这里需要使用 JavaScript 回调来接收消息
    # 由于 Streamlit 的限制，我们使用 session_state 传递数据

    # 检查是否有待保存的快速笔记
    if "quick_note_to_save" in st.session_state:
        note_data = st.session_state.pop("quick_note_to_save")

        # 保存笔记
        from utils.user_manager import save_user_note_dict
        import uuid
        from datetime import datetime

        username = st.session_state.get("username", "")
        if username:
            new_note = {
                "id": str(uuid.uuid4())[:8],
                "title": note_data.get("title", "快速笔记"),
                "content": note_data.get("content", ""),
                "step": "",
                "tags": ["快速笔记"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if save_user_note_dict(username, new_note):
                st.toast("✅ 笔记已保存", icon="✅")
            else:
                st.toast("❌ 保存失败", icon="❌")

    # 检查是否启用分屏模式
    if st.session_state.get("enable_split_mode_request"):
        st.session_state.pop("enable_split_mode_request")
        st.session_state["split_mode_enabled"] = True
        st.rerun()
