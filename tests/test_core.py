"""Tests for StructPilot v6.0 core functionality."""

from __future__ import annotations

import tempfile
import os
import json
import pytest
from datetime import datetime
from pathlib import Path

# Test imports
from graph.state import PipelineState, CheckpointRecord, Message, CheckpointStatus
from validator.validator import InputValidator, extract_params_from_text, ValidationResult
from agents.navigator_agent import NavigatorAgent
from knowledge_base.retriever import KnowledgeRetriever
from knowledge_base.importer import KnowledgeDoc, load_knowledge_doc, update_knowledge_index, doc_to_text
from knowledge_base.corrections import append_correction, load_corrections, make_correction, normalize_query
from knowledge_base.document_ingest import build_ingest_draft


class TestPipelineState:
    """Tests for PipelineState data class."""

    def test_initial_state(self):
        """Test default state initialization."""
        state = PipelineState(session_id="test_123")
        assert state.session_id == "test_123"
        assert state.current_cp_id == "cp_01"
        assert state.session_started is False
        assert state.completed == []
        assert state.failed == []
        assert state.skipped == []
        assert state.messages == []
        assert state.params == {}

    def test_mark_checkpoint_passed(self):
        """Test marking checkpoint as passed."""
        state = PipelineState(session_id="test_123")
        state.mark_checkpoint("cp_01", "passed", "Test passed", "user input")
        assert "cp_01" in state.completed
        assert "cp_01" not in state.failed
        assert "cp_01" not in state.skipped
        assert state.checkpoint_records["cp_01"].status == "passed"

    def test_mark_checkpoint_failed(self):
        """Test marking checkpoint as failed."""
        state = PipelineState(session_id="test_123")
        state.mark_checkpoint("cp_01", "failed", "Test failed", "user input")
        assert "cp_01" in state.failed
        assert "cp_01" not in state.completed
        assert state.checkpoint_records["cp_01"].status == "failed"

    def test_mark_checkpoint_skipped(self):
        """Test marking checkpoint as skipped."""
        state = PipelineState(session_id="test_123")
        state.mark_checkpoint("cp_01", "skipped", "User skipped", "user input")
        assert "cp_01" in state.skipped
        assert "cp_01" not in state.completed
        assert state.checkpoint_records["cp_01"].status == "skipped"

    def test_add_message(self):
        """Test adding messages to state."""
        state = PipelineState(session_id="test_123")
        state.add_message("user", "Hello", "general")
        assert len(state.messages) == 1
        assert state.messages[0].role == "user"
        assert state.messages[0].content == "Hello"
        assert state.messages[0].action_tag == "general"

    def test_touch_updates_timestamp(self):
        """Test that touch() updates last_updated."""
        state = PipelineState(session_id="test_123")
        old_time = state.last_updated
        state.touch()
        assert state.last_updated != old_time


class TestInputValidator:
    """Tests for InputValidator."""

    def setup_method(self):
        self.validator = InputValidator()

    def test_validate_feedback_empty(self):
        """Test validation of empty input."""
        result = self.validator.validate_feedback("")
        assert result.passed is False
        assert "输入为空" in result.summary

    def test_validate_feedback_failure_keywords(self):
        """Test detection of failure keywords."""
        result = self.validator.validate_feedback("任务失败了")
        assert result.passed is False
        assert "失败" in result.summary

    def test_validate_feedback_pass_keywords(self):
        """Test detection of pass keywords."""
        result = self.validator.validate_feedback("任务完成了")
        assert result.passed is True
        assert "完成" in result.summary or "通过" in result.summary

    def test_validate_feedback_neutral(self):
        """Test neutral input defaults to pass."""
        result = self.validator.validate_feedback("我在看文档")
        assert result.passed is True
        assert "中性" in result.summary or "默认" in result.summary

    def test_validate_checkpoint_id_valid(self):
        """Test valid checkpoint ID."""
        result = self.validator.validate_checkpoint_id("cp_01", ["cp_01", "cp_02"])
        assert result.passed is True

    def test_validate_checkpoint_id_invalid(self):
        """Test invalid checkpoint ID."""
        result = self.validator.validate_checkpoint_id("cp_99", ["cp_01", "cp_02"])
        assert result.passed is False

    def test_validate_params_pixel_size(self):
        """Test pixel_size parameter validation."""
        result = self.validator.validate_params({"pixel_size": "1.5"})
        assert result.passed is True

        result = self.validator.validate_params({"pixel_size": "0"})
        assert result.passed is False

        result = self.validator.validate_params({"pixel_size": "15"})
        assert result.passed is False


