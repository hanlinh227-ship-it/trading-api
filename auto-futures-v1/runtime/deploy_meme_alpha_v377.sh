#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V377_DEPLOY=DEFER_NOT_ROOT'; exit 0; }

APP=/opt/meme-alpha/app
SIGNER_ROOT=/opt/meme-alpha-signer
SIGNAL="$APP/src/safe-signal-export.js"
EXECUTOR="$APP/src/micro-live-executor.js"
SIGNER="$SIGNER_ROOT/ready_signer.py"
PATCHER=/opt/trading/trading-api/auto-futures-v1/runtime/meme_alpha_patch_v377.py
LIVE_STATE=/var/lib/meme-alpha/data/micro-live/state.json
ARM=/etc/meme-alpha/micro-live-armed
MAINT_STATE=/var/lib/meme-alpha/deploy-v377-maintenance.json
BACKUP_ROOT=/opt/meme-alpha/backups
LOCK=/tmp/meme-alpha-v377-deploy.lock
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v377_$TS"
TMP="$(mktemp -d /tmp/meme-alpha-v377.XXXXXX)"
BACKUP_READY=0
SERVICES_STOPPED=0

cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT
exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V377_DEPLOY=DEFER_LOCK_BUSY'; exit 0; fi

for f in "$SIGNAL" "$EXECUTOR" "$SIGNER" "$PATCHER"; do
  [[ -f "$f" ]] || { echo "MEME_V377_DEPLOY=DEFER_MISSING_FILE name=$(basename "$f")"; exit 0; }
done

already_hardened(){
  grep -q "3.77.0-objective-insider-risk" "$SIGNAL" 2>/dev/null &&
  grep -q "function insiderSafe(c)" "$EXECUTOR" 2>/dev/null &&
  grep -q "def objective_insider_ok(c):" "$SIGNER" 2>/dev/null &&
  grep -q "'version':'8.0'" "$SIGNER" 2>/dev/null
}

read_original_arm(){
  if [[ -f "$MAINT_STATE" ]]; then
    python3 - "$MAINT_STATE" <<'PY'
import json,sys
try: print(json.load(open(sys.argv[1])).get('original','MISSING'))
except Exception: print('MISSING')
PY
  elif [[ -f "$ARM" ]]; then
    cat "$ARM"
  else
    echo MISSING
  fi
}

write_arm(){
  local value="$1" group= rootgroup
  if [[ -f "$ARM" ]]; then group="$(stat -c %G "$ARM")"; else group=root; fi
  local t; t="$(mktemp /tmp/meme-alpha-arm.XXXXXX)"
  printf '%s\n' "$value" > "$t"
  install -o root -g "$group" -m 0640 "$t" "$ARM"
  rm -f "$t"
}

enter_maintenance(){
  [[ -f "$MAINT_STATE" ]] && return 0
  local original
  original="$( [[ -f "$ARM" ]] && cat "$ARM" || echo MISSING )"
  mkdir -p "$(dirname "$MAINT_STATE")"
  python3 - "$MAINT_STATE" "$original" <<'PY'
import json,os,sys,time
p=sys.argv[1];orig=sys.argv[2]
t=p+'.tmp';open(t,'w').write(json.dumps({'original':orig,'startedAt':time.time(),'version':'v377'},separators=(',',':')));os.chmod(t,0o600);os.replace(t,p)
PY
  if [[ "$original" == 'ARMED=YES' ]]; then
    write_arm 'MAINTENANCE=V377'
    echo 'MEME_V377_MAINTENANCE=NEW_BUYS_PAUSED_EXITS_REMAIN_AVAILABLE'
  else
    echo 'MEME_V377_MAINTENANCE=EXISTING_ARM_STATE_PRESERVED'
  fi
}

restore_maintenance(){
  [[ -f "$MAINT_STATE" ]] || return 0
  local original
  original="$(read_original_arm)"
  if [[ "$original" == 'MISSING' ]]; then
    rm -f "$ARM"
  else
    write_arm "$original"
  fi
  rm -f "$MAINT_STATE"
  echo 'MEME_V377_MAINTENANCE=RESTORED'
}

position_count(){
  python3 - "$LIVE_STATE" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1]))
 p=d.get('positions')
 if isinstance(p,list): print(len(p))
 elif d.get('position'): print(1)
 else: print(0)
except Exception: print(-1)
PY
}

# v3.79 is a strict successor of the v3.77/v3.78 executor line. If an old
# v3.77 deployment was interrupted after entering maintenance, recovery must
# restore the original root arm state even while positions are open. This path
# performs no source patch, no service stop, and no position close.
if grep -q 'MICRO_LIVE_EXECUTOR_V379_HIGH_OPPORTUNITY' "$EXECUTOR" 2>/dev/null; then
  restore_maintenance
  echo 'MEME_V377_DEPLOY=ALREADY_SUPERSEDED_BY_V379'
  exit 0
fi

if already_hardened; then
  restore_maintenance
  echo 'MEME_V377_DEPLOY=ALREADY_APPLIED'
  exit 0
fi

