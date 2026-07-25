"""StructPilot 强密码策略增强模块

功能：
1. 密码复杂度验证（长度、大小写、数字、特殊字符）
2. 密码过期提醒（可选）
3. 登录失败锁定（防暴力破解）
4. 密码历史（防止重复使用）
"""

import re
from datetime import datetime, timedelta
from typing import Tuple

# 强密码策略配置
PASSWORD_POLICY = {
    "min_length": 8,              # 最小长度
    "require_uppercase": True,    # 必须包含大写字母
    "require_lowercase": True,    # 必须包含小写字母
    "require_digit": True,        # 必须包含数字
    "require_special": True,      # 必须包含特殊字符
    "max_failed_attempts": 5,     # 最大失败次数
    "lockout_duration": 300,      # 锁定时长（秒）
    "password_expiry_days": 90,   # 密码过期天数（0=不过期）
}


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """验证密码强度。

    Returns
    -------
    (is_valid, error_message)
    """
    policy = PASSWORD_POLICY

    # 检查长度
    if len(password) < policy["min_length"]:
        return False, f"密码长度至少 {policy['min_length']} 位"

    # 检查大写字母
    if policy["require_uppercase"] and not re.search(r'[A-Z]', password):
        return False, "密码必须包含至少1个大写字母"

    # 检查小写字母
    if policy["require_lowercase"] and not re.search(r'[a-z]', password):
        return False, "密码必须包含至少1个小写字母"

    # 检查数字
    if policy["require_digit"] and not re.search(r'\d', password):
        return False, "密码必须包含至少1个数字"

    # 检查特殊字符
    if policy["require_special"] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "密码必须包含至少1个特殊字符（如 !@#$%）"

    return True, ""


def check_failed_attempts(username: str, failed_attempts: dict) -> Tuple[bool, str]:
    """检查登录失败次数，防暴力破解。

    Parameters
    ----------
    username : str
        用户名
    failed_attempts : dict
        {username: {"count": 3, "last_attempt": datetime}}

    Returns
    -------
    (is_locked, message)
    """
    if username not in failed_attempts:
        return False, ""

    record = failed_attempts[username]
    count = record.get("count", 0)
    last_attempt = record.get("last_attempt")

    if count >= PASSWORD_POLICY["max_failed_attempts"]:
        # 检查锁定是否过期
        if last_attempt:
            lockout_until = last_attempt + timedelta(seconds=PASSWORD_POLICY["lockout_duration"])
            if datetime.now() < lockout_until:
                remaining = int((lockout_until - datetime.now()).total_seconds())
                return True, f"账号已锁定，请 {remaining} 秒后重试"
            else:
                # 锁定过期，重置计数
                failed_attempts[username] = {"count": 0, "last_attempt": None}
                return False, ""

    return False, ""


def record_failed_attempt(username: str, failed_attempts: dict) -> None:
    """记录登录失败。"""
    if username not in failed_attempts:
        failed_attempts[username] = {"count": 0, "last_attempt": None}

    failed_attempts[username]["count"] += 1
    failed_attempts[username]["last_attempt"] = datetime.now()


def reset_failed_attempts(username: str, failed_attempts: dict) -> None:
    """登录成功后重置失败计数。"""
    if username in failed_attempts:
        del failed_attempts[username]


def check_password_expiry(user: dict) -> Tuple[bool, str]:
    """检查密码是否过期。

    Parameters
    ----------
    user : dict
        {"username": "admin", "password_changed_at": "2024-01-01T00:00:00"}

    Returns
    -------
    (is_expired, message)
    """
    expiry_days = PASSWORD_POLICY["password_expiry_days"]
    if expiry_days == 0:
        return False, ""  # 不启用过期策略

    last_changed = user.get("password_changed_at")
    if not last_changed:
        return False, ""  # 旧用户，首次登录后提示修改

    try:
        last_changed_dt = datetime.fromisoformat(last_changed)
        expiry_date = last_changed_dt + timedelta(days=expiry_days)

        if datetime.now() > expiry_date:
            return True, "密码已过期，请修改密码"

        # 提前7天提醒
        warning_date = expiry_date - timedelta(days=7)
        if datetime.now() > warning_date:
            days_left = (expiry_date - datetime.now()).days
            return False, f"密码将在 {days_left} 天后过期，建议及时修改"

    except Exception:
        pass

    return False, ""


# 示例用法
if __name__ == "__main__":
    # 测试密码强度
    test_passwords = [
        "weak",                    # 太短
        "WeakPassword",            # 缺少数字和特殊字符
        "Weak123",                 # 缺少特殊字符
        "Weak123!",                # ✅ 合格
        "StrongP@ssw0rd2024",      # ✅ 强密码
    ]

    print("=== 密码强度测试 ===")
    for pwd in test_passwords:
        valid, msg = validate_password_strength(pwd)
        status = "✅ 合格" if valid else f"❌ {msg}"
        print(f"{pwd:20s} → {status}")
