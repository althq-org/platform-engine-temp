#!/usr/bin/env bash
# Test HTTPS endpoint with retries. Reports HTTP status and body.
# Usage: ./scripts/check_endpoint.sh <url> [timeout_seconds]
#   url: e.g. https://my-ecs-service.althq-dev.com/health
#   timeout_seconds: total retry window (default: 300 = 5 min)
# Exit: 0 if endpoint returns 200, 1 otherwise

set -euo pipefail

URL="${1:?Usage: $0 <url> [timeout_seconds]}"
TIMEOUT="${2:-300}"
DEADLINE=$(($(date +%s) + TIMEOUT))
INTERVAL=10

echo "Testing $URL (timeout: ${TIMEOUT}s, retry every ${INTERVAL}s)..."
while true; do
  if [[ $(date +%s) -ge $DEADLINE ]]; then
    echo "Timeout. Endpoint did not return 200 in time." >&2
    exit 1
  fi
  HTTP_CODE=$(curl -s -o /tmp/check_endpoint_body -w "%{http_code}" --connect-timeout 10 --max-time 15 "$URL" || echo "000")
  echo "[$(date +%H:%M:%S)] HTTP $HTTP_CODE"
  if [[ "$HTTP_CODE" == "200" ]]; then
    echo "Success. Response body (first 500 chars):"
    head -c 500 /tmp/check_endpoint_body
    echo ""
    rm -f /tmp/check_endpoint_body
    exit 0
  fi
  if [[ "$HTTP_CODE" != "000" ]]; then
    echo "Response body:" >&2
    head -c 300 /tmp/check_endpoint_body >&2
    echo "" >&2
  fi
  sleep "$INTERVAL"
done
