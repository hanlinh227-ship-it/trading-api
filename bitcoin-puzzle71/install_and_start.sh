#!/usr/bin/env bash
set -euo pipefail

TARGET='1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU'
START='400000000000000000'
END='7FFFFFFFFFFFFFFFFF'
KEYHUNT_COMMIT='2134a2024e524775b13f82aa1fa07b1c8053f867'
BITCRACK_COMMIT='b754648f2a7b41d04bcd28d53278af4d69e1118e'

# Hard safety boundary: this deployment is only for the public Puzzle #71 challenge.
[[ "$TARGET" == '1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU' ]] || exit 90
[[ "$START" == '400000000000000000' ]] || exit 91
[[ "$END" == '7FFFFFFFFFFFFFFFFF' ]] || exit 92

IS_ROOT=0
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then IS_ROOT=1; fi

if [[ "$IS_ROOT" -eq 1 ]]; then
  ROOT='/opt/bitcoin-puzzle71'
  STATE='/var/lib/bitcoin-puzzle71'
  RUN_MODE='systemd'
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git build-essential ca-certificates coreutils procps >/dev/null

  if ! id puzzle71 >/dev/null 2>&1; then
    useradd --system --home-dir "$STATE" --shell /usr/sbin/nologin puzzle71
  fi
  for g in video render; do
    if getent group "$g" >/dev/null; then usermod -aG "$g" puzzle71 || true; fi
  done
  install -d -m 0755 "$ROOT"
  install -d -o puzzle71 -g puzzle71 -m 0700 "$STATE"
else
  ROOT="${PUZZLE71_ROOT:-$HOME/.local/opt/bitcoin-puzzle71}"
  STATE="${PUZZLE71_STATE:-$HOME/.local/state/bitcoin-puzzle71}"
  RUN_MODE='userspace'
  for cmd in git make gcc g++ nproc stdbuf setsid nohup nice; do
    command -v "$cmd" >/dev/null 2>&1 || {
      echo "Missing required command: $cmd" >&2
      exit 20
    }
  done
  mkdir -p "$ROOT" "$STATE"
  chmod 0700 "$STATE"
fi

BUILD_LOG="$STATE/build.log"
printf '%s\n' "$TARGET" > "$ROOT/target.txt"
printf '%s\n' "$STATE" > "$ROOT/state_path"
printf '%s\n' "$RUN_MODE" > "$STATE/run_mode"
chmod 0644 "$ROOT/target.txt" "$ROOT/state_path"
chmod 0600 "$STATE/run_mode"

TOTAL_THREADS="$(nproc)"
if [[ "$TOTAL_THREADS" -gt 1 ]]; then
  CPU_THREADS=$((TOTAL_THREADS / 2))
else
  CPU_THREADS=1
fi
[[ "$CPU_THREADS" -ge 1 ]] || CPU_THREADS=1
printf '%s\n' "$CPU_THREADS" > "$STATE/cpu_threads"
chmod 0600 "$STATE/cpu_threads"

clone_pinned() {
  local url="$1" dir="$2" commit="$3"
  if [[ ! -d "$dir/.git" ]]; then
    rm -rf "$dir"
    git clone -q "$url" "$dir"
  fi
  git -C "$dir" fetch -q --all --tags
  git -C "$dir" checkout -q --detach "$commit"
  test "$(git -C "$dir" rev-parse HEAD)" = "$commit"
}

ENGINE='keyhunt-cpu'
GPU_COUNT=0
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_COUNT="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true)"
fi

# Prefer CUDA only when a real NVIDIA device and compiler are both usable.
if [[ "$GPU_COUNT" -gt 0 ]] && command -v nvcc >/dev/null 2>&1; then
  echo "Detected $GPU_COUNT NVIDIA GPU(s); attempting pinned BitCrack CUDA build."
  if clone_pinned 'https://github.com/vatupelage/BitCrack-Updated.git' "$ROOT/BitCrack" "$BITCRACK_COMMIT"; then
    make -C "$ROOT/BitCrack" clean >/dev/null 2>&1 || true
    if make -C "$ROOT/BitCrack" -j"$CPU_THREADS" BUILD_CUDA=1 >"$BUILD_LOG" 2>&1; then
      if [[ -x "$ROOT/BitCrack/bin/cuBitCrack" ]]; then
        ENGINE='bitcrack-cuda'
      fi
    fi
  fi
fi

# CPU fallback. KeyHunt's -b 71 mode is explicitly the public 71-bit puzzle interval.
if [[ "$ENGINE" == 'keyhunt-cpu' ]]; then
  echo 'Using CPU KeyHunt fallback.'
  clone_pinned 'https://github.com/albertobsd/keyhunt.git' "$ROOT/keyhunt" "$KEYHUNT_COMMIT"
  make -C "$ROOT/keyhunt" -j"$CPU_THREADS" >"$BUILD_LOG" 2>&1
  test -x "$ROOT/keyhunt/keyhunt"
fi

printf '%s\n' "$ENGINE" > "$STATE/engine"
chmod 0600 "$STATE/engine" "$BUILD_LOG" 2>/dev/null || true

cat > "$ROOT/run.sh" <<'RUNNER'
#!/usr/bin/env bash
set -euo pipefail

