from pathlib import Path

p=Path('cloudflare-worker/engine-v77168.js')
s=p.read_text()
s=s.replace('version: "V77.16.15",','version: "V77.16.16",').replace('service: "Trading V77.16.15 Native Index Failover",','service: "Trading V77.16.16 Verified Index Pricing",')
needle='const MASSIVE_INDEX_PROVIDER = {NAS100:"I:NDX",US30:"I:DJI",US500:"I:SPX",DEX:"I:DAX",JP225:"I:N225"};\n'
insert='''const MASSIVE_INDEX_PROVIDER = {NAS100:"I:NDX",US30:"I:DJI",US500:"I:SPX",DEX:"I:DAX",JP225:"I:N225"};
const INDEX_SANITY = {
  NAS100:{min:1000,max:100000}, US30:{min:5000,max:100000}, US500:{min:500,max:20000},
  DEX:{min:1000,max:100000}, JP225:{min:5000,max:100000}
};
function validIndexPrice(symbol,price){const r=INDEX_SANITY[norm(symbol)],x=Number(price);return !!r&&Number.isFinite(x)&&x>=r.min&&x<=r.max;}
function tdIndexNode(raw){return raw?.data?.values?raw.data:raw;}
function assertTdIndexIdentity(symbol,node){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,m=node?.meta||{},typ=String(m.type||"").toLowerCase(),got=norm(m.symbol||ps);if(typ&&!typ.includes("index"))throw new Error(`Twelve Data wrong instrument type ${s}: ${m.type}`);if(got&&got!==norm(ps))throw new Error(`Twelve Data wrong symbol ${s}: ${m.symbol}`);return m;}
'''
if needle not in s: raise SystemExit('provider needle missing')
s=s.replace(needle,insert)
old='''async function tdSingleIndexCandles(symbol,interval,env,outputsize=CONFIG.candleOutputSize){
  const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,interval,outputsize:String(outputsize),order:"ASC",timezone:"UTC"},env),c=tdCandlesFromNode(p,interval);
  if(!c?.length)throw new Error(`Twelve Data index candles unavailable ${s}/${ps}`);return c;
}'''
new='''async function tdSingleIndexCandles(symbol,interval,env,outputsize=CONFIG.candleOutputSize){
  const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval,outputsize:String(outputsize),order:"ASC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,interval);
  if(!c?.length)throw new Error(`Twelve Data index candles unavailable ${s}/${ps}`);const last=c.at(-1);if(!validIndexPrice(s,last?.close))throw new Error(`Twelve Data implausible index price ${s}: ${last?.close}`);return c;
}'''
if old not in s: raise SystemExit('tdSingle old missing')
s=s.replace(old,new)
old='''async function massiveIndexCandles(symbol,interval,env,limit=CONFIG.candleOutputSize){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const r=massiveIndexRange(interval),j=await massiveIndexFetch(`/v2/aggs/ticker/${encodeURIComponent(ticker)}/range/${r.mult}/${r.span}/${r.from}/${r.to}`,{adjusted:"true",sort:"asc",limit:String(Math.max(limit,120))},env);return normalizeCandles((j.results||[]).map(x=>({timestamp:Math.floor(Number(x.t)/1000),open:x.o,high:x.h,low:x.l,close:x.c,volume:null})),candleSec(interval));}'''
new='''async function massiveIndexCandles(symbol,interval,env,limit=CONFIG.candleOutputSize){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const r=massiveIndexRange(interval),j=await massiveIndexFetch(`/v2/aggs/ticker/${encodeURIComponent(ticker)}/range/${r.mult}/${r.span}/${r.from}/${r.to}`,{adjusted:"true",sort:"asc",limit:String(Math.max(limit,120))},env),c=normalizeCandles((j.results||[]).map(x=>({timestamp:Math.floor(Number(x.t)/1000),open:x.o,high:x.h,low:x.l,close:x.c,volume:null})),candleSec(interval));if(c.length&&!validIndexPrice(s,c.at(-1)?.close))throw new Error(`Massive implausible index price ${s}: ${c.at(-1)?.close}`);return c;}'''
if old not in s: raise SystemExit('massive candles old missing')
s=s.replace(old,new)
old='''async function massiveIndexQuote(symbol,env){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const j=await massiveIndexFetch("/v3/snapshot/indices",{ticker,limit:"10"},env),r=(j.results||[]).find(x=>x?.ticker===ticker&&!x?.error),price=num(r?.value);if(!(price>0))throw new Error(r?.message||r?.error||"Massive index snapshot unavailable");const ts=r?.last_updated?Math.floor(Number(r.last_updated)/1e9):null,age=ts?Math.max(0,nowSec()-ts):null;return {source:"Massive Indices Snapshot",requestedSymbol:s,providerSymbol:ticker,price,providerTimestamp:ts,quoteAgeSec:age,timeframe:r?.timeframe||null,marketStatus:r?.market_status||null,fresh:age==null?false:age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true};}
async function tdIndexQuote(symbol,env){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s;try{const p=await tdFetch("price",{symbol:ps},env),price=num(p?.price);if(price>0)return {source:"Twelve Data Index Price",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:null,quoteAgeSec:null,fresh:true,bid:null,ask:null,executionVerified:false,analysisOnly:true};}catch{}const p=await tdFetch("quote",{symbol:ps},env),price=num(p.close)??num(p.price);if(!(price>0))throw new Error("TD index price invalid");const ts=parseTs(p.last_quote_at??p.timestamp??p.datetime),age=ts==null?null:Math.max(0,nowSec()-ts);return {source:"Twelve Data Index Quote",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:ts,quoteAgeSec:age,fresh:age==null?true:age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true};}'''
new='''async function massiveIndexQuote(symbol,env){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const j=await massiveIndexFetch("/v3/snapshot/indices",{ticker,limit:"10"},env),r=(j.results||[]).find(x=>x?.ticker===ticker&&!x?.error),price=num(r?.value);if(!(price>0)||!validIndexPrice(s,price))throw new Error(r?.message||r?.error||`Massive invalid index value ${s}: ${price}`);const ts=r?.last_updated?Math.floor(Number(r.last_updated)/1e9):null,age=ts?Math.max(0,nowSec()-ts):null;return {source:"Massive Indices Snapshot",requestedSymbol:s,providerSymbol:ticker,price,providerTimestamp:ts,quoteAgeSec:age,timeframe:r?.timeframe||null,marketStatus:r?.market_status||null,fresh:age==null?false:age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true};}
async function tdIndexQuote(symbol,env){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval:"1min",outputsize:"2",order:"DESC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,"1min"),last=c?.at(-1),price=num(last?.close);if(!(price>0)||!validIndexPrice(s,price))throw new Error(`Twelve Data invalid native index value ${s}/${ps}: ${price}`);return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null,fresh:true,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}'''
if old not in s: raise SystemExit('quote block missing')
s=s.replace(old,new)
# Add source visibility into signal metadata where context source is available.
s=s.replace('providers:{forex:"Twelve Data analysis; MT5 broker quote required for execution",crypto:"Exchange-native analysis + exact canonical bid/ask execution",metal:"Twelve Data analysis; MT5 broker quote required for execution",index:"Massive native index snapshot/OHLC primary + Twelve Data native index per-symbol fallback"}', 'providers:{forex:"Twelve Data analysis; MT5 broker quote required for execution",crypto:"Exchange-native analysis + exact canonical bid/ask execution",metal:"Twelve Data analysis; MT5 broker quote required for execution",index:"Verified native Index only: Massive I:ticker primary + Twelve Data type=Index fallback; sanity fail-closed"}')
p.write_text(s)

p=Path('cloudflare-worker/index.js');s=p.read_text().replace('const VERSION="V77.18.34",SERVICE="Trading V77.18.34 Native Index Failover";','const VERSION="V77.18.35",SERVICE="Trading V77.18.35 Verified Index Pricing";').replace('const RELEASE_NAME="Native Index Failover";','const RELEASE_NAME="Verified Index Pricing";');p.write_text(s)
p=Path('cloudflare-worker/hub-v77171.js');s=p.read_text().replace('const VERSION="V77.18.34",UI_REV="HUB-R6-SPLIT-LIVE",SERVICE="Trading V77.18.34 • Native Index Failover";','const VERSION="V77.18.35",UI_REV="HUB-R6-SPLIT-LIVE",SERVICE="Trading V77.18.35 • Verified Index Pricing";');p.write_text(s)
print('V771835_PATCH_OK')
