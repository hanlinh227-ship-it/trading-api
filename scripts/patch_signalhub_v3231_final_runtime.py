from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()

# Keep status/decision metadata synchronized with the V3.23.1 health engine.
w=w.replace("healthModel:'V3227_REALTIME_SIGNAL_HEALTH_1S'","healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'")
w=w.replace("qualityMode:'PRECISION_MARKET_ENTRY_MULTI_CONFIRMATION_HARD_SAFETY'","qualityMode:'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY'")

# V3.23.0's fresh MARKET creator still calls helpers that were removed by an
# earlier refactor boundary. Restore them against the Durable Object active-book
# authority only; historical KV rows are never deleted or rewritten here.
marker='async function maybeCreateV31(env,market,style,setups){'
i=w.find(marker)
assert i>=0, 'maybeCreateV31 marker missing'
helpers=''
if 'async function getActiveBook(env)' not in w:
    helpers+="""async function getActiveBook(env){
  const rows=await realtimeActiveSignals(env);
  return (Array.isArray(rows)?rows:[]).filter(s=>s&&String(s.market||'').toUpperCase()==='CRYPTO'&&String(s.status||'').toUpperCase()==='OPEN'&&String(s.orderType||'MARKET').toUpperCase()==='MARKET');
}

"""
if 'async function reserveRealtimeSignal(env,s,kvKey)' not in w:
    helpers+="""async function reserveRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub)return {accepted:false,reason:'NO_ATOMIC_RESERVATION_BUS'};
  try{const r=await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});if(!r.ok)return {accepted:false,reason:`RESERVATION_HTTP_${r.status}`};return await r.json();}catch(e){return {accepted:false,reason:`RESERVATION_ERROR:${String(e?.message||e)}`};}
}

"""
if 'async function releaseRealtimeSignal(env,id)' not in w:
    helpers+="""async function releaseRealtimeSignal(env,id){
  const stub=mt5LiveStub(env);if(!stub)return;
  try{await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id})});}catch{}
}

"""
if helpers:
    w=w[:i]+helpers+w[i:]

assert 'async function getActiveBook(env)' in w
assert 'async function reserveRealtimeSignal(env,s,kvKey)' in w
assert 'async function releaseRealtimeSignal(env,id)' in w
assert "healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'" in w
assert "qualityMode:'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY'" in w
p.write_text(w)
print('V3.23.1 final runtime compatibility patched')
