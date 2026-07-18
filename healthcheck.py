"""StructPilot runtime health check.

Run this before demos or handoff:

    python healthcheck.py

It verifies imports, core source syntax, writable runtime storage, and the
knowledge-base structure without starting Streamlit.
"""

from __future__ import annotations

import importlib
import ast
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
try:
    from config.settings import RUNTIME_ROOT, MEMORY_DIR, UPLOAD_DIR, AUDIO_DIR
except Exception:  # pragma: no cover - healthcheck must still diagnose imports
    RUNTIME_ROOT = Path(
        os.getenv(
            "STRUCTPILOT_RUNTIME_DIR",
            str(BASE_DIR / "runtime"),
        )
    )
    MEMORY_DIR = RUNTIME_ROOT / "memory"
    UPLOAD_DIR = MEMORY_DIR / "uploads"
    AUDIO_DIR = MEMORY_DIR / "audio"

RUNTIME_DIR = RUNTIME_ROOT

REQUIRED_IMPORTS = [
    "streamlit",
    "langgraph",
    "langchain_core",
    "dotenv",
    "requests",
    "loguru",
    "numpy",
    "PIL",
    "streamlit_paste_button",
]

CORE_FILES = [
    "main.py",
    "graph/app.py",
    "graph/state.py",
    "agents/navigator_agent.py",
    "agents/llm_agent.py",
    "agents/memory_agent.py",
    "agents/expert_agent.py",
    "agents/sop_agent.py",
    "knowledge_base/importer.py",
    "knowledge_base/retriever.py",
    "knowledge_base/validate_kb_structure.py",
    "validator/validator.py",
]


def check_imports() -> tuple[bool, list[str]]:
    errors: list[str] = []
    for module in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover - diagnostic output
            errors.append(f"{module}: {exc}")
    return not errors, errors


def check_compile() -> tuple[bool, list[str]]:
    errors: list[str] = []
    for rel_path in CORE_FILES:
        path = BASE_DIR / rel_path
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:  # pragma: no cover - diagnostic output
            errors.append(f"{rel_path}: {exc}")
    return not errors, errors


def check_runtime_dir() -> tuple[bool, list[str]]:
    errors: list[str] = []
    for path in [RUNTIME_DIR, MEMORY_DIR, UPLOAD_DIR, AUDIO_DIR]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    return not errors, errors


def check_sqlite() -> tuple[bool, list[str]]:
    db_path = MEMORY_DIR / "healthcheck.sqlite3"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS healthcheck (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO healthcheck(value) VALUES ('ok')")
            conn.execute("DELETE FROM healthcheck")
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def check_kb() -> tuple[bool, list[str]]:
    try:
        from knowledge_base.validate_kb_structure import validate

        result = validate(BASE_DIR / "knowledge_base")
    except Exception as exc:
        return False, [str(exc)]

    if isinstance(result, dict):
        errors = [str(item) for item in result.get("errors", [])]
        warnings = [f"warning: {item}" for item in result.get("warnings", [])]
        return not errors, errors + warnings
    return False, [f"unexpected validator result: {result!r}"]


def print_section(name: str, ok: bool, details: list[str]) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}")
    for item in details:
        print(f"  - {item}")


def main() -> int:
    print("StructPilot health check")
    print(f"Project: {BASE_DIR}")
    print(f"Runtime: {RUNTIME_DIR}")
    print(f"Temp: {Path(tempfile.gettempdir())}")
    print()

    checks = [
        ("dependencies", check_imports()),
        ("source syntax", check_compile()),
        ("runtime directories", check_runtime_dir()),
        ("sqlite", check_sqlite()),
        ("knowledge base", check_kb()),
    ]

    all_ok = True
    report = {}
    for name, (ok, details) in checks:
        print_section(name, ok, details)
        report[name] = {"ok": ok, "details": details}
        all_ok = all_ok and ok

    print()
    print(json.dumps({"ok": all_ok, "report": report}, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
