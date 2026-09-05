#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V300 PAPER LOOP AUDIT R2 ==='
echo '=== FILE OWNERSHIP / WRITABILITY ==='
for f in run-paper.sh src/paper.js src/scanner.js src/safe-signal-export.js config/runtime.json runtime-status/signal-snapshot.json; do
  [ -e "$f" ] || continue
  stat -c '%n owner=%U group=%G mode=%a size=%s' "$f" || true
  if [ -w "$f" ]; then echo "$f WRITABLE=TRUE"; else echo "$f WRITABLE=FALSE"; fi
done

echo '=== PAPER SERVICE UNIT ==='
systemctl cat meme-alpha-paper.service 2>/dev/null | sed -E 's/(Environment=.*(TOKEN|KEY|SECRET|PASSWORD|PRIVATE).*)/Environment=[REDACTED]/I' | head -160 || true

echo '=== RUN PAPER LAUNCHER ==='
if [ -r run-paper.sh ]; then
  nl -ba run-paper.sh | sed -n '1,260p' | sed -E 's/(TOKEN|KEY|SECRET|PASSWORD|PRIVATE)[^ =]*=.*/\1=[REDACTED]/I'
fi

echo '=== PAPER JS ==='
if [ -r src/paper.js ]; then
  nl -ba src/paper.js | sed -n '1,260p' | sed -E 's/(token|secret|private[_-]?key|password)[[:space:]]*[:=][[:space:]]*[^,; ]+/\1=[REDACTED]/Ig'
fi

echo '=== SAFE SIGNAL EXPORT ==='
if [ -r src/safe-signal-export.js ]; then
  nl -ba src/safe-signal-export.js | sed -n '1,220p' | sed -E 's/(token|secret|private[_-]?key|password)[[:space:]]*[:=][[:space:]]*[^,; ]+/\1=[REDACTED]/Ig'
fi

echo '=== SCANNER TIMING / EXPORT CALLS ==='
if [ -r src/scanner.js ]; then
  grep -nEi 'setInterval|setTimeout|sleep|delay|interval|safe-signal|signal-snapshot|writeFile|timestamp|updatedAt|generatedAt|liveExecution' src/scanner.js | head -180 || true
fi

echo '=== RUNTIME JSON SAFE KEYS ==='
if [ -r config/runtime.json ]; then
 node - <<'NODE' || true
const fs=require('fs');
try { const x=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
 const out={}; const re=/(interval|poll|scan|signal|fresh|cycle|mode|live|paper|risk|slippage|impact|exposure)/i;
 for(const [k,v] of Object.entries(x)) if(re.test(k) && (typeof v==='number'||typeof v==='boolean'||typeof v==='string')) out[k]=v;
 console.log(JSON.stringify(out,null,2)); } catch(e){console.log('RUNTIME_JSON_PARSE_SKIP')}
NODE
fi

echo 'V300_PAPER_LOOP_AUDIT_R2_PASS'
