"""StructPilot v6.0 — 简易用户管理。

本地部署：用文本输入 username
Streamlit Cloud：自动读取 st.experimental_user（如果可用）

用户数据存储在 runtime/user_data/{user_id}/notes.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_USER_DATA_DIR = BASE_DIR / "runtime" / "user_data"


def get_current_user() -> Optional[str]:
    """获取当前用户 ID。

    Returns
    -------
    str or None
        用户 ID（Streamlit Cloud 的 email 或本地输入的 username）
    """
    # 尝试 Streamlit Cloud 的 user API
    try:
        user_info = st.user
        if hasattr(user_info, "email") and user_info.email:
            return user_info.email
    except Exception:
        pass

    # 本地模式：从 session_state 读取
    if "structpilot_user_id" not in st.session_state:
        st.session_state.structpilot_user_id = None

    return st.session_state.structpilot_user_id


def set_local_user(username: str) -> None:
    """设置本地用户 ID（仅本地部署使用）。"""
    st.session_state.structpilot_user_id = username.strip() or None


def get_user_notes_path(user_id: str) -> Path:
    """获取用户笔记文件路径。"""
    user_dir = _USER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "notes.json"


def load_user_notes(user_id: str) -> list[dict]:
    """加载用户笔记。

    Returns
    -------
    list[dict]
        笔记列表，每条笔记包含 {id, timestamp, step, content, tags}
    """
    try:
        path = get_user_notes_path(user_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []
    except Exception:
        return []


def save_user_note(user_id: str, step: str, content: str, tags: list[str]) -> bool:
    """保存一条笔记。

    Parameters
    ----------
    user_id
        用户 ID
    step
        checkpoint_id
    content
        笔记内容
    tags
        标签列表

    Returns
    -------
    bool
        是否成功
    """
    try:
        path = get_user_notes_path(user_id)
        notes = load_user_notes(user_id)

        import datetime
        new_note = {
            "id": f"note_{len(notes)+1:03d}",
            "timestamp": datetime.datetime.now().isoformat(),
            "step": step,
            "content": content,
            "tags": tags,
        }
        notes.append(new_note)

        path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def delete_user_note(user_id: str, note_id: str) -> bool:
    """删除一条笔记。"""
    try:
        path = get_user_notes_path(user_id)
        notes = load_user_notes(user_id)
        notes = [n for n in notes if n.get("id") != note_id]
        path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
