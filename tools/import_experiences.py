"""
自动导入实战经验到经验库

功能：
1. 读取 contributed_experiences_demo.json
2. 合并到 runtime/lab_board/posts.json
3. 避免重复
4. 自动设置为 approved 状态（管理员已审核）
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def import_experiences():
    """导入实战经验到经验库"""

    # 文件路径
    demo_file = Path("contributed_experiences_demo.json")
    posts_file = Path("runtime/lab_board/posts.json")

    # 检查 demo 文件
    if not demo_file.exists():
        print(f"❌ 找不到示例文件：{demo_file}")
        print("请确保 contributed_experiences_demo.json 在当前目录")
        return False

    # 读取 demo 数据
    print(f"📖 读取示例数据：{demo_file}")
    with open(demo_file, 'r', encoding='utf-8') as f:
        demo_data = json.load(f)

    demo_entries = demo_data.get("entries", [])
    print(f"✅ 找到 {len(demo_entries)} 条经验")

    # 创建或读取现有经验库
    if posts_file.exists():
        print(f"📖 读取现有经验库：{posts_file}")
        with open(posts_file, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
    else:
        print(f"📝 创建新经验库：{posts_file}")
        posts_file.parent.mkdir(parents=True, exist_ok=True)
        posts_data = {"entries": []}

    # 检查重复
    existing_ids = {e["id"] for e in posts_data["entries"]}
    new_entries = []

    for entry in demo_entries:
        if entry["id"] in existing_ids:
            print(f"⚠️ 跳过重复经验：{entry['id']} - {entry['title']}")
        else:
            # 更新状态为已审核
            entry["status"] = "approved"
            entry["date"] = datetime.now().strftime("%Y-%m-%d")
            new_entries.append(entry)
            print(f"✅ 添加新经验：{entry['id']} - {entry['title']}")

    if not new_entries:
        print("\n💡 没有新经验需要导入（所有经验已存在）")
        return True

    # 合并数据
    posts_data["entries"].extend(new_entries)

    # 备份原文件
    if posts_file.exists():
        backup_file = posts_file.with_suffix('.json.backup')
        shutil.copy2(posts_file, backup_file)
        print(f"💾 备份原文件：{backup_file}")

    # 保存
    with open(posts_file, 'w', encoding='utf-8') as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 成功导入 {len(new_entries)} 条经验！")
    print(f"📊 经验库总计：{len(posts_data['entries'])} 条")
    print(f"📁 文件位置：{posts_file}")

    return True


def copy_images():
    """复制配图到项目目录"""

    # 图片来源（Claude image cache）
    cache_dir = Path(r"C:\Users\17706\.claude\image-cache\a6558aff-b50b-4474-aab4-ac8115bc8507")

    # 目标目录
    images_dir = Path("runtime/images/experiences")
    images_dir.mkdir(parents=True, exist_ok=True)

    # 复制图片
    image_files = ["41.png", "42.png", "43.png", "44.png", "45.png", "46.png"]
    copied_count = 0

    print("\n📷 开始复制配图...")

    for img_file in image_files:
        src = cache_dir / img_file
        dst = images_dir / img_file

        if src.exists():
            if not dst.exists():
                shutil.copy2(src, dst)
                print(f"✅ 复制：{img_file}")
                copied_count += 1
            else:
                print(f"⚠️ 已存在：{img_file}")
        else:
            print(f"❌ 找不到：{img_file}")

    if copied_count > 0:
        print(f"\n🎉 成功复制 {copied_count} 张图片到：{images_dir}")
    else:
        print(f"\n💡 所有图片已存在，无需复制")

    return copied_count > 0


if __name__ == "__main__":
    print("=" * 60)
    print("实战经验自动导入工具")
    print("=" * 60)
    print()

    # 导入经验
    success = import_experiences()

    if success:
        # 复制图片
        copy_images()

        print()
        print("=" * 60)
        print("✅ 导入完成！")
        print()
        print("下一步：")
        print("1. 启动 Web 应用：streamlit run main.py")
        print("2. 登录管理员账号（admin / admin123）")
        print("3. 进入「设置」→「📚 实验室共同知识库」")
        print("4. 查看新导入的 6 条经验")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ 导入失败，请检查错误信息")
        print("=" * 60)
