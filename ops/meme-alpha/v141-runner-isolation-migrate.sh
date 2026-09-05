#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
RUNNER_DIR=/opt/actions-runner/actions-runner
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
RUNNER_USER=github-runner
RUNNER_GROUP=github-runner
DEPLOY_GROUP=meme-alpha-deploy
DROPIN=/etc/systemd/system/${RUNNER_UNIT}.d
BACKUP=/var/lib/meme-alpha/data/backups/v141-runner-isolation-$(date -u +%Y%m%d-%H%M%S)

cd "$APP"
echo '=== MEME ALPHA v1.4.1 RUNNER ISOLATION MIGRATION ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

[ "$(id -u)" -eq 0 ] || { echo 'ABORT_REQUIRES_CURRENT_ROOT_RUNNER'; exit 1; }
systemctl is-active --quiet "$RUNNER_UNIT"
systemctl is-active --quiet meme-alpha-paper.service
[ -d "$RUNNER_DIR" ]

mkdir -p "$BACKUP"
cp -a "/etc/systemd/system/$RUNNER_UNIT" "$BACKUP/runner.service"
cp -a "$RUNNER_DIR/.runner" "$BACKUP/runner.metadata" 2>/dev/null || true
stat -c '%U:%G %a %n' /var/lib/meme-alpha/wallet > "$BACKUP/wallet-perms-before.txt" 2>/dev/null || true

echo "BACKUP=$BACKUP"

if ! getent group "$RUNNER_GROUP" >/dev/null; then
  groupadd --system "$RUNNER_GROUP"
fi
if ! id "$RUNNER_USER" >/dev/null 2>&1; then
  useradd --system --gid "$RUNNER_GROUP" --home-dir "$RUNNER_DIR" --shell /usr/sbin/nologin "$RUNNER_USER"
fi
if ! getent group "$DEPLOY_GROUP" >/dev/null; then
  groupadd --system "$DEPLOY_GROUP"
fi
usermod -a -G "$DEPLOY_GROUP" "$RUNNER_USER"
usermod -a -G "$DEPLOY_GROUP" meme-alpha

# Runner owns only its own installation/workspace, never Meme Alpha wallet.
chown -R "$RUNNER_USER:$RUNNER_GROUP" "$RUNNER_DIR"
chmod 700 "$RUNNER_DIR/.credentials_rsaparams" 2>/dev/null || true
chmod 600 "$RUNNER_DIR/.credentials" "$RUNNER_DIR/.runner" "$RUNNER_DIR/.env" "$RUNNER_DIR/.path" 2>/dev/null || true
find "$RUNNER_DIR" -maxdepth 1 -type d -exec chmod 755 {} +
chmod 700 "$RUNNER_DIR/_diag" 2>/dev/null || true

# App may be deployed by the unprivileged runner, but wallet remains private to meme-alpha.
chown -R meme-alpha:"$DEPLOY_GROUP" /opt/meme-alpha/app
find /opt/meme-alpha/app -type d -exec chmod 2775 {} +
find /opt/meme-alpha/app -type f -exec chmod g+rw,o-rwx {} +
find /opt/meme-alpha/app -type f \( -name '*.sh' -o -name 'run-paper.sh' \) -exec chmod 775 {} +

chown meme-alpha:meme-alpha /var/lib/meme-alpha/wallet
chmod 700 /var/lib/meme-alpha/wallet
find /var/lib/meme-alpha/wallet -type f -exec chown meme-alpha:meme-alpha {} + -exec chmod 600 {} + 2>/dev/null || true

# Narrow restart capability only. No shell, editor, arbitrary systemctl, or signer access.
cat > /etc/sudoers.d/github-runner-meme-alpha <<'EOF'
Defaults:github-runner !requiretty
Cmnd_Alias MEME_ALPHA_PAPER_CTL = /bin/systemctl restart meme-alpha-paper.service, /bin/systemctl is-active meme-alpha-paper.service, /bin/systemctl is-enabled meme-alpha-paper.service
 github-runner ALL=(root) NOPASSWD: MEME_ALPHA_PAPER_CTL
EOF
chmod 440 /etc/sudoers.d/github-runner-meme-alpha
visudo -cf /etc/sudoers.d/github-runner-meme-alpha >/dev/null

mkdir -p "$DROPIN"
cat > "$DROPIN/10-isolation.conf" <<EOF
[Service]
User=$RUNNER_USER
Group=$RUNNER_GROUP
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
EOF
systemctl daemon-reload

# Pre-restart invariants.
[ "$(stat -c %U /var/lib/meme-alpha/wallet)" = meme-alpha ]
[ "$(stat -c %a /var/lib/meme-alpha/wallet)" = 700 ]
[ "$(stat -c %U "$RUNNER_DIR")" = "$RUNNER_USER" ]
getent group "$DEPLOY_GROUP" | grep -q "$RUNNER_USER"
getent group "$DEPLOY_GROUP" | grep -q 'meme-alpha'

printf 'RUNNER_TARGET_USER=%s\n' "$RUNNER_USER"
printf 'RUNNER_TARGET_GROUP=%s\n' "$RUNNER_GROUP"
echo 'RUNNER_SUDO=LIMITED_PAPER_RESTART_ONLY'
echo 'WALLET_OWNER=meme-alpha:meme-alpha'
echo 'WALLET_MODE=700'
echo 'WALLET_FILE_COUNT='"$(find /var/lib/meme-alpha/wallet -maxdepth 1 -type f | wc -l)"
echo 'BOT_WALLET=NOT_CREATED'
echo 'PRE_RESTART_INVARIANT_PASS'

# Restart after this workflow has had time to finish and upload logs.
unit_name="meme-alpha-runner-cutover-$(date +%s)"
systemd-run --unit="$unit_name" --on-active=15s /bin/systemctl restart "$RUNNER_UNIT" >/dev/null
echo "CUTOVER_SCHEDULED_UNIT=$unit_name"
echo 'CUTOVER_DELAY_SEC=15'
echo 'V141_MIGRATION_STAGED_PASS'
