#!/usr/bin/env bash
set -euo pipefail

TARGET='1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU'
START='400000000000000000'
END='7FFFFFFFFFFFFFFFFF'
KEYHUNT_COMMIT='2134a2024e524775b13f82aa1fa07b1c8053f867'
BITCRACK_COMMIT='b754648f2a7b41d04bcd28d53278af4d69e1118e'
ROOT='/opt/bitcoin-puzzle71'
STATE='/var/lib/bitcoin-puzzle71'
ENGINE_FILE="$STATE/engine"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo 'This installer must run as root.' >&2
  exit 1
fi

# Hard safety boundary: this deployment is only for the public Puzzle #71 challenge.
[[ "$TARGET" == '1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU' ]] || exit 90
[[ "$START" == '400000000000000000' ]] || exit 91
[[ "$END" == '7FFFFFFFFFFFFFFFFF' ]] || exit 92

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
printf '%s\n' "$TARGET" > "$ROOT/target.txt"
chmod 0644 "$ROOT/target.txt"

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

# Prefer CUDA when the VPS really has both a visible NVIDIA device and a compiler.
if [[ "$GPU_COUNT" -gt 0 ]] && command -v nvcc >/dev/null 2>&1; then
  echo "Detected $GPU_COUNT NVIDIA GPU(s); attempting pinned BitCrack CUDA build."
  if clone_pinned 'https://github.com/vatupelage/BitCrack-Updated.git' "$ROOT/BitCrack" "$BITCRACK_COMMIT"; then
    if make -C "$ROOT/BitCrack" clean >/dev/null 2>&1 || true; then :; fi
    if make -C "$ROOT/BitCrack" -j"$(nproc)" BUILD_CUDA=1 >/var/log/bitcoin-puzzle71-build.log 2>&1; then
      if [[ -x "$ROOT/BitCrack/bin/cuBitCrack" ]]; then
        ENGINE='bitcrack-cuda'
      fi
    fi
  fi
fi

# Guaranteed CPU fallback.
if [[ "$ENGINE" == 'keyhunt-cpu' ]]; then
  echo 'Using CPU KeyHunt fallback.'
  clone_pinned 'https://github.com/albertobsd/keyhunt.git' "$ROOT/keyhunt" "$KEYHUNT_COMMIT"
  make -C "$ROOT/keyhunt" -j"$(nproc)" >/var/log/bitcoin-puzzle71-build.log 2>&1
  test -x "$ROOT/keyhunt/keyhunt"
fi

printf '%s\n' "$ENGINE" > "$ENGINE_FILE"
chown puzzle71:puzzle71 "$ENGINE_FILE"
chmod 0600 "$ENGINE_FILE"

cat > "$ROOT/run.sh" <<'RUNNER'
#!/usr/bin/env bash
set -euo pipefail
TARGET='1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU'
START='400000000000000000'
END='7FFFFFFFFFFFFFFFFF'
ROOT='/opt/bitcoin-puzzle71'
STATE='/var/lib/bitcoin-puzzle71'
ENGINE="$(cat "$STATE/engine")"

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
    touch "$out" "$log"
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
        # Never print the result. Keep it local and stop the whole search immediately.
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
  THREADS="$(nproc)"
  LOG="$STATE/keyhunt.log"
  : > "$LOG"
  chmod 600 "$LOG"
  stdbuf -oL -eL "$ROOT/keyhunt/keyhunt" \
    -m address -f "$ROOT/target.txt" -b 71 -l compress -R -q -s 10 -t "$THREADS" \
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
Nice=5
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

chown -R root:root "$ROOT"
chmod 0755 "$ROOT" "$ROOT/run.sh"
chown -R puzzle71:puzzle71 "$STATE"
chmod 0700 "$STATE"

systemctl daemon-reload
systemctl enable bitcoin-puzzle71.service >/dev/null
systemctl restart bitcoin-puzzle71.service
sleep 2
systemctl is-active --quiet bitcoin-puzzle71.service

echo "Puzzle #71 solver active with engine: $ENGINE"
