"""发邮件到指定地址，自动记录为经验条目。"""

import json
import email
import imaplib
import threading
import time
from pathlib import Path
from email.header import decode_header

BASE_DIR = Path(__file__).resolve().parent.parent
_EMAIL_CONFIG_PATH = BASE_DIR / "runtime" / "config" / "email_bot.json"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def load_email_config() -> dict:
    try:
        return json.loads(_EMAIL_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "imap_host": "",
            "imap_port": 993,
            "username": "",
            "password": "",
            "enabled": False,
            "check_interval": 300,
        }


def save_email_config(host: str, port: int, username: str, password: str, enabled: bool) -> bool:
    try:
        _EMAIL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg = {
            "imap_host": host,
            "imap_port": port,
            "username": username,
            "password": password,
            "enabled": enabled,
            "check_interval": 300,
        }
        _EMAIL_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _decode_str(s) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def fetch_new_emails(cfg: dict) -> list[dict]:
    """从 IMAP 拉取未读邮件，返回 [{subject, from, body}]"""
    try:
        conn = imaplib.IMAP4_SSL(cfg["imap_host"], cfg.get("imap_port", 993))
        conn.login(cfg["username"], cfg["password"])
        conn.select("INBOX")
        _, ids = conn.search(None, "UNSEEN")

        emails = []
        for uid in ids[0].split() or []:
            _, data = conn.fetch(uid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            subject = _decode_str(msg["Subject"])
            sender = _decode_str(msg["From"])
            body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            # 只处理主题包含 #经验 的邮件
            if "#经验" in subject or "[经验]" in subject:
                emails.append({"subject": subject, "from": sender, "body": body})
                conn.store(uid, "+FLAGS", "\\Seen")

        conn.logout()
        return emails
    except Exception:
        return []


def process_email_experiences(cfg: dict) -> int:
    """处理新邮件，返回新增经验条数"""
    emails = fetch_new_emails(cfg)
    count = 0
    for em in emails:
        try:
            data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {"entries": [], "meta": {}}

        import datetime
        import re
        title = re.sub(r"#经验\s*|\[经验\]\s*", "", em["subject"]).strip()
        new_entry = {
            "id": f"lab_email_{len(data['entries'])+1:03d}",
            "category": "邮件记录",
            "title": title,
            "source": "email",
            "author": em["from"],
            "date": datetime.date.today().isoformat(),
            "status": "pending",
            "software": "通用",
            "step": "",
            "symptoms_text": "",
            "solution": em["body"][:2000],
            "tags": [],
            "images": [],
        }
        data["entries"].append(new_entry)
        _LAB_EXP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
    return count


def start_email_polling(cfg: dict):
    """后台轮询邮件"""
    def poll():
        while True:
            try:
                process_email_experiences(cfg)
            except Exception:
                pass
            time.sleep(cfg.get("check_interval", 300))

    t = threading.Thread(target=poll, daemon=True)
    t.start()
    return t
