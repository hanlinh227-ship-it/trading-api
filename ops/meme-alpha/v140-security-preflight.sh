#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data
WALLET=/var/lib/meme-alpha/wallet

echo '=== MEME ALPHA v1.4 SECURITY PREFLIGHT ==='

cd "$APP"
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(cfg.mode!=='PAPER') throw new Error('SAFETY_BLOCK_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

SERVICE_USER=$(systemctl show meme-alpha-paper.service -p User --value || true)
SERVICE_GROUP=$(systemctl show meme-alpha-paper.service -p Group --value || true)
[ -n "$SERVICE_USER" ] || SERVICE_USER=root
[ -n "$SERVICE_GROUP" ] || SERVICE_GROUP=root
printf 'SERVICE_USER=%s\n' "$SERVICE_USER"
printf 'SERVICE_GROUP=%s\n' "$SERVICE_GROUP"

RUNNER_PID=$(pgrep -f 'Runner.Listener' | head -1 || true)
if [ -n "$RUNNER_PID" ]; then
  RUNNER_USER=$(ps -o user= -p "$RUNNER_PID" | xargs)
  echo "RUNNER_USER=$RUNNER_USER"
else
  RUNNER_USER=unknown
  echo 'RUNNER_USER=unknown'
fi

mkdir -p "$WALLET"
chown meme-alpha:meme-alpha "$WALLET"
chmod 700 "$WALLET"
WOWNER=$(stat -c '%U:%G' "$WALLET")
WMODE=$(stat -c '%a' "$WALLET")
WFILES=$(find "$WALLET" -maxdepth 1 -type f | wc -l | xargs)
echo "WALLET_OWNER=$WOWNER"
echo "WALLET_MODE=$WMODE"
echo "WALLET_FILE_COUNT=$WFILES"
if [ "$WFILES" -eq 0 ]; then echo 'BOT_WALLET=NOT_CREATED'; else echo 'BOT_WALLET=MATERIAL_PRESENT_REVIEW_REQUIRED'; fi

TRACKED_SENSITIVE=$(git -C /opt/actions-runner/actions-runner/_work/trading-api/trading-api ls-files 2>/dev/null | grep -Ei '(^|/)(\.env($|\.)|secrets?/|credentials?/|wallets?/)|keypair.*\.json$|\.pem$|\.p12$|\.pfx$|\.keystore$' | wc -l | xargs || true)
TRACKED_SENSITIVE=${TRACKED_SENSITIVE:-0}
echo "TRACKED_SENSITIVE_FILENAMES=$TRACKED_SENSITIVE"

REPO=/opt/actions-runner/actions-runner/_work/trading-api/trading-api
for marker in '.env' '.env.*' 'secrets/' 'wallet/' '*keypair*.json' '*.pem' '*.key'; do
  if grep -Fqx "$marker" "$REPO/.gitignore"; then
    echo "GITIGNORE_PASS=$marker"
  else
    echo "GITIGNORE_MISSING=$marker"
  fi
done

PRIVATE_MARKER_FILES=$(git -C "$REPO" grep -IlE 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|\[[[:space:]]*[0-9]+([[:space:]]*,[[:space:]]*[0-9]+){31,}[[:space:]]*\]' -- ':!*.md' ':!ops/meme-alpha/v140-security-preflight.sh' 2>/dev/null | wc -l | xargs || true)
PRIVATE_MARKER_FILES=${PRIVATE_MARKER_FILES:-0}
echo "TRACKED_PRIVATE_KEY_MARKER_FILES=$PRIVATE_MARKER_FILES"

SUDO_RULES=$(sudo -l -U meme-alpha 2>/dev/null | grep -E '\(ALL(:ALL)?\).*ALL|NOPASSWD' | wc -l | xargs || true)
SUDO_RULES=${SUDO_RULES:-0}
echo "MEME_ALPHA_SUDO_RULE_LINES=$SUDO_RULES"

UNIT=$(systemctl cat meme-alpha-paper.service 2>/dev/null || true)
for directive in 'NoNewPrivileges=true' 'PrivateTmp=true' 'ProtectSystem=' 'ProtectHome='; do
  if printf '%s\n' "$UNIT" | grep -Fq "$directive"; then
    echo "SYSTEMD_HARDENING_PRESENT=$directive"
  else
    echo "SYSTEMD_HARDENING_MISSING=$directive"
  fi
done

BLOCKS=0
[ "$RUNNER_USER" = root ] && { echo 'BLOCKER=ROOT_SELF_HOSTED_RUNNER_CAN_ACCESS_FUTURE_LOCAL_SIGNER'; BLOCKS=$((BLOCKS+1)); }
[ "$WOWNER" != 'meme-alpha:meme-alpha' ] && { echo 'BLOCKER=WALLET_OWNER_INVALID'; BLOCKS=$((BLOCKS+1)); }
[ "$WMODE" != '700' ] && { echo 'BLOCKER=WALLET_MODE_INVALID'; BLOCKS=$((BLOCKS+1)); }
[ "$TRACKED_SENSITIVE" -gt 0 ] && { echo 'BLOCKER=TRACKED_SENSITIVE_FILENAME'; BLOCKS=$((BLOCKS+1)); }
[ "$PRIVATE_MARKER_FILES" -gt 0 ] && { echo 'BLOCKER=TRACKED_PRIVATE_KEY_MARKER'; BLOCKS=$((BLOCKS+1)); }
[ "$SUDO_RULES" -gt 0 ] && { echo 'BLOCKER=MEME_ALPHA_HAS_BROAD_SUDO'; BLOCKS=$((BLOCKS+1)); }

echo "SECURITY_BLOCKERS=$BLOCKS"
if [ "$BLOCKS" -eq 0 ]; then
  echo 'MICRO_LIVE_SECURITY_PREFLIGHT=PASS'
else
  echo 'MICRO_LIVE_SECURITY_PREFLIGHT=BLOCKED'
fi

echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_SECRET_READ_OR_PRINT=TRUE'
echo 'V140_SECURITY_PREFLIGHT_COMPLETE'
