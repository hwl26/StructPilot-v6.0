"""
读取 CSV 文件的工具脚本
"""

import sys
import csv
from pathlib import Path


def read_csv(file_path: str, encoding: str = 'utf-8') -> None:
    """读取 CSV 文件并输出内容"""
    csv_path = Path(file_path)

    if not csv_path.exists():
        print(f"❌ 文件不存在：{file_path}")
        return

    # 尝试不同编码
    encodings = [encoding, 'utf-8', 'gbk', 'gb2312', 'utf-8-sig']

    for enc in encodings:
        try:
            with open(csv_path, 'r', encoding=enc, newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)

                print(f"📄 文件：{csv_path.name}")
                print(f"📊 行数：{len(rows)}")
                print(f"📝 编码：{enc}")
                print("=" * 80)
                print()

                # 输出前 50 行
                for i, row in enumerate(rows[:50], 1):
                    print(f"[{i}] {' | '.join(row)}")

                if len(rows) > 50:
                    print()
                    print(f"... 还有 {len(rows) - 50} 行未显示 ...")

                return

        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"❌ 读取失败（编码 {enc}）：{e}")
            continue

    print(f"❌ 无法读取文件，尝试了以下编码：{encodings}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python read_csv.py <文件路径> [编码]")
        print("示例：python read_csv.py data.csv utf-8")
        sys.exit(1)

    file_path = sys.argv[1]
    encoding = sys.argv[2] if len(sys.argv) > 2 else 'utf-8'
    read_csv(file_path, encoding)
