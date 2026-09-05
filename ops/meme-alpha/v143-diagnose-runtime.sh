#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== RUN-PAPER ==='
sed -n '1,220p' run-paper.sh || true
echo '=== PACKAGE ==='
cat package.json || true
echo '=== SERVICE ==='
sudo -n /bin/systemctl is-active meme-alpha-paper.service || true
sudo -n /bin/systemctl is-enabled meme-alpha-paper.service || true
echo '=== RUNTIME STATUS DIR ==='
ls -la runtime-status 2>&1 || true
echo '=== MICRO LIVE GATE FILE ==='
ls -l src/micro-live-gate.js 2>&1 || true
echo 'V143_DIAG_COMPLETE'
