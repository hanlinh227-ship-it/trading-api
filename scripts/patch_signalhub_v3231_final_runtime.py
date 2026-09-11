from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()

# Keep status/decision metadata synchronized with the V3.23.1 health engine.
w=w.replace("healthModel:'V3227_REALTIME_SIGNAL_HEALTH_1S'","healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'")
w=w.replace("qualityMode:'PRECISION_MARKET_ENTRY_MULTI_CONFIRMATION_HARD_SAFETY'","qualityMode:'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY'")

# V3.23.0's fresh MARKET creator still calls getActiveBook(). Earlier refactors
# removed that helper. Restore it using the Durable Object as the sole active-book
# authority; this touches no historical KV rows.
if 'async function getActiveBook(env)' not in w:
    marker='async function maybeCreateV31(env,market,style,setups){'
    i=w.find(marker)
    assert i>=0, 'maybeCreateV31 marker missing'
    helper="""async function getActiveBook(env){
  const rows=await realtimeActiveSignals(env);
  return (Array.isArray(rows)?rows:[]).filter(s=>s&&String(s.market||'').toUpperCase()==='CRYPTO'&&String(s.status||'').toUpperCase()==='OPEN'&&String(s.orderType||'MARKET').toUpperCase()==='MARKET');
}

"""
    w=w[:i]+helper+w[i:]

assert 'async function getActiveBook(env)' in w
assert "healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'" in w
assert "qualityMode:'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY'" in w
p.write_text(w)
print('V3.23.1 final runtime compatibility patched')
