"""Deterministic eval runner for StructPilot QA changes.

The runner uses local/rule mode by default so it is safe for CI and does not
require API keys. JSONL cases can assert expected/forbidden keywords and, when
images are available, attach an uploaded screenshot path to the app state.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from graph.app import StructPilotApp
from graph.state import PipelineState


BASE_DIR = Path(__file__).resolve().parent
CASES_DIR = BASE_DIR / "eval_cases"


def load_cases(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                data.setdefault("_source", f"{path.name}:{line_no}")
                cases.append(data)
    return cases


def iter_default_case_files() -> List[Path]:
    return sorted(CASES_DIR.glob("*_cases.jsonl"))


def make_state(case_id: str) -> PipelineState:
    return PipelineState(session_id=f"eval_{case_id}", current_cp_name="数据导入与初检")


def attach_image_if_available(state: PipelineState, case: Dict[str, Any]) -> bool:
    image_path = str(case.get("image_path") or "").strip()
    if not image_path:
        return False
    path = Path(image_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        return False
    state.pending_images.append({
        "image_name": path.name,
        "image_path": str(path),
        "source_type": "eval",
    })
    state.image_observations.append({
        "image_name": path.name,
        "ocr": {"available": False, "text": ""},
        "vision": {"screen": "eval_image"},
    })
    return True


def run_case(app: StructPilotApp, case: Dict[str, Any]) -> Dict[str, Any]:
    state = make_state(case["id"])
    modality = str(case.get("modality") or ("image" if case.get("image_path") else "text"))
    has_image = attach_image_if_available(state, case)
    if case.get("skip_without_image") and not has_image:
        return {"id": case["id"], "modality": modality, "status": "skipped", "reason": "image_missing"}
    input_text = str(case.get("transcript") or case.get("input") or "")
    if modality == "voice_transcript" and "transcript" not in case:
        input_text = f"[voice transcript] {input_text}"

    tmp = tempfile.mkdtemp(prefix="structpilot_eval_")
    started = time.perf_counter()
    try:
        app.memory = app.memory.__class__(memory_dir=tmp)
        result = app.handle(state, input_text)
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        try:
            shutil.rmtree(tmp)
        except PermissionError:
            # Windows may keep the SQLite file handle briefly after the case ends.
            pass
    answer = result.agent_reply or (result.messages[-1].content if result.messages else "")
    expected = [str(x) for x in case.get("expected_keywords", [])]
    forbidden = [str(x) for x in case.get("forbidden_keywords", [])]
    missing = [kw for kw in expected if kw and kw.lower() not in answer.lower()]
    present_forbidden = [kw for kw in forbidden if kw and kw.lower() in answer.lower()]
    trace = result.messages[-1].metadata.get("qa_trace", {}) if result.messages else {}
    max_latency_ms = case.get("max_latency_ms")
    latency_failed = isinstance(max_latency_ms, (int, float)) and elapsed_ms > float(max_latency_ms)
    require_fallback = case.get("require_fallback_reason")
    fallback_ok = True
    if require_fallback is not None:
        fallback_ok = str(trace.get("fallback_reason") or "") == str(require_fallback)
    ok = not missing and not present_forbidden and not latency_failed and fallback_ok and bool(trace)
    return {
        "id": case["id"],
        "modality": modality,
        "status": "passed" if ok else "failed",
        "missing_keywords": missing,
        "forbidden_keywords_found": present_forbidden,
        "latency_ms": elapsed_ms,
        "latency_failed": latency_failed,
        "fallback_ok": fallback_ok,
        "mode_label": trace.get("mode_label", ""),
        "fallback_reason": trace.get("fallback_reason", ""),
        "answer_preview": answer[:240],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", help="Specific JSONL case files. Defaults to eval_cases/*_cases.jsonl")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON results")
    args = parser.parse_args()

    case_paths = [Path(p) for p in args.cases] if args.cases else iter_default_case_files()
    cases = load_cases(case_paths)
    if not cases:
        print("No eval cases found.", file=sys.stderr)
        return 2

    os.environ.setdefault("STRUCTPILOT_LLM_PROVIDER", "none")
    app = StructPilotApp()
    results = [run_case(app, case) for case in cases]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]

    if args.json:
        summary = {
            "total": len(results),
            "passed": len(results) - len(failed) - len(skipped),
            "failed": len(failed),
            "skipped": len(skipped),
            "avg_latency_ms": round(
                sum(float(r.get("latency_ms") or 0) for r in results if r["status"] != "skipped")
                / max(len([r for r in results if r["status"] != "skipped"]), 1),
                1,
            ),
        }
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            latency = f"{item.get('latency_ms', '-')}ms" if item["status"] != "skipped" else "-"
            print(
                f"{item['status'].upper():7} {item['id']} "
                f"[{item.get('modality', 'text')}] {latency} {item.get('mode_label', '')} {item.get('reason', '')}"
            )
            if item["status"] == "failed":
                print(
                    f"  missing={item['missing_keywords']} "
                    f"forbidden={item['forbidden_keywords_found']} "
                    f"latency_failed={item.get('latency_failed')} fallback_ok={item.get('fallback_ok')}"
                )
                print(f"  answer={item['answer_preview']}")
        measured = [r for r in results if r["status"] != "skipped"]
        avg_latency = sum(float(r.get("latency_ms") or 0) for r in measured) / max(len(measured), 1)
        print(
            f"\nSummary: {len(results) - len(failed) - len(skipped)} passed, "
            f"{len(failed)} failed, {len(skipped)} skipped, avg_latency={avg_latency:.1f}ms"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
