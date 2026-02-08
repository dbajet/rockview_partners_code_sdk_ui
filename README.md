# Claude Agent SDK UI

Dockerized UI stack to drive Claude Agent SDK sessions with:
- FastAPI backend (Python, OOP service/repository/runtime classes)
- Raw JavaScript frontend
- PostgreSQL persistence for users, message logs, and session logs

## Features

- Uses `ClaudeSDKClient` (not `query`) for long-lived session behavior
- Per-session runtime state with Claude resume support
- Stores all message events in `message_logs`
- Stores session lifecycle events in `session_logs`
- User records in DB (auth can be added later)
- Theme toggle (dark/light)
- Streaming UI updates via SSE
- Default permission mode is `bypassPermissions`

## Project structure

- `docker-compose.yml`
- `backend/Dockerfile`
- `backend/app/main.py`
- `backend/app/core/`
- `backend/app/models/`
- `backend/app/repositories/`
- `backend/app/runtime/`
- `backend/app/schemas/`
- `backend/app/services/`
- `backend/app/static/`

## Prerequisites

1. Set `ANTHROPIC_API_KEY` in `.env`.
2. Claude Code CLI is installed in the API container (`@anthropic-ai/claude-code`).

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open: `http://localhost:8070`

PostgreSQL is exposed on host port `5433` by default (configurable with `DB_HOST_PORT`).

## Notes on SDK options class

The latest Python docs expose `ClaudeCodeOptions` with the same option set referenced by the docs anchor for Claude agent options.
This project uses that class and falls back to `ClaudeAgentOptions` for compatibility.
