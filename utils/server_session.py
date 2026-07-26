"""服务端session存储模块"""
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

SESSION_DIR = Path(__file__).parent.parent / "runtime" / "sessions"
SESSION_EXPIRE_DAYS = 7

def generate_session_id() -> str:
    """生成新的session ID"""
    return str(uuid.uuid4())

def save_server_session(session_id: str, data: Dict[str, Any]) -> bool:
    """保存session数据到服务端文件"""
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        session_file = SESSION_DIR / f"{session_id}.json"
        payload = {
            "data": data,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=SESSION_EXPIRE_DAYS)).isoformat()
        }
        session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def load_server_session(session_id: str) -> Optional[Dict[str, Any]]:
    """从服务端文件加载session数据"""
    try:
        session_file = SESSION_DIR / f"{session_id}.json"
        if not session_file.exists():
            return None

        payload = json.loads(session_file.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(payload["expires_at"])

        if datetime.now() > expires_at:
            session_file.unlink()  # 删除过期session
            return None

        return payload["data"]
    except Exception:
        return None

def delete_server_session(session_id: str) -> bool:
    """删除session文件"""
    try:
        session_file = SESSION_DIR / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
        return True
    except Exception:
        return False

def cleanup_expired_sessions() -> int:
    """清理所有过期session，返回清理数量"""
    count = 0
    try:
        if not SESSION_DIR.exists():
            return 0

        now = datetime.now()
        for session_file in SESSION_DIR.glob("*.json"):
            try:
                payload = json.loads(session_file.read_text(encoding="utf-8"))
                expires_at = datetime.fromisoformat(payload["expires_at"])
                if now > expires_at:
                    session_file.unlink()
                    count += 1
            except Exception:
                continue
    except Exception:
        pass
    return count
