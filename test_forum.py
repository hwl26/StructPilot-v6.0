#!/usr/bin/env python3
"""StructPilot 论坛模块快速测试"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from utils.forum_data import (
    load_forum_data,
    create_question,
    create_answer,
    create_comment,
    upvote,
    search_posts,  # 修正函数名
    get_question,
    get_answers,
    accept_answer
)


def test_forum():
    """测试论坛功能"""
    print("=" * 60)
    print("StructPilot 论坛模块测试")
    print("=" * 60)
    print()

    # 测试1：加载数据
    print("【测试1】加载论坛数据...")
    data = load_forum_data()
    assert "posts" in data, "缺少 posts 字段"
    assert "answers" in data, "缺少 answers 字段"
    assert "comments" in data, "缺少 comments 字段"
    assert "votes" in data, "缺少 votes 字段"
    print(f"✅ 成功加载数据")
    print(f"   - 问题数: {len(data['posts'])}")
    print(f"   - 回答数: {len(data['answers'])}")
    print(f"   - 评论数: {len(data['comments'])}")
    print(f"   - 投票数: {len(data['votes'])}")
    print()

    # 测试2：创建问题
    print("【测试2】创建新问题...")
    question_id = create_question(
        author="test_user",
        author_display="测试用户",
        title="测试问题：如何配置论坛？",
        content="我想知道如何配置StructPilot的论坛功能，请问有详细教程吗？",
        tags=["test", "forum", "configuration"],
        software="StructPilot",
        step="",
        anonymous=False,
        author_lab="test_lab",
        visibility="public"
    )
    print(f"✅ 创建问题成功")
    print(f"   - 问题 ID: {question_id}")
    print()

    # 测试3：回答问题
    print("【测试3】回答问题...")
    answer_id = create_answer(
        question_id=question_id,
        author="test_expert",
        author_display="测试专家",
        content="论坛配置很简单！\n\n**步骤：**\n1. 打开 StructPilot\n2. 点击「💬 讨论区」Tab\n3. 点击「➕ 提问」按钮\n\n就可以开始使用了！",
        anonymous=False
    )
    print(f"✅ 创建回答成功")
    print(f"   - 回答 ID: {answer_id}")
    print()

    # 测试4：添加评论
    print("【测试4】添加评论...")
    comment_id = create_comment(
        parent_id=answer_id,
        parent_type="answer",
        author="test_user",
        author_display="测试用户",
        content="谢谢！非常清楚 👍"
    )
    print(f"✅ 创建评论成功")
    print(f"   - 评论 ID: {comment_id}")
    print()

    # 测试5：点赞
    print("【测试5】点赞测试...")
    success = upvote("test_user2", question_id, "question")
    assert success, "点赞问题失败"
    success = upvote("test_user3", answer_id, "answer")
    assert success, "点赞回答失败"
    print("✅ 点赞成功")
    print()

    # 测试6：采纳答案
    print("【测试6】采纳最佳答案...")
    success = accept_answer(question_id, answer_id, "test_user")
    assert success, "采纳答案失败"
    print("✅ 采纳答案成功")
    print()

    # 测试7：搜索功能
    print("【测试7】搜索功能...")
    results = search_posts(keyword="配置")
    print(f"✅ 搜索 '配置' 找到 {len(results)} 个结果")

    results_with_tag = search_posts(keyword="", tags=["test"])
    print(f"✅ 标签 'test' 找到 {len(results_with_tag)} 个结果")
    print()

    # 测试8：读取问题详情
    print("【测试8】读取问题详情...")
    question = get_question(question_id)
    assert question is not None, "问题不存在"
    assert question["title"] == "测试问题：如何配置论坛？", "标题不匹配"
    print("✅ 读取问题成功")
    print(f"   - 标题: {question['title']}")
    print(f"   - 作者: {question['author_display']}")
    print(f"   - 状态: {question['status']}")
    print(f"   - 点赞数: {question['upvotes']}")
    print()

    # 测试9：读取回答列表
    print("【测试9】读取回答列表...")
    answers = get_answers(question_id)
    assert len(answers) >= 1, "回答数量不正确"
    print(f"✅ 读取到 {len(answers)} 个回答")
    print()

    print("=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)
    print()
    print("下一步：")
    print("1. 运行 streamlit run main.py")
    print("2. 打开浏览器 http://localhost:8501")
    print("3. 点击「💬 讨论区」Tab")
    print("4. 查看测试数据和示例问题")
    print()


if __name__ == "__main__":
    try:
        test_forum()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
