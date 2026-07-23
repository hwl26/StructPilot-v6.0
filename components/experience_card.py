"""StructPilot v6.0 — 课题组经验卡片组件

渲染带截图的经验卡片，支持审核状态标记。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_IMG_DIR = BASE_DIR / "runtime" / "experience_images"
_VIDEO_DIR = BASE_DIR / "runtime" / "experience_videos"


def render_experience_card(exp: dict, expanded: bool = False) -> None:
    """渲染单个经验卡片（含截图和审核状态）"""
    # 审核状态徽章
    status = exp.get("status", "pending")
    status_badges = {
        "approved": "🥇 已验证",
        "pending": "⚠️ 待验证",
        "rejected": "❌ 已拒绝",
    }
    badge = status_badges.get(status, "⚠️ 待验证")

    title = exp.get("title", "未命名经验")

    with st.expander(f"{badge} · {title}", expanded=expanded):
        # 基本信息
        category = exp.get("category", "")
        if category:
            st.caption(f"分类：{category}")

        # 症状描述
        symptoms_text = exp.get("symptoms_text", "")
        if symptoms_text:
            st.markdown(f"**症状**：{symptoms_text}")

        # 解决方案
        solution = exp.get("solution", "")
        if solution:
            st.markdown(f"**解决方案**：{solution}")

        # 📸 显示关联截图
        images = exp.get("images", [])
        if images:
            st.markdown("**📸 相关截图**")
            cols = st.columns(min(len(images), 3))
            for idx, img_name in enumerate(images):
                with cols[idx]:
                    img_path = _IMG_DIR / img_name

                    if img_path.exists():
                        st.image(str(img_path), use_container_width=True, caption=f"截图 {idx+1}")
                    else:
                        st.caption(f"📎 {img_name}（文件丢失）")

        # 标签
        tags = exp.get("tags", [])
        if tags:
            tags_display = " · ".join(f"`{t}`" for t in tags)
            st.markdown(f"**标签**：{tags_display}")

        # 📹 短视频（支持本地文件路径和外部链接）
        video_url = exp.get("video_url", "")
        video_path = exp.get("video_path", "")
        if video_url or video_path:
            st.markdown("**📹 操作演示视频**")
            try:
                if video_url:
                    # 外部链接：B站/YouTube/腾讯视频等，用 iframe 嵌入
                    st.video(video_url)
                elif video_path:
                    # 本地文件路径
                    from pathlib import Path
                    vp = Path(video_path)
                    if not vp.is_absolute():
                        vp = BASE_DIR / "runtime" / "experience_videos" / video_path
                    if vp.exists():
                        st.video(str(vp))
                    else:
                        st.caption(f"视频文件不存在：{video_path}")
            except Exception as e:
                st.caption(f"视频加载失败：{e}")

        # 作者和日期（增强显示：来源、角色、机构）
        author = exp.get("author", "匿名")
        date = exp.get("date", "")
        author_role = exp.get("author_role", "")
        institution = exp.get("institution", "")
        source_type = exp.get("source", "")
        source_label = {
            "lab_experience": "🏫 课题组",
            "open_source": "🌐 开源知识库",
            "teacher": "👨‍🏫 老师",
            "senior": "🎓 师兄/师姐",
        }.get(source_type, "")

        # 拼接显示
        meta_parts = [p for p in [author, author_role, institution] if p]
        meta_line = " · ".join(meta_parts)
        if date:
            meta_line += f"　{date}"
        if source_label:
            meta_line = f"{source_label} | " + meta_line
        st.caption(meta_line)


def render_experience_list(
    experiences: list[dict],
    title: str = "🥇 课题组经验",
    expanded_first: bool = True,
) -> None:
    """渲染经验列表"""
    if not experiences:
        st.info("暂无相关经验记录。")
        return

    st.markdown(f"### {title}")
    st.caption(f"共 {len(experiences)} 条经验")

    for idx, exp in enumerate(experiences):
        render_experience_card(exp, expanded=(idx == 0 and expanded_first))
