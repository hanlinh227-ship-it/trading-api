from pathlib import Path
p=Path('cloudflare-worker/engine-v77168.js')
s=p.read_text()
old='''async function tdQuote(symbol,env){
  if(marketType(symbol)==="index"){if(env.MASSIVE_API_KEY){try{return await massiveIndexQuote(symbol,env);}catch{}}if(env.TWELVE_DATA_API_KEY){try{return await tdIndexQuote(symbol,env);}catch{}try{return await tdIndexQuoteVisibilityFallback(symbol,env);}catch{}}throw new Error("No native index quote available");}
'''
new='''async function yahooUs30CashVisibilityQuote(){const s="US30",ps="^DJI",u=`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ps)}?interval=1m&range=1d`,r=await fetchTimeout(u,{headers:{"user-agent":"Mozilla/5.0"}}),j=await r.json().catch(()=>null),x=j?.chart?.result?.[0],m=x?.meta||{},price=num(m.regularMarketPrice),ts=num(m.regularMarketTime);if(!r.ok||j?.chart?.error||m.symbol!==ps||String(m.instrumentType||"").toUpperCase()!=="INDEX"||!validIndexPrice(s,price))throw new Error(j?.chart?.error?.description||`Yahoo invalid cash index ${s}/${ps}: ${price}`);const age=ts?Math.max(0,nowSec()-ts):null;return {source:"Yahoo Finance Cash Index Fallback",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:ts||null,quoteAgeSec:age,fresh:false,bid:null,ask:null,executionVerified:false,analysisOnly:true,fallback:true,fallbackInterval:"quote",assetType:"Index",instrumentIdentity:"CASH_INDEX"};}
async function tdQuote(symbol,env){
  if(marketType(symbol)==="index"){const s=norm(symbol);if(env.MASSIVE_API_KEY){try{return await massiveIndexQuote(s,env);}catch{}}if(env.TWELVE_DATA_API_KEY){try{return await tdIndexQuote(s,env);}catch{}try{return await tdIndexQuoteVisibilityFallback(s,env);}catch{}}if(s==="US30"){try{return await yahooUs30CashVisibilityQuote();}catch{}}throw new Error("No native index quote available");}
'''
if s.count(old)!=1: raise SystemExit(f'guard mismatch: {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('V78-028 US30 Yahoo CASH INDEX visibility patch applied')
