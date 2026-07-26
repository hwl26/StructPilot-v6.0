"""Knowledge retriever: pure-numpy cosine similarity RAG over checkpoints + index.

设计原则（与 plan 一致）：
- 语料来源 = pipeline_checkpoints.json 各站点 + knowledge_index 文档，统一经
  doc_to_text 转文本。
- embedding 走 LLMAgent.embed_texts（硅基流动 OpenAI 兼容 /v1/embeddings）。
- 向量相似度用纯 numpy 余弦，不引入 Chroma/FAISS。
- embedding 缓存到 config/embeddings_cache.json，key = sha256(text)，命中跳过 API。
- 语料与向量矩阵缓存到内存，避免每次检索重新读文件、拼文本、算向量。
- 全程优雅降级：embedding 不可用 / 语料空 / 任何异常 → search 返回 []。
- 支持按 tier/status 加权排序：builtin > sop > note > draft，draft 得分降权50%。
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from knowledge_base.importer import doc_to_text, TIER_WEIGHTS
from knowledge_base.paths import (
    iter_runtime_allowed_docs,
    load_json_with_fallback,
    load_sharded_knowledge_index,
)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KNOWLEDGE_DIR = os.path.join(_BASE_DIR, "knowledge_base")
_CHECKPOINTS_PATH = os.path.join(_KNOWLEDGE_DIR, "pipeline_checkpoints.json")
_INDEX_PATH = os.path.join(_BASE_DIR, "knowledge_base", "knowledge_index.json")
# P1-10: knowledge_index.json 已按 checkpoint 拆分到 knowledge_index/ 目录，
# retriever 现在通过 load_sharded_knowledge_index 遍历分片加载；保留 _INDEX_PATH
# 仅作为占位文件引用，不再用于读取语料。
_INDEX_DIR = os.path.join(_KNOWLEDGE_DIR, "knowledge_index")
_CACHE_PATH = os.path.join(_BASE_DIR, "config", "embeddings_cache.json")
_CORPUS_CACHE_PATH = os.path.join(_BASE_DIR, "config", "corpus_cache.json")
_RUNTIME_ROOT = os.getenv("STRUCTPILOT_RUNTIME_DIR", os.path.join(_BASE_DIR, "runtime"))
_HIT_COUNTS_PATH = os.path.join(_RUNTIME_ROOT, "knowledge_hit_counts.json")
_CORPUS_CACHE_VERSION = 2
_DEFAULT_MIN_SCORE = 0.30

# P2-9: _record_hits 热路径改为内存累积 + 定时落盘，避免每次检索同步写文件。
_hits_buffer: Dict[str, Dict[str, Any]] = {}
_hits_last_flush: float = 0.0
_HITS_FLUSH_INTERVAL = 30.0  # 30 秒落盘一次


def _tokenize(text: str) -> List[str]:
    """Small local fallback tokenizer for retrieval when embeddings are off.

    改进（B 阶段官方文档集成前置）：
    - 保留 ASCII 词（正则）+ 既有硬编码中文/英文词表。
    - 新增 CJK 连续段处理：保留整段 + 生成二元gram（bigram）。
      此前正则只匹配 [a-z0-9]，中文查询词几乎全部丢失（如"用户管理"
      只剩 ASCII 的 "cryosparc"），导致中文检索近乎失效。bigram 让
      "用户管理" 与文档中的 "用户管理" 通过 "用户"/"管理" 等重叠命中。
    """
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9_./+-]{2,}", text)
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.append(run)  # 整段，便于精确短语匹配
        if len(run) >= 2:
            for i in range(len(run) - 1):
                tokens.append(run[i:i + 2])  # 二元 gram
    for term in (
        "导入", "运动", "校正", "ctf", "挑选", "二维", "三维", "分类",
        "精修", "抛光", "后处理", "分辨率", "像素", "剂量", "路径", "报错",
        "用户", "管理", "创建", "密码", "提取", "颗粒", "角色", "许可",
        "particle", "micrograph", "movie", "relion", "star", "pixel", "motion",
        "polish", "refine", "classification", "reconstruction",
    ):
        if term in text:
            tokens.append(term)
    return tokens


def _doc_weight(doc: Dict[str, Any]) -> float:
    tier = doc.get("tier", "note")
    status = doc.get("status", "formal_ready")
    w = TIER_WEIGHTS.get(tier, 0.6)
    if status != "formal_ready":
        w *= 0.5
    return w


def _lexical_search(corpus: List[Tuple[str, str, float]], query: str, top_k: int) -> List[Tuple[str, str, float]]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    query_set = set(query_tokens)
    scored: List[Tuple[str, str, float]] = []
    for doc_id, text, weight in corpus:
        doc_tokens = _tokenize(text)
        if not doc_tokens:
            continue
        doc_set = set(doc_tokens)
        overlap = query_set & doc_set
        if not overlap:
            continue
        score = len(overlap) / max(len(query_set), 1) * weight
        if any(token in doc_set for token in query_set if token in {"relion", "ctf", "star"}):
            score += 0.15 * weight
        # 不再用 min(score, 1.0) 封顶：单 token 命中的 checkpoint（权重 1.0）
        # 会得满分 1.0 并挤占 top_k，把多 token 命中的官方文档（权重 0.95）挤出。
        # 去掉封顶后，token 覆盖度更高的文档自然排在前面。
        scored.append((doc_id, text, score))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored[:top_k]


def _record_hits(results: List[Tuple[str, str, float]]) -> None:
    """Best-effort retrieval telemetry for the review panel.

    P2-9: 改为内存累积 + 定时落盘，避免热路径上同步写文件。
    命中记录先累积到 _hits_buffer，每隔 _HITS_FLUSH_INTERVAL 秒落盘一次；
    进程退出时通过 atexit 保证剩余缓冲写入磁盘。
    """
    global _hits_last_flush
    if not results:
        return
    now_str = time.strftime("%Y-%m-%dT%H:%M:%S")
    for doc_id, _text, score in results:
        if not doc_id:
            continue
        item = _hits_buffer.setdefault(str(doc_id), {"hits": 0, "last_hit_at": "", "last_score": 0})
        item["hits"] = int(item.get("hits") or 0) + 1
        item["last_hit_at"] = now_str
        item["last_score"] = round(float(score), 4)
    now = time.time()
    if now - _hits_last_flush > _HITS_FLUSH_INTERVAL:
        _flush_hits_to_disk()
        _hits_last_flush = now


def _flush_hits_to_disk() -> None:
    """将内存缓冲的命中计数合并落盘（定时 / 进程退出时调用）。"""
    if not _hits_buffer:
        return
    try:
        os.makedirs(os.path.dirname(_HIT_COUNTS_PATH), exist_ok=True)
        data: Dict[str, Any] = {}
        if os.path.exists(_HIT_COUNTS_PATH):
            with open(_HIT_COUNTS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        counts = data.setdefault("counts", {})
        for doc_id, buf_item in _hits_buffer.items():
            existing = counts.get(doc_id, {"hits": 0, "last_hit_at": "", "last_score": 0})
            existing["hits"] = int(existing.get("hits") or 0) + int(buf_item.get("hits") or 0)
            existing["last_hit_at"] = buf_item.get("last_hit_at", "")
            existing["last_score"] = buf_item.get("last_score", 0)
            counts[doc_id] = existing
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(_HIT_COUNTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _hits_buffer.clear()
    except Exception:
        pass  # 遥测失败不影响主路径


atexit.register(_flush_hits_to_disk)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _checkpoint_to_text(cp: Dict[str, Any]) -> str:
    """把一个站点拼成检索文本，复用与 doc_to_text 类似的字段平铺。"""
    parts: List[str] = []
    name = (cp.get("checkpoint_cn") or cp.get("checkpoint_name") or "").strip()
    if name:
        parts.append(name)
    for key in ("phase", "stage_goal", "input_needed"):
        val = (cp.get(key) or "").strip()
        if val:
            parts.append(val)

    def _add_list(label: str, items: Any) -> None:
        if isinstance(items, list):
            cleaned = [str(x).strip() for x in items if str(x).strip()]
            if cleaned:
                parts.append(f"{label}：" + "；".join(cleaned))

    for soft in ("cryosparc", "relion"):
        block = cp.get(soft) or {}
        if isinstance(block, dict):
            _add_list(f"{soft} 步骤", block.get("key_steps"))
    _add_list("质控", cp.get("qc_check"))
    _add_list("常见坑", cp.get("common_pitfalls"))
    return "\n".join(parts)


def _runtime_doc_to_text(doc: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in (
        "title_cn", "title", "question", "answer", "summary", "checkpoint_id",
        "software", "module", "screen_name",
    ):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    for key in ("action_steps", "qc_checks", "common_errors", "rollback_nodes", "keywords", "tags"):
        val = doc.get(key)
        if isinstance(val, list):
            cleaned = [str(item).strip() for item in val if str(item).strip()]
            if cleaned:
                parts.append("; ".join(cleaned))
    return "\n".join(parts)


def _glossary_to_text(item: Dict[str, Any]) -> str:
    term = str(item.get("term") or "").strip()
    aliases = item.get("aliases") or []
    definition = str(item.get("definition_cn") or item.get("definition") or "").strip()
    parts = [term, definition]
    if isinstance(aliases, list):
        parts.append("; ".join(str(alias) for alias in aliases if alias))
    return "\n".join(part for part in parts if part)


class KnowledgeRetriever:
    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self._corpus_cache: Optional[List[Tuple[str, str, float]]] = None
        self._corpus_embeddings: Optional[Dict[str, List[float]]] = None
        self._doc_matrix: Optional[np.ndarray] = None
        self._corpus_texts: Optional[List[str]] = None
        self._corpus_weights: Optional[List[float]] = None
        self._corpus_lock = threading.Lock()
        self._cache_loaded = False

    def _load_corpus_cache(self) -> Optional[List[Tuple[str, str, float]]]:
        if not os.path.exists(_CORPUS_CACHE_PATH):
            return None
        try:
            with open(_CORPUS_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("cache_version") != _CORPUS_CACHE_VERSION:
                return None
            if isinstance(data, dict) and "corpus" in data:
                result = []
                for item in data["corpus"]:
                    w = item.get("weight", 1.0)
                    result.append((item["doc_id"], item["text"], float(w)))
                return result
        except Exception:
            pass
        return None

    def _save_corpus_cache(self, corpus: List[Tuple[str, str, float]]) -> None:
        try:
            os.makedirs(os.path.dirname(_CORPUS_CACHE_PATH), exist_ok=True)
            data = {
                "cache_version": _CORPUS_CACHE_VERSION,
                "corpus": [{"doc_id": doc_id, "text": text, "weight": w} for doc_id, text, w in corpus],
                "cached_at": os.path.getmtime(_CHECKPOINTS_PATH) if os.path.exists(_CHECKPOINTS_PATH) else 0,
            }
            with open(_CORPUS_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _invalidate_corpus_cache(self) -> None:
        self._corpus_cache = None
        self._corpus_embeddings = None
        self._doc_matrix = None
        self._corpus_texts = None
        self._corpus_weights = None
        self._cache_loaded = False
        try:
            if os.path.exists(_CORPUS_CACHE_PATH):
                os.remove(_CORPUS_CACHE_PATH)
        except Exception:
            pass

    def build_corpus(self, force_rebuild: bool = False) -> List[Tuple[str, str, float]]:
        """收集 (doc_id, text, weight)。checkpoints(weight=1.0) + 知识文档(按tier加权)。"""
        with self._corpus_lock:
            if not force_rebuild and self._corpus_cache is not None:
                return self._corpus_cache

            if not force_rebuild and not self._cache_loaded:
                cached = self._load_corpus_cache()
                if cached:
                    self._corpus_cache = cached
                    self._cache_loaded = True
                    return cached

            corpus: List[Tuple[str, str, float]] = []
            try:
                checkpoints = load_json_with_fallback(
                    _KNOWLEDGE_DIR,
                    "flows/pipeline_checkpoints.json",
                    "pipeline_checkpoints.json",
                    default=[],
                )
                if isinstance(checkpoints, list):
                    for cp in checkpoints:
                        if not isinstance(cp, dict):
                            continue
                        text = _checkpoint_to_text(cp)
                        if text.strip():
                            corpus.append((cp.get("checkpoint_id", ""), text, TIER_WEIGHTS["builtin"]))
            except Exception:
                pass

            try:
                for doc in iter_runtime_allowed_docs(_KNOWLEDGE_DIR):
                    text = _runtime_doc_to_text(doc)
                    if text.strip():
                        doc_id = str(doc.get("doc_id") or doc.get("id") or "formal_answer")
                        corpus.append((doc_id, text, TIER_WEIGHTS.get("sop", 0.8)))
            except Exception:
                pass

            try:
                # P1-10: 改为从 knowledge_index/ 分片目录加载并合并。
                # load_sharded_knowledge_index 遍历目录下所有 *.json 并返回扁平 doc 列表，
                # 无分片目录时自动回退到旧的 knowledge_index.json（仅当其仍为 list）。
                for doc in load_sharded_knowledge_index(_KNOWLEDGE_DIR):
                    text = doc_to_text(doc)
                    if text.strip():
                        w = _doc_weight(doc)
                        corpus.append((str(doc.get("doc_id", "")), text, w))
            except Exception:
                pass

            try:
                glossary = load_json_with_fallback(
                    _KNOWLEDGE_DIR,
                    "terminology/glossary.json",
                    None,
                    default=[],
                )
                if isinstance(glossary, list):
                    for item in glossary:
                        if not isinstance(item, dict):
                            continue
                        if item.get("runtime_allowed", True) is False:
                            continue
                        text = _glossary_to_text(item)
                        if text.strip():
                            corpus.append((f"glossary:{item.get('term', '')}", text, TIER_WEIGHTS.get("note", 0.6)))
            except Exception:
                pass

            self._corpus_cache = corpus
            self._cache_loaded = True
            self._save_corpus_cache(corpus)
            return corpus

    def _load_cache(self) -> Dict[str, List[float]]:
        if not os.path.exists(_CACHE_PATH):
            return {}
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self, cache: Dict[str, List[float]]) -> None:
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    def clear_cache(self) -> None:
        try:
            if os.path.exists(_CACHE_PATH):
                os.remove(_CACHE_PATH)
        except Exception:
            pass
        self._corpus_embeddings = None
        self._doc_matrix = None
        self._corpus_texts = None
        self._corpus_weights = None

    def invalidate_corpus_cache(self) -> None:
        self._invalidate_corpus_cache()

    def _embed_with_cache(self, texts: List[str]) -> Dict[str, List[float]]:
        cache = self._load_cache()
        missing = [t for t in texts if _sha256(t) not in cache]
        if missing:
            vectors = self.llm.embed_texts(missing)
            if len(vectors) != len(missing):
                raise RuntimeError("embedding 返回数量与输入不一致")
            for t, vec in zip(missing, vectors):
                cache[_sha256(t)] = vec
            self._save_cache(cache)
        return {t: cache[_sha256(t)] for t in texts}

    def _ensure_corpus_ready(self) -> bool:
        if self._doc_matrix is not None and self._corpus_texts is not None:
            return True

        corpus = self.build_corpus()
        if not corpus:
            return False

        self._corpus_texts = [t for _, t, _ in corpus]
        self._corpus_weights = [w for _, _, w in corpus]
        try:
            emb_map = self._embed_with_cache(self._corpus_texts)
            self._doc_matrix = np.array([emb_map[t] for t in self._corpus_texts], dtype=np.float64)
            self._corpus_embeddings = emb_map
            return True
        except Exception:
            return False

    def search(self, query: str, top_k: int = 3,
               min_score: float = _DEFAULT_MIN_SCORE) -> List[Tuple[str, str, float]]:
        """返回 top-k [(doc_id, text, weighted_score)]。

        排序分数 = 余弦相似度 × 文档权重(tier/status)。
        draft 文档权重0.2，仅在没有更高权重匹配时才可能进入 top-k。
        """
        query = (query or "").strip()
        if not query:
            return []
        if not getattr(self.llm, "embedding_enabled", False):
            results = _lexical_search(self.build_corpus(), query, top_k)
            _record_hits(results)
            return results
        try:
            if not self._ensure_corpus_ready():
                return []

            if self._doc_matrix is None or self._corpus_texts is None or self._corpus_cache is None:
                return []

            query_vec = np.array(self.llm.embed_texts([query])[0], dtype=np.float64)

            doc_matrix = self._doc_matrix
            corpus = self._corpus_cache
            weights = np.array(self._corpus_weights or [1.0] * len(corpus), dtype=np.float64)

            doc_norms = np.linalg.norm(doc_matrix, axis=1)
            query_norm = np.linalg.norm(query_vec)
            denom = doc_norms * query_norm
            denom[denom == 0] = 1e-12
            raw_scores = (doc_matrix @ query_vec) / denom
            weighted_scores = raw_scores * weights

            order = np.argsort(weighted_scores)[::-1][:top_k]
            results = [
                (corpus[i][0], corpus[i][1], float(weighted_scores[i]))
                for i in order
                if weighted_scores[i] >= min_score
            ]
            _record_hits(results)
            return results
        except Exception:
            results = _lexical_search(self.build_corpus(), query, top_k)
            _record_hits(results)
            return results
