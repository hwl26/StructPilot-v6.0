"""StructPilot 论坛数据管理模块

轻量级 Q&A 论坛，支持：
- 提问/回答/评论
- 点赞/采纳最佳答案
- 标签分类
- 搜索过滤
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid

BASE_DIR = Path(__file__).resolve().parent.parent
FORUM_DIR = BASE_DIR / "runtime" / "forum"
FORUM_DATA_PATH = FORUM_DIR / "forum_posts.json"


def ensure_forum_dir():
    """确保论坛数据目录存在"""
    FORUM_DIR.mkdir(parents=True, exist_ok=True)


def load_forum_data() -> Dict:
    """加载论坛数据

    Returns
    -------
    {
        "posts": [
            {
                "id": "uuid",
                "type": "question",
                "author": "username",
                "author_display": "张三",
                "author_lab": "labA",  // 可选
                "anonymous": false,
                "created_at": "2025-01-25T10:00:00",
                "title": "Motion Correction 报错如何解决？",
                "content": "详细描述...",
                "tags": ["cryosparc", "cp_02", "error"],
                "software": "cryosparc",
                "step": "cp_02",
                "upvotes": 5,
                "views": 100,
                "answers_count": 3,
                "accepted_answer_id": "uuid",
                "status": "open",  // open | answered | closed
                "visibility": "public"  // public | lab_only
            }
        ],
        "answers": [
            {
                "id": "uuid",
                "question_id": "uuid",
                "author": "username",
                "author_display": "李四",
                "anonymous": false,
                "created_at": "2025-01-25T11:00:00",
                "content": "解决方案...",
                "upvotes": 3,
                "is_accepted": false
            }
        ],
        "comments": [
            {
                "id": "uuid",
                "parent_id": "uuid",  // question_id or answer_id
                "parent_type": "question",  // question | answer
                "author": "username",
                "author_display": "王五",
                "created_at": "2025-01-25T12:00:00",
                "content": "补充说明..."
            }
        ],
        "votes": [
            {
                "user": "username",
                "target_id": "uuid",
                "target_type": "question",  // question | answer
                "vote_type": "up"  // up | down
            }
        ]
    }
    """
    ensure_forum_dir()

    if not FORUM_DATA_PATH.exists():
        default_data = {
            "posts": [],
            "answers": [],
            "comments": [],
            "votes": []
        }
        save_forum_data(default_data)
        return default_data

    try:
        return json.loads(FORUM_DATA_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading forum data: {e}")
        return {"posts": [], "answers": [], "comments": [], "votes": []}


def save_forum_data(data: Dict) -> bool:
    """保存论坛数据"""
    ensure_forum_dir()
    try:
        FORUM_DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        print(f"Error saving forum data: {e}")
        return False


def create_question(
    author: str,
    author_display: str,
    title: str,
    content: str,
    tags: List[str],
    software: str = "",
    step: str = "",
    anonymous: bool = False,
    author_lab: str = "",
    visibility: str = "public"
) -> str:
    """创建新问题

    Returns
    -------
    question_id : str
    """
    data = load_forum_data()

    question = {
        "id": uuid.uuid4().hex[:16],
        "type": "question",
        "author": author if not anonymous else "anonymous",
        "author_display": "匿名用户" if anonymous else author_display,
        "author_lab": author_lab,
        "anonymous": anonymous,
        "created_at": datetime.now().isoformat(),
        "title": title,
        "content": content,
        "tags": tags,
        "software": software,
        "step": step,
        "upvotes": 0,
        "views": 0,
        "answers_count": 0,
        "accepted_answer_id": None,
        "status": "open",
        "visibility": visibility
    }

    data["posts"].append(question)
    save_forum_data(data)

    return question["id"]


def create_answer(
    question_id: str,
    author: str,
    author_display: str,
    content: str,
    anonymous: bool = False
) -> str:
    """回答问题

    Returns
    -------
    answer_id : str
    """
    data = load_forum_data()

    answer = {
        "id": uuid.uuid4().hex[:16],
        "question_id": question_id,
        "author": author if not anonymous else "anonymous",
        "author_display": "匿名用户" if anonymous else author_display,
        "anonymous": anonymous,
        "created_at": datetime.now().isoformat(),
        "content": content,
        "upvotes": 0,
        "is_accepted": False
    }

    data["answers"].append(answer)

    # 更新问题的回答数
    for post in data["posts"]:
        if post["id"] == question_id:
            post["answers_count"] = len([a for a in data["answers"] if a["question_id"] == question_id])
            if post["status"] == "open":
                post["status"] = "answered"
            break

    save_forum_data(data)
    return answer["id"]


def create_comment(
    parent_id: str,
    parent_type: str,
    author: str,
    author_display: str,
    content: str
) -> str:
    """添加评论

    Parameters
    ----------
    parent_type : str
        'question' or 'answer'
    """
    data = load_forum_data()

    comment = {
        "id": uuid.uuid4().hex[:16],
        "parent_id": parent_id,
        "parent_type": parent_type,
        "author": author,
        "author_display": author_display,
        "created_at": datetime.now().isoformat(),
        "content": content
    }

    data["comments"].append(comment)
    save_forum_data(data)

    return comment["id"]


def upvote(user: str, target_id: str, target_type: str) -> bool:
    """点赞

    Parameters
    ----------
    target_type : str
        'question' or 'answer'
    """
    data = load_forum_data()

    # 检查是否已点赞
    existing_vote = next(
        (v for v in data["votes"] if v["user"] == user and v["target_id"] == target_id),
        None
    )

    if existing_vote:
        # 取消点赞
        data["votes"].remove(existing_vote)

        # 更新点赞数
        if target_type == "question":
            for post in data["posts"]:
                if post["id"] == target_id:
                    post["upvotes"] = max(0, post["upvotes"] - 1)
                    break
        elif target_type == "answer":
            for answer in data["answers"]:
                if answer["id"] == target_id:
                    answer["upvotes"] = max(0, answer["upvotes"] - 1)
                    break

        save_forum_data(data)
        return False  # 取消点赞
    else:
        # 新增点赞
        vote = {
            "user": user,
            "target_id": target_id,
            "target_type": target_type,
            "vote_type": "up"
        }
        data["votes"].append(vote)

        # 更新点赞数
        if target_type == "question":
            for post in data["posts"]:
                if post["id"] == target_id:
                    post["upvotes"] += 1
                    break
        elif target_type == "answer":
            for answer in data["answers"]:
                if answer["id"] == target_id:
                    answer["upvotes"] += 1
                    break

        save_forum_data(data)
        return True  # 点赞成功


def accept_answer(question_id: str, answer_id: str, author: str) -> bool:
    """采纳最佳答案（仅提问者可操作）"""
    data = load_forum_data()

    # 验证提问者身份
    question = next((p for p in data["posts"] if p["id"] == question_id), None)
    if not question or question["author"] != author:
        return False

    # 取消之前的采纳
    if question["accepted_answer_id"]:
        for answer in data["answers"]:
            if answer["id"] == question["accepted_answer_id"]:
                answer["is_accepted"] = False
                break

    # 设置新的采纳
    for answer in data["answers"]:
        if answer["id"] == answer_id:
            answer["is_accepted"] = True
            question["accepted_answer_id"] = answer_id
            question["status"] = "answered"
            break

    save_forum_data(data)
    return True


def increment_views(question_id: str):
    """增加问题浏览量"""
    data = load_forum_data()

    for post in data["posts"]:
        if post["id"] == question_id:
            post["views"] = post.get("views", 0) + 1
            break

    save_forum_data(data)


def get_question(question_id: str) -> Optional[Dict]:
    """获取问题详情"""
    data = load_forum_data()
    return next((p for p in data["posts"] if p["id"] == question_id), None)


def get_answers(question_id: str) -> List[Dict]:
    """获取问题的所有回答"""
    data = load_forum_data()
    answers = [a for a in data["answers"] if a["question_id"] == question_id]
    # 按点赞数和时间排序（采纳的答案置顶）
    answers.sort(key=lambda x: (not x["is_accepted"], -x["upvotes"], x["created_at"]))
    return answers


def get_comments(parent_id: str) -> List[Dict]:
    """获取评论"""
    data = load_forum_data()
    comments = [c for c in data["comments"] if c["parent_id"] == parent_id]
    comments.sort(key=lambda x: x["created_at"])
    return comments


def search_posts(
    keyword: str = "",
    tags: List[str] = None,
    software: str = "",
    status: str = "",
    sort_by: str = "latest"
) -> List[Dict]:
    """搜索问题

    Parameters
    ----------
    sort_by : str
        'latest' | 'votes' | 'views' | 'unanswered'
    """
    data = load_forum_data()
    posts = data["posts"].copy()

    # 关键词过滤
    if keyword:
        keyword_lower = keyword.lower()
        posts = [
            p for p in posts
            if keyword_lower in p["title"].lower() or keyword_lower in p["content"].lower()
        ]

    # 标签过滤
    if tags:
        posts = [p for p in posts if any(t in p["tags"] for t in tags)]

    # 软件过滤
    if software:
        posts = [p for p in posts if p.get("software") == software]

    # 状态过滤
    if status:
        posts = [p for p in posts if p.get("status") == status]

    # 排序
    if sort_by == "latest":
        posts.sort(key=lambda x: x["created_at"], reverse=True)
    elif sort_by == "votes":
        posts.sort(key=lambda x: x["upvotes"], reverse=True)
    elif sort_by == "views":
        posts.sort(key=lambda x: x.get("views", 0), reverse=True)
    elif sort_by == "unanswered":
        posts = [p for p in posts if p["answers_count"] == 0]
        posts.sort(key=lambda x: x["created_at"], reverse=True)

    return posts


def get_user_votes(user: str) -> List[str]:
    """获取用户点赞的 ID 列表"""
    data = load_forum_data()
    return [v["target_id"] for v in data["votes"] if v["user"] == user]


def has_user_upvoted(user: str, target_id: str, target_type: str) -> bool:
    """检查用户是否已点赞

    Parameters
    ----------
    user : str
        用户名
    target_id : str
        目标ID（问题或回答）
    target_type : str
        'question' or 'answer'

    Returns
    -------
    bool
        是否已点赞
    """
    data = load_forum_data()
    for vote in data["votes"]:
        if (vote["user"] == user and
            vote["target_id"] == target_id and
            vote["target_type"] == target_type):
            return True
    return False
