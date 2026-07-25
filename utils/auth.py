"""StructPilot v6.0 — 成员权限管理系统。

实现管理员、普通成员、访客三级权限体系。
"""

from __future__ import annotations

import json
import hashlib
import secrets
from pathlib import Path
from typing import Literal

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

BASE_DIR = Path(__file__).resolve().parent.parent
_USERS_PATH = BASE_DIR / "runtime" / "config" / "users.json"

# 默认密码的明文，用于检测用户是否仍在使用默认密码
_DEFAULT_ADMIN_PASSWORD = "admin123"


RoleType = Literal["admin", "member", "guest"]


def _hash_password(password: str) -> str:
    """哈希密码，优先使用 bcrypt，fallback 为 PBKDF2-SHA256。"""
    if _HAS_BCRYPT:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    else:
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return f"pbkdf2:{salt.hex()}:{dk.hex()}"


def load_users() -> dict:
    """加载用户配置。

    Returns
    -------
    dict
        {
            "users": [
                {"username": "admin", "password_hash": "xxx", "role": "admin", "display_name": "管理员"},
                {"username": "zhangsan", "password_hash": "yyy", "role": "member", "display_name": "张三"},
            ],
            "default_role": "guest"  # 未登录时的默认角色
        }
    """
    try:
        data = json.loads(_USERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        # 首次使用，创建默认管理员账号（密码：admin123）
        default_data = {
            "users": [
                {
                    "username": "admin",
                    "password_hash": _hash_password("admin123"),
                    "role": "admin",
                    "display_name": "管理员",
                    "email": "",
                    "force_change_password": True
                }
            ],
            "default_role": "guest",
            "permissions": {
                "admin": ["all"],
                "member": ["view", "contribute", "comment", "personal_notes"],
                "guest": ["view"]
            }
        }
        _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USERS_PATH.write_text(json.dumps(default_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return default_data

    # 检测用户是否仍在使用默认密码，设置 force_change_password 标志
    for user in data.get("users", []):
        if user.get("username") == "admin" and not user.get("force_change_password"):
            if _verify_password(_DEFAULT_ADMIN_PASSWORD, user["password_hash"]):
                user["force_change_password"] = True
                save_users(data)


def save_users(data: dict) -> bool:
    """保存用户配置。"""
    try:
        _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _verify_password(password: str, password_hash: str) -> bool:
    """验证密码，兼容旧的 SHA256 哈希、bcrypt 和 PBKDF2 三种格式。"""
    if password_hash.startswith("$2b$") or password_hash.startswith("$2a$"):
        # bcrypt 哈希
        if _HAS_BCRYPT:
            try:
                return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
            except Exception:
                return False
        return False
    elif password_hash.startswith("pbkdf2:"):
        # PBKDF2-SHA256 哈希（自身 fallback）
        try:
            _, salt_hex, dk_hex = password_hash.split(":", 2)
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            return secrets.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False
    else:
        # 旧的 SHA256 哈希（向后兼容）
        computed = hashlib.sha256(password.encode()).hexdigest()
        return secrets.compare_digest(computed, password_hash)


def authenticate(username: str, password: str) -> dict | None:
    """验证用户登录。

    Returns
    -------
    dict | None
        成功返回用户信息，失败返回 None
    """
    data = load_users()
    for user in data.get("users", []):
        if user["username"] == username and _verify_password(password, user["password_hash"]):
            return user
    return None


def get_current_user(session_state) -> dict:
    """获取当前登录用户。

    Returns
    -------
    dict
        {"username": "...", "role": "...", "display_name": "..."}
        未登录时返回 guest 角色
    """
    if hasattr(session_state, "current_user") and session_state.current_user:
        return session_state.current_user
    # 未登录，返回访客
    data = load_users()
    return {
        "username": "guest",
        "role": data.get("default_role", "guest"),
        "display_name": "访客"
    }


def has_permission(user: dict, permission: str) -> bool:
    """检查用户是否有指定权限。

    Parameters
    ----------
    user
        用户信息字典
    permission
        权限名称，如 "contribute" / "approve" / "manage_users"

    Returns
    -------
    bool
    """
    data = load_users()
    role = user.get("role", "guest")
    perms = data.get("permissions", {}).get(role, [])
    return "all" in perms or permission in perms


def add_user(username: str, password: str, role: RoleType, display_name: str, email: str = "") -> bool:
    """添加新用户。"""
    data = load_users()
    # 检查用户名是否已存在
    if any(u["username"] == username for u in data["users"]):
        return False
    data["users"].append({
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "display_name": display_name,
        "email": email
    })
    return save_users(data)


def delete_user(username: str) -> bool:
    """删除用户。"""
    if username == "admin":
        return False  # 不允许删除管理员
    data = load_users()
    data["users"] = [u for u in data["users"] if u["username"] != username]
    return save_users(data)


def change_password(username: str, new_password: str) -> tuple[bool, str]:
    """修改密码（含密码强度验证）。

    Returns
    -------
    (success, error_message)
    """
    from utils.password_policy import validate_password_strength
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        return False, error_msg
    data = load_users()
    for user in data["users"]:
        if user["username"] == username:
            user["password_hash"] = _hash_password(new_password)
            user["force_change_password"] = False
            return save_users(data), ""
    return False, "用户不存在"


def change_role(username: str, new_role: RoleType) -> bool:
    """修改用户角色。"""
    if username == "admin":
        return False  # 不允许修改管理员角色
    data = load_users()
    for user in data["users"]:
        if user["username"] == username:
            user["role"] = new_role
            return save_users(data)
    return False
