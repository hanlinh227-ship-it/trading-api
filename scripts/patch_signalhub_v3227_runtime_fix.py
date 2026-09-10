from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()
start='async function realtimePortfolioSnapshot(env){'
end='async function releaseCoverageClaim(env,market)'
i=w.find(start);j=w.find(end,i)
assert i>=0 and j>i, 'realtime portfolio/helper block missing'
replacement="""async function realtimePortfolioSnapshot(env){
  const stub=mt5LiveStub(env);if(!stub)return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0},orderTypes:{SCALP:{MARKET:0,LIMIT:0,STOP:0},SWING:{MARKET:0,LIMIT:0,STOP:0}},uniqueSymbols:0,duplicateSymbols:[],marketOnly:false,exactTarget:false};
  try{const r=await stub.fetch('https://mt5-live/portfolio-snapshot');if(r.ok)return await r.json();}catch{}return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0},orderTypes:{SCALP:{MARKET:0,LIMIT:0,STOP:0},SWING:{MARKET:0,LIMIT:0,STOP:0}},uniqueSymbols:0,duplicateSymbols:[],marketOnly:false,exactTarget:false};
}
async function realtimeActiveSignals(env,style=''){
  const stub=mt5LiveStub(env);if(!stub)return[];
  try{const suffix=style?`?style=${encodeURIComponent(style)}`:'';const r=await stub.fetch('https://mt5-live/active-signals'+suffix);if(!r.ok)return[];const x=await r.json();return Array.isArray(x?.rows)?x.rows:[];}catch{return[];}
}
"""
w=w[:i]+replacement+w[j:]
p.write_text(w)
assert 'async function realtimeActiveSignals' in w
assert w.count('async function realtimeActiveSignals')==1
print('fixed V3.22.7 realtime helper placement')
