#!/usr/bin/env bash
set -euo pipefail
STATE='/var/lib/bitcoin-puzzle71'
SERVICE='bitcoin-puzzle71.service'

echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "target=Puzzle-71-public"
echo "service=$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
echo "enabled=$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)"
echo "engine=$(cat "$STATE/engine" 2>/dev/null || echo unavailable)"
echo "cpu_threads=$(nproc 2>/dev/null || echo unknown)"
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "gpu_count=$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true)"
else
  echo 'gpu_count=0'
fi

if [[ -e "$STATE/FOUND.lock" ]]; then
  echo 'result=FOUND_LOCAL_ONLY'
  echo 'result_path=/var/lib/bitcoin-puzzle71/FOUND_PRIVATE_KEY.txt'
else
  echo 'result=SEARCHING_OR_IDLE'
fi

# Only expose a sanitized speed/progress line. Never emit Hit/private-key lines.
ENGINE="$(cat "$STATE/engine" 2>/dev/null || true)"
if [[ "$ENGINE" == 'keyhunt-cpu' && -f "$STATE/keyhunt.log" ]]; then
  line="$(grep -E 'keys in|keys/s|Mkeys|Gkeys' "$STATE/keyhunt.log" 2>/dev/null | tail -n1 || true)"
  [[ -n "$line" ]] && printf 'last_rate=%s\n' "$(printf '%s' "$line" | tr '\n\r' '  ' | cut -c1-240)"
elif [[ "$ENGINE" == 'bitcrack-cuda' ]]; then
  for f in "$STATE"/gpu*.log; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f" .log)"
    line="$(grep -E 'MKey|GKey|keys/s|Key/s|progress|Progress' "$f" 2>/dev/null | tail -n1 || true)"
    [[ -n "$line" ]] && printf '%s_rate=%s\n' "$base" "$(printf '%s' "$line" | tr '\n\r' '  ' | cut -c1-240)"
  done
fi
