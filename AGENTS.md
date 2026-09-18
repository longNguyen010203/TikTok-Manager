# Project Agent Rules

## Shared rules
- Read `ARCHITECTURE.md`, `TASKS.md`, and relevant files before making changes.
- Do not modify files outside your assigned scope unless the task explicitly requires it.
- Keep changes focused on the assigned task.
- Run relevant tests before finishing.
- Summarize files changed, tests run, and any remaining issues.

## Codex role
Primary responsibility:
- backend/
- workers/
- database-related code
- tests/
- infrastructure and integration logic

Codex must NOT modify:
- frontend/

unless the task explicitly allows it.

## Antigravity role
Primary responsibility:
- frontend/
- UI components
- client-side state
- frontend tests

Antigravity must NOT modify:
- backend/
- workers/

unless the task explicitly allows it.

## Shared files
The following files may be read by both agents:
- README.md
- AGENTS.md
- ARCHITECTURE.md
- TASKS.md
- docs/

Changes to shared files should only be made when the assigned task explicitly requires it.