"""StructPilot v6.0 — 成员权限管理系统。

实现管理员、普通成员、访客三级权限体系。
"""

from __future__ import annotations

import json
import hashlib
import os
import secrets
from pathlib import Path
from typing import Literal
from utils.atomic_io import atomic_write_json, path_lock

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

BASE_DIR = Path(__file__).resolve().parent.parent
_USERS_PATH = BASE_DIR / "runtime" / "config" / "users.json"

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
        # Public deployments must never create a known administrator password.
        # Administrators are only bootstrapped when the hosting environment
        # explicitly provides a private password through its secret store.
        bootstrap_password = os.getenv("STRUCTPILOT_BOOTSTRAP_ADMIN_PASSWORD", "").strip()
        default_data = {
            "users": [],
            "default_role": "guest",
            "permissions": {
                "admin": ["all"],
                "member": ["view", "contribute", "comment", "personal_notes"],
                "guest": ["view"]
            }
        }
        if bootstrap_password:
            default_data["users"].append({
                "username": "admin",
                "password_hash": _hash_password(bootstrap_password),
                "role": "admin",
                "display_name": "管理员",
                "email": "",
                "force_change_password": True,
            })
        _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(_USERS_PATH, default_data)
        return default_data

    return data


def save_users(data: dict) -> bool:
    """保存用户配置。"""
    try:
        _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(_USERS_PATH, data)
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
        # 兼容旧的无盐SHA256（不安全，建议用户重置密码）
        # 假设是 SHA256(password)
        import hashlib
        computed_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return secrets.compare_digest(computed_hash, password_hash)


def authenticate(username: str, password: str) -> dict | None:
    """验证用户登录。

    Returns
    -------
    dict | None
        成功返回用户信息，失败返回 None
    """
    from utils.password_policy import check_failed_attempts, record_failed_attempt, reset_failed_attempts
    from utils.server_session import generate_session_id, save_server_session

    # 暴力破解防护检查
    is_locked, lock_msg = check_failed_attempts(username, {})
    if is_locked:
        return None

    data = load_users()
    for user in data.get("users", []):
        # 用户名是公开信息，直接字符串比较即可
        if user.get("username") == username and _verify_password(password, user["password_hash"]):
            reset_failed_attempts(username, {})

            # 生成 session_id 并保存到服务端
            session_id = generate_session_id()
            save_server_session(session_id, {
                "username": user["username"],
                "role": user.get("role", "user"),
                "display_name": user.get("display_name", user["username"]),
                "logged_in": True
            })
            return {
                "username": user["username"],
                "role": user.get("role", "member"),
                "display_name": user.get("display_name", user["username"]),
                "email": user.get("email", ""),
                "force_change_password": bool(user.get("force_change_password", False)),
                "session_id": session_id,
            }

    record_failed_attempt(username, {})
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
    with path_lock(_USERS_PATH):
        data = load_users()
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
    with path_lock(_USERS_PATH):
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
    with path_lock(_USERS_PATH):
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
    with path_lock(_USERS_PATH):
        data = load_users()
        for user in data["users"]:
            if user["username"] == username:
                user["role"] = new_role
                return save_users(data)
    return False
