#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
PUB='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk'
CFG="$APP/config/runtime.json"

echo '=== V326 PHANTOM PUBLIC CHAIN AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ
node - "$PUB" "$CFG" <<'NODE'
const fs=require('fs');
const [pub,cfgPath]=process.argv.slice(2);
const cfg=JSON.parse(fs.readFileSync(cfgPath,'utf8'));
const rpc=cfg.rpc;if(!rpc)throw new Error('RPC_CONFIG_MISSING');
async function call(method,params){
  const r=await fetch(rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(15000)});
  const j=await r.json(); if(j.error) throw new Error(method+':'+JSON.stringify(j.error)); return j.result;
}
function tokMap(arr){const m=new Map();for(const x of arr||[]){if(x.owner!==pub)continue;const a=x.uiTokenAmount||{};m.set(x.mint,{raw:BigInt(a.amount||'0'),dec:Number(a.decimals||0)});}return m}
function ui(raw,dec){return Number(raw)/10**dec}
async function main(){
  const bal=await call('getBalance',[pub,{commitment:'confirmed'}]);
  console.log(`PHANTOM_PUBLIC_KEY=${pub}`);
  console.log(`LIVE_SOL_BALANCE=${(Number(bal.value)/1e9).toFixed(9)} lamports=${bal.value}`);
  const programs=['TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'];
  const holdings=[];
  for(const programId of programs){
    const res=await call('getTokenAccountsByOwner',[pub,{programId},{encoding:'jsonParsed',commitment:'confirmed'}]);
    for(const x of res.value||[]){const info=x.account?.data?.parsed?.info||{};const a=info.tokenAmount||{};if(BigInt(a.amount||'0')>0n)holdings.push({programId,mint:info.mint,amount:a.uiAmountString||String(a.uiAmount||0),raw:a.amount,decimals:a.decimals});}
  }
  console.log(`LIVE_NONZERO_TOKEN_ACCOUNTS=${holdings.length}`);
  for(const h of holdings.slice(0,100)) console.log(`HOLDING mint=${h.mint} amount=${h.amount} decimals=${h.decimals} program=${h.programId===programs[0]?'SPL':'TOKEN2022'}`);

  const sigs=await call('getSignaturesForAddress',[pub,{limit:20,commitment:'confirmed'}]);
  console.log(`RECENT_SIGNATURES=${sigs.length}`);
  let material=0;
  for(const s of sigs){
    let tx; try{tx=await call('getTransaction',[s.signature,{encoding:'jsonParsed',commitment:'confirmed',maxSupportedTransactionVersion:0}])}catch(e){console.log(`TX_FETCH_FAIL sig=${s.signature} err=${String(e.message||e).slice(0,120)}`);continue}
    if(!tx?.meta) continue;
    const keys=(tx.transaction?.message?.accountKeys||[]).map(k=>typeof k==='string'?k:k.pubkey);
    const idx=keys.indexOf(pub);
    const solDelta=idx>=0?(Number(tx.meta.postBalances[idx])-Number(tx.meta.preBalances[idx]))/1e9:0;
    const pre=tokMap(tx.meta.preTokenBalances),post=tokMap(tx.meta.postTokenBalances);
    const mints=new Set([...pre.keys(),...post.keys()]);
    const deltas=[];
    for(const mint of mints){const a=pre.get(mint)||{raw:0n,dec:(post.get(mint)||{}).dec||0},b=post.get(mint)||{raw:0n,dec:a.dec};const d=b.raw-a.raw;if(d!==0n)deltas.push({mint,delta:ui(d,b.dec||a.dec),raw:d.toString(),dec:b.dec||a.dec});}
    if(Math.abs(solDelta)>0.000001||deltas.length){
      material++;
      console.log(`TX time=${s.blockTime?new Date(s.blockTime*1000).toISOString():'unknown'} sig=${s.signature} err=${s.err?JSON.stringify(s.err):'null'} solDelta=${solDelta.toFixed(9)}`);
      for(const d of deltas) console.log(`  TOKEN_DELTA mint=${d.mint} delta=${d.delta} raw=${d.raw} decimals=${d.dec}`);
    }
  }
  console.log(`RECENT_MATERIAL_TX=${material}`);
}
main().catch(e=>{console.error('V326_ERROR='+String(e.message||e).slice(0,500));process.exit(1)});
NODE

echo '=== LIVE GATE SUMMARY ==='
node - <<'NODE'
const fs=require('fs');const p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';
try{const g=JSON.parse(fs.readFileSync(p,'utf8'));console.log(JSON.stringify({timestamp:g.timestamp,allowed:g.allowed,riskEntryAllowed:g.riskEntryAllowed,paperRiskEntryAllowed:g.paperRiskEntryAllowed,riskLiveBlockReasons:g.riskLiveBlockReasons,reasons:g.reasons},null,0))}catch(e){console.log('GATE_UNREADABLE')}
NODE

echo V326_PHANTOM_PUBLIC_CHAIN_AUDIT_PASS