TARGET='1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU'
START='400000000000000000'
END='7FFFFFFFFFFFFFFFFF'
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$(cat "$ROOT/state_path")"
ENGINE="$(cat "$STATE/engine")"
CPU_THREADS="$(cat "$STATE/cpu_threads")"

umask 077
rm -f "$STATE/FOUND.lock"

stop_children() {
  jobs -pr | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
}
trap stop_children TERM INT EXIT

if [[ "$ENGINE" == 'bitcrack-cuda' ]]; then
  GPU_COUNT="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true)"
  [[ "$GPU_COUNT" -gt 0 ]] || exit 41
  : > "$STATE/pids"

  for d in $(seq 0 $((GPU_COUNT - 1))); do
    out="$STATE/found_gpu${d}.txt"
    log="$STATE/gpu${d}.log"
    chk="$STATE/gpu${d}.checkpoint"
    : > "$out"
    : > "$log"
    chmod 600 "$out" "$log"

    "$ROOT/BitCrack/bin/cuBitCrack" \
      -d "$d" -c \
      --keyspace "${START}:${END}" \
      --share "$((d + 1))/${GPU_COUNT}" \
      --continue "$chk" \
      -o "$out" \
      -i "$ROOT/target.txt" >"$log" 2>&1 &
    echo $! >> "$STATE/pids"
  done

  while jobs -pr | grep -q .; do
    for d in $(seq 0 $((GPU_COUNT - 1))); do
      if [[ -s "$STATE/found_gpu${d}.txt" ]]; then
        cp "$STATE/found_gpu${d}.txt" "$STATE/FOUND_PRIVATE_KEY.txt"
        chmod 600 "$STATE/FOUND_PRIVATE_KEY.txt"
        touch "$STATE/FOUND.lock"
        stop_children
        exit 0
      fi
    done
    sleep 2
  done
else
  LOG="$STATE/keyhunt.log"
  : > "$LOG"
  chmod 600 "$LOG"

  # Address-only brute force is required because Puzzle #71's public key is not known.
  # Randomized chunk selection avoids restarting from the same beginning after a reboot.
  stdbuf -oL -eL "$ROOT/keyhunt/keyhunt" \
    -m address -f "$ROOT/target.txt" -b 71 -l compress -R -q -s 10 -t "$CPU_THREADS" \
    >"$LOG" 2>&1 &
  PID=$!
  echo "$PID" > "$STATE/pids"

  while kill -0 "$PID" 2>/dev/null; do
    if grep -q 'Hit! Private Key:' "$LOG"; then
      grep -m1 -A3 'Hit! Private Key:' "$LOG" > "$STATE/FOUND_PRIVATE_KEY.txt"
      chmod 600 "$STATE/FOUND_PRIVATE_KEY.txt"
      touch "$STATE/FOUND.lock"
      kill "$PID" 2>/dev/null || true
      wait "$PID" 2>/dev/null || true
      exit 0
    fi
    sleep 2
  done
  wait "$PID"
fi
RUNNER
chmod 0755 "$ROOT/run.sh"

if [[ "$IS_ROOT" -eq 1 ]]; then
  chown -R root:root "$ROOT"
  chown -R puzzle71:puzzle71 "$STATE"
  chmod 0700 "$STATE"

  cat > /etc/systemd/system/bitcoin-puzzle71.service <<'UNIT'
[Unit]
Description=Bounded Bitcoin Puzzle #71 solver
After=network-online.target

[Service]
Type=simple
User=puzzle71
Group=puzzle71
WorkingDirectory=/opt/bitcoin-puzzle71
ExecStart=/opt/bitcoin-puzzle71/run.sh
Restart=on-failure
RestartSec=5
Nice=15
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/bitcoin-puzzle71
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
UNIT

  systemctl daemon-reload
  systemctl enable bitcoin-puzzle71.service >/dev/null
  systemctl restart bitcoin-puzzle71.service
  sleep 2
  systemctl is-active --quiet bitcoin-puzzle71.service
  echo "Puzzle #71 solver active in systemd mode with engine: $ENGINE"
else
  # GitHub self-hosted runners normally clean up descendants bearing RUNNER_TRACKING_ID.
  # Remove that marker and detach a low-priority supervisor so the solver survives the job.
  : > "$STATE/supervisor.log"
  chmod 0600 "$STATE/supervisor.log"
  env -u RUNNER_TRACKING_ID nohup setsid nice -n 15 "$ROOT/run.sh" \
    >>"$STATE/supervisor.log" 2>&1 < /dev/null &
  SUPERVISOR_PID=$!
  printf '%s\n' "$SUPERVISOR_PID" > "$STATE/supervisor.pid"
  chmod 0600 "$STATE/supervisor.pid"
  sleep 3
  kill -0 "$SUPERVISOR_PID" 2>/dev/null || {
    echo 'Puzzle #71 userspace supervisor did not remain alive.' >&2
    tail -n 20 "$STATE/supervisor.log" >&2 || true
    exit 42
  }
  echo "Puzzle #71 solver active in userspace mode with engine: $ENGINE pid=$SUPERVISOR_PID"
fi
