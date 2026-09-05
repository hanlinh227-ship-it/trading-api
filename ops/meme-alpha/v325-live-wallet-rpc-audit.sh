#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SOCK=/run/meme-alpha-signer/signer.sock

echo '=== V325 READ-ONLY LIVE WALLET RPC AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ

node - "$SOCK" "$APP/config/runtime.json" <<'NODE'
const net=require('net'),fs=require('fs');
const [sock,cfgPath]=process.argv.slice(2);
function signerHealth(){return new Promise((resolve,reject)=>{const s=net.createConnection(sock);let d='';s.setTimeout(4000);s.on('connect',()=>s.write(JSON.stringify({op:'health'})+'\n'));s.on('data',b=>{d+=b; if(d.includes('\n')){try{resolve(JSON.parse(d.split('\n')[0]))}catch(e){reject(e)} try{s.destroy()}catch{}}});s.on('error',reject);s.on('timeout',()=>reject(new Error('SOCKET_TIMEOUT')));});}
async function main(){
 let h;
 try{h=await signerHealth()}catch(e){console.log('SIGNER_HEALTH_READ=DENIED_OR_UNAVAILABLE error='+String(e.message||e));process.exit(20)}
 console.log(`SIGNER_HEALTH ok=${h.ok===true} signingEnabled=${h.signingEnabled===true} walletLoaded=${h.walletLoaded===true} publicKey=${h.publicKey||''}`);
 if(!h.ok||!h.publicKey||!h.walletLoaded)process.exit(21);
 let cfg;try{cfg=JSON.parse(fs.readFileSync(cfgPath,'utf8'))}catch(e){console.log('RUNTIME_CONFIG_READ=FAILED');process.exit(22)}
 const rpc=cfg.rpc;if(!rpc){console.log('RPC_CONFIG_MISSING');process.exit(23)}
 async function call(method,params){const r=await fetch(rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(10000)});const j=await r.json();if(j.error)throw new Error(JSON.stringify(j.error));return j.result}
 const bal=await call('getBalance',[h.publicKey,{commitment:'confirmed'}]);
 console.log(`LIVE_SOL_BALANCE=${(Number(bal.value)/1e9).toFixed(9)} lamports=${bal.value}`);
 const toks=await call('getTokenAccountsByOwner',[h.publicKey,{programId:'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},{encoding:'jsonParsed',commitment:'confirmed'}]);
 const rows=[];
 for(const x of toks.value||[]){const info=x.account?.data?.parsed?.info||{};const a=info.tokenAmount||{};if(BigInt(a.amount||'0')>0n)rows.push({mint:info.mint,amount:a.uiAmountString||a.amount,decimals:a.decimals});}
 console.log('LIVE_NONZERO_TOKEN_ACCOUNTS='+rows.length);
 for(const r of rows.slice(0,50))console.log(`TOKEN mint=${r.mint} amount=${r.amount} decimals=${r.decimals}`);
}
main().catch(e=>{console.log('RPC_AUDIT_ERROR='+String(e.message||e).slice(0,500));process.exit(24)});
NODE

echo '=== SYSTEMD/PROCESS CONFLICT SNAPSHOT ==='
ps -eo pid,ppid,user,stat,args | grep -E '/opt/meme-alpha/app/(run-paper.sh|src/trend-pulse.js|src/micro-live-executor.js|src/new-listing-radar.js)|/opt/meme-alpha-signer/ready_signer.py' | grep -v grep || true

echo V325_LIVE_WALLET_RPC_AUDIT_PASS
