from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()
old="""const snap=await loadCryptoSnapshot(env),ticker=snap.rows.find(x=>canonical(x.symbol)===symbol);
  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_ON_LIVE_PROVIDER',provider:snap.provider},404);"""
new="const snap=await loadCryptoSnapshot(env),ticker=snap.rows.find(x=>canonical(x.symbol)===symbol);  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_ON_LIVE_PROVIDER',provider:snap.provider},404);"
if old not in w:
    raise SystemExit('precompat watch source anchor missing')
w=w.replace(old,new,1)
p.write_text(w)
print('V3.21 precompat Watch anchor normalized')
