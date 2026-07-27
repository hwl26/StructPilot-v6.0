from __future__ import annotations

import inspect
import io
from pathlib import Path
import tempfile

import pytest
from PIL import Image

from agents.memory_agent import MemoryAgent
from components.parameter_card import render_parameter_section
from graph.state import PipelineState
from utils.file_upload import validate_image_bytes
from utils.network_security import validate_service_base_url
from utils import server_session


def test_memory_sessions_are_owner_isolated():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryAgent(tmpdir)
        state = PipelineState(session_id="private", owner_id="guest:a")
        memory.save_state(state)
        assert memory.load_state("private", "guest:a") is not None
        assert memory.load_state("private", "guest:b") is None
        assert memory.list_sessions("guest:b") == []
        assert memory.rename_session("private", "stolen", "guest:b") is False
        assert memory.delete_session("private", "guest:b") is False
        with pytest.raises(PermissionError):
            memory.save_state(PipelineState(session_id="private", owner_id="guest:b"))


def test_guest_ai_quota_is_atomic_and_enforced(monkeypatch):
    monkeypatch.setenv("STRUCTPILOT_GUEST_AI_HOURLY_LIMIT", "1")
    monkeypatch.setenv("STRUCTPILOT_GUEST_AI_DAILY_LIMIT", "10")
    monkeypatch.setenv("STRUCTPILOT_GLOBAL_GUEST_AI_DAILY_LIMIT", "10")
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryAgent(tmpdir)
        assert memory.consume_ai_quota("guest:a", is_guest=True)[0] is True
        allowed, reason = memory.consume_ai_quota("guest:a", is_guest=True)
        assert allowed is False
        assert "每小时限额" in reason


def test_image_validation_checks_actual_content_and_extension():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    result = validate_image_bytes(buffer.getvalue(), ".png")
    assert result["format"] == "PNG"
    with pytest.raises(ValueError):
        validate_image_bytes(b"not an image", ".png")
    with pytest.raises(ValueError):
        validate_image_bytes(buffer.getvalue(), ".jpg")


def test_outbound_api_target_allowlist_and_private_ip_blocking(monkeypatch):
    assert validate_service_base_url("https://api.openai.com/v1")[0] is True
    assert validate_service_base_url("http://127.0.0.1:11434/v1", allow_local=True)[0] is True
    assert validate_service_base_url("http://169.254.169.254/latest/meta-data")[0] is False
    assert validate_service_base_url("https://unapproved.example/v1")[0] is False
    monkeypatch.setenv("STRUCTPILOT_ALLOWED_LLM_HOSTS", "llm.example.org")
    assert validate_service_base_url("https://llm.example.org/v1")[0] is True


def test_server_session_rejects_non_uuid_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(server_session, "SESSION_DIR", tmp_path)
    assert server_session.save_server_session("../outside", {"role": "admin"}) is False
    assert server_session.load_server_session("../outside") is None
    assert server_session.delete_server_session("../outside") is False
    assert list(tmp_path.iterdir()) == []


def test_parameter_editor_keeps_workflow_split_layout_contract():
    parameters = inspect.signature(render_parameter_section).parameters
    assert "workflow" in parameters
    assert "split_layout" in parameters


def test_desk_pet_options_are_global_and_right_click_uses_them():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "PET_OPTIONS = {" in source
    assert 'if _new_pet in PET_OPTIONS:' in source
    assert '"robot": "🤖 科研助手"' in source


def test_no_dynamic_eval_or_secret_widget_prefill_in_main():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "eval(atob" not in source
    assert '"API Key", value="", type="password"' in source
    assert '"Bot Token", value="", type="password"' in source


def test_llm_status_never_exposes_key_fragments():
    from agents.llm_agent import LLMAgent
    llm = LLMAgent()
    llm.enabled = True
    llm.api_key = "unit-test-secret-tail"
    status = llm.status_text()
    assert "sk-" not in status
    assert "tail" not in status
    assert llm.masked_api_key() == "已配置"
