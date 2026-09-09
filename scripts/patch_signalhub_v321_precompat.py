from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()
ws=w.find('async function watchAnalyze')
if ws<0: raise SystemExit('watchAnalyze missing')
s=w.find('const snap=await loadCryptoSnapshot(env)',ws)
a=w.find("const active=await listActiveSignals",s)
if s<0 or a<0: raise SystemExit(f'watch source boundaries missing s={s} a={a}')
# Normalize only the ticker lookup section. V3.21's next patch deliberately uses this
# canonical one-line anchor so generated-source whitespace from older patch layers cannot drift.
normalized="const snap=await loadCryptoSnapshot(env),ticker=snap.rows.find(x=>canonical(x.symbol)===symbol);  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_ON_LIVE_PROVIDER',provider:snap.provider},404);\n  "
w=w[:s]+normalized+w[a:]
p.write_text(w)
print('V3.21 precompat Watch anchor normalized by function boundaries')
