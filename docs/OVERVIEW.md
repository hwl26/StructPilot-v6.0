# StructPilot Overview

StructPilot v2.0 is a local cryo-EM workflow copilot. It does not replace cryoSPARC, RELION, or other processing tools. Instead, it helps users move through a standard processing workflow with checkpoint guidance, troubleshooting suggestions, parameter reminders, session memory, and optional LLM-enhanced responses.

## What It Does

- Guides users through checkpoint-based cryo-EM processing.
- Tracks checkpoint status as `pending`, `in_progress`, `passed`, `failed`, or `skipped`.
- Provides SOP-style instructions and troubleshooting responses from local knowledge-base files.
- Saves sessions, messages, checkpoint records, and image metadata in SQLite.
- Supports optional RAG, vision, and audio transcription when API keys are configured.
- Falls back to rule-based local behavior when API features are not configured.

## Primary Users

- Cryo-EM beginners who need step-by-step workflow coaching.
- Lab members who want consistent process tracking across sessions.
- Developers or knowledge engineers adding structured lab SOPs and troubleshooting content.

## Runtime Model

The application starts from `main.py` and runs in Streamlit. User input flows through `StructPilotApp`, then the Navigator agent applies workflow rules. If configured, retrieval and LLM rewrite layers enrich the rule-based answer. The Memory agent persists state after each interaction.

```text
User input
  -> Streamlit UI
  -> StructPilotApp
  -> NavigatorAgent rule decision
  -> optional RAG / optional LLM rewrite / optional vision context
  -> MemoryAgent SQLite persistence
  -> UI render
```

## Important Files

- `README.md`: installation, launch, configuration, and release checklist.
- `start.bat`: Windows launcher for non-developer users.
- `healthcheck.py`: non-interactive readiness check for demos and delivery.
- `requirements.txt`: runtime dependencies.
- `requirements-dev.txt`: runtime dependencies plus test tools.
- `knowledge_base/validate_kb_structure.py`: knowledge-base structure validation.
- `docs/ARCHITECTURE.md`: deeper implementation notes.

## Configuration Modes

Rule-only mode:

- No API key required.
- Uses local checkpoints, rules, SOPs, and validators.
- Best for offline demos and stable baseline behavior.

LLM-enhanced mode:

- Requires `.env` or saved config with API details.
- Can rewrite answers, use embedding search, process vision inputs, and transcribe audio depending on provider support.

## Delivery Readiness

Run before demos:

```bash
.venv/Scripts/python healthcheck.py
```

Run before developer handoff:

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
```

## Current Maturity

The project is suitable for internal demonstrations and continued iteration. The next step toward production quality is to modularize the large Streamlit entrypoint, expand tests, and complete checkpoint knowledge content.
