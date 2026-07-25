"""分屏模式组件

实现对话区和笔记区的并排显示，支持拖拽调整比例。
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid


def render_split_view():
    """渲染分屏视图（对话区 + 笔记区）"""

    # 检查登录状态
    if not st.session_state.get("logged_in"):
        st.warning("⚠️ 请先登录才能使用分屏模式")
        return

    # 分屏布局的HTML + CSS + JavaScript
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: 'Segoe UI', sans-serif;
        }

        #split-container {
            display: flex;
            width: 100vw;
            height: 100vh;
        }

        #chat-pane {
            flex: 1;
            min-width: 300px;
            overflow-y: auto;
            padding: 20px;
            background: #f9fafb;
            border-right: 1px solid #e5e7eb;
        }

        #note-pane {
            width: 40%;
            min-width: 300px;
            display: flex;
            flex-direction: column;
            background: white;
            box-shadow: -4px 0 8px rgba(0,0,0,0.05);
        }

        #resize-handle {
            width: 8px;
            background: #e5e7eb;
            cursor: col-resize;
            transition: background 0.2s;
            position: relative;
        }

        #resize-handle:hover {
            background: #9ca3af;
        }

        #resize-handle::before {
            content: '⋮';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #6b7280;
            font-size: 16px;
        }

        #note-header {
            padding: 16px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        #note-header h3 {
            margin: 0;
            font-size: 16px;
        }

        #note-controls {
            display: flex;
            gap: 8px;
        }

        #note-controls button {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }

        #note-controls button:hover {
            background: rgba(255,255,255,0.3);
        }

        #note-body {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            overflow-y: auto;
        }

        #note-title-input {
            width: 100%;
            padding: 10px;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        #note-content-input {
            flex: 1;
            width: 100%;
            padding: 12px;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 14px;
            font-family: 'Consolas', 'Monaco', monospace;
            resize: none;
            line-height: 1.6;
        }

        #note-status {
            padding: 8px 20px;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #6b7280;
            text-align: right;
        }

        /* 深色模式 */
        @media (prefers-color-scheme: dark) {
            #chat-pane {
                background: #1f2937;
                border-right-color: #374151;
            }

            #note-pane {
                background: #111827;
            }

            #note-body {
                background: #111827;
            }

            #note-title-input,
            #note-content-input {
                background: #1f2937;
                border-color: #374151;
                color: #f3f4f6;
            }

            #note-status {
                background: #1f2937;
                border-top-color: #374151;
                color: #9ca3af;
            }
        }

        /* 工具提示 */
        .tooltip {
            position: relative;
            display: inline-block;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            width: 120px;
            background-color: #1f2937;
            color: white;
            text-align: center;
            border-radius: 4px;
            padding: 4px 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -60px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 11px;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        </style>
    </head>
    <body>
        <div id="split-container">
            <!-- 对话区 -->
            <div id="chat-pane">
                <h2 style="color: #374151; margin-top: 0;">💬 对话陪跑</h2>
                <p style="color: #6b7280; font-size: 14px;">
                    这里显示AI对话内容（由主应用渲染）
                </p>
                <div id="chat-messages">
                    <!-- Streamlit 主应用会渲染对话消息 -->
                </div>
            </div>

            <!-- 可拖拽分隔条 -->
            <div id="resize-handle"></div>

            <!-- 笔记区 -->
            <div id="note-pane">
                <div id="note-header">
                    <h3>📝 实时笔记</h3>
                    <div id="note-controls">
                        <button class="tooltip" onclick="saveNote()">
                            💾 保存
                            <span class="tooltiptext">Ctrl+S</span>
                        </button>
                        <button class="tooltip" onclick="clearNote()">
                            🗑️ 清空
                            <span class="tooltiptext">清除内容</span>
                        </button>
                        <button class="tooltip" onclick="exitSplitView()">
                            ✖️ 退出
                            <span class="tooltiptext">ESC</span>
                        </button>
                    </div>
                </div>

                <div id="note-body">
                    <input
                        type="text"
                        id="note-title-input"
                        placeholder="笔记标题..."
                        value="分屏笔记"
                    />
                    <textarea
                        id="note-content-input"
                        placeholder="在这里记录你的想法、参数设置、遇到的问题...

支持 Markdown 格式
快捷键：
  Ctrl+S - 保存
  ESC - 退出分屏"
                    ></textarea>
                </div>

                <div id="note-status">
                    <span id="status-text">未保存</span>
                    <span id="char-count">0 字符</span>
                </div>
            </div>
        </div>

        <script>
        // ==================== 拖拽调整比例 ====================
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        const resizeHandle = document.getElementById('resize-handle');
        const chatPane = document.getElementById('chat-pane');
        const notePane = document.getElementById('note-pane');

        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = notePane.offsetWidth;
            document.body.style.cursor = 'col-resize';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const deltaX = startX - e.clientX;
            const newWidth = startWidth + deltaX;
            const containerWidth = document.getElementById('split-container').offsetWidth;

            // 限制最小和最大宽度
            const minWidth = 300;
            const maxWidth = containerWidth - 300;

            if (newWidth >= minWidth && newWidth <= maxWidth) {
                notePane.style.width = newWidth + 'px';
            }
        });

        document.addEventListener('mouseup', () => {
            isResizing = false;
            document.body.style.cursor = 'default';
        });

        // ==================== 笔记操作 ====================
        const titleInput = document.getElementById('note-title-input');
        const contentInput = document.getElementById('note-content-input');
        const statusText = document.getElementById('status-text');
        const charCount = document.getElementById('char-count');

        // 实时字符统计
        contentInput.addEventListener('input', () => {
            const count = contentInput.value.length;
            charCount.textContent = count + ' 字符';
            statusText.textContent = '未保存';
            statusText.style.color = '#ef4444';
        });

        // 保存笔记
        function saveNote() {
            const title = titleInput.value.trim() || '分屏笔记';
            const content = contentInput.value.trim();

            if (!content) {
                alert('笔记内容不能为空');
                return;
            }

            // 发送到 Streamlit
            const noteData = {
                title: title,
                content: content,
                timestamp: new Date().toISOString()
            };

            parent.postMessage({
                type: 'split_note_save',
                data: noteData
            }, '*');

            statusText.textContent = '已保存';
            statusText.style.color = '#10b981';

            setTimeout(() => {
                statusText.textContent = '未保存';
                statusText.style.color = '#6b7280';
            }, 2000);
        }

        // 清空笔记
        function clearNote() {
            if (contentInput.value && !confirm('确定要清空笔记内容吗？')) {
                return;
            }
            titleInput.value = '分屏笔记';
            contentInput.value = '';
            charCount.textContent = '0 字符';
        }

        // 退出分屏
        function exitSplitView() {
            if (contentInput.value && !confirm('笔记未保存，确定要退出吗？')) {
                return;
            }

            parent.postMessage({
                type: 'exit_split_view'
            }, '*');
        }

        // ==================== 快捷键 ====================
        document.addEventListener('keydown', (e) => {
            // Ctrl+S - 保存
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveNote();
            }

            // ESC - 退出
            if (e.key === 'Escape') {
                exitSplitView();
            }
        });

        // ==================== 自动保存（每30秒）====================
        setInterval(() => {
            if (contentInput.value.length > 0) {
                saveNote();
            }
        }, 30000);
        </script>
    </body>
    </html>
    """

    # 渲染分屏界面
    components.html(html, height=800, scrolling=False)


def enable_split_mode():
    """启用分屏模式"""
    st.session_state.split_mode_enabled = True
    st.rerun()


def disable_split_mode():
    """禁用分屏模式"""
    st.session_state.split_mode_enabled = False
    st.rerun()


def handle_split_note_save(note_data: dict):
    """处理分屏笔记保存

    Parameters
    ----------
    note_data : dict
        包含 title, content, timestamp
    """
    from utils.user_manager import save_user_note_dict

    username = st.session_state.get("username", "")
    if not username:
        return False

    note = {
        "id": str(uuid.uuid4())[:8],
        "title": note_data.get("title", "分屏笔记"),
        "content": note_data.get("content", ""),
        "step": "",
        "tags": ["分屏笔记"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    return save_user_note_dict(username, note)