# Maintenance mode closes only the BUY gate. Existing sells remain signable.
enter_maintenance

OPEN="$(position_count)"
if [[ "$OPEN" -lt 0 ]]; then
  echo 'MEME_V377_DEPLOY=DEFER_STATE_UNREADABLE'
  exit 0
fi
if [[ "$OPEN" -gt 0 ]]; then
  echo "MEME_V377_DEPLOY=DEFER_OPEN_POSITIONS count=$OPEN"
  exit 0
fi

cp -a "$SIGNAL" "$TMP/safe-signal-export.js"
cp -a "$EXECUTOR" "$TMP/micro-live-executor.js"
cp -a "$SIGNER" "$TMP/ready_signer.py"
python3 "$PATCHER" "$TMP/safe-signal-export.js" "$TMP/micro-live-executor.js" "$TMP/ready_signer.py"
node --check "$TMP/safe-signal-export.js"
node --check "$TMP/micro-live-executor.js"
python3 -m py_compile "$TMP/ready_signer.py"
node "$TMP/safe-signal-export.js" --self-test >/dev/null
node "$TMP/micro-live-executor.js" --self-test >/dev/null
python3 "$TMP/ready_signer.py" --self-test >/dev/null

grep -q "3.77.0-objective-insider-risk" "$TMP/safe-signal-export.js"
grep -q "function insiderSafe(c)" "$TMP/micro-live-executor.js"
grep -q "def objective_insider_ok(c):" "$TMP/ready_signer.py"
grep -q "'version':'8.0'" "$TMP/ready_signer.py"
echo 'MEME_V377_STAGE_TEST=PASS'

mkdir -p "$BACKUP"
cp -a "$SIGNAL" "$BACKUP/safe-signal-export.js"
cp -a "$EXECUTOR" "$BACKUP/micro-live-executor.js"
cp -a "$SIGNER" "$BACKUP/ready_signer.py"
BACKUP_READY=1

rollback(){
  local rc=$?
  trap - ERR
  echo "MEME_V377_DEPLOY=ROLLBACK rc=$rc"
  if [[ "$BACKUP_READY" -eq 1 ]]; then
    cp -a "$BACKUP/safe-signal-export.js" "$SIGNAL" || true
    cp -a "$BACKUP/micro-live-executor.js" "$EXECUTOR" || true
    cp -a "$BACKUP/ready_signer.py" "$SIGNER" || true
  fi
  systemctl restart meme-alpha-signer.service meme-alpha-paper.service meme-alpha-micro-live.service 2>/dev/null || true
  restore_maintenance || true
  exit "$rc"
}
trap rollback ERR

systemctl stop meme-alpha-micro-live.service
SERVICES_STOPPED=1
OPEN="$(position_count)"
if [[ "$OPEN" -ne 0 ]]; then
  systemctl start meme-alpha-micro-live.service
  SERVICES_STOPPED=0
  echo "MEME_V377_DEPLOY=DEFER_RACE_OPEN_POSITION count=$OPEN"
  exit 0
fi
systemctl stop meme-alpha-paper.service meme-alpha-signer.service

install_like(){
  local src="$1" dst="$2" owner group mode
  owner="$(stat -c %U "$dst")"; group="$(stat -c %G "$dst")"; mode="$(stat -c %a "$dst")"
  install -o "$owner" -g "$group" -m "$mode" "$src" "$dst"
}
install_like "$TMP/safe-signal-export.js" "$SIGNAL"
install_like "$TMP/micro-live-executor.js" "$EXECUTOR"
install_like "$TMP/ready_signer.py" "$SIGNER"

node --check "$SIGNAL"
node --check "$EXECUTOR"
python3 -m py_compile "$SIGNER"

systemctl start meme-alpha-signer.service
systemctl start meme-alpha-paper.service
sleep 2
systemctl start meme-alpha-micro-live.service
sleep 3

for u in meme-alpha-signer.service meme-alpha-paper.service meme-alpha-micro-live.service; do
  systemctl is-active --quiet "$u" || { echo "MEME_V377_HEALTH=FAIL unit=$u"; false; }
done

python3 - <<'PY'
import json,socket
p='/run/meme-alpha-signer/signer.sock'
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(3);s.connect(p);s.sendall(b'{"op":"health"}\n');d=b''
while b'\n' not in d:
 d+=s.recv(4096)
j=json.loads(d.split(b'\n',1)[0]);assert j.get('ok') is True;assert j.get('version')=='8.0';assert j.get('arbitraryRawSign') is False
PY

already_hardened || { echo 'MEME_V377_HEALTH=MARKER_FAIL'; false; }
restore_maintenance
mkdir -p "$APP/runtime-status"
printf '{"version":"3.77.0","status":"DEPLOYED","timestamp":"%s"}\n' "$(date -u +%FT%TZ)" > "$APP/runtime-status/v377-deployed.json"
chmod 0664 "$APP/runtime-status/v377-deployed.json" || true
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'v377_*' -mtime +14 -exec rm -rf {} + 2>/dev/null || true
trap - ERR
echo 'MEME_V377_DEPLOY=SUCCESS'