class TestExtractParamsFromText:
    """Tests for extract_params_from_text function."""

    def test_extract_pixel_size(self):
        """Test extracting pixel_size from text."""
        params = extract_params_from_text("pixel size = 1.2")
        assert params.get("pixel_size") == 1.2

    def test_extract_voltage(self):
        """Test extracting voltage from text."""
        params = extract_params_from_text("voltage: 300")
        assert params.get("voltage") == 300

    def test_extract_ctf_fit(self):
        """Test extracting CTF fit from text."""
        params = extract_params_from_text("ctf fit = 0.85")
        assert params.get("ctf_fit") == 0.85

    def test_extract_box_size(self):
        """Test extracting box_size from text."""
        params = extract_params_from_text("box size: 256")
        assert params.get("box_size") == 256

    def test_extract_multiple_params(self):
        """Test extracting multiple parameters."""
        params = extract_params_from_text("pixel size = 1.2, box size = 256, voltage = 300")
        assert params.get("pixel_size") == 1.2
        assert params.get("box_size") == 256
        assert params.get("voltage") == 300


class TestNavigatorAgent:
    """Tests for NavigatorAgent."""

    def setup_method(self):
        self.agent = NavigatorAgent()

    def test_get_opening_speech(self):
        """Test opening speech retrieval."""
        speech = self.agent.get_opening_speech()
        assert isinstance(speech, str)
        assert len(speech) > 0

    def test_get_stage_guide_existing(self):
        """Test getting stage guide for existing checkpoint."""
        from graph.state import PipelineState
        state = PipelineState(session_id="test", current_cp_id="cp_01")
        guide = self.agent.get_stage_guide(state, "cp_01")
        assert isinstance(guide, str)
        assert "数据导入" in guide or "cp_01" in guide

    def test_get_stage_guide_nonexistent(self):
        """Test getting stage guide for non-existent checkpoint."""
        from graph.state import PipelineState
        state = PipelineState(session_id="test", current_cp_id="cp_01")
        guide = self.agent.get_stage_guide(state, "cp_99")
        assert "未找到" in guide

    def test_advance_first_checkpoint(self):
        """Test advancing from first checkpoint."""
        from graph.state import PipelineState
        state = PipelineState(session_id="test", current_cp_id="cp_01")
        result = self.agent.advance(state)
        # Should advance to cp_02 (运动校正) or indicate completion
        assert "运动校正" in result or "完成" in result or "所有检查站" in result or "cp_02" in result

    def test_get_progress(self):
        """Test progress reporting."""
        from graph.state import PipelineState
        state = PipelineState(session_id="test")
        state.completed = ["cp_01", "cp_02"]
        progress = self.agent.get_progress(state)
        # Should show completed count and total
        assert "2/" in progress

    def test_generate_report(self):
        """Test report generation."""
        from graph.state import PipelineState
        state = PipelineState(session_id="test", current_cp_id="cp_03")
        state.completed = ["cp_01", "cp_02"]
        state.params = {"pixel_size": 1.2}
        report = self.agent.generate_report(state)
        assert "流程报告" in report
        assert "cp_01" in report
        assert "pixel_size" in report


class TestKnowledgeDoc:
    """Tests for KnowledgeDoc dataclass."""

    def test_knowledge_doc_creation(self):
        """Test creating a KnowledgeDoc."""
        doc = KnowledgeDoc(
            doc_id="test_001",
            software="cryosparc",
            title_cn="测试文档",
            summary="这是一个测试摘要",
            action_steps=["步骤1", "步骤2"],
            qc_checks=["检查1"],
            common_errors=["错误1"],
            tags=["测试", "cryosparc"]
        )
        assert doc.doc_id == "test_001"
        assert doc.software == "cryosparc"
        assert len(doc.action_steps) == 2

    def test_knowledge_doc_to_dict(self):
        """Test KnowledgeDoc serialization."""
        doc = KnowledgeDoc(doc_id="test_001", software="cryosparc")
        data = doc.to_dict()
        assert data["doc_id"] == "test_001"
        assert data["software"] == "cryosparc"
        # None fields should be converted to empty list/string
        assert isinstance(data["action_steps"], list)

    def test_load_knowledge_doc_yaml(self):
        """Test loading KnowledgeDoc from YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            yaml_content = """
