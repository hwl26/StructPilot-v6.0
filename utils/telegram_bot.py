"""StructPilot Telegram Bot — 发消息自动记录经验。

配置方法：
1. 在 https://t.me/BotFather 创建机器人，获取 Token
2. 在高级模式「设置」→「Telegram Bot」填入 Token
3. 发 /start 绑定用户
4. 发消息格式：#经验 [步骤] 标题\\n症状：...\\n解决：...
   简短记录也可以，AI 会帮你整理
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_TGBOT_CONFIG_PATH = BASE_DIR / "runtime" / "config" / "telegram_bot.json"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def load_bot_config() -> dict:
    try:
        return json.loads(_TGBOT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"token": "", "allowed_chat_ids": [], "enabled": False}


def save_bot_config(token: str, allowed_chat_ids: list, enabled: bool) -> bool:
    try:
        _TGBOT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg = {"token": token, "allowed_chat_ids": allowed_chat_ids, "enabled": enabled}
        _TGBOT_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def parse_experience_message(text: str, step_hint: str = "") -> dict:
    """解析 Telegram 消息，提取经验信息。"""
    import re
    result = {"title": "", "symptoms_text": "", "solution": "", "step": step_hint, "tags": []}

    # 去掉 #经验 标签
    text = re.sub(r"^#经验\s*", "", text.strip())

    # 提取步骤（如果有 [cp_01] 格式）
    step_match = re.search(r"\[(cp_\d+)\]", text)
    if step_match:
        result["step"] = step_match.group(1)
        text = text.replace(step_match.group(0), "").strip()

    # 解析结构化格式
    lines = text.split("\n")
    title = lines[0].strip()
    result["title"] = title

    for line in lines[1:]:
        if line.startswith("症状：") or line.startswith("问题："):
            result["symptoms_text"] = line.split("：", 1)[1].strip()
        elif line.startswith("解决：") or line.startswith("方案："):
            result["solution"] = line.split("：", 1)[1].strip()
        elif line.startswith("标签："):
            result["tags"] = [t.strip() for t in line.split("：", 1)[1].split(",")]

    # 如果没有结构化格式，把全文作为内容
    if not result["solution"]:
        result["solution"] = text

    return result


def save_experience_from_telegram(text: str, author: str, step_hint: str = "") -> bool:
    """将 Telegram 消息保存为待审核经验。"""
    try:
        exp = parse_experience_message(text, step_hint)
        if not exp["title"] or not exp["solution"]:
            return False

        try:
            data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {"entries": [], "meta": {}}

        import datetime
        new_entry = {
            "id": f"lab_tg_{len(data['entries'])+1:03d}",
            "category": "Telegram记录",
            "title": exp["title"],
            "source": "telegram",
            "author": author,
            "date": datetime.date.today().isoformat(),
            "status": "pending",
            "software": "通用",
            "step": exp["step"],
            "symptoms_text": exp["symptoms_text"],
            "solution": exp["solution"],
            "tags": exp["tags"],
            "images": [],
        }
        data["entries"].append(new_entry)
        _LAB_EXP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def start_polling(token: str, allowed_chat_ids: list):
    """启动 Telegram Bot 轮询（后台线程）。"""
    try:
        import requests
        import threading
        import time

        base_url = f"https://api.telegram.org/bot{token}"
        offset = [0]

        def poll():
            while True:
                try:
                    r = requests.get(
                        f"{base_url}/getUpdates",
                        params={"offset": offset[0], "timeout": 30},
                        timeout=35,
                    )
                    if r.ok:
                        updates = r.json().get("result", [])
                        for update in updates:
                            offset[0] = update["update_id"] + 1
                            msg = update.get("message", {})
                            chat_id = str(msg.get("chat", {}).get("id", ""))
                            text = msg.get("text", "")
                            from_user = (
                                msg.get("from", {}).get("username")
                                or msg.get("from", {}).get("first_name", "匿名")
                            )

                            if allowed_chat_ids and chat_id not in [str(c) for c in allowed_chat_ids]:
                                continue

                            if text.startswith("#经验") or text.startswith("/save"):
                                ok = save_experience_from_telegram(text, from_user)
                                reply = (
                                    "✅ 已记录到经验库（待审核）"
                                    if ok
                                    else "❌ 格式不对，请参考：\n#经验 标题\n症状：...\n解决：..."
                                )
                                requests.post(
                                    f"{base_url}/sendMessage",
                                    json={"chat_id": chat_id, "text": reply},
                                )
                            elif text.startswith("/start"):
                                help_text = (
                                    "🔬 StructPilot 经验记录机器人\n\n"
                                    "发送格式：\n"
                                    "#经验 [步骤] 标题\n"
                                    "症状：遇到了什么问题\n"
                                    "解决：怎么解决的\n\n"
                                    "例：\n"
                                    "#经验 [cp_02] Motion Correction 漂移过大\n"
                                    "症状：运动校正后 drift plot 超出范围\n"
                                    "解决：增大 B-factor 到 300"
                                )
                                requests.post(
                                    f"{base_url}/sendMessage",
                                    json={"chat_id": chat_id, "text": help_text},
                                )
                except Exception:
                    time.sleep(5)

        t = threading.Thread(target=poll, daemon=True)
        t.start()
        return t
    except Exception:
        return None
