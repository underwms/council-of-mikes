# Council Autonomous Orchestrator

The Council Autonomous Orchestration Engine is a cross-platform (Windows 11 + macOS) multi-agent orchestration runtime for modern engineering teams.

Powered by **LangGraph** (`langgraph`), Python 3.11+, and Pydantic v2 schemas, it autonomously plans, delegates, tests, and validates code changes across microservices under the direction of The Council's 15 specialist packages.

---

## Features
- **Cross-Platform Invariant**: Runs natively on Windows 11 (PowerShell 7+) and macOS (zsh) with zero manual script conversions.
- **Enterprise Approval Gates**: Targeted Human-in-the-Loop review at Gate 1 (Plan Approval) and Gate 2 (Pre-Submit Approval).
- **Automated Test-Repair Loop**: Parses compiler (`CS` errors) and test assertion failures into actionable diagnostics, automatically routing retries back to the responsible specialist (up to 3 loops).
- **Universal Workspace Validator**: Zero-dependency standard library Python validator (`scripts/validate_workspace.py`).
- **Multi-Model Support**: Pluggable support for Google Gemini (default), Anthropic Claude, and OpenAI GPT via environment variables.
- **SQLite Persistence**: Automatic checkpointing via `SqliteSaver` supporting pause, crash recovery, and `--resume <run_id>`.

---

## Quick Start

### 1. Installation
```bash
cd tools/council
pip install -r requirements.txt
```

### 2. Configure Environment
Set your preferred model API keys in your environment or a `.env` file:
```bash
GEMINI_API_KEY="your-gemini-key"
# Optional alternatives:
ANTHROPIC_API_KEY="your-claude-key"
OPENAI_API_KEY="your-gpt-key"
```

### 3. Usage
```bash
# Standard interactive run
python -m council run "Implement distance_unit filter for shipping rates"

# Run from a markdown user story
python -m council run --story temp/userstories/sprint3/ORDER-185.md

# Unattended batch run (auto-approve gates)
python -m council run --story temp/userstories/sprint3/ORDER-185.md --auto-approve

# Resume a previous run
python -m council run --resume <run_id>
```
