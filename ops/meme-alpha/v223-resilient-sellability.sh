#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.3 RESILIENT SELLABILITY ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

B="code-backups/v223-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/scanner.js src/safe-signal-export.js "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('src/scanner.js'); s=p.read_text()
start=s.find('async function sellability(candidate) {')
end=s.find('\nconsole.log("=== MEME ALPHA SCANNER', start)
if start<0 or end<0: raise SystemExit('SELLABILITY_FUNCTION_NOT_FOUND')
new=r'''async function sellability(candidate) {
  const transient = (http, message='') => ({
    sellRoute: null,
    sellQuoteHttp: http ?? null,
    sellOutAmount: null,
    sellPriceImpactPct: null,
    sellQuoteError: message || 'SELLABILITY_TRANSIENT'
  });

  try {
    const decimals = Math.max(0, Math.min(12, Number(candidate.decimals ?? 6)));
    let tokens = 1;
    if (candidate.priceUsd > 0) {
      tokens = Math.min(1_000_000, Math.max(1, 1 / candidate.priceUsd));
    }
    const raw = BigInt(Math.max(1, Math.floor(tokens * 10 ** decimals)));
    const url = `${cfg.jupiter}/swap/v2/order` +
      `?inputMint=${candidate.mint}` +
      `&outputMint=${WSOL}` +
      `&amount=${raw}`;

    for (let attempt=0; attempt<2; attempt++) {
      try {
        const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
        let body = {};
        try { body = await r.json(); } catch { body = {}; }

        if (r.status === 429 || r.status >= 500) {
          if (attempt === 0) { await new Promise(x=>setTimeout(x,700)); continue; }
          return transient(r.status, `JUPITER_TRANSIENT_HTTP_${r.status}`);
        }

        if (!r.ok) {
          return {
            sellRoute: false,
            sellQuoteHttp: r.status,
            sellOutAmount: body.outAmount ?? null,
            sellPriceImpactPct: body.priceImpactPct ?? null,
            sellQuoteError: String(body.error || body.errorMessage || `JUPITER_HTTP_${r.status}`).slice(0,180)
          };
        }

        const ok = Boolean(body.outAmount) && Number(body.outAmount) > 0;
        return {
          sellRoute: ok,
          sellQuoteHttp: r.status,
          sellOutAmount: body.outAmount ?? null,
          sellPriceImpactPct: body.priceImpactPct ?? null,
          ...(ok ? {} : { sellQuoteError: 'NO_POSITIVE_OUT_AMOUNT' })
        };
      } catch (err) {
        if (attempt === 0) { await new Promise(x=>setTimeout(x,700)); continue; }
        return transient(null, String(err?.message || err).slice(0,180));
      }
    }
    return transient(null, 'SELLABILITY_RETRY_EXHAUSTED');
  } catch (err) {
    return transient(null, String(err?.message || err).slice(0,180));
  }
}
'''
s=s[:start]+new+s[end:]
old='''    if (!sell.sellRoute) {
      enriched.decision = "IGNORE";
      enriched.hardReject.push(
        "NO_SELL_ROUTE"
      );
    }

    const impact ='''
new2='''    if (sell.sellRoute === false) {
      enriched.decision = "IGNORE";
      enriched.hardReject.push(
        "NO_SELL_ROUTE"
      );
    } else if (sell.sellRoute !== true) {
      enriched.decision = "WATCH";
      enriched.reasons.push(
        "SELLABILITY_TEMPORARILY_UNAVAILABLE"
      );
    }

    const impact ='''
if old in s: s=s.replace(old,new2,1)
elif 'SELLABILITY_TEMPORARILY_UNAVAILABLE' not in s: raise SystemExit('SELLABILITY_DECISION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/scanner.js

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js'); s=p.read_text()
needle="sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):null,"
add="sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):null,sellQuoteHttp:c.sellQuoteHttp??null,sellQuoteError:c.sellQuoteError??null,"
if needle in s:s=s.replace(needle,add,1)
elif 'sellQuoteHttp:c.sellQuoteHttp??null' not in s:raise SystemExit('SAFE_SIGNAL_SELL_OBSERVABILITY_PATTERN_NOT_FOUND')
for oldv in ["version:'2.2.2'","version:'2.2.0'","version:'2.1.6'"]:
    if oldv in s:s=s.replace(oldv,"version:'2.2.3'",1);break
if "version:'2.2.3'" not in s:raise SystemExit('SAFE_SIGNAL_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 135
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status'; const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));
const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json');
const cs=sig.candidates||[], n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);
console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAIL=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`CANDIDATES=${cs.length} MEME=${n(x=>x.universeClass==='MEME_CONFIRMED')} SELL_TRUE=${n(x=>x.sellRoute===true)} SELL_FALSE=${n(x=>x.sellRoute===false&&x.sellQuoteHttp!=null)} SELL_TRANSIENT=${n(x=>x.sellRoute!==true&&String(x.sellQuoteError||'').includes('TRANSIENT'))}`);
console.log(`SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} PAPER_READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,12))console.log(`MEME ${x.symbol} score=${x.score} sec=${x.securityDecision} decision=${x.decision} sell=${x.sellRoute} http=${x.sellQuoteHttp} err=${x.sellQuoteError||'-'} persist=${x.persistenceDecision||'-'}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)} STRESS=${s.status}`);
console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
if(sig.version!=='2.2.3')throw new Error('SIGNAL_VERSION');
if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');
if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');
console.log('V223_RESILIENT_SELLABILITY_PASS');
NODE

echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
