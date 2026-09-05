#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V357_BOOTSTRAP_FAIL=ROOT_REQUIRED; exit 1; }
WRAP=/usr/local/sbin/meme-alpha-safe-deploy
cat > "$WRAP" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
BASE=/opt/meme-alpha/app/runtime-status/deploy-candidates
APP=/opt/meme-alpha/app
[ "$#" -eq 3 ] || { echo SAFE_DEPLOY_FAIL=ARGS; exit 2; }
COMP="$1"; NAME="$2"; EXPECT="$3"
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo SAFE_DEPLOY_FAIL=NAME; exit 2; }
[[ "$EXPECT" =~ ^[a-f0-9]{64}$ ]] || { echo SAFE_DEPLOY_FAIL=SHA; exit 2; }
SRC="$BASE/$NAME"
[ -f "$SRC" ] && [ ! -L "$SRC" ] || { echo SAFE_DEPLOY_FAIL=SOURCE; exit 2; }
REAL=$(readlink -f "$SRC"); [[ "$REAL" == "$BASE/"* ]] || { echo SAFE_DEPLOY_FAIL=PATH; exit 2; }
ACT=$(sha256sum "$SRC" | awk '{print $1}'); [ "$ACT" = "$EXPECT" ] || { echo SAFE_DEPLOY_FAIL=HASH_MISMATCH; exit 2; }
case "$COMP" in
  executor) DST="$APP/src/micro-live-executor.js"; SERVICE=meme-alpha-micro-live.service; ARM=/etc/meme-alpha/micro-live-armed ;;
  whale) DST="$APP/src/whale-flow-intel.js"; SERVICE=meme-alpha-whale-flow.service; ARM= ;;
  realtime) DST="$APP/src/realtime-pool-pulse.js"; SERVICE=meme-alpha-realtime-pulse.service; ARM= ;;
  radar) DST="$APP/src/new-listing-radar.js"; SERVICE=meme-alpha-paper.service; ARM= ;;
  trend) DST="$APP/src/trend-pulse.js"; SERVICE=meme-alpha-trend-pulse.service; ARM= ;;
  scanner) DST="$APP/src/scanner.js"; SERVICE=meme-alpha-paper.service; ARM= ;;
  signal) DST="$APP/src/safe-signal-export.js"; SERVICE=meme-alpha-paper.service; ARM= ;;
  gate) DST="$APP/src/micro-live-gate.js"; SERVICE=meme-alpha-paper.service; ARM= ;;
  *) echo SAFE_DEPLOY_FAIL=COMPONENT; exit 2 ;;
esac
runuser -u github-runner -- /usr/bin/node --check "$SRC"
STAMP=$(date -u +%Y%m%dT%H%M%SZ); B="$APP/runtime-status/safe-deploy-backup-$STAMP-$COMP"; mkdir -p "$B"; cp -a "$DST" "$B/old.js"
ARM_BAK=''; if [ -n "${ARM:-}" ]; then ARM_BAK="$B/arm"; cp -a "$ARM" "$ARM_BAK"; printf 'ARMED=NO\n' > "$ARM"; systemctl stop "$SERVICE"; fi
rollback(){ rc=$?; if [ $rc -ne 0 ]; then cp -a "$B/old.js" "$DST" || true; if [ -n "$ARM_BAK" ] && [ -f "$ARM_BAK" ]; then cp -a "$ARM_BAK" "$ARM" || true; fi; systemctl restart "$SERVICE" || true; echo SAFE_DEPLOY_ROLLBACK=TRUE; fi; exit $rc; }
trap rollback EXIT
install -o root -g root -m 0644 "$SRC" "$DST"
if [ -n "$ARM_BAK" ] && [ -f "$ARM_BAK" ]; then cp -a "$ARM_BAK" "$ARM"; fi
systemctl restart "$SERVICE"; sleep 4; systemctl is-active --quiet "$SERVICE"
if [ "$COMP" = executor ]; then [ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]; fi
echo SAFE_DEPLOY_COMPONENT="$COMP"; echo SAFE_DEPLOY_SHA="$ACT"; echo SAFE_DEPLOY_BACKUP="$B"; echo SAFE_DEPLOY_SUCCESS=TRUE
trap - EXIT
WRAPPER
chown root:root "$WRAP"; chmod 0755 "$WRAP"
cat > /etc/sudoers.d/meme-alpha-safe-deploy <<'SUDO'
github-runner ALL=(root) NOPASSWD: /usr/local/sbin/meme-alpha-safe-deploy *
SUDO
chown root:root /etc/sudoers.d/meme-alpha-safe-deploy; chmod 0440 /etc/sudoers.d/meme-alpha-safe-deploy
visudo -cf /etc/sudoers.d/meme-alpha-safe-deploy >/dev/null
mkdir -p /opt/meme-alpha/app/runtime-status/deploy-candidates
chown github-runner:meme-alpha-deploy /opt/meme-alpha/app/runtime-status/deploy-candidates
chmod 2775 /opt/meme-alpha/app/runtime-status/deploy-candidates
# Activate the already staged v3.56 hardening in this same one-time root bootstrap.
if [ -x /opt/meme-alpha/app/runtime-status/v356-stage/install-v356.sh ]; then
  /opt/meme-alpha/app/runtime-status/v356-stage/install-v356.sh
fi
echo V357_SAFE_AUTODEPLOY_BOOTSTRAP_ACTIVE=TRUE
