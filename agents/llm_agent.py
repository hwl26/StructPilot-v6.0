"""LLM Agent adapter.

Optional LLM layer. Supports OpenAI-compatible APIs plus native Anthropic
Claude and Google Gemini adapters. StructPilot still works in rule-based mode
when no API key is configured.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from response_profiles import (
    normalize_response_profile,
    response_focus_instruction,
    response_profile_instruction,
)


_MAX_IMAGE_EDGE = int(os.getenv("STRUCTPILOT_MAX_IMAGE_EDGE", "768"))


def _encode_raw(path: str) -> str:
    """原样读取并 base64 编码（PIL 不可用或压缩失败时的降级路径）。"""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _image_to_data_url(path: str) -> str:
    """把本地图片读成 data URL；路径无效或读取失败返回空串（由调用方过滤）。

    大截图直接 base64 会让 token 暴涨甚至超模型上限，故先用 PIL 把长边缩到
    _MAX_IMAGE_EDGE 再编码为 JPEG。PIL 不可用或任何异常都降级为原图字节。
    """
    if not path or not os.path.exists(path):
        return ""
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            longest = max(im.size)
            if longest > _MAX_IMAGE_EDGE:
                scale = _MAX_IMAGE_EDGE / longest
                new_size = (max(1, int(im.width * scale)), max(1, int(im.height * scale)))
                im = im.resize(new_size, Image.LANCZOS)
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=85)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        try:
            return _encode_raw(path)
        except Exception:
            return ""


def _split_data_url(data_url: str) -> tuple[str, str]:
    """Return (mime_type, base64_data) from a data URL."""
    if not data_url.startswith("data:") or ";base64," not in data_url:
        return "image/png", ""
    header, payload = data_url.split(";base64,", 1)
    mime = header.removeprefix("data:") or "image/png"
    return mime, payload


def _obfuscate(key: str) -> str:
    """简单混淆 API Key，避免明文存储。非强加密，仅防偶然窥视。"""
    if not key:
        return ""
    return "obf:" + base64.b64encode(key.encode("utf-8")).decode("ascii")


def _deobfuscate(stored: str) -> str:
    """解混淆 API Key。"""
    if not stored or not stored.startswith("obf:"):
        return stored  # 向后兼容：旧明文配置直接返回
    try:
        return base64.b64decode(stored[4:]).decode("utf-8")
    except Exception:
        return ""


class LLMTransientError(Exception):
    """临时性错误（网络超时、连接失败、429/500/502/503），可安全重试。"""


class LLMAgent:
    DIAGNOSTIC_VERSION = 2

    AUDIO_MODEL_ALIASES = {
        "FunAudioLLM/SenseVoiceSmal": "FunAudioLLM/SenseVoiceSmall",
        "funaudiollm/sensevoicesmal": "FunAudioLLM/SenseVoiceSmall",
        "SenseVoiceSmal": "FunAudioLLM/SenseVoiceSmall",
        "sensevoicesmal": "FunAudioLLM/SenseVoiceSmall",
        "FunAudioLLM/SenseVoiceSmall": "FunAudioLLM/SenseVoiceSmall",
        "funaudiollm/sensevoicesmall": "FunAudioLLM/SenseVoiceSmall",
        "SenseVoiceSmall": "FunAudioLLM/SenseVoiceSmall",
        "sensevoicesmall": "FunAudioLLM/SenseVoiceSmall",
    }

    @classmethod
    def normalize_audio_model(cls, model: str) -> str:
        """Normalize common audio model typos before saving or calling the API."""
        value = (model or "").strip()
        return cls.AUDIO_MODEL_ALIASES.get(value, cls.AUDIO_MODEL_ALIASES.get(value.lower(), value))

    @staticmethod
    def _dir_is_writable(path: str) -> bool:
        """Probe whether a directory can be created and written into."""
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(probe)
            return True
        except Exception:
            return False

    @staticmethod
    def _file_is_writable(path: str) -> bool:
        """Probe whether the parent directory of ``path`` is writable."""
        return LLMAgent._dir_is_writable(os.path.dirname(path) or ".")

    def _resolve_config_path(self, base: str, explicit_path: Optional[str]) -> str:
        """Return the best config path from a prioritized candidate list.

        Two-pass strategy:
          Pass 1 — Prefer an existing, readable config file regardless of writability.
                  This ensures pre-existing configs (e.g. in sandbox-restricted dirs) are loaded.
          Pass 2 — Fall back to the first writable directory (for fresh installs / saves).
        """
        legacy_config_path = os.path.join(base, "config", "llm_config.json")

        # Build candidate list (same priority as before)
        candidates = []
        if explicit_path:
            candidates.append(explicit_path)

        env_path = os.getenv("STRUCTPILOT_LLM_CONFIG_PATH")
        if env_path:
            candidates.append(env_path)

        runtime_dir = os.getenv(
            "STRUCTPILOT_RUNTIME_DIR",
            os.path.join(base, "runtime"),
        )
        candidates.append(os.path.join(runtime_dir, "config", "llm_config.json"))

        candidates.append(legacy_config_path)

        try:
            workspace_root = os.path.dirname(os.path.dirname(base))
            candidates.append(
                os.path.join(workspace_root, "trae_more", "runtime", "config", "llm_config.json")
            )
        except Exception:
            pass

        candidates.append(os.path.join(tempfile.gettempdir(), "structpilot_llm_config.json"))

        read_only_candidate = None

        # --- Pass 1: Return first EXISTING, READABLE and WRITABLE config ---
        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)  # noqa: F841 — validate it's valid JSON
                    if self._file_is_writable(path):
                        return path
                    read_only_candidate = path
                except Exception:
                    continue

        # --- Pass 2: First WRITABLE dir (for fresh install / save-as) ---
        for path in candidates:
            if path and self._file_is_writable(path):
                return path

        # --- Pass 3: Fallback to read-only candidate (for read-only environments) ---
        if read_only_candidate:
            return read_only_candidate

        return legacy_config_path

    def __init__(self, config_path: Optional[str] = None) -> None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.legacy_config_path = os.path.join(base, "config", "llm_config.json")
        self.config_path = self._resolve_config_path(base, config_path)
        self.provider = "none"
        self.api_key = ""
        self.model = "gpt-4o-mini"
        self.base_url = "https://api.openai.com/v1"
        self.timeout = 60.0
        self.enabled = False
        # Embedding 与 rewrite 解耦：可单独配置，缺省复用主 api_key/base_url。
        self.embedding_model = ""
        self.embedding_base_url = ""
        self.embedding_api_key = ""
        self.embedding_enabled = False
        self.audio_model = ""
        self.audio_base_url = ""
        self.audio_api_key = ""
        self.audio_enabled = False
        # SSL 证书校验：默认开启，仅在自签名代理环境下通过环境变量关闭。
        self.verify_ssl = os.environ.get("STRUCTPILOT_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
        self.reload()

    def reload(self) -> None:
        file_config = self.load_config()
        self.provider = os.getenv("STRUCTPILOT_LLM_PROVIDER", file_config.get("provider", "none")).lower()
        self.api_key = os.getenv("STRUCTPILOT_LLM_API_KEY", file_config.get("api_key", ""))
        self.model = os.getenv("STRUCTPILOT_LLM_MODEL", file_config.get("model", "gpt-4o-mini"))
        self.base_url = os.getenv("STRUCTPILOT_LLM_BASE_URL", file_config.get("base_url", "https://api.openai.com/v1"))
        self.timeout = float(os.getenv("STRUCTPILOT_LLM_TIMEOUT", file_config.get("timeout", 60)))
        self.enabled = self.provider in {"openai", "openai_compatible", "compatible", "anthropic", "claude", "gemini", "google_gemini"} and bool(self.api_key)
        # Embedding 配置：缺省复用主 api_key/base_url，便于硅基流动同账号直接用。
        self.embedding_model = os.getenv("STRUCTPILOT_EMBEDDING_MODEL", file_config.get("embedding_model", ""))
        self.embedding_base_url = os.getenv("STRUCTPILOT_EMBEDDING_BASE_URL", file_config.get("embedding_base_url", "")) or self.base_url
        self.embedding_api_key = os.getenv("STRUCTPILOT_EMBEDDING_API_KEY", file_config.get("embedding_api_key", "")) or self.api_key
        self.embedding_enabled = bool(self.embedding_model) and bool(self.embedding_api_key)
        self.audio_model = self.normalize_audio_model(os.getenv("STRUCTPILOT_AUDIO_MODEL", file_config.get("audio_model", "")))
        self.audio_base_url = os.getenv("STRUCTPILOT_AUDIO_BASE_URL", file_config.get("audio_base_url", "")) or self.base_url
        self.audio_api_key = os.getenv("STRUCTPILOT_AUDIO_API_KEY", file_config.get("audio_api_key", "")) or self.api_key
        self.audio_enabled = bool(self.audio_model) and bool(self.audio_api_key)

    def load_config(self) -> Dict[str, Any]:
        for path in (self.config_path, self.legacy_config_path):
            if not path or not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # 还原混淆存储的 API Key（向后兼容旧明文配置）
                    data["api_key"] = _deobfuscate(data.get("api_key") or "")
                    data["embedding_api_key"] = _deobfuscate(data.get("embedding_api_key") or "")
                    data["audio_api_key"] = _deobfuscate(data.get("audio_api_key") or "")
                    return data
            except Exception:
                continue
        return {}

    def save_config(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 30,
        embedding_model: Optional[str] = None,
        embedding_base_url: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
    ) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        # 保留已存在的 embedding 配置，未显式传入则沿用旧值，避免保存主 LLM 时清空 embedding。
        existing = self.load_config()
        data = {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
            "timeout": timeout,
            "embedding_model": existing.get("embedding_model", "") if embedding_model is None else embedding_model,
            "embedding_base_url": existing.get("embedding_base_url", "") if embedding_base_url is None else embedding_base_url,
            "embedding_api_key": existing.get("embedding_api_key", "") if embedding_api_key is None else embedding_api_key,
            "audio_model": existing.get("audio_model", ""),
            "audio_base_url": existing.get("audio_base_url", ""),
            "audio_api_key": existing.get("audio_api_key", ""),
        }
        # 写入前混淆 API Key，避免明文存储
        data["api_key"] = _obfuscate(data.get("api_key") or "")
        data["embedding_api_key"] = _obfuscate(data.get("embedding_api_key") or "")
        data["audio_api_key"] = _obfuscate(data.get("audio_api_key") or "")
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.reload()

    def save_audio_config(
        self,
        audio_model: str,
        audio_base_url: str = "",
        audio_api_key: str = "",
    ) -> None:
        """单独保存语音转写配置，保留主 LLM 与 embedding 配置不变。"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = self.load_config()
        data["audio_model"] = self.normalize_audio_model(audio_model)
        data["audio_base_url"] = audio_base_url
        data["audio_api_key"] = audio_api_key
        # 写入前混淆 API Key，避免明文存储
        data["api_key"] = _obfuscate(data.get("api_key") or "")
        data["embedding_api_key"] = _obfuscate(data.get("embedding_api_key") or "")
        data["audio_api_key"] = _obfuscate(data.get("audio_api_key") or "")
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.reload()

    def save_embedding_config(
        self,
        embedding_model: str,
        embedding_base_url: str = "",
        embedding_api_key: str = "",
    ) -> None:
        """单独保存 embedding 配置，保留主 LLM 配置不变。"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = self.load_config()
        data["embedding_model"] = embedding_model
        data["embedding_base_url"] = embedding_base_url
        data["embedding_api_key"] = embedding_api_key
        # 写入前混淆 API Key，避免明文存储
        data["api_key"] = _obfuscate(data.get("api_key") or "")
        data["embedding_api_key"] = _obfuscate(data.get("embedding_api_key") or "")
        data["audio_api_key"] = _obfuscate(data.get("audio_api_key") or "")
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.reload()

    def masked_api_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "..." + self.api_key[-4:]

    def rewrite(self, user_text: str, rule_reply: str, context: str = "",
                image_paths: Optional[List[str]] = None, references: str = "",
                response_profile: str = "teaching") -> str:
        result = self.rewrite_with_metadata(
            user_text, rule_reply, context, image_paths, references, response_profile
        )
        return result["text"]

    def rewrite_with_metadata(self, user_text: str, rule_reply: str, context: str = "",
                              image_paths: Optional[List[str]] = None, references: str = "",
                              response_profile: str = "teaching") -> Dict[str, Any]:
        response_profile = normalize_response_profile(response_profile)
        meta = {
            "enabled": bool(self.enabled),
            "provider": self.provider,
            "model": self.model,
            "vision_requested": bool(image_paths),
            "fallback": False,
            "fallback_reason": "",
            "response_profile": response_profile,
        }
        if not self.enabled:
            meta["fallback"] = True
            meta["fallback_reason"] = "llm_disabled"
            return {"text": rule_reply, **meta}
        try:
            if self.provider in {"anthropic", "claude"}:
                text = self._anthropic_rewrite(user_text, rule_reply, context, image_paths, references, response_profile)
                return {"text": text, **meta}
            if self.provider in {"gemini", "google_gemini"}:
                text = self._gemini_rewrite(user_text, rule_reply, context, image_paths, references, response_profile)
                return {"text": text, **meta}
            text = self._openai_compatible_rewrite(user_text, rule_reply, context, image_paths, references, response_profile)
            return {"text": text, **meta}
        except Exception as exc:
            meta["fallback"] = True
            meta["fallback_reason"] = f"llm_error:{exc.__class__.__name__}"
            return {"text": rule_reply, **meta}

    def test_connection(self) -> str:
        if not self.enabled:
            return "LLM 未启用：请先填写服务商和 API Key。"
        import requests as _req
        try:
            base = self.base_url.rstrip("/")
            models_url = f"{base}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            fast_resp = _req.get(models_url, headers=headers, timeout=(10, self.timeout), verify=self.verify_ssl)
            fast_resp.raise_for_status()
            model_list = fast_resp.json().get("data", [])
            model_names = [m.get("id", "") for m in model_list[:5]]
            probe = self._dispatch_rewrite("ping", "请回复：连接成功", context="connection_test")
            return f"连接测试成功：{probe[:120]}\n可用模型示例：{', '.join(model_names)}"
        except Exception as exc:
            return self._format_connection_error("LLM", exc, self.base_url)

    def test_embedding_connection(self) -> str:
        if not self.embedding_enabled:
            return "向量检索未启用：请先填写 Embedding 模型和 API Key。"
        try:
            probe_result = self.embed_texts(["connection test"])
            if probe_result and len(probe_result) > 0 and len(probe_result[0]) > 0:
                return f"向量检索连接成功：返回向量维度 {len(probe_result[0])}"
            return "连接测试失败：返回结果为空"
        except Exception as exc:
            return self._format_connection_error("向量检索", exc, self.embedding_base_url)

    def test_audio_connection(self) -> str:
        if not self.audio_enabled:
            return "语音转写未启用：请先填写 Audio Model 和 API Key。"
        try:
            import tempfile, wave, struct
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                for _ in range(1600):
                    wf.writeframes(struct.pack("<h", 0))
            try:
                text = self.transcribe_audio(tmp_path, language="zh")
                return f"语音转写连接成功（静音测试音频已识别，返回 {len(text)} 字符）"
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as exc:
            return self._format_connection_error("语音转写", exc, self.audio_base_url)

    def _format_connection_error(self, label: str, exc: Exception, base_url: str = "") -> str:
        """Turn low-level requests errors into actionable settings-page diagnostics."""
        host = urlparse(base_url or "").netloc or base_url or "目标服务"
        raw = str(exc)
        detail = raw[:700]

        if isinstance(exc, requests.exceptions.HTTPError):
            response = exc.response
            status = response.status_code if response is not None else None
            body = ""
            if response is not None:
                body = (response.text or "").strip().replace("\n", " ")[:300]
            if status in {401, 403}:
                reason = "API Key 无效、额度/权限不足，或当前 Key 没有访问该模型的权限。"
            elif status == 400 and ("Model does not exist" in body or "model does not exist" in body.lower()):
                reason = "模型名不存在或当前账号不可用。请检查模型名拼写，例如 SenseVoiceSmall 不要写成 SenseVoiceSmal。"
            elif status == 404:
                reason = "接口路径或模型名可能不被该服务商支持。请核对 Base URL、Model 和服务商文档。"
            elif status == 429:
                reason = "服务商限流或额度不足，请稍后重试，或检查账号额度。"
            elif status and 500 <= status < 600:
                reason = "服务商端暂时异常，请稍后重试或切换服务商。"
            else:
                reason = "服务端拒绝了请求，请核对 Base URL、Model、API Key 和账号权限。"
            suffix = f" 服务端返回：{body}" if body else ""
            return f"{label}连接失败：HTTP {status}。{reason}{suffix}"

        if isinstance(exc, requests.exceptions.Timeout):
            return f"{label}连接失败：连接 {host} 超时。请检查网络、代理/VPN、防火墙，或把 Timeout 秒调大后重试。原始错误：{detail}"

        if isinstance(exc, requests.exceptions.ConnectionError):
            if "WinError 10013" in raw:
                reason = "Windows 网络权限拒绝了本程序的出站连接，常见原因是防火墙、杀毒软件、代理策略或校园/单位网络策略拦截。"
            elif "NameResolutionError" in raw or "getaddrinfo failed" in raw:
                reason = "域名解析失败，请检查 DNS、网络连接或代理配置。"
            elif "Connection refused" in raw:
                reason = "目标服务拒绝连接。若使用本地模型，请确认本地服务已启动且端口正确。"
            else:
                reason = "无法建立到目标服务的网络连接。"
            return f"{label}连接失败：{reason}目标：{host}。原始错误：{detail}"

        if isinstance(exc, requests.exceptions.RequestException):
            return f"{label}连接失败：请求未完成。请检查 Base URL、网络、代理和证书配置。原始错误：{detail}"

        return f"{label}连接失败：{detail}"

    def _dispatch_rewrite(self, user_text: str, rule_reply: str, context: str = "") -> str:
        if self.provider in {"anthropic", "claude"}:
            return self._anthropic_rewrite(user_text, rule_reply, context)
        if self.provider in {"gemini", "google_gemini"}:
            return self._gemini_rewrite(user_text, rule_reply, context)
        return self._openai_compatible_rewrite(user_text, rule_reply, context)

    def _system_prompt(self, response_profile: str = "teaching") -> str:
        return (
            "你是 StructPilot，一位冷冻电镜 cryo-EM 数据处理陪跑教练。"
            "你的回答要专业、简洁、温和，适合新手理解。\n"
            "请严格遵守以下信息层级：\n"
            "1) 【规则层结论】是权威事实——步骤、参数、质控结论必须保留其核心信息，但你可以调整措辞让它更自然、更有陪跑感。\n"
            "2) 【检索参考】是背景资料，可用于补充解释或举例，但它不是权威事实；"
            "若与规则层结论冲突，以规则层为准，不要用检索参考覆盖结论。\n"
            "3) 若检索参考与本次问题无关，直接忽略它，不要强行引用。\n"
            "4) 最重要的原则：**直接回答用户的问题**！不要重复规则层的完整内容，而是提取与用户问题相关的要点进行回答。\n"
            "5) 如果规则层内容比较笼统，而检索参考中有针对用户具体问题的答案，优先使用检索参考中的具体答案。\n"
            "6) 回答要自然流畅，像和用户对话一样，不要使用生硬的模板格式。\n"
            "7) 若用户附带 cryoSPARC / RELION 截图，请结合截图和文字描述判断；"
            "只描述图中能看见的现象，不要编造不可见的数值或结果。\n"
            "8) 若规则层结论为空或过于笼统、且检索参考中也无针对该问题的可用依据，"
            "请明确说明「当前知识库暂无确切依据，建议参考官方文档或咨询有经验的操作者」，"
            "**不要编造具体参数值、步骤或结论**。宁可少答，不可乱答。\n"
            f"9) {response_profile_instruction(response_profile)}"
        )

    def _rewrite_prompt(self, user_text: str, rule_reply: str, context: str = "",
                        references: str = "", response_profile: str = "teaching") -> str:
        blocks = [
            f"【规则层结论（权威，不可改）】\n{rule_reply}",
        ]
        if references and references.strip():
            blocks.append(f"【检索参考（可引用，不可当事实）】\n{references.strip()}")
        blocks.append(f"【当前上下文】\n{context}")
        blocks.append(f"【用户输入】\n{user_text}")
        blocks.append(f"【回答焦点要求】\n{response_focus_instruction(user_text, context=context)}")
        # SmartQA 增强：当上下文中存在「智能问答理解」块时，指示 LLM 优先据此直接回答。
        # 该指令仅在 SmartQA 启用（AI 模式）时出现，不影响无 LLM 的规则路径。
        if "【智能问答理解】" in f"{context}\n{references}":
            blocks.append(
                "【重要】上下文中包含【智能问答理解】块，这是系统对用户问题的结构化理解"
                "（意图 / 阶段 / 软件 / 具体诉求）。请优先据此直接回应用户的实际问题，"
                "并在不改变权威规则层事实（步骤、参数、质控结论）的前提下，补充针对性的"
                "步骤、参数建议或排查方向；不要只复述模板。"
            )
        blocks.append("若本轮包含截图，请优先把截图当作当前处理状态的证据，并指出需要用户补充的关键参数或视图。")
        blocks.append(f"【回答深度要求】\n{response_profile_instruction(response_profile)}")
        blocks.append("请在不编造事实、不改变规则层结论的前提下，改写成自然、清晰、有陪跑感的回复。")
        return "\n\n".join(blocks)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(LLMTransientError),
        reraise=True,
    )
    def _request_with_retry(
        self,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
        stream: bool = False,
    ):
        """执行 requests.post，遇到临时性错误自动指数退避重试。

        重试仅覆盖连接建立阶段；流式响应（stream=True）拿到 response 对象后即返回，
        后续 iter_lines 由调用方处理，不会触发重复输出。全部重试失败后抛出
        LLMTransientError，由上层 try/except 降级为 rule_reply。
        """
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=json_data,
                data=data,
                files=files,
                timeout=timeout,
                stream=stream,
                verify=self.verify_ssl,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            raise LLMTransientError(f"Network error: {exc.__class__.__name__}") from exc
        if resp.status_code in (429, 500, 502, 503):
            raise LLMTransientError(f"HTTP {resp.status_code}")
        return resp

    def _openai_compatible_rewrite(self, user_text: str, rule_reply: str, context: str = "",
                                   image_paths: Optional[List[str]] = None, references: str = "",
                                   response_profile: str = "teaching") -> str:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        prompt_text = self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)
        # 有图片时用多模态 content 数组（text + image_url data url）；否则保持纯字符串。
        image_urls = [u for u in (_image_to_data_url(p) for p in (image_paths or [])) if u]
        if image_urls:
            user_content: Any = [{"type": "text", "text": prompt_text}]
            for url in image_urls:
                user_content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            user_content = prompt_text
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(response_profile)},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.35,
        }
        response = self._request_with_retry(
            endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json_data=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip() or rule_reply

    def _openai_compatible_rewrite_stream(self, user_text: str, rule_reply: str, context: str = "",
                                          image_paths: Optional[List[str]] = None, references: str = "",
                                          temperature: float = 0.35,
                                          response_profile: str = "teaching"):
        """OpenAI-compatible 流式改写：逐块 yield 文本片段（stream=True）。"""
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        prompt_text = self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)
        image_urls = [u for u in (_image_to_data_url(p) for p in (image_paths or [])) if u]
        if image_urls:
            user_content: Any = [{"type": "text", "text": prompt_text}]
            for url in image_urls:
                user_content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            user_content = prompt_text
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(response_profile)},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "stream": True,
        }
        response = self._request_with_retry(
            endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json_data=payload,
            timeout=self.timeout,
            stream=True,
        )
        response.raise_for_status()
        for raw in response.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                yield delta

    def rewrite_with_metadata_stream(self, user_text: str, rule_reply: str, context: str = "",
                                     image_paths: Optional[List[str]] = None, references: str = "",
                                     response_profile: str = "teaching"):
        """流式改写入口。仅 OpenAI-compatible 真正流式；其它 provider 退化为一次性 yield 完整文本。
        任意异常都退化为阻塞式 rewrite_with_metadata，保证不丢答案。"""
        provider = (self.provider or "").lower()
        if provider in {"openai", "openai_compatible", "compatible"}:
            try:
                for chunk in self._openai_compatible_rewrite_stream(
                    user_text, rule_reply, context=context, image_paths=image_paths,
                    references=references, response_profile=response_profile
                ):
                    yield chunk
                return
            except Exception:
                pass
        result = self.rewrite_with_metadata(
            user_text, rule_reply, context=context, image_paths=image_paths,
            references=references, response_profile=response_profile
        )
        text = result.get("text", rule_reply) if isinstance(result, dict) else result
        yield text or rule_reply

    def _anthropic_rewrite(self, user_text: str, rule_reply: str, context: str = "",
                           image_paths: Optional[List[str]] = None, references: str = "",
                           response_profile: str = "teaching") -> str:
        # TODO(P2): anthropic 多模态待实现，当前忽略 image_paths 走纯文本。
        endpoint = (self.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        payload = {
            "model": self.model or "claude-3-5-sonnet-latest",
            "max_tokens": 1200,
            "temperature": 0.35,
            "system": self._system_prompt(response_profile),
            "messages": [{"role": "user", "content": self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)}],
        }
        response = self._request_with_retry(
            endpoint,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json_data=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        parts = data.get("content", [])
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        return text.strip() or rule_reply

    def _gemini_rewrite(self, user_text: str, rule_reply: str, context: str = "",
                        image_paths: Optional[List[str]] = None, references: str = "",
                        response_profile: str = "teaching") -> str:
        # TODO(P2): gemini 多模态待实现，当前忽略 image_paths 走纯文本。
        base_url = (self.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        model = self.model or "gemini-1.5-pro"
        endpoint = f"{base_url}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": self._system_prompt(response_profile)}]},
            "contents": [
                {"role": "user", "parts": [{"text": self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)}]}
            ],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 1200},
        }
        response = self._request_with_retry(endpoint, headers={"Content-Type": "application/json"}, json_data=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return rule_reply
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        return text.strip() or rule_reply

    def _anthropic_rewrite(self, user_text: str, rule_reply: str, context: str = "",
                           image_paths: Optional[List[str]] = None, references: str = "",
                           response_profile: str = "teaching") -> str:
        endpoint = (self.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        user_content: Any = [{"type": "text", "text": self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)}]
        for data_url in (_image_to_data_url(p) for p in (image_paths or [])):
            mime, payload = _split_data_url(data_url)
            if payload:
                user_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": payload},
                })
        payload = {
            "model": self.model or "claude-3-5-sonnet-latest",
            "max_tokens": 1200,
            "temperature": 0.35,
            "system": self._system_prompt(response_profile),
            "messages": [{"role": "user", "content": user_content}],
        }
        response = self._request_with_retry(
            endpoint,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json_data=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        parts = data.get("content", [])
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        return text.strip() or rule_reply

    def _gemini_rewrite(self, user_text: str, rule_reply: str, context: str = "",
                        image_paths: Optional[List[str]] = None, references: str = "",
                        response_profile: str = "teaching") -> str:
        base_url = (self.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        model = self.model or "gemini-1.5-pro"
        endpoint = f"{base_url}/models/{model}:generateContent?key={self.api_key}"
        parts: List[Dict[str, Any]] = [{"text": self._rewrite_prompt(user_text, rule_reply, context, references, response_profile)}]
        for data_url in (_image_to_data_url(p) for p in (image_paths or [])):
            mime, payload = _split_data_url(data_url)
            if payload:
                parts.append({"inline_data": {"mime_type": mime, "data": payload}})
        payload = {
            "systemInstruction": {"parts": [{"text": self._system_prompt(response_profile)}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 1200},
        }
        response = self._request_with_retry(endpoint, headers={"Content-Type": "application/json"}, json_data=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return rule_reply
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        return text.strip() or rule_reply

    # ---------------------------------------------------------------------------
    # 概念问答：统一的单轮补全（openai / anthropic / gemini 三端共用）
    # ---------------------------------------------------------------------------

    def concept_answer(
        self,
        user_text: str,
        glossary_entry: Optional[Dict[str, Any]] = None,
        software: str = "",
        extra_context: str = "",
        response_profile: str = "teaching",
    ) -> str:
        """AI 模式概念解释：让 LLM 基于专业 cryo-EM 知识直接回答（1 次 LLM 调用）。

        若 glossary 命中，作为权威事实注入；否则 LLM 凭自有知识作答。
        若提供 extra_context（RAG 检索结果），作为补充参考资料注入。
        无 API Key 或未启用时返回空串，由 SmartQAEngine 降级为规则术语卡。

        Args:
            extra_context: RAG 检索到的知识库/官方文档片段，用于增强回答的准确性。
        """
        if not self.enabled:
            return ""
        try:
            system = self._concept_system_prompt(response_profile)
            user_block = self._concept_user_prompt(
                user_text, glossary_entry, software, extra_context, response_profile
            )
            return self._chat_complete(system, user_block).strip()
        except Exception as exc:
            # 不再静默吞掉异常——调用方需要知道失败原因
            raise

    def _concept_system_prompt(self, response_profile: str = "teaching") -> str:
        return (
            "你是 StructPilot，一位冷冻电镜 cryo-EM 数据处理陪跑教练，尤其擅长单颗粒分析"
            "（cryoSPARC / RELION 双体系）。\n"
            "请用简洁、专业、适合新手的中文解释用户提到的 cryo-EM 概念、文件格式或缩写。\n"
            "要求：\n"
            "1) 先一句话给出核心定义；\n"
            "2) 说明它在 14 步工作流（Import → Motion Correction → CTF → Picking → "
            "Extraction → 2D → Ab-Initio → 3D Classification → Refinement → Sharpening → "
            "Masking → Resolution → Validation → Export）中的位置与作用；\n"
            "3) 说明在 cryoSPARC 与 RELION 中如何处理/对应（如适用）；\n"
            "4) 不要编造不确定的参数数值；若有不确定，明确说明「建议查阅官方文档」。\n"
            "若下方提供了【术语库权威条目】，请以其为准并补充解释，不要与之冲突。\n\n"
            "**严格的输出格式要求（必须遵守）**：\n"
            "- 直接输出纯 Markdown 文本，从第一个字开始就是 ## 标题或正文\n"
            "- 绝对不要输出 JSON 对象（不要 {\"cards\": ...} 或 {\"type\": ...}）\n"
            "- 绝对不要使用代码块标记（不要 ```json 或 ```）\n"
            "- 不要使用 ### placeholder_id ###、### content ###、### 原因 ### 等占位符\n"
            "- 使用标准 Markdown 二级标题（## 标题）组织内容\n"
            "- 段落之间用空行分隔，保持清晰易读\n\n"
            "**输出示例**：\n"
            "## MRC 文件是什么\n\n"
            "MRC 是 cryo-EM 领域最通用的图像文件格式...\n\n"
            "## 在工作流中的位置\n\n"
            "MRC 格式贯穿整个流程...\n\n"
            + response_profile_instruction(response_profile)
        )

    def _concept_user_prompt(
        self,
        user_text: str,
        glossary_entry: Optional[Dict[str, Any]],
        software: str,
        extra_context: str = "",
        response_profile: str = "teaching",
    ) -> str:
        parts = [f"用户问题：{user_text}"]
        if software in ("cryosparc", "relion"):
            parts.append(f"当前软件体系：{software}")
        if glossary_entry:
            # 不要传递 JSON，改为传递易读的文本格式
            term = glossary_entry.get("term", "")
            definition = glossary_entry.get("definition_cn", "")
            aliases = glossary_entry.get("aliases", [])
            aliases_text = f"（别名：{', '.join(aliases)}）" if aliases else ""
            parts.append(f"【术语库权威条目（若有，请以其为准）】\n术语：{term} {aliases_text}\n定义：{definition}")
        if extra_context and extra_context.strip():
            parts.append(f"【知识库参考资料（官方文档 / 术语 / SOP，可引用增强回答）】\n{extra_context.strip()[:1500]}")
        parts.append("请直接给出纯 Markdown 格式的解释，不要输出 JSON，不要使用占位符，从第一个字开始就是 ## 标题或正文。")
        return "\n\n".join(parts)

    def _chat_complete(self, system_prompt: str, user_prompt: str) -> str:
        """统一的单轮对话补全（供概念问答等专用场景），覆盖 openai/anthropic/gemini。

        与改写管线（_rewrite_prompt）解耦：概念问答不需要规则层结论作为前提，
        故单独实现一份精简的「system + user」调用，避免改动既有改写逻辑。
        """
        if self.provider in {"anthropic", "claude"}:
            endpoint = (self.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
            payload = {
                "model": self.model or "claude-3-5-sonnet-latest",
                "max_tokens": 1000,
                "temperature": 0.3,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        elif self.provider in {"gemini", "google_gemini"}:
            base_url = (self.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
            model = self.model or "gemini-1.5-pro"
            endpoint = f"{base_url}/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000},
            }
            headers = {"Content-Type": "application/json"}
        else:
            endpoint = self.base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        response = self._request_with_retry(endpoint, headers=headers, json_data=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if self.provider in {"anthropic", "claude"}:
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        if self.provider in {"gemini", "google_gemini"}:
            cands = data.get("candidates", [])
            if not cands:
                return ""
            parts = cands[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        return data["choices"][0]["message"]["content"].strip()

    def casual_reply(self, user_text: str, response_profile: str = "teaching") -> str:
        """双轨 Track L：闲聊/通用问题的 LLM 直答（1 次 LLM 调用）。

        用于非 cryo-EM 专业问题（问候、通用问答）。未启用时返回空串，
        由调用方（app._casual_node）降级为 navigator.casual_rule_reply（规则友好回复）。
        """
        if not self.enabled:
            return ""
        system = (
            "你是 StructPilot，一位冷冻电镜 cryo-EM 单颗粒分析陪跑教练。"
            "用户现在说的不是具体的 cryo-EM 操作问题，而是闲聊或通用问题。"
            "请用自然、友好、简洁的中文回应；若是与 cryo-EM 无关的问题，可以简短回答，"
            "并自然地把话题引回 cryo-EM 数据处理流程的陪跑支持。不要编造 cryo-EM 专业结论。"
            + response_profile_instruction(response_profile)
        )
        try:
            return self._chat_complete(system, user_text or "").strip()
        except Exception:
            return ""

    def embed_texts(self, texts):
        """对一批文本求 embedding 向量（OpenAI 兼容 /embeddings，如硅基流动）。

        返回 List[List[float]]，顺序与输入对齐。未配置 embedding 时抛异常，
        由调用方（retriever）try/except 降级为空检索。
        """
        if not self.embedding_enabled:
            raise RuntimeError("embedding 未配置：缺少 embedding_model 或 api_key")
        if not texts:
            return []
        endpoint = self.embedding_base_url.rstrip("/") + "/embeddings"
        payload = {"model": self.embedding_model, "input": list(texts)}
        response = self._request_with_retry(
            endpoint,
            headers={"Authorization": f"Bearer {self.embedding_api_key}", "Content-Type": "application/json"},
            json_data=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items]

    def transcribe_audio(self, audio_path: str, language: str = "zh") -> str:
        """Transcribe an audio file through an OpenAI-compatible /audio/transcriptions API."""
        if not self.audio_enabled:
            raise RuntimeError("语音转写未启用：请先配置 audio_model 和 API Key")
        if not audio_path or not os.path.exists(audio_path):
            raise RuntimeError("音频文件不存在")
        endpoint = self.audio_base_url.rstrip("/") + "/audio/transcriptions"
        mime = mimetypes.guess_type(audio_path)[0] or "application/octet-stream"
        with open(audio_path, "rb") as f:
            file_bytes = f.read()
        files = {"file": (os.path.basename(audio_path), file_bytes, mime)}
        data = {"model": self.audio_model}
        if language:
            data["language"] = language
        response = self._request_with_retry(
            endpoint,
            headers={"Authorization": f"Bearer {self.audio_api_key}"},
            data=data,
            files=files,
            timeout=max(self.timeout, 60.0),
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        return text.strip()

    def extract_knowledge_doc(self, snippet: str) -> Dict[str, Any]:
        """把一段对话/经验抽成 KnowledgeDoc 字段（dict）。

        启用 LLM 时让模型抽取 title_cn/summary/action_steps/qc_checks/
        common_errors/tags；未启用或解析失败则降级为仅含 summary=snippet
        的最简 dict，保证「沉淀」按钮始终可用。
        """
        snippet = (snippet or "").strip()
        fallback = {"summary": snippet}
        if not snippet or not self.enabled:
            return fallback
        instruction = (
            "请把下面的 cryo-EM 操作经验/对话片段抽取成结构化知识，"
            "只输出 JSON（不要代码块、不要解释），字段："
            "title_cn(简短标题), summary(一句话摘要), "
            "action_steps(操作步骤数组), qc_checks(质控要点数组), "
            "common_errors(常见错误数组), tags(标签数组)。"
            "数组无内容则给空数组。\n\n片段：\n" + snippet
        )
        try:
            raw = self._dispatch_rewrite(snippet, instruction, context="extract_knowledge")
            text = raw.strip()
            # 容错：模型可能仍包了 ```json 代码块或多余前后缀，截取首个 { 到末个 }。
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return fallback
            data = json.loads(text[start:end + 1])
            if not isinstance(data, dict):
                return fallback
            return data
        except Exception:
            return fallback

    def status_text(self) -> str:
        if self.enabled:
            return f"LLM 已启用：{self.provider} / {self.model} / {self.masked_api_key()}"
        return "LLM 未启用：当前使用规则 + 知识库模式"

    def audio_status_text(self) -> str:
        if self.audio_enabled:
            return f"语音转写已启用：{self.audio_model}"
        return "语音转写未启用"
