#!/usr/bin/env bash
set -uo pipefail

SYSTEM_STATE='/var/lib/bitcoin-puzzle71'
USER_STATE="${PUZZLE71_STATE:-$HOME/.local/state/bitcoin-puzzle71}"
SERVICE='bitcoin-puzzle71.service'

if [[ -r "$SYSTEM_STATE/engine" ]]; then
  STATE="$SYSTEM_STATE"
  MODE='systemd'
elif [[ -r "$USER_STATE/engine" ]]; then
  STATE="$USER_STATE"
  MODE='userspace'
else
  STATE="$USER_STATE"
  MODE='unavailable'
fi

active='inactive'
enabled='no'
if [[ "$MODE" == 'systemd' ]]; then
  active="$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
  enabled="$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)"
elif [[ "$MODE" == 'userspace' ]]; then
  pid="$(cat "$STATE/supervisor.pid" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    active='active'
  fi
  enabled='userspace-detached'
fi

echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'target=Puzzle-71-public'
echo "mode=$MODE"
echo "service=$active"
echo "enabled=$enabled"
echo "engine=$(cat "$STATE/engine" 2>/dev/null || echo unavailable)"
echo "cpu_threads=$(cat "$STATE/cpu_threads" 2>/dev/null || echo unavailable)"

if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_count="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true)"
  echo "gpu_count=${gpu_count:-0}"
else
  echo 'gpu_count=0'
fi

if [[ -e "$STATE/FOUND.lock" ]]; then
  echo 'result=FOUND_LOCAL_ONLY'
elif [[ "$active" == 'active' ]]; then
  echo 'result=SEARCHING'
else
  echo 'result=IDLE_OR_FAILED'
fi

# Expose only sanitized rate/progress output. Never emit hit/private-key lines.
ENGINE="$(cat "$STATE/engine" 2>/dev/null || true)"
if [[ "$ENGINE" == 'keyhunt-cpu' && -f "$STATE/keyhunt.log" ]]; then
  line="$(grep -E 'Total .* keys in|keys/s|Mkeys/s|Gkeys/s' "$STATE/keyhunt.log" 2>/dev/null | tail -n1 || true)"
  if [[ -n "$line" ]]; then
    printf 'last_rate=%s\n' "$(printf '%s' "$line" | tr '\n\r' '  ' | cut -c1-240)"
  fi
elif [[ "$ENGINE" == 'bitcrack-cuda' ]]; then
  for f in "$STATE"/gpu*.log; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f" .log)"
    line="$(grep -E 'MKey|GKey|keys/s|Key/s|progress|Progress' "$f" 2>/dev/null | tail -n1 || true)"
    if [[ -n "$line" ]]; then
      printf '%s_rate=%s\n' "$base" "$(printf '%s' "$line" | tr '\n\r' '  ' | cut -c1-240)"
    fi
  done
fi

exit 0
