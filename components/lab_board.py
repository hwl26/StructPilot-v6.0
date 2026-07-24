"""课题组内部留言板组件。

帖子数据存储在 runtime/lab_board/posts.json
每个帖子：{id, title, content, author, timestamp, category, replies: [{author, content, timestamp}], images: []}
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_POSTS_PATH = BASE_DIR / "runtime" / "lab_board" / "posts.json"

CATEGORIES = ["通知公告", "踩坑经验", "问题求助", "资源分享", "日常交流"]


def load_posts() -> list[dict]:
    """加载所有帖子，返回列表（新→旧）。"""
    try:
        data = json.loads(_POSTS_PATH.read_text(encoding="utf-8"))
        posts = data if isinstance(data, list) else data.get("posts", [])
        return sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)
    except Exception:
        return []


def _save_posts(posts: list[dict]) -> bool:
    try:
        _POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _POSTS_PATH.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def save_post(title: str, content: str, author: str, category: str, images: list | None = None) -> bool:
    """新建帖子并保存。"""
    posts = load_posts()
    new_post = {
        "id": str(uuid.uuid4())[:8],
        "title": title.strip(),
        "content": content.strip(),
        "author": author,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "replies": [],
        "images": images or [],
    }
    posts.insert(0, new_post)
    return _save_posts(posts)


def add_reply(post_id: str, author: str, content: str) -> bool:
    """为指定帖子添加回复。"""
    posts = load_posts()
    for post in posts:
        if post.get("id") == post_id:
            if not isinstance(post.get("replies"), list):
                post["replies"] = []
            post["replies"].append({
                "author": author,
                "content": content.strip(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
            return _save_posts(posts)
    return False


def render_board(current_user: str) -> None:
    """渲染留言板 Streamlit UI。"""

    # ── 新建帖子按钮 ──────────────────────────────────────────
    with st.expander("✏️ 新建帖子", expanded=st.session_state.get("_lab_board_new_open", False)):
        with st.form("lab_board_new_post_form", clear_on_submit=True):
            np_title = st.text_input("标题", placeholder="请输入帖子标题")
            np_category = st.selectbox("分类", options=CATEGORIES)
            np_content = st.text_area("内容", height=120, placeholder="详细描述...")
            submitted = st.form_submit_button("📤 发布", use_container_width=True)
        if submitted:
            if not np_title.strip() or not np_content.strip():
                st.warning("标题和内容不能为空")
            else:
                if save_post(np_title, np_content, current_user, np_category):
                    st.success("✅ 帖子已发布")
                    st.session_state["_lab_board_new_open"] = False
                    st.rerun()
                else:
                    st.error("发布失败，请重试")

    # ── 分类筛选 ──────────────────────────────────────────────
    all_categories = ["全部"] + CATEGORIES
    selected_cat = st.selectbox(
        "筛选分类",
        options=all_categories,
        key="lab_board_cat_filter",
        label_visibility="collapsed",
    )

    posts = load_posts()
    if selected_cat != "全部":
        posts = [p for p in posts if p.get("category") == selected_cat]

    if not posts:
        st.info("暂无帖子，来发第一篇吧！")
        return

    # ── 帖子列表 ──────────────────────────────────────────────
    for post in posts:
        pid = post.get("id", "")
        title = post.get("title", "（无标题）")
        category = post.get("category", "")
        author = post.get("author", "匿名")
        ts = post.get("timestamp", "")[:16].replace("T", " ")
        replies = post.get("replies") or []
        reply_count = len(replies)

        # 帖子摘要行
        header_label = f"**{title}**  `{category}`  ·  {author}  ·  {ts}  ·  {reply_count} 条回复"
        detail_key = f"_lab_board_detail_{pid}"
        with st.expander(header_label, expanded=st.session_state.get(detail_key, False)):
            # 帖子正文
            st.markdown(post.get("content", ""))
            if post.get("images"):
                st.caption(f"附件：{', '.join(post['images'])}")

            st.divider()

            # 已有回复
            if replies:
                st.markdown(f"**回复（{reply_count}）**")
                for rep in replies:
                    rep_ts = rep.get("timestamp", "")[:16].replace("T", " ")
                    st.markdown(
                        f"<div style='background:#f8fafc;border-left:3px solid #93c5fd;"
                        f"padding:6px 10px;margin:4px 0;border-radius:4px;font-size:0.9rem;'>"
                        f"<b>{rep.get('author','匿名')}</b> <span style='color:#94a3b8;font-size:0.8rem;'>{rep_ts}</span><br>"
                        f"{rep.get('content','')}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("暂无回复")

            # 回复表单
            with st.form(f"lab_board_reply_{pid}", clear_on_submit=True):
                reply_content = st.text_area("写下回复…", height=70, key=f"reply_text_{pid}",
                                             label_visibility="collapsed")
                reply_submitted = st.form_submit_button("💬 回复", use_container_width=True)
            if reply_submitted:
                if not reply_content.strip():
                    st.warning("回复内容不能为空")
                else:
                    if add_reply(pid, current_user, reply_content):
                        st.success("回复成功")
                        st.rerun()
                    else:
                        st.error("回复失败")
