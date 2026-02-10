#!/usr/bin/env bash

# Production deployment script for Claude Agent SDK UI
# Builds a new API image while DB stays up, then swaps API container.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/docker/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker/docker-compose.yml}"
APP_SERVICE="${APP_SERVICE:-api}"
DB_SERVICE="${DB_SERVICE:-db}"
APP_INTERNAL_PORT="${APP_INTERNAL_PORT:-8000}"
DEFAULT_PUBLIC_PORT="${DEFAULT_PUBLIC_PORT:-8070}"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

echo "========================================="
echo "  Claude Agent SDK UI Production Deploy"
echo "========================================="
echo

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: $ENV_FILE file not found"
  echo "Create $ENV_FILE with production configuration before deploying."
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Error: $COMPOSE_FILE file not found"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "Step 1: Pulling latest code from git..."
if git rev-parse --git-dir >/dev/null 2>&1; then
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  echo "Current branch: $current_branch"
  git pull origin "$current_branch"
  echo "Code updated"
else
  echo "Not a git repository, skipping git pull"
fi
echo

echo "Step 2: Ensuring database is running..."
compose up -d "$DB_SERVICE"
echo "Database ready"
echo

echo "Step 3: Building new API image..."
compose build "$APP_SERVICE"
echo "New image built"
echo

echo "Step 4: Recreating API container..."
compose up -d --no-deps --force-recreate "$APP_SERVICE"
echo "API updated"
echo

echo "Step 5: Waiting for service startup..."
sleep 5
compose ps
echo

echo "Step 6: Cleaning unused images..."
docker image prune -f >/dev/null
echo "Cleanup complete"
echo

published_port=""
if compose port "$APP_SERVICE" "$APP_INTERNAL_PORT" >/dev/null 2>&1; then
  published_port="$(compose port "$APP_SERVICE" "$APP_INTERNAL_PORT" | head -n 1 | awk -F: '{print $NF}')"
fi

if [[ -z "$published_port" ]]; then
  published_port="${APP_PUBLIC_PORT:-$DEFAULT_PUBLIC_PORT}"
fi

echo "========================================="
echo "Deployment complete"
echo "========================================="
echo
echo "Application: http://localhost:${published_port}"
echo
echo "Useful commands:"
echo "  Logs:   docker compose --env-file $ENV_FILE -f $COMPOSE_FILE logs -f $APP_SERVICE"
echo "  Status: docker compose --env-file $ENV_FILE -f $COMPOSE_FILE ps"
echo
