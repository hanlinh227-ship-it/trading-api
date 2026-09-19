const KEY='bybit:context:news:v1';
const CACHE_MS=5*60*1000;
const MAX_STALE_MS=30*60*1000;
const SOURCES=Object.freeze([
  {id:'COINDESK',kind:'CRYPTO_NEWS',url:'https://www.coindesk.com/arc/outboundfeeds/rss/'},
  {id:'COINTELEGRAPH',kind:'CRYPTO_NEWS',url:'https://cointelegraph.com/rss'},
  {id:'FEDERAL_RESERVE',kind:'MACRO_POLICY',url:'https://www.federalreserve.gov/feeds/press_all.xml'},
  {id:'BLS',kind:'MACRO_DATA',url:'https://www.bls.gov/feed/bls_latest.rss'},
]);
const clean=s=>String(s||'').replace(/<!\[CDATA\[|\]\]>/g,'').replace(/<[^>]+>/g,' ').replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/\s+/g,' ').trim();
const num=v=>Number.isFinite(Number(v))?Number(v):0;
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:'json'})||{};}catch{return {}}}
async function put(env,x){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x))}catch{}}
function tag(block,name){const m=String(block||'').match(new RegExp('<'+name+'[^>]*>([\\s\\S]*?)<\\/'+name+'>','i'));return clean(m?.[1]||'');}
function feedItems(text='',limit=12){
  const blocks=[...String(text||'').matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)].map(m=>m[1]);
  return blocks.slice(0,limit).map(b=>{const title=tag(b,'title'),pubDate=tag(b,'pubDate'),category=tag(b,'category'),link=tag(b,'link');const ts=Date.parse(pubDate);return {title:title.slice(0,220),category:category.slice(0,80),publishedAt:Number.isFinite(ts)?ts:null,link:link.slice(0,400)}}).filter(x=>x.title);
}
function blsSummary(text=''){
  const plain=clean(text);const keys=['Consumer Price Index (CPI)','Unemployment Rate','Payroll Employment','Average Hourly Earnings','Producer Price Index - Final Demand'];
  return keys.map(k=>{const i=plain.indexOf(k);return i>=0?plain.slice(i,Math.min(plain.length,i+220)):''}).filter(Boolean);
}
function relevance(items=[],symbol='BTCUSDT'){
  const base=String(symbol||'BTCUSDT').toUpperCase().replace(/USDT$/,'');
  const macro=/fed|fomc|rate|inflation|cpi|ppi|payroll|jobs|unemployment|dollar|treasury|boj|ecb|central bank/i;
  const crypto=/bitcoin|ethereum|crypto|token|stablecoin|exchange|etf|sec|cftc|defi|blockchain/i;
  return items.map(x=>{const t=String(x.title||'');let score=0;if(t.toUpperCase().includes(base))score+=3;if(macro.test(t))score+=2;if(crypto.test(t))score+=1;return {...x,relevance:score}}).sort((a,b)=>b.relevance-a.relevance||(num(b.publishedAt)-num(a.publishedAt))).slice(0,16);
}
export async function collectBybitNewsContext(env={},symbol='BTCUSDT'){
  const now=Date.now(),cached=await get(env);
  if(cached?.at&&now-num(cached.at)<CACHE_MS&&Array.isArray(cached.sources))return {...cached,cached:true,stale:false,symbol};
  const settled=await Promise.allSettled(SOURCES.map(async source=>{
    const r=await fetch(source.url,{headers:{accept:'application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5','user-agent':'trading-api-news-context/1.0'},signal:AbortSignal.timeout(3500)});
    if(!r.ok)throw new Error(source.id+'_HTTP_'+r.status);
    const text=await r.text();
    return {id:source.id,kind:source.kind,ok:true,items:source.id==='BLS'?[]:feedItems(text,12),summary:source.id==='BLS'?blsSummary(text):[]};
  }));
  const sources=settled.map((x,i)=>x.status==='fulfilled'?x.value:{id:SOURCES[i].id,kind:SOURCES[i].kind,ok:false,error:String(x.reason?.message||x.reason||'FETCH_FAILED').slice(0,160),items:[],summary:[]});
  const items=relevance(sources.flatMap(x=>(x.items||[]).map(y=>({...y,source:x.id,kind:x.kind}))),symbol);
  const macroSummary=sources.filter(x=>x.kind==='MACRO_DATA').flatMap(x=>x.summary||[]).slice(0,8);
  const freshItems=items.filter(x=>!x.publishedAt||now-x.publishedAt<=24*60*60*1000);
  const out={version:'BYBIT_NEWS_CONTEXT_V1',at:now,symbol,sources,items:freshItems,macroSummary,sourceCount:sources.filter(x=>x.ok).length,stale:false};
  if(out.sourceCount>0){await put(env,out);return out;}
  if(cached?.at&&now-num(cached.at)<MAX_STALE_MS)return {...cached,cached:true,stale:true,symbol,error:'ALL_NEWS_SOURCES_UNAVAILABLE_USING_BOUNDED_CACHE'};
  return {...out,stale:true,error:'ALL_NEWS_SOURCES_UNAVAILABLE',items:[],macroSummary:[]};
}
export const BYBIT_NEWS_CONTEXT_VERSION='BYBIT_NEWS_CONTEXT_V1';
