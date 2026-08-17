#!/usr/bin/env bash
set -euo pipefail
RUN_IDS=(32025195558 32024676960 32025078599 32025444113)
for rid in "${RUN_IDS[@]}"; do
  echo "===== RUN ${rid} ====="
  gh run view "$rid" --repo hanlinh227-ship-it/trading-api --log 2>/dev/null \
    | grep -E 'FINAL \{|SUMMARY_JSON|SUMMARY \{|TEST .*"pass": true|EURUSD ONLINE' \
    | tail -n 250 || true
  echo
 done
