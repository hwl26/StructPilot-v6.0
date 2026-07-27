"""Outbound API target validation used before saving or testing integrations."""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse


def validate_service_base_url(value: str, *, allow_local: bool = False) -> tuple[bool, str]:
    value = str(value or "").strip()
    if not value:
        return True, ""
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.username or parsed.password or not host:
        return False, "Base URL 不能包含账号信息，且必须包含有效主机名。"
    if allow_local and parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}:
        return True, ""
    if parsed.scheme != "https":
        return False, "远程 API 必须使用 HTTPS；本地 Ollama 仅允许 localhost/127.0.0.1。"
    try:
        address = ipaddress.ip_address(host)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            return False, "Base URL 不允许指向内网、回环或保留 IP。"
    except ValueError:
        pass
    known_hosts = {
        "api.openai.com", "api.deepseek.com", "openrouter.ai",
        "api.anthropic.com", "generativelanguage.googleapis.com",
        "api.siliconflow.cn",
    }
    configured_hosts = {
        item.strip().lower().rstrip(".")
        for item in os.getenv("STRUCTPILOT_ALLOWED_LLM_HOSTS", "").split(",")
        if item.strip()
    }
    if host not in known_hosts | configured_hosts:
        return False, (
            f"主机 {host} 未在允许列表中。自定义服务请通过 "
            "STRUCTPILOT_ALLOWED_LLM_HOSTS 配置逗号分隔的主机名。"
        )
    return True, ""
