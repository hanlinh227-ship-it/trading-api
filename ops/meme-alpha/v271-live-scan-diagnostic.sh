#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
cd "$APP"
echo '=== MEME ALPHA v2.7 LIVE SCAN DIAGNOSTIC ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const age=ts=>Number.isFinite(Date.parse(ts))?((Date.now()-Date.parse(ts))/1000):Infinity;
const s=read('/opt/meme-alpha/app/runtime-status/signal-snapshot.json');
const g=read('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
const cs=s.candidates||[];
console.log(`NOW=${new Date().toISOString()}`);
console.log(`SIGNAL_TS=${s.timestamp||'-'}`);
console.log(`SIGNAL_AGE_SEC=${age(s.timestamp).toFixed(1)}`);
console.log(`SOURCE_STATUS=${s.sourceHealth?.status||'-'}`);
console.log(`SUCCESSFUL_SOURCES=${s.sourceHealth?.successfulSources??'-'}`);
console.log(`USING_CACHE=${s.sourceHealth?.usingCache??'-'}`);
console.log(`TOTAL_CANDIDATES=${cs.length}`);
console.log(`MEME_CONFIRMED=${cs.filter(x=>x.universeClass==='MEME_CONFIRMED').length}`);
console.log(`GATE_ALLOWED=${g.allowed===true}`);
console.log(`EXECUTION_MODE=${g.executionMode||'-'}`);
console.log(`GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'}`);
const trend=cs.filter(x=>x.universeClass==='MEME_CONFIRMED'&&Number.isFinite(Number(x.priceChange5m))&&Number(x.priceChange5m)>0&&Number(x.priceChange5m)<=18&&Number(x.netBuyers5m)>0).sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,12);
console.log(`TREND_CANDIDATES=${trend.length}`);
for(const x of trend) console.log(`TREND ${x.symbol} score=${x.score} chg5m=${Number(x.priceChange5m).toFixed(2)} buyers5m=${x.netBuyers5m} organic=${x.organicRatio5m} liq=${Math.round(Number(x.liquidityUsd||0))} sec=${x.securityDecision} holder=${x.holderClusterDecision??'-'} sell=${x.sellRoute??'-'} persist=${x.persistenceDecision??'-'} elig=${x.consecutiveEligible||0}`);
const ready=cs.filter(c=>c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'&&!c.token2022&&c.sellRoute===true&&Number(c.score)>=82&&Number(c.liquidityUsd)>=50000&&Number.isFinite(Number(c.sellPriceImpactPct))&&Math.abs(Number(c.sellPriceImpactPct))<=1.25&&Number(c.consecutiveEligible||0)>=2&&Number(c.priceChange5m)>=0.30&&Number(c.priceChange5m)<=18&&Number(c.netBuyers5m)>=3&&Number(c.avgNetBuyersLast2)>=3&&Number(c.scoreSlopeLast2)>=0&&c.liquidityStableLast2===true);
console.log(`REAL_BUY_READY=${ready.length}`);
for(const c of ready.slice(0,8)) console.log(`READY ${c.symbol} score=${c.score} chg5m=${c.priceChange5m} buyers=${c.netBuyers5m} liq=${Math.round(Number(c.liquidityUsd||0))}`);
NODE
echo '=== SERVICES ==='
echo -n 'PAPER='; systemctl is-active meme-alpha-paper.service || true
echo -n 'SIGNER='; systemctl is-active meme-alpha-signer.service || true
echo -n 'MICRO='; systemctl is-active meme-alpha-micro-live.service || true
systemctl show meme-alpha-paper.service meme-alpha-micro-live.service -p MainPID -p ActiveState -p SubState --no-pager || true
echo V271_LIVE_SCAN_DIAGNOSTIC_PASS
