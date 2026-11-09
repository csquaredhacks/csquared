#!/usr/bin/env bash
# Put the Hallway dashboard, check rules and SLO into Dash0. Safe to run again: each
# item has a fixed id, so a second run updates it instead of making a copy.
#
#   DASH0_API_URL     e.g. https://api.us-west-2.aws.dash0.com  (Dash0 -> Settings -> Endpoints -> API)
#   DASH0_API_TOKEN   an auth token that may write dashboards, check rules and SLOs.
#                     Falls back to DASH0_AUTH_TOKEN, which works if that token is not ingest-only.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
api="${DASH0_API_URL:?Set DASH0_API_URL, e.g. https://api.us-west-2.aws.dash0.com}"
token="${DASH0_API_TOKEN:-${DASH0_AUTH_TOKEN:?Set DASH0_API_TOKEN or DASH0_AUTH_TOKEN}}"
dataset="${DASH0_DATASET:-default}"

put() { # put <api path> <file>
  local status
  status=$(curl -sS -o /tmp/dash0-apply.out -w '%{http_code}' -X PUT \
    -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    --data-binary "@${here}/$2" "${api%/}$1?dataset=${dataset}")
  if [ "${status}" -ge 300 ]; then
    echo "FAILED ${status}: $2" >&2
    cat /tmp/dash0-apply.out >&2
    echo >&2
    exit 1
  fi
  echo "ok ${status}: $2"
}

put /api/dashboards/hallway dashboard.json
put /api/alerting/check-rules/hallway-matches-slow check-matches-slow.json
put /api/alerting/check-rules/hallway-server-errors check-server-errors.json
put /api/slos/hallway-api-availability slo-availability.json
