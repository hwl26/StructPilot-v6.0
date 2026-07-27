"""
复制配图到项目目录的脚本

将 Claude image cache 中的图片复制到项目 runtime/images/experiences/ 目录
"""

import sys
import shutil
import os
from pathlib import Path

# 设置输出编码为 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def copy_experience_images():
    """复制经验库配图"""

    # 源目录由调用者显式提供，避免把开发者本机路径写入公开仓库。
    source_dir = os.getenv("STRUCTPILOT_EXPERIENCE_IMAGE_SOURCE", "").strip()
    if not source_dir:
        print("请先设置 STRUCTPILOT_EXPERIENCE_IMAGE_SOURCE 为图片源目录。")
        return False
    cache_dir = Path(source_dir).expanduser().resolve()

    # 目标目录
    target_dir = Path(__file__).parent.parent / "runtime" / "images" / "experiences"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 要复制的图片
    image_files = ["41.png", "42.png", "43.png", "44.png", "45.png", "46.png"]

    print("📷 开始复制经验库配图...")
    print(f"源目录：{cache_dir}")
    print(f"目标目录：{target_dir}")
    print()

    copied = 0
    skipped = 0
    missing = 0

    for img_file in image_files:
        src = cache_dir / img_file
        dst = target_dir / img_file

        if not src.exists():
            print(f"❌ 找不到源文件：{img_file}")
            missing += 1
            continue

        if dst.exists():
            print(f"⚠️ 已存在，跳过：{img_file}")
            skipped += 1
            continue

        try:
            shutil.copy2(src, dst)
            print(f"✅ 复制成功：{img_file}")
            copied += 1
        except Exception as e:
            print(f"❌ 复制失败：{img_file} - {e}")
            missing += 1

    print()
    print("=" * 60)
    print(f"📊 复制结果：")
    print(f"  ✅ 成功复制：{copied} 张")
    print(f"  ⚠️ 已存在：{skipped} 张")
    print(f"  ❌ 失败/缺失：{missing} 张")
    print(f"  📁 目标目录：{target_dir}")
    print("=" * 60)

    return copied + skipped == len(image_files)


if __name__ == "__main__":
    success = copy_experience_images()

    if success:
        print("\n🎉 所有图片准备完毕！")
        print("\n下一步：")
        print("1. 启动 Web 应用：streamlit run main.py")
        print("2. 进入「设置」→「实验室共同知识库」")
        print("3. 展开经验条目，查看配图")
    else:
        print("\n⚠️ 部分图片复制失败，请检查源文件路径")