doc_id: test_yaml
software: cryosparc
title_cn: YAML测试
summary: YAML格式测试
action_steps:
  - 步骤A
  - 步骤B
tags:
  - yaml
"""
            f.write(yaml_content)
            f.flush()
            doc = load_knowledge_doc(f.name)
            assert doc.doc_id == "test_yaml"
            assert doc.title_cn == "YAML测试"
            assert len(doc.action_steps) == 2
        os.unlink(f.name)

    def test_load_knowledge_doc_json(self):
        """Test loading KnowledgeDoc from JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json_content = {
                "doc_id": "test_json",
                "software": "relion",
                "title_cn": "JSON测试",
                "summary": "JSON格式测试",
                "action_steps": ["步骤1"],
                "tags": ["json"]
            }
            json.dump(json_content, f, ensure_ascii=False)
            f.flush()
            doc = load_knowledge_doc(f.name)
            assert doc.doc_id == "test_json"
            assert doc.title_cn == "JSON测试"
        os.unlink(f.name)


class TestKnowledgeIndex:
    """Tests for knowledge index operations."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "knowledge_index.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_update_knowledge_index_new(self):
        """Test adding first document to index."""
        doc = KnowledgeDoc(doc_id="doc_1", software="cryosparc", title_cn="文档1")
        update_knowledge_index(doc, self.index_path)

        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["doc_id"] == "doc_1"

    def test_update_knowledge_index_update_existing(self):
        """Test updating existing document."""
        doc1 = KnowledgeDoc(doc_id="doc_1", software="cryosparc", title_cn="文档1")
        update_knowledge_index(doc1, self.index_path)

        doc2 = KnowledgeDoc(doc_id="doc_1", software="cryosparc", title_cn="文档1_更新")
        update_knowledge_index(doc2, self.index_path)

        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title_cn"] == "文档1_更新"

    def test_update_knowledge_index_multiple(self):
        """Test adding multiple documents."""
        doc1 = KnowledgeDoc(doc_id="doc_1", software="cryosparc", title_cn="文档1")
        doc2 = KnowledgeDoc(doc_id="doc_2", software="relion", title_cn="文档2")
        update_knowledge_index(doc1, self.index_path)
        update_knowledge_index(doc2, self.index_path)

        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 2


class TestDocToText:
    """Tests for doc_to_text function."""

    def test_doc_to_text_knowledge_doc(self):
        """Test converting KnowledgeDoc to text."""
        doc = KnowledgeDoc(
            doc_id="test_001",
            software="cryosparc",
            title_cn="测试标题",
            summary="测试摘要",
            action_steps=["步骤1", "步骤2"],
            qc_checks=["检查1"],
            common_errors=["错误1"]
        )
        text = doc_to_text(doc)
        assert "测试标题" in text
        assert "测试摘要" in text
        assert "步骤1" in text
        assert "检查1" in text
        assert "错误1" in text

    def test_doc_to_text_dict(self):
        """Test converting dict to text."""
        doc = {
            "title_cn": "字典标题",
            "summary": "字典摘要",
            "action_steps": ["步骤A"],
            "qc_checks": [],
            "common_errors": ["错误A"]
        }
        text = doc_to_text(doc)
        assert "字典标题" in text
        assert "字典摘要" in text
        assert "步骤A" in text
        assert "错误A" in text

    def test_doc_to_text_empty(self):
        """Test converting empty doc."""
        text = doc_to_text({})
        assert text == ""


class TestCorrections:
    """Tests for query normalization and auditable corrections."""

    def test_normalize_query_detects_context_and_typos(self):
        query = normalize_query("RELION moton corection parameter", default_checkpoint="cp_01")

        assert query.software == "relion"
        assert query.checkpoint_id == "cp_02"
        assert query.problem_type == "parameter"
        assert "motion correction" in query.normalized
        assert "moton->motion" in query.corrections
        assert "corection->correction" in query.corrections

    def test_append_and_load_correction_roundtrip(self, tmp_path):
        path = tmp_path / "user_corrections.jsonl"
        correction = make_correction(
            session_id="session_001",
            kind="understanding_fix",
            original_query="moton corection",
            normalized_query="[relion, cp_02] motion correction",
            corrected_query="RELION motion correction 参数设置",
            checkpoint_id="cp_02",
            software="relion",
        )

        append_correction(path, correction)
        rows = load_corrections(path)

        assert len(rows) == 1
        assert rows[0]["correction_id"].startswith("corr_")
        assert rows[0]["corrected_query"] == "RELION motion correction 参数设置"
        assert rows[0]["status"] == "pending_review"


class TestDocumentIngest:
    """Tests for operation document ingestion drafts."""

    def test_build_ingest_draft_from_markdown_and_image(self, tmp_path):
        source = tmp_path / "relion_cp02_motion.md"
        source.write_text(
            "RELION Motion correction SOP\n"
            "1. Open Motion correction job.\n"
            "2. Set dose and pixel size.\n"
            "QC: check corrected micrographs.\n"
            "Error: gain reference mismatch.\n",
            encoding="utf-8",
        )
        image = tmp_path / "motion_io.png"
        image.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
                "0000000c49444154789c63606060000000040001f61738550000000049454e44ae426082"
            )
        )

        draft = build_ingest_draft(source, tmp_path / "assets", extra_image_paths=[image])

        assert draft.doc.software == "relion"
        assert draft.doc.checkpoint_id == "cp_02"
        assert draft.doc.tier == "note"
        assert draft.doc.status == "draft"
        assert "RELION Motion correction SOP" in draft.doc.title_cn
        assert draft.doc.action_steps
        assert draft.doc.qc_checks
        assert draft.doc.common_errors
        assert len(draft.images) == 1
        assert Path(draft.images[0].stored_path).exists()
        assert draft.doc.image_refs == [draft.images[0].stored_path]

    def test_build_ingest_draft_image_only_warns(self, tmp_path):
        image = tmp_path / "screen.png"
        image.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
                "0000000c49444154789c63606060000000040001f61738550000000049454e44ae426082"
            )
        )

        draft = build_ingest_draft(image, tmp_path / "assets")

        assert draft.images
        assert draft.doc.image_refs
        assert any("Image-only input" in warning for warning in draft.warnings)


class TestKnowledgeRetriever:
    """Tests for KnowledgeRetriever (mocked LLM)."""

    def setup_method(self):
        # Create a mock LLM that returns fixed embeddings
        class MockLLM:
            embedding_enabled = True
            embedding_model = "test-model"

            def embed_texts(self, texts):
                # Return fixed deterministic embeddings based on text hash
                import hashlib
                embeddings = []
                for t in texts:
                    h = hashlib.md5(t.encode()).hexdigest()
                    # Convert first 32 chars to 8 float values
                    vec = [float(int(h[i:i+4], 16)) / 65535.0 for i in range(0, 32, 4)]
                    # Pad to 384 dimensions (typical embedding size)
                    vec = vec + [0.0] * (384 - len(vec))
                    embeddings.append(vec[:384])
                return embeddings

        self.mock_llm = MockLLM()
        self.retriever = KnowledgeRetriever(self.mock_llm)

    def test_build_corpus(self):
        """Test building corpus from knowledge base."""
        # The retriever should load checkpoints and knowledge index
        corpus = self.retriever.build_corpus()
        assert isinstance(corpus, list)
        # Should have at least the checkpoint documents
        assert len(corpus) > 0

    def test_search_requires_embedding_enabled(self):
        """Test search returns empty when embedding not enabled."""
        class DisabledLLM:
            embedding_enabled = False

        retriever = KnowledgeRetriever(DisabledLLM())
        results = retriever.search("test query")
        assert results == []

    def test_search_empty_query(self):
        """Test search with empty query."""
        results = self.retriever.search("")
        assert results == []

    def test_clear_cache(self):
        """Test clearing cache."""
        self.retriever.clear_cache()
        # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
