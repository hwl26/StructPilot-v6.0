#!/usr/bin/env python
"""三模式架构完整性测试。

运行前确保：
1. 在 final_struct 目录下执行
2. Python 环境已安装 streamlit
"""

import json
import sys
from pathlib import Path

def test_file_structure():
    """Test file structure integrity."""
    print("[1/5] Checking file structure...")
    required = [
        "modes/__init__.py",
        "modes/beginner.py",
        "modes/teaching.py",
        "modes/expert.py",
        "components/__init__.py",
        "components/qa_card.py",
        "knowledge_base/teaching_cards.json",
        "knowledge_base/quiz_bank.json",
        "knowledge_base/lab_experience_kb.json",
        "main.py",
    ]
    missing = []
    for f in required:
        if not Path(f).exists():
            missing.append(f)
    if missing:
        print(f"  [FAIL] Missing files: {missing}")
        return False
    print("  [PASS] File structure complete")
    return True

def test_json_validity():
    """Test JSON file validity."""
    print("\n[2/5] Checking JSON files...")
    json_files = [
        "knowledge_base/teaching_cards.json",
        "knowledge_base/quiz_bank.json",
        "knowledge_base/lab_experience_kb.json",
    ]
    for f in json_files:
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            print(f"  [PASS] {f}")
        except Exception as exc:
            print(f"  [FAIL] {f}: {exc}")
            return False
    print("  [PASS] All JSON files valid")
    return True

def test_imports():
    """Test module imports."""
    print("\n[3/5] Checking module imports...")
    try:
        sys.path.insert(0, str(Path.cwd()))
        from modes import render_beginner_view, render_teaching_view, render_expert_view
        from components import evaluate_qa, render_qa_card
        print("  [PASS] Modules imported successfully")
        return True
    except Exception as exc:
        print(f"  [FAIL] Import error: {exc}")
        return False

def test_knowledge_content():
    """Test knowledge base content."""
    print("\n[4/5] Checking knowledge base content...")

    # Teaching cards
    cards = json.loads(Path("knowledge_base/teaching_cards.json").read_text(encoding="utf-8"))
    card_steps = list(cards.keys())
    print(f"  · Teaching cards: {len(card_steps)} steps")

    # Quizzes
    quizzes = json.loads(Path("knowledge_base/quiz_bank.json").read_text(encoding="utf-8"))
    quiz_steps = list(quizzes.keys())
    total_questions = sum(len(q.get("questions", [])) for q in quizzes.values())
    print(f"  · Quiz bank: {len(quiz_steps)} steps, {total_questions} questions")

    # Lab experiences
    lab_kb = json.loads(Path("knowledge_base/lab_experience_kb.json").read_text(encoding="utf-8"))
    entries = lab_kb.get("entries", [])
    approved = sum(1 for e in entries if e.get("status") == "approved")
    pending = sum(1 for e in entries if e.get("status") == "pending")
    print(f"  · Lab experiences: {len(entries)} entries ({approved} approved, {pending} pending)")

    if len(card_steps) < 4:
        print("  [WARN] Less than 4 teaching card steps")
    if total_questions < 9:
        print("  [WARN] Less than 9 quiz questions")
    if len(entries) < 3:
        print("  [WARN] Less than 3 lab experience entries")

    print("  [PASS] Knowledge base content checked")
    return True

def test_main_py_injection():
    """Test main.py injection points."""
    print("\n[5/5] Checking main.py injection points...")
    main_content = Path("main.py").read_text(encoding="utf-8")

    checks = {
        "app_mode initialization": 'st.session_state.app_mode',
        "mode switcher": '_mode_options',
        "mode router": 'if _app_mode == "beginner"',
        "beginner render": 'from modes import render_beginner_view',
        "teaching render": 'render_teaching_view',
        "expert panel": 'if st.session_state.app_mode == "expert"',
    }

    missing = []
    for name, pattern in checks.items():
        if pattern not in main_content:
            missing.append(name)

    if missing:
        print(f"  [FAIL] Missing injection points: {missing}")
        return False

    print("  [PASS] All injection points found")
    return True

def main():
    print("=" * 60)
    print("StructPilot v6.0 Final - Three-Mode Architecture Test")
    print("=" * 60)

    tests = [
        test_file_structure,
        test_json_validity,
        test_imports,
        test_knowledge_content,
        test_main_py_injection,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as exc:
            print(f"\n[ERROR] Test exception: {exc}")
            results.append(False)

    print("\n" + "=" * 60)
    if all(results):
        print("[SUCCESS] All tests passed! Architecture is complete.")
        print("\nTo start the application:")
        print("  streamlit run main.py")
    else:
        print("[FAIL] Some tests failed. Check errors above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
