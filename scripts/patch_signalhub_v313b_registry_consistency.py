from pathlib import Path
import re

W=Path('signalhub-worker/gateway-v3.js')
w=W.read_text()

def must(old,new,label):
    global w
    if old not in w: raise SystemExit(f'{label}: pattern missing')
    w=w.replace(old,new,1)

def sub(pattern,repl,label):
    global w
    w2,n=re.subn(pattern,repl,w,count=1,flags=re.S)
    if n!=1: raise SystemExit(f'{label}: expected 1 got {n}')
    w=w2

# The Durable Object is the strong-consistency authority for the ACTIVE book.
# KV remains the durable/history store but is eventually consistent across PoPs.
must(
"  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO');}",
"  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO'&&String(x.engineVersion||'')===V3_VERSION);}",
'active rows current engine')

must(
"    if(req.method==='GET'&&url.pathname==='/portfolio-snapshot'){return new Response(JSON.stringify(await this.portfolioSnapshot()),{headers:{'content-type':'application/json'}});}",
"    if(req.method==='GET'&&url.pathname==='/active-signals'){const rows=this.activeRows(await this.registry()).map(x=>{const y={...x};delete y.kvKey;return y;});return new Response(JSON.stringify({ok:true,rows,portfolio:this.portfolioFrom(await this.registry())}),{headers:{'content-type':'application/json'}});}\n    if(req.method==='GET'&&url.pathname==='/portfolio-snapshot'){return new Response(JSON.stringify(await this.portfolioSnapshot()),{headers:{'content-type':'application/json'}});}",
'active signals endpoint')

# Add strongly-consistent active-book helper plus best-effort KV repair.
marker="async function getActiveBook(env){"
if marker not in w: raise SystemExit('getActiveBook marker missing')
helper=r'''async function realtimeActiveSignals(env){
  const stub=mt5LiveStub(env);if(!stub)return[];
  try{const r=await stub.fetch('https://mt5-live/active-signals',{method:'GET'});if(!r.ok)return[];const p=await r.json();return Array.isArray(p?.rows)?p.rows.filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO'&&String(x.engineVersion||'')===V3_VERSION):[];}catch{return[];}
}
async function repairRealtimeActiveKv(env,rows){
  if(!env?.SIGNALS_KV||!Array.isArray(rows)||!rows.length)return;
  await Promise.all(rows.map(async s=>{try{const clean={...s};delete clean.kvKey;const key=v31Prefix('CRYPTO',clean.style)+clean.id;await env.SIGNALS_KV.put(key,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put(activePointer('CRYPTO',clean.style,clean.symbol),clean.id,{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put(activeAnyPointer('CRYPTO',clean.symbol),clean.id,{expirationTtl:SIGNAL_TTL});}catch{}}));
}
'''
w=w.replace(marker,helper+marker,1)

sub(r"async function getActiveBook\(env\)\{.*?\n\}",r'''async function getActiveBook(env){
  const realtime=await realtimeActiveSignals(env);if(realtime.length){await repairRealtimeActiveKv(env,realtime);return realtime;}
  const out=[];for(const style of ['SCALP','SWING']){const rows=await getV31Signals(env,'CRYPTO',style);for(const s of rows)if((s.status==='PENDING'||s.status==='OPEN')&&String(s.engineVersion||'')===V3_VERSION)out.push(s);}return out;
}''','getActiveBook strong consistency')

# Active API must read from DO so a fresh reservation is visible immediately from every PoP.
sub(r"async function unifiedSignals\(url,env,ctx\)\{.*?\n\}\n\nasync function unifiedPerformance",r'''async function unifiedSignals(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',status=String(url.searchParams.get('status')||'active').toLowerCase(),limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  const rt=await realtimeActiveSignals(env);if(rt.length&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(repairRealtimeActiveKv(env,rt)).catch(()=>{}));
  let rows;
  if(status==='active')rows=rt.filter(s=>String(s.style||'').toUpperCase()===style);
  else{
    const kv=await getV31Signals(env,market,style),by=new Map(kv.map(x=>[x.id,x]));for(const x of rt.filter(s=>String(s.style||'').toUpperCase()===style))by.set(x.id,x);rows=[...by.values()];
    rows=rows.filter(s=>status==='all'||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status);
  }
  rows=rows.map(x=>normalizeDisplaySignal(x,market,style)).sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0)).slice(0,limit);
  if(status==='active'&&rows.length===0&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(scanCrypto(env,style)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',activeBookAuthority:'DURABLE_OBJECT_STRONG_CONSISTENCY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
}

async function unifiedPerformance''','unifiedSignals DO authority')

sub(r"async function unifiedPerformance\(url,env\)\{.*?\n\}\nasync function scanRoute",r'''async function unifiedPerformance(url,env){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',kv=await getV31Signals(env,market,style),rt=(await realtimeActiveSignals(env)).filter(s=>String(s.style||'').toUpperCase()===style),by=new Map(kv.map(x=>[x.id,x]));for(const x of rt)by.set(x.id,x);const rows=[...by.values()],active=rt,resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',activeBookAuthority:'DURABLE_OBJECT_STRONG_CONSISTENCY',market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute''','performance merge realtime')

# Status documents the active-book authority explicitly.
must(
"return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',service:'SignalHub Crypto SCALP/SWING gateway'",
"return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',activeBookAuthority:'DURABLE_OBJECT_STRONG_CONSISTENCY',service:'SignalHub Crypto SCALP/SWING gateway'",
'status authority')

W.write_text(w)
print('patched V3.13b realtime active-book consistency')
