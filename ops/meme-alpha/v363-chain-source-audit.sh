#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
WALLET='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk'
SC="$APP/src/scanner.js"
OBS="$APP/runtime-status/portfolio-observability.json"

echo '=== V363 CHAIN + SOURCE AUDIT ==='
echo NOW_UTC=$(date -u +%FT%TZ)
echo '--- scanner source topology ---'
grep -nEi 'sourceHealth|successfulSources|failedSources|usingCache|allowNewEntries|fetch\(|https://|jupiter|dexscreener|birdeye|helius|recent|trending|organic' "$SC" 2>/dev/null | head -n 220 || true

echo '--- runtime config non-secret topology ---'
node - "$APP/config/runtime.json" <<'NODE'
const fs=require('fs');let x={};try{x=JSON.parse(fs.readFileSync(process.argv[2]))}catch{}
for(const [k,v] of Object.entries(x)){if(/key|secret|token|private|credential|pass/i.test(k))continue;if(typeof v==='string'&&/^https?:/.test(v)){try{const u=new URL(v);console.log(`${k}=${u.protocol}//${u.host}${u.pathname}`)}catch{}}else if(/rpc|source|provider|endpoint/i.test(k))console.log(`${k}=${typeof v==='string'?v:JSON.stringify(v)}`)}
NODE

echo '--- chain reconciliation ---'
node - "$APP/config/runtime.json" "$OBS" "$WALLET" <<'NODE'
const fs=require('fs');
const cfg=JSON.parse(fs.readFileSync(process.argv[2]));const obs=JSON.parse(fs.readFileSync(process.argv[3]));const wallet=process.argv[4];
async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});const j=await r.json();if(j.error)throw new Error(`${method}:${j.error.code}:${j.error.message}`);return j.result}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 let acc=[];try{const x=await rpc('getTokenAccountsByOwner',[wallet,{programId:'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},{encoding:'jsonParsed',commitment:'confirmed'}]);acc=x.value||[]}catch(e){console.log('TOKEN_ACCOUNTS_RPC_ERROR='+e.message);process.exit(2)}
 const chain=new Map();for(const a of acc){const i=a.account?.data?.parsed?.info;if(!i?.mint)continue;const amt=Number(i.tokenAmount?.uiAmountString||i.tokenAmount?.uiAmount||0);if(amt>0)chain.set(i.mint,amt)}
 const stateMints=new Set(obs.positionMints||[]), chainMints=new Set(chain.keys());
 const ghosts=[...stateMints].filter(m=>!chainMints.has(m));const unmanaged=[...chainMints].filter(m=>!stateMints.has(m));
 console.log('OBS_STATE_READABLE='+obs.stateReadable);console.log('OBS_OPEN_POSITIONS='+obs.openPositions);console.log('CHAIN_NONZERO_TOKEN_MINTS='+chain.size);
 for(const m of [...stateMints].sort())console.log(`STATE_MINT ${m} CHAIN_AMOUNT=${chain.get(m)||0}`);
 console.log('GHOST_STATE_MINTS='+JSON.stringify(ghosts));console.log('UNMANAGED_CHAIN_MINTS='+JSON.stringify(unmanaged));
 console.log('CHAIN_STATE_CONSISTENT='+(ghosts.length===0&&unmanaged.length===0));
 try{const bal=await rpc('getBalance',[wallet,{commitment:'confirmed'}]);console.log('LIVE_SOL='+(Number(bal.value)/1e9).toFixed(9))}catch(e){console.log('BALANCE_RPC_ERROR='+e.message)}
 await sleep(350);
 try{const sigs=await rpc('getSignaturesForAddress',[wallet,{limit:12,commitment:'confirmed'}]);for(const s of sigs)console.log(`SIG ${s.blockTime?new Date(s.blockTime*1000).toISOString():'NA'} ${s.signature} err=${JSON.stringify(s.err)}`)}catch(e){console.log('SIGNATURE_RPC_ERROR='+e.message)}
})().catch(e=>{console.error(e);process.exit(1)})
NODE

echo '--- latest source health snapshots ---'
for f in "$APP/runtime-status/signal-snapshot.json" "$APP/runtime-status/micro-live-gate.json"; do [ -f "$f" ] && { echo "### $f"; cat "$f"; }; done

echo V363_CHAIN_SOURCE_AUDIT=COMPLETE
