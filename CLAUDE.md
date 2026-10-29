# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:1105d646 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/core-concepts/sync-concepts.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Multi-Agent Workflow

Work runs through agents defined in `.claude/agents/`. Start a session with `claude --agent orchestrator`.

- **orchestrator**: main session. Picks beads with `bd ready` and dispatches the others. Never edits code.
- **planner**: writes beads (design and acceptance criteria). Read-only on code.
- **coder**: implements one bead.
- **tester**: verifies acceptance criteria. Edits `tests/` only.
- **reviewer**: checks the diff against the standards below. Read-only.

Design discussions happen separately in `claude --agent brainstorm`, an interactive session outside the loop.
It resolves open `decision` beads with the user and owns the Coding Standards section below. Closing a decision
bead unblocks the work that depends on it, which the orchestrator picks up on its next run.

New work enters as a rough bead labelled `stage:needs-design`, filed by the orchestrator or by brainstorm. Only the
planner turns intake beads into ready tasks with acceptance criteria.

Stage labels: `stage:needs-design` → `stage:ready` → `stage:in-progress` → `stage:testing` → `stage:review` →
`stage:awaiting-merge` → closed.
Agents leave their results as bead notes prefixed `IMPL:`, `TEST:`, `QA:`, `REVIEW:`, or `HANDOFF:`.

Each bead is built in its own worktree at `../golf_scoring_workbench-worktrees/<id>`, on branch `bead/<id>`.
The main checkout is never edited by agents. The orchestrator commits on the bead branch and prints a HANDOFF with
what changed, where to look closely, and QA steps. It merges into `main` only when the user replies "merge <id>".

Run the loop in auto mode: `claude --agent orchestrator --permission-mode auto`.

## Build & Test

```bash
uv sync                    # install deps (Python 3.14, see .python-version)
uv run pytest -q           # tests
uv run ruff check .        # lint
uv run ruff format .       # format
```

Never use pip. Add dependencies with `uv add` (or `uv add --dev`).

## Architecture Overview

- `pipelines/strokeplay/`: golf.nl scraper (Selenium + BeautifulSoup). `config_manager.py` loads
  `config.yaml` plus credentials from `.env`. `scrapers/` holds `BaseScraper` and `GolfNLScraper`.
  `models.py` holds the dataclasses. `scrape_strokeplay_data.py` is the CLI entry point.
  `golf_nl.py`, `debug_html.py`, and `models_example.py` are legacy/reference scripts.
- `data/scripts/`: SQLite schema creation and deletion for `data/golf_workbench.db`.
- `analysis/notebooks/`: exploratory Jupyter notebooks.
- `tests/`: pytest suite (currently minimal).

## Coding Standards

The reviewer enforces these. Do not block a bead for problems that were already in the code. File those as chores instead.

1. Code passes `ruff check` and `ruff format`. The config lives in `pyproject.toml`.
2. Type hints on all public functions and methods. Use built-in generics (`list[str]`, `X | None`).
3. Docstrings on public modules, classes, and functions. Comments explain why, not what.
4. Use package imports. No `sys.path.append` hacks.
5. Errors: catch specific exceptions. No bare or blind `except Exception` that swallows errors. Log with `logging`, never `print`, in library code.
6. Resources: WebDriver, DB connections, and files are closed via context managers or `try/finally`.
7. SQL uses parameterized queries. Never use string formatting with values.
8. Secrets come only from the config loader or the environment. They are never logged, hard-coded, or used in tests.
9. Tests: pytest with plain `assert`. No network, no real browser, no real DB. Use fixtures, mocks, and `tmp_path`.
10. Keep changes scoped to the bead. Put unrelated improvements in new beads.

## Safety

- Never read or print `.env` files, and never commit them.
- Never modify `data/golf_workbench.db` or `data/raw/` unless a bead explicitly requires it.
