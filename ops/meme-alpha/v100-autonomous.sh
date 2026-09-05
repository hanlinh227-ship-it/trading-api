#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v1.1 HARDENING INSPECTION ==='
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('JUPITER='+c.jupiter);
NODE

echo '=== RISK FULL ==='
sed -n '1,520p' src/risk.js

echo '=== VALIDATION FULL ==='
sed -n '1,520p' src/validation.js

echo '=== PERSISTENCE KEY SECTIONS ==='
grep -nE 'version|generatedAt|updatedAt|persistenceDecision|positionId|PAPER_ENTRY_READY|STALE|observations' src/persistence.js || true
sed -n '1,380p' src/persistence.js

echo '=== PACKAGE CYCLE ==='
cat package.json

echo '=== SOURCE HEALTH ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json 2>/dev/null || true

echo '=== RISK STATE ==='
cat /var/lib/meme-alpha/data/paper/risk-state.json 2>/dev/null || true

echo '=== PAPER SUMMARY ==='
node src/paper.js || true

echo '=== SERVICE ==='
systemctl --no-pager is-active meme-alpha-paper.service || true
systemctl --no-pager is-enabled meme-alpha-paper.service || true

echo 'V110_INSPECTION_COMPLETE'
