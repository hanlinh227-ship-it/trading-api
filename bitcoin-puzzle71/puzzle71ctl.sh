#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
USER_ROOT="${PUZZLE71_ROOT:-$HOME/.local/opt/bitcoin-puzzle71}"
USER_STATE="${PUZZLE71_STATE:-$HOME/.local/state/bitcoin-puzzle71}"

stop_userspace() {
  local state="$USER_STATE" root="$USER_ROOT" pid='' cmd=''
  [[ -f "$state/supervisor.pid" ]] || return 0
  pid="$(cat "$state/supervisor.pid" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || { rm -f "$state/supervisor.pid"; return 0; }
  if kill -0 "$pid" 2>/dev/null; then
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    if [[ "$cmd" == *"$root/run.sh"* ]]; then
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
      done
    else
      echo "Refusing to kill PID $pid because it does not belong to Puzzle #71." >&2
      return 3
    fi
  fi
  rm -f "$state/supervisor.pid"
}

case "$ACTION" in
  start)
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
      bash "$(dirname "$0")/install_and_start.sh"
    else
      stop_userspace
      bash "$(dirname "$0")/install_and_start.sh"
    fi
    ;;
  restart)
    if [[ ${EUID:-$(id -u)} -eq 0 ]] && systemctl cat bitcoin-puzzle71.service >/dev/null 2>&1; then
      systemctl restart bitcoin-puzzle71.service
    else
      stop_userspace
      bash "$(dirname "$0")/install_and_start.sh"
    fi
    ;;
  stop)
    if [[ ${EUID:-$(id -u)} -eq 0 ]] && systemctl cat bitcoin-puzzle71.service >/dev/null 2>&1; then
      systemctl stop bitcoin-puzzle71.service || true
    else
      stop_userspace
    fi
    ;;
  status)
    bash "$(dirname "$0")/status.sh"
    ;;
  *)
    echo "Usage: $0 {start|restart|stop|status}" >&2
    exit 2
    ;;
esac
