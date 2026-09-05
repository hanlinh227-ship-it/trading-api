#!/usr/bin/env bash
set -euo pipefail

echo '=== MEME ALPHA v1.4.1 RUNNER ISOLATION DIAGNOSTIC ==='
APP=/opt/meme-alpha/app
cd "$APP"
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

echo "CURRENT_UID=$(id -u)"
echo "CURRENT_USER=$(id -un)"
echo '=== ACTIONS RUNNER SERVICES ==='
mapfile -t units < <(systemctl list-unit-files --type=service --no-legend | awk '/actions\.runner\./{print $1}')
printf 'RUNNER_UNIT_COUNT=%s\n' "${#units[@]}"
for u in "${units[@]}"; do
  echo "RUNNER_UNIT=$u"
  systemctl show "$u" -p User -p Group -p FragmentPath -p ExecStart --no-pager || true
  systemctl cat "$u" --no-pager || true
done

echo '=== RUNNER DIRECTORY ==='
stat -c 'PATH=%n OWNER=%U:%G MODE=%a' /opt/actions-runner /opt/actions-runner/actions-runner 2>/dev/null || true
find /opt/actions-runner/actions-runner -maxdepth 1 -printf '%u:%g %m %f\n' 2>/dev/null | head -40 || true

echo '=== RUNNER CONFIG ==='
for f in /opt/actions-runner/actions-runner/.runner /opt/actions-runner/actions-runner/.credentials /opt/actions-runner/actions-runner/.credentials_rsaparams; do
  if [ -e "$f" ]; then stat -c 'FILE=%n OWNER=%U:%G MODE=%a SIZE=%s' "$f"; else echo "MISSING=$f"; fi
done

echo '=== SUDO / USERS ==='
getent passwd github-runner || true
getent passwd actions-runner || true
getent passwd meme-alpha || true
grep -RIlE 'github-runner|actions-runner|meme-alpha' /etc/sudoers /etc/sudoers.d 2>/dev/null | sed 's/^/SUDO_FILE=/' || true

echo '=== MEME ALPHA SERVICE ==='
systemctl show meme-alpha-paper.service -p User -p Group -p FragmentPath -p ExecStart -p NoNewPrivileges -p ProtectSystem -p ProtectHome --no-pager || true
stat -c 'WALLET_DIR=%n OWNER=%U:%G MODE=%a' /var/lib/meme-alpha/wallet 2>/dev/null || true
find /var/lib/meme-alpha/wallet -maxdepth 1 -type f -printf 'WALLET_FILE=%f OWNER=%u:%g MODE=%m\n' 2>/dev/null || true

echo '=== SECURITY CONCLUSION ==='
runner_user=$(systemctl show "${units[0]:-nonexistent.service}" -p User --value 2>/dev/null || true)
if [ -z "$runner_user" ]; then runner_user=root; fi
echo "RUNNER_EFFECTIVE_USER=$runner_user"
if [ "$runner_user" = root ]; then
  echo 'RUNNER_ISOLATION=BLOCKED_ROOT'
else
  echo 'RUNNER_ISOLATION=NONROOT_CANDIDATE'
fi
echo 'NO_WALLET_CREATED_BY_DIAGNOSTIC=TRUE'
echo 'V141_DIAGNOSTIC_COMPLETE'
