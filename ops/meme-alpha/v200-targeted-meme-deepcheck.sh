#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.0 TARGETED MEME DEEPCHECK ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE

B="code-backups/v200-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/scanner.js src/universe.js "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('src/scanner.js')
s=p.read_text()
old='''// Deep-check only best 20 to avoid API spam\nconst deep =\n  preliminary.slice(0, 20);'''
new='''// v2.0: keep the best 20, then add at most 6 high-signal meme/launchpad candidates.\n// This preserves rate-limit headroom while preventing credible memes just below the\n// global top-20 from being invisible to DEX/sellability checks.\nconst baseDeep = preliminary.slice(0, 20);\nconst baseMints = new Set(baseDeep.map(x => x.result?.mint));\nconst canonicalMemeMints = new Set([\n  "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", // dogwifhat\n  "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv", // PENGU\n  "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9"  // GIGA\n]);\nconst memeHint = /(?:meme|doge|shib|pepe|bonk|wif|dogwifhat|cat|dog|frog|goat|ape|pnut|peanut|popcat|chillguy|fart|pengu|pudgy|wojak|mog|floki|inu|giga|gigachad|troll)/i;\nconst extraMeme = preliminary\n  .slice(20)\n  .filter(x => {\n    const r=x.result||{};\n    const mint=String(r.mint||"");\n    const text=`${r.symbol||""} ${r.name||""}`;\n    return !baseMints.has(mint) && (mint.toLowerCase().endsWith("pump") || canonicalMemeMints.has(mint) || memeHint.test(text));\n  })\n  .slice(0, 6);\nconst deep = [...baseDeep, ...extraMeme];\nconsole.log(`DEEPCHECK_BASE=${baseDeep.length} MEME_EXTRA=${extraMeme.length} TOTAL=${deep.length}`);'''
if old not in s:
    raise SystemExit('SCANNER_DEEPCHECK_BLOCK_NOT_FOUND')
s=s.replace(old,new,1)
p.write_text(s)
PY

python3 - <<'PY'
from pathlib import Path
p=Path('src/universe.js')
s=p.read_text()
old="const MEME_TERMS=/\\b(meme|memecoin|doge|shib|pepe|bonk|wif|cat|kitty|kitten|dog|doggo|frog|goat|monkey|ape|pnut|peanut|popcat|chillguy|fart|moo|pengu|pudgy|wojak|mog|brett|floki|inu|hamster|capy|hippo|sigma|gigachad|chad)\\b/i;"
new="""const CANONICAL_MEME_MINTS=new Set(['EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm','2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv','63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9']);\nconst MEME_TERMS=/(?:\\b(meme|memecoin|doge|shib|pepe|bonk|wif|cat|kitty|kitten|dog|doggo|frog|goat|monkey|ape|pnut|peanut|popcat|chillguy|fart|moo|pengu|pudgy|penguin|wojak|mog|brett|floki|inu|hamster|capy|hippo|sigma|gigachad|giga|chad|troll)\\b|dogwifhat)/i;"""
if old not in s:
    raise SystemExit('UNIVERSE_MEME_TERMS_NOT_FOUND')
s=s.replace(old,new,1)
needle=""" if(reasons.length) return {universeClass:'NON_MEME',universeConfidence:'HIGH',reasons};\n const sourceCount=new Set(c.sources||[]).size;"""
repl=""" if(reasons.length) return {universeClass:'NON_MEME',universeConfidence:'HIGH',reasons};\n if(CANONICAL_MEME_MINTS.has(mint)) return {universeClass:'MEME_CONFIRMED',universeConfidence:'HIGH',reasons:['CANONICAL_MEME_MINT']};\n const sourceCount=new Set(c.sources||[]).size;"""
if needle not in s:
    raise SystemExit('UNIVERSE_CLASSIFY_NEEDLE_NOT_FOUND')
s=s.replace(needle,repl,1)
s=s.replace("version:'1.6'","version:'1.6.1'",1)
p.write_text(s)
PY

# Replace with runner-owned readable inodes where needed.
for f in src/scanner.js src/universe.js; do
  node --check "$f"
  chmod 664 "$f" 2>/dev/null || true
done

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 155
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

echo '=== SOAK CHECK ==='
LOG=$(journalctl -u meme-alpha-paper.service --since '-150 seconds' --no-pager || true)
printf '%s\n' "$LOG" | tail -n 80
HTTP429=$(printf '%s\n' "$LOG" | grep -c 'HTTP 429\|HTTP429\|status 429' || true)
CYCLEFAIL=$(printf '%s\n' "$LOG" | grep -c 'FULL_CYCLE_FAILED\|CYCLE_FAILED' || true)
PERMFAIL=$(printf '%s\n' "$LOG" | grep -c 'EACCES\|Permission denied' || true)
echo "HTTP429=$HTTP429"; echo "CYCLE_FAILURES=$CYCLEFAIL"; echo "PERMISSION_FAILURES=$PERMFAIL"
[ "$HTTP429" -eq 0 ]
[ "$CYCLEFAIL" -eq 0 ]
[ "$PERMFAIL" -eq 0 ]

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const u=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/universe.json','utf8'));
const g=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));
const s=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/signal-snapshot.json','utf8'));
console.log(`SOURCE_STATUS=${h.status} SUCCESS=${h.successfulSources} FAIL=${h.failedSources} CACHE=${h.usingCache}`);
console.log(`UNIVERSE_VERSION=${u.version} MEME_CONFIRMED=${u.memeConfirmed} NON_MEME=${u.nonMemeBlocked} UNCLASSIFIED=${u.unclassifiedBlocked}`);
console.log(`GATE_ALLOWED=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
const names=['TROLL','$WIF','WIF','PENGU','GIGA'];
for(const c of s.candidates||[]){if(names.includes(String(c.symbol||'').toUpperCase())||['TROLL','PENGU','GIGACHAD','dogwifhat'].includes(c.name)) console.log(`RECALL ${c.symbol} ${c.name} class=${c.universeClass} security=${c.securityDecision} decision=${c.decision}`)}
if(h.status!=='HEALTHY'||Number(h.successfulSources)<2||h.usingCache===true) throw new Error('SOURCE_HEALTH_INVARIANT');
if(u.version!=='1.6.1'||u.unknownEntryEligible!==false) throw new Error('UNIVERSE_INVARIANT');
if(g.allowed!==false||g.executionMode!=='DISABLED') throw new Error('LIVE_GATE_INVARIANT');
console.log('V200_TARGETED_DEEPCHECK_SOAK_PASS');
NODE

echo 'WALLET_CREATED=FALSE'; echo 'LIVE_EXECUTION=FALSE'; echo "BACKUP=$B"
