#!/usr/bin/env bash
# Example cron entry (daily at 03:15):
# 15 3 * * * cd /path/to/AirRaidAnalysis && ./scripts/retrain.sh >> logs/retrain.log 2>&1

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "Virtual environment .venv not found. Run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

# Optional production API token:
# export AIRRAID_ALERTS_IN_UA_TOKEN="your_token"
# export AIRRAID_DATA_SOURCE_TYPE="alerts_in_ua_api"

.venv/bin/python -m src.retrain
