#!/usr/bin/env python3
"""快速修改 StructPilot 管理员密码"""

import json
import hashlib
from pathlib import Path

def hash_password(password: str) -> str:
    """SHA256 哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()

def main():
    # 用户配置文件路径
    config_file = Path(__file__).parent / "runtime" / "config" / "users.json"

    if not config_file.exists():
        print(f"❌ 配置文件不存在: {config_file}")
        return

    # 加载配置
    data = json.loads(config_file.read_text(encoding="utf-8"))

    print("=" * 50)
    print("StructPilot 密码修改工具")
    print("=" * 50)
    print()

    # 显示现有用户
    print("现有用户列表：")
    for i, user in enumerate(data["users"], 1):
        print(f"  {i}. {user['username']} ({user['display_name']}) - 角色: {user['role']}")
    print()

    # 选择用户
    try:
        choice = int(input("请选择要修改密码的用户（输入序号）: "))
        if choice < 1 or choice > len(data["users"]):
            print("❌ 无效的选择")
            return
    except ValueError:
        print("❌ 请输入数字")
        return

    user = data["users"][choice - 1]
    print()
    print(f"选择的用户: {user['username']} ({user['display_name']})")
    print()

    # 输入新密码
    new_password = input("请输入新密码: ").strip()
    if len(new_password) < 6:
        print("❌ 密码长度至少6位")
        return

    confirm_password = input("请再次输入新密码: ").strip()
    if new_password != confirm_password:
        print("❌ 两次输入的密码不一致")
        return

    # 更新密码
    user["password_hash"] = hash_password(new_password)

    # 保存配置
    config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("✅ 密码修改成功！")
    print()
    print("新的登录信息：")
    print(f"  用户名: {user['username']}")
    print(f"  密码: {new_password}")
    print()
    print("=" * 50)

if __name__ == "__main__":
    main()
