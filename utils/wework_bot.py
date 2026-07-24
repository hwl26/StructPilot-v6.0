"""StructPilot v6.0 — 企业微信机器人集成。

配置方法：
1. 企业微信创建群聊 → 添加「群机器人」
2. 复制 Webhook URL
3. 在 StructPilot 高级模式设置中填入 Webhook
4. 发消息格式：#经验 标题\\n症状：...\\n解决：...
"""

import json
import requests
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
_WEWORK_CONFIG = BASE_DIR / "runtime" / "config" / "wework_bot.json"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def load_wework_config() -> dict:
    """加载企业微信配置。"""
    try:
        return json.loads(_WEWORK_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {"webhook_url": "", "enabled": False}


def save_wework_config(webhook_url: str, enabled: bool) -> bool:
    """保存企业微信配置。"""
    try:
        _WEWORK_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        cfg = {"webhook_url": webhook_url, "enabled": enabled}
        _WEWORK_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def send_wework_message(webhook_url: str, content: str) -> bool:
    """发送企业微信消息。

    Parameters
    ----------
    webhook_url
        企业微信群机器人 Webhook URL
    content
        消息内容（markdown 格式）

    Returns
    -------
    bool
        是否发送成功
    """
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        r = requests.post(webhook_url, json=payload, timeout=5)
        return r.ok and r.json().get("errcode") == 0
    except Exception:
        return False


def parse_wework_experience(text: str) -> Optional[dict]:
    """解析企业微信消息，提取经验信息。

    格式示例：
    #经验 [cp_02] Motion Correction 漂移过大
    症状：drift plot 超出范围
    解决：增大 B-factor 到 300
    标签：运动校正, 漂移

    Returns
    -------
    dict | None
        成功返回 {"title": ..., "symptoms_text": ..., "solution": ..., "step": ..., "tags": []}
        失败返回 None
    """
    import re

    if not text.strip().startswith("#经验"):
        return None

    result = {"title": "", "symptoms_text": "", "solution": "", "step": "", "tags": []}

    # 去掉 #经验 标签
    text = re.sub(r"^#经验\s*", "", text.strip())

    # 提取步骤（如果有 [cp_XX] 格式）
    step_match = re.search(r"\[(cp_\d+)\]", text)
    if step_match:
        result["step"] = step_match.group(1)
        text = text.replace(step_match.group(0), "").strip()

    # 按行解析
    lines = text.split("\n")
    result["title"] = lines[0].strip()

    for line in lines[1:]:
        if line.startswith("症状：") or line.startswith("问题："):
            result["symptoms_text"] = line.split("：", 1)[1].strip()
        elif line.startswith("解决：") or line.startswith("方案："):
            result["solution"] = line.split("：", 1)[1].strip()
        elif line.startswith("标签："):
            result["tags"] = [t.strip() for t in line.split("：", 1)[1].split(",")]

    # 如果没有结构化格式，把全文作为解决方案
    if not result["solution"]:
        result["solution"] = text

    return result if result["title"] else None


def save_experience_from_wework(text: str, author: str = "企业微信用户") -> bool:
    """将企业微信消息保存为待审核经验。

    Parameters
    ----------
    text
        消息内容
    author
        发送者（企业微信昵称）

    Returns
    -------
    bool
        是否保存成功
    """
    try:
        exp = parse_wework_experience(text)
        if not exp:
            return False

        try:
            data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {"entries": [], "meta": {}}

        import datetime
        new_entry = {
            "id": f"lab_wework_{len(data['entries'])+1:03d}",
            "category": "企业微信记录",
            "title": exp["title"],
            "source": "wework",
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

        # 发送确认消息
        cfg = load_wework_config()
        if cfg.get("enabled") and cfg.get("webhook_url"):
            send_wework_message(
                cfg["webhook_url"],
                f"✅ **经验已记录**\n\n"
                f"标题：{exp['title']}\n"
                f"状态：待管理员审核\n"
                f"作者：{author}"
            )

        return True
    except Exception:
        return False


# ============ 企业微信消息接收（需要独立服务） ============

def start_wework_webhook_server(port: int = 8502):
    """启动企业微信 Webhook 接收服务器（需要公网IP或内网穿透）。

    ⚠️ 此功能需要：
    1. 独立运行一个 HTTP 服务器
    2. 公网 IP 或内网穿透（ngrok / frp）
    3. 企业微信配置「接收消息」回调 URL

    使用方法：
    ```python
    # 在单独的终端运行
    python -c "from utils.wework_bot import start_wework_webhook_server; start_wework_webhook_server()"
    ```
    """
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    @app.route("/wework/callback", methods=["POST"])
    def wework_callback():
        try:
            data = request.get_json()
            # 企业微信消息格式
            msg_type = data.get("msgtype")
            if msg_type == "text":
                content = data.get("text", {}).get("content", "")
                sender = data.get("From", {}).get("Name", "企业微信用户")

                # 处理 #经验 消息
                if content.strip().startswith("#经验"):
                    ok = save_experience_from_wework(content, sender)
                    if ok:
                        return jsonify({"errcode": 0, "errmsg": "ok"})

            return jsonify({"errcode": 0, "errmsg": "ignored"})
        except Exception as e:
            return jsonify({"errcode": 1, "errmsg": str(e)})

    print(f"企业微信 Webhook 服务启动在 http://0.0.0.0:{port}/wework/callback")
    print("请配置企业微信「接收消息」回调 URL 为此地址")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    # 测试解析
    test_msg = """#经验 [cp_02] Motion Correction 漂移过大
症状：drift plot 超出范围，很多 micrograph 被丢弃
解决：增大 B-factor 从 150 调到 300，同时检查样品制备
标签：运动校正, 漂移, B-factor"""

    result = parse_wework_experience(test_msg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
