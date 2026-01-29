#!/usr/bin/env bash
# Poll GitHub Actions workflow run until complete. On failure, fetch and display failed logs.
# Usage: ./scripts/check_workflow.sh [repo] [run_id]
#   repo: e.g. althq-org/my-ecs-service (default: althq-org/my-ecs-service)
#   run_id: optional; if omitted, uses latest run for main branch
# Exit: 0=success, 1=failure, 2=timeout
# Prerequisite: gh CLI installed and authenticated

set -euo pipefail

REPO="${1:-althq-org/my-ecs-service}"
RUN_ID="${2:-}"
POLL_INTERVAL="${POLL_INTERVAL:-15}"
TIMEOUT_MINUTES="${TIMEOUT_MINUTES:-60}"
TIMEOUT_SECONDS=$((TIMEOUT_MINUTES * 60))
DEADLINE=$(($(date +%s) + TIMEOUT_SECONDS))

if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI not found. Install from https://cli.github.com/" >&2
  exit 2
fi

if [[ -z "$RUN_ID" ]]; then
  echo "Getting latest run for $REPO (branch: main)..."
  RUN_ID=$(gh run list --repo "$REPO" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')
  if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
    echo "No runs found for $REPO on main." >&2
    exit 2
  fi
  echo "Run ID: $RUN_ID"
fi

echo "Watching run $RUN_ID (timeout: ${TIMEOUT_MINUTES}m, poll every ${POLL_INTERVAL}s)..."
while true; do
  if [[ $(date +%s) -ge $DEADLINE ]]; then
    echo "Timeout after ${TIMEOUT_MINUTES} minutes." >&2
    exit 2
  fi
  STATUS=$(gh run view --repo "$REPO" "$RUN_ID" --json status,conclusion --jq '"\(.status) \(.conclusion // "none")"')
  echo "[$(date +%H:%M:%S)] $STATUS"
  if [[ "$STATUS" == "completed success" ]]; then
    echo "Run succeeded."
    exit 0
  fi
  if [[ "$STATUS" == "completed failure" ]] || [[ "$STATUS" == "completed cancelled" ]] || [[ "$STATUS" == "completed "* ]]; then
    echo "Run failed or cancelled. Fetching failed job logs..." >&2
    gh run view --repo "$REPO" "$RUN_ID" --log-failed 2>&1 || true
    exit 1
  fi
  sleep "$POLL_INTERVAL"
done
