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

- `docker/docker-compose.yml`
- `docker/Dockerfile`
- `docker/.env.example`
- `app/backend/main.py`
- `app/backend/core/`
- `app/backend/models/`
- `app/backend/repositories/`
- `app/backend/schemas/`
- `app/backend/services/`
- `app/backend/claude_sdk/`
- `app/frontend/static/`

## Prerequisites

1. Set `ANTHROPIC_API_KEY` in `docker/.env`.
2. Claude Code CLI is installed in the API container (`@anthropic-ai/claude-code`).

## Run

```bash
cp docker/.env.example docker/.env
docker compose --env-file docker/.env -f docker/docker-compose.yml up --build
```

Open: `http://localhost:8070`

PostgreSQL host port is configurable with `DB_HOST_PORT` in `docker/.env`.

## Notes on SDK options class

The latest Python docs expose `ClaudeCodeOptions` with the same option set referenced by the docs anchor for Claude agent options.
This project uses that class and falls back to `ClaudeAgentOptions` for compatibility.
Set `CLAUDE_DEBUG_STDERR=true` in `docker/.env` when you need verbose Claude CLI stderr diagnostics in container logs.
