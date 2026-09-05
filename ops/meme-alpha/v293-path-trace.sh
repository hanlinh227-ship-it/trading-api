#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.9.3 PATH TRACE ==='
echo '--- run-paper.sh ---'; sed -n '1,260p' "$APP/run-paper.sh" 2>/dev/null || true
echo '--- gate source ---'; sed -n '1,260p' "$APP/src/micro-live-gate.js" 2>/dev/null || true
echo '--- risk source ---'; sed -n '1,220p' "$APP/src/risk.js" 2>/dev/null || true
echo '--- source health mentions ---'; grep -RniE 'source.?health|risk.?state|SOURCE_HEALTH|RISK_NOT_READY|risk-state|source-health' "$APP/src" "$APP/run-paper.sh" 2>/dev/null | head -n 300 || true
echo '--- matching files ---'; find "$APP" /var/lib/meme-alpha -maxdepth 6 -type f \( -iname '*source*health*' -o -iname '*risk*state*' -o -iname '*risk*.json' -o -iname '*health*.json' \) -printf '%p %TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null | sort || true
echo V293_PATH_TRACE_PASS
