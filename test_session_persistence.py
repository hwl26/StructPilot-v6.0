"""Session持久化验证脚本

用于快速验证session保存和恢复逻辑是否正常工作。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 设置UTF-8输出（Windows兼容）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 测试路径
SESSION_DIR = Path(__file__).parent / "runtime" / "sessions"

def test_session_files():
    """测试1：检查session文件是否存在"""
    print("\n=== 测试1：检查session文件 ===")
    if not SESSION_DIR.exists():
        print("❌ 错误：runtime/sessions/ 目录不存在")
        return False

    session_files = list(SESSION_DIR.glob("*.json"))
    if not session_files:
        print("⚠️  警告：没有找到活跃的session文件")
        print("   提示：请先登录应用以生成session")
        return True

    print(f"✅ 找到 {len(session_files)} 个session文件")
    for session_file in session_files:
        print(f"   - {session_file.name}")
    return True

def test_session_content():
    """测试2：验证session文件内容"""
    print("\n=== 测试2：验证session文件内容 ===")
    session_files = list(SESSION_DIR.glob("*.json"))
    if not session_files:
        print("⚠️  跳过：没有session文件")
        return True

    for session_file in session_files:
        try:
            payload = json.loads(session_file.read_text(encoding="utf-8"))

            # 验证必需字段
            required_fields = ["data", "created_at", "expires_at"]
            missing_fields = [f for f in required_fields if f not in payload]
            if missing_fields:
                print(f"❌ 错误：{session_file.name} 缺少字段：{missing_fields}")
                return False

            # 验证data内容
            data = payload["data"]
            required_data_fields = ["username", "role", "display_name", "logged_in"]
            missing_data = [f for f in required_data_fields if f not in data]
            if missing_data:
                print(f"❌ 错误：{session_file.name} 的data缺少字段：{missing_data}")
                return False

            # 检查是否过期
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.now() > expires_at:
                print(f"⚠️  警告：{session_file.name} 已过期")
            else:
                print(f"✅ {session_file.name} 内容有效")
                print(f"   - 用户：{data['username']} ({data['display_name']})")
                print(f"   - 角色：{data['role']}")
                print(f"   - 过期时间：{expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            print(f"❌ 错误：无法解析 {session_file.name}")
            print(f"   原因：{e}")
            return False

    return True

def test_session_restore_logic():
    """测试3：模拟session恢复逻辑"""
    print("\n=== 测试3：模拟session恢复逻辑 ===")

    from utils.server_session import load_server_session

    session_files = list(SESSION_DIR.glob("*.json"))
    if not session_files:
        print("⚠️  跳过：没有session文件")
        return True

    for session_file in session_files:
        session_id = session_file.stem  # 去掉.json后缀
        print(f"\n尝试恢复session：{session_id}")

        session_data = load_server_session(session_id)
        if session_data:
            print(f"✅ Session恢复成功")
            print(f"   - 用户名：{session_data.get('username')}")
            print(f"   - 角色：{session_data.get('role')}")
            print(f"   - 显示名称：{session_data.get('display_name')}")
            print(f"   - 登录状态：{session_data.get('logged_in')}")
        else:
            print(f"❌ Session恢复失败（可能已过期）")
            return False

    return True

def main():
    """运行所有测试"""
    print("=" * 60)
    print("Session持久化验证脚本")
    print("=" * 60)

    tests = [
        test_session_files,
        test_session_content,
        test_session_restore_logic
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ 测试执行失败：{e}")
            results.append(False)

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过：{passed}/{total}")

    if passed == total:
        print("\n✅ 所有测试通过！Session持久化逻辑正常。")
    else:
        print("\n⚠️  部分测试未通过，请检查上述错误信息。")

    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
