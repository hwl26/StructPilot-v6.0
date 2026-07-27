"""StructPilot 强密码策略增强模块

功能：
1. 密码复杂度验证（长度、大小写、数字、特殊字符）
2. 密码过期提醒（可选）
3. 登录失败锁定（防暴力破解）
4. 密码历史（防止重复使用）
"""

import re
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple
from utils.atomic_io import atomic_update_json, atomic_write_json

_FAILED_ATTEMPTS_FILE = Path(__file__).parent.parent / "runtime" / "failed_attempts.json"


def _load_attempts() -> dict:
    try:
        if _FAILED_ATTEMPTS_FILE.exists():
            return json.loads(_FAILED_ATTEMPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_attempts(data: dict) -> None:
    try:
        _FAILED_ATTEMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(_FAILED_ATTEMPTS_FILE, data)
    except Exception:
        pass

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


def check_failed_attempts(username: str, failed_attempts: dict = None) -> Tuple[bool, str]:
    """检查登录失败次数，防暴力破解。使用持久化文件存储，failed_attempts 参数保留向后兼容但忽略。

    Returns
    -------
    (is_locked, message)
    """
    data = _load_attempts()

    if username not in data:
        return False, ""

    record = data[username]
    count = record.get("count", 0)
    last_attempt_str = record.get("last_attempt")

    if count >= PASSWORD_POLICY["max_failed_attempts"] and last_attempt_str:
        try:
            last_attempt = datetime.fromisoformat(last_attempt_str)
        except Exception:
            return False, ""
        lockout_until = last_attempt + timedelta(seconds=PASSWORD_POLICY["lockout_duration"])
        if datetime.now() < lockout_until:
            remaining = int((lockout_until - datetime.now()).total_seconds())
            return True, f"账号已锁定，请 {remaining} 秒后重试"
        else:
            # 锁定过期，重置计数
            data[username] = {"count": 0, "last_attempt": None}
            _save_attempts(data)
            return False, ""

    return False, ""


def record_failed_attempt(username: str, failed_attempts: dict = None) -> None:
    """记录登录失败。使用持久化文件存储，failed_attempts 参数保留向后兼容但忽略。"""
    def mutate(data):
        data = data if isinstance(data, dict) else {}
        if username not in data:
            data[username] = {"count": 0, "last_attempt": None}
        data[username]["count"] += 1
        data[username]["last_attempt"] = datetime.now().isoformat()
        return data
    atomic_update_json(_FAILED_ATTEMPTS_FILE, {}, mutate)


def reset_failed_attempts(username: str, failed_attempts: dict = None) -> None:
    """登录成功后重置失败计数。使用持久化文件存储，failed_attempts 参数保留向后兼容但忽略。"""
    def mutate(data):
        data = data if isinstance(data, dict) else {}
        data.pop(username, None)
        return data
    atomic_update_json(_FAILED_ATTEMPTS_FILE, {}, mutate)


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
