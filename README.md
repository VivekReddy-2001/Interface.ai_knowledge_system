# Interface.ai Knowledge System

A Python project for the interface.ai knowledge-system assignment: answer from
dated website snapshots, cite evidence, and resolve conflicting claims.

**Status:** Phases 1 and 2 are implemented: dataset inventory, SQLite snapshot
storage, and capture-date selection. Phase 3a adds provenance-preserving evidence
units. Ranked retrieval is not implemented yet. The engine still abstains while
retrieval, fact extraction, and conflict resolution are being built.

## Windows setup

Install Git, Python 3.11, and VS Code if you do not already have them. In PowerShell:

```powershell
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.11 --exact --source winget
winget install --id Microsoft.VisualStudioCode --exact --source winget
```

Close and reopen PowerShell after installation. Once the scaffold has been pushed,
clone the repository and enter its folder:

```powershell
git clone https://github.com/VivekReddy-2001/Interface.ai_knowledge_system.git
cd Interface.ai_knowledge_system
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -v
code knowledge-now.code-workspace
```

These commands do not require activating the environment or changing PowerShell's
execution policy. `scripts/setup.ps1` is an optional convenience script if your
existing PowerShell policy allows local scripts.

In VS Code, install the workspace's recommended extensions (Python, Pylance,
Python Debugger, and Ruff). Run **Python: Select Interpreter** from Ctrl+Shift+P
and choose `.venv\Scripts\python.exe` if it was not selected automatically.
Use **Terminal > Run Task** for testing, linting, or evaluation. Use F5 with
**Debug smoke tests** or **Debug public evaluation** for debugging.

## Import the private participant kit

Keep the provided ZIP in Downloads; do not add it to Git. From the project folder:

```powershell
.\.venv\Scripts\python.exe scripts\import_kit.py "$env:USERPROFILE\Downloads\hackathon-knowledge-kit-participant.zip"
.\.venv\Scripts\python.exe scripts\evaluate.py --starter
.\.venv\Scripts\python.exe scripts\evaluate.py
```

The import creates `.local/kit/`, which is ignored by Git. The unchanged official
harness unpacks the five inner snapshot ZIPs on its first run. Evaluation results
are written to `.local/results/`, also ignored. The public evaluation does not
fully measure hidden-set performance or conflict detection.

If your terminal is **Command Prompt** rather than PowerShell, import with:

```cmd
.\.venv\Scripts\python.exe scripts\import_kit.py "%USERPROFILE%\Downloads\hackathon-knowledge-kit-participant.zip"
```

## Learn and run Phases 1 and 2

Read [Phase 1](docs/phase-1.md) and [Phase 2](docs/phase-2.md) for code walkthroughs,
dataset findings, design decisions, tests, and debugging exercises.

With the virtual environment activated, these commands work in Command Prompt:

```cmd
python scripts\inspect_snapshots.py --find auto-motorcycle-loans --find savings-account
python scripts\check_ingestion.py --as-of 2026-05-31
python scripts\check_ingestion.py --database .local\evidence.sqlite
python -m pytest -v
```

The inspection report is `.local/reports/inventory.json`. The demonstration reuses
the supplied loader; the engine's `ingest()` receives already loaded objects.
No API keys or additional runtime packages are needed; SQLite is included in Python.

## Inspect an evidence unit (Phase 3a)

Read the [evidence-unit walkthrough](docs/phase-3-evidence.md) before running:

```cmd
python scripts\inspect_evidence.py --url https://www.dupaco.com/personal/savings-account --as-of 2026-05-31 --kind table --contains "10 Month"
```

This selects a stored capture, gets an already stored page by URL, and builds table
and passage units. It does not fetch the live website or rank questions. The private
report is `.local/reports/evidence-units.json`; the source URL is an identifier.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -v
```

On macOS/Linux, create the environment with `python3.11 -m venv .venv` and use
`.venv/bin/python` instead of `.venv\Scripts\python.exe` in the commands above.

## Project layout

```text
solution.py                    Evaluator entry point: build() and three methods
knowledge_now/models.py        Types for development without the participant kit
knowledge_now/ingestion.py     Atomic, immutable snapshot/page storage
knowledge_now/temporal.py      Capture-date validation and selection
knowledge_now/parsing.py       Source-preserving passage/table evidence units
scripts/inspect_snapshots.py   Inventory, file checks, and raw-content changes
scripts/check_ingestion.py     Demonstrate ingestion and date selection
scripts/inspect_evidence.py    Inspect units from one stored source page
scripts/import_kit.py          Import the supplied ZIP into an ignored folder
scripts/evaluate.py            Run the official local evaluator
scripts/setup.ps1              Optional Windows bootstrap
tests/                        Synthetic contract, inventory, ingestion, and date tests
docs/                         Phase walkthroughs and learning exercises
.vscode/                      Interpreter, extensions, tasks, and debugger
.github/workflows/checks.yml   Python 3.11 lint, format, and test checks
requirements.txt              Runtime requirements (none initially)
requirements-dev.txt          Pinned development dependencies
NOTES.md                      Design decisions and implementation status
.local/                       Private kit and results; never committed
```

## GitHub setup

Repository: https://github.com/VivekReddy-2001/Interface.ai_knowledge_system

After cloning the repository, make changes and push with your own GitHub account:

```powershell
git add .
git status --short
git commit -m "Describe your change"
git push
```

If Git requests an author identity, set your own name/email with
`git config user.name` and `git config user.email`.
Use Git Credential Manager's browser sign-in for authentication; do not paste
passwords or tokens into project files or chat.

Before every push, review `git status --short` and `git diff --cached --stat`.
The provided website snapshots, ZIPs, API keys, and generated evidence must remain
local. No license for the supplied dataset is granted by this repository.
