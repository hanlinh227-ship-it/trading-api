from pathlib import Path

p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
s=s.replace('version: "V77.16.17",','version: "V77.16.18",').replace('service: "Trading V77.16.17 Market Isolation + Forex R4",','service: "Trading V77.16.18 Price First + No Global Actions",')
# Native index freshness: delayed/old values may display but must never be treated as fresh MARKET data.
s=s.replace('fresh:age==null?false:age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true};}', 'fresh:age!=null&&age<=180&&String(r?.timeframe||"REAL-TIME").toUpperCase()!=="DELAYED",bid:null,ask:null,executionVerified:false,analysisOnly:true};}',1)
old='return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null,fresh:true,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}'
new='const age=last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null;return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:age,fresh:age!=null&&age<=180,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}'
if old not in s: raise SystemExit('tdIndex freshness block missing')
s=s.replace(old,new)
# Replace runSymbol with quote-first variant. It returns a concrete quote even if technical candles fail.
start=s.index('async function runSymbol(symbol,env){')
end=s.index('async function quotePool(',start)
newfun=r'''async function symbolFirstQuote(symbol,type,env){
  try{if(type==="crypto")return {quote:await cryptoExecutionQuote(symbol),error:null};return {quote:await tdQuote(symbol,env),error:null};}
  catch(e){return {quote:null,error:String(e?.message||e)};}
}
async function runSymbol(symbol,env){
  const s=canonicalUserSymbol(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};
  const first=await symbolFirstQuote(s,type,env),upfrontQuote=first.quote;if(!upfrontQuote?.price)return {ok:false,status:"DATA_BLOCK",symbol:s,market:type,reason:"CURRENT_PRICE_UNAVAILABLE",price:null,analysisQuote:null,quoteError:first.error,engine:CONFIG.version};
  try{
    if(type==="crypto"){
      let b;try{b=await cryptoDeepBundle(s,{preferAnalysis:true});}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,market:type,reason:"EXCHANGE_DEEP_UNAVAILABLE",currentPrice:upfrontQuote.price,analysisQuote:upfrontQuote,error:e?.message||String(e),engine:CONFIG.version};}
      let context={score:5};try{const bulk=await cryptoBulk(),sq=b.quote?.percentChange??bulk.get(s)?.percentChange??0,bq=s==="BTCUSDT"?sq:(bulk.get("BTCUSDT")?.percentChange??0),rel=sq-bq;context={relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel)),...(await cryptoDerivativesContext(s))};}catch{}
      const a=await deepAnalyze(s,env,b.candles,upfrontQuote,b.source,context);a.analysisQuote=upfrontQuote;a.currentPrice=Number(upfrontQuote.price);return a;
    }
    if(type==="forex"){
      let cached=await loadMarketContext("forex",env),fx=cached?.strength||null,h1;if(fx){h1=await tdBatchCandles([s],"1h",env,60);}else{h1=await tdBatchCandles(FOREX,"1h",env,60);fx=forexStrengthMap(h1);await saveMarketContext("forex",{strength:fx},env);}const base=s.slice(0,3),quote=s.slice(3),d=(fx[base]||0)-(fx[quote]||0),sess=forexSessionBias(s),context={baseStrength:fx[base]||0,quoteStrength:fx[quote]||0,strengthDiff:d,strengthNormalizedSigned:Math.max(-1,Math.min(1,d/.60)),session:sess.label,sessionScore:sess.score,score:Math.min(10,4.7+Math.abs(d)*4.2+sess.score*.75),contextCached:!!cached},extra=await Promise.all(["5min","15min","4h","1day"].map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=[extra[0].get(s)||[],extra[1].get(s)||[],h1.get(s)||[],extra[2].get(s)||[],extra[3].get(s)||[]];const a=await deepAnalyze(s,env,candles,upfrontQuote,"Twelve Data price-first + cached 28-pair strength",context);a.analysisQuote=upfrontQuote;a.currentPrice=Number(upfrontQuote.price);return a;
    }
    if(type==="metal"){
      let cached=await loadMarketContext("metal",env),moves=cached?.moves||null,h1;if(moves){h1=await tdBatchCandles([s],"1h",env,60);}else{h1=await tdBatchCandles(METALS,"1h",env,60);moves={};for(const x of METALS)moves[x]=changeFromCandles(h1.get(x)||[]);await saveMarketContext("metal",{moves},env);}const other=s==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(moves[s]||0)-(moves[other]||0),sess=metalSessionBias(),context={relativeStrength:rel,benchmark:other,session:sess.label,sessionScore:sess.score,score:Math.min(10,4.8+Math.abs(rel)*3.2+sess.score*.75),contextCached:!!cached},extra=await Promise.all(["5min","15min","4h","1day"].map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=[extra[0].get(s)||[],extra[1].get(s)||[],h1.get(s)||[],extra[2].get(s)||[],extra[3].get(s)||[]];const a=await deepAnalyze(s,env,candles,upfrontQuote,"Twelve Data price-first + cached metal relative",context);a.analysisQuote=upfrontQuote;a.currentPrice=Number(upfrontQuote.price);return a;
    }
    const maps=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=maps.map(m=>m.get(s)||[]),sess=indexSessionBias(s),context={session:sess.label,sessionScore:sess.score,score:Math.min(10,5+sess.score*.8)};const a=await deepAnalyze(s,env,candles,upfrontQuote,upfrontQuote.source||"Verified native Index",context);a.analysisQuote=upfrontQuote;a.currentPrice=Number(upfrontQuote.price);return a;
  }catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,market:type,reason:"ANALYSIS_DATA_UNAVAILABLE",currentPrice:Number(upfrontQuote.price),analysisQuote:upfrontQuote,error:String(e?.message||e),engine:CONFIG.version};}
}
'''
s=s[:start]+newfun+s[end:]
# Market-scoped sendGroup must refresh only its own books.
s=s.replace('const run=await runGroup(group,env,"GROUP_MANUAL"),books=await getBooksLive(env);return sendText(env,summary(group,books,run),chatId,groupKeyboard(group,run));','const run=await runGroup(group,env,"GROUP_MANUAL"),books=await getBooksLive(env,group);return sendText(env,summary(group,books,run),chatId,groupKeyboard(group,run));')
# Disable the cross-market /hub scanner and require group for live books.
s=s.replace('if(p==="/hub")return json(await runHub(env,"API_HUB"));','if(p==="/hub")return json({ok:true,version:CONFIG.version,mode:"MARKET_ISOLATED",message:"Cross-market scan disabled. Use /run-now?group=..."});')
s=s.replace('if(p==="/books"||p==="/orders"){const g=u.searchParams.get("group");if(g&&!GROUPS[g])return json({ok:false,error:"invalid group"},400);return json(await getBooksLive(env,g||null));}', 'if(p==="/books"||p==="/orders"){const g=u.searchParams.get("group");if(!g||!GROUPS[g])return json({ok:false,error:"group is required: forex|crypto|metal|index"},400);return json(await getBooksLive(env,g));}')
# Endpoint documentation no longer advertises global books/hub scans.
s=s.replace('["/status","/hub","/run-now?group=forex|crypto|metal|index"','["/status","/run-now?group=forex|crypto|metal|index"')
s=s.replace(',"/telegram/menu","/books","/order-history"]',',"/telegram/menu","/books?group=forex|crypto|metal|index","/order-history"]')
p.write_text(s)

# HUB: old global callbacks from stale Telegram messages are explicitly rejected, never forwarded to legacy engine.
p=Path('cloudflare-worker/hub-v77171.js'); s=p.read_text()
s=s.replace('const VERSION="V77.18.36",UI_REV="HUB-R7-MARKET-ISOLATED",SERVICE="Trading V77.18.36 • Market Isolated UX";', 'const VERSION="V77.18.37",UI_REV="HUB-R8-PRICE-FIRST",SERVICE="Trading V77.18.37 • Price First / No Global Actions";')
old='handled=["prop","prop:setup","prop:hyro","prop:orders","prop:risk","prop:connect","menu","hub:more","signal","status"].includes(cb)||cb?.startsWith("prop:wiz:")||cb?.startsWith("market:")||cb?.startsWith("signal:scan:")||cb?.startsWith("live:")||cb?.startsWith("symbols:")||cb?.startsWith("symbol:")||text==="/start"||text==="/menu"'
new='handled=["prop","prop:setup","prop:hyro","prop:orders","prop:risk","prop:connect","menu","hub:more","signal","status","live","books","symbols","signal:top"].includes(cb)||cb?.startsWith("prop:wiz:")||cb?.startsWith("market:")||cb?.startsWith("signal:scan:")||cb?.startsWith("live:")||cb?.startsWith("symbols:")||cb?.startsWith("symbol:")||text==="/start"||text==="/menu"'
if old not in s: raise SystemExit('hub handled missing')
s=s.replace(old,new)
needle='if(cb==="menu"||text==="/start"||text==="/menu")'
insert='if(["live","books","symbols","signal:top"].includes(cb)){await sendText(env,"♻️ NÚT CŨ ĐÃ NGỪNG\\n━━━━━━━━━━━━\\nKhông còn Quét/Live/Symbol dùng chung. Hãy chọn đúng Forex, Crypto, Metal hoặc Index.",chatId,signalKeyboard());return json({ok:true,deprecated:true});}'
if needle not in s: raise SystemExit('menu handler missing')
s=s.replace(needle,insert+needle,1)
# setup cards and single-symbol output visibly separate current price from planned entry.
old='let L=[`${i?i+". ":""}${mode==="MARKET"?"⚡":mode==="LIMIT"?"🎯":"👀"} ${a.symbol} • ${side(a.side)}`,`   ${mode} • Score ${score}/100${rr?` • RR ${rr.toFixed(2)}`:""}`];'
new='const q=a.analysisQuote||a.quote||{},px=Number(q?.price??a.currentPrice);let L=[`${i?i+". ":""}${mode==="MARKET"?"⚡":mode==="LIMIT"?"🎯":"👀"} ${a.symbol} • ${side(a.side)}`,`   ${mode} • Score ${score}/100${rr?` • RR ${rr.toFixed(2)}`:""}`];if(Number.isFinite(px)&&px>0)L.push(`   💵 Giá ${fmt(px)} • ${q?.source||a.source||"analysis"}`);'
if old not in s: raise SystemExit('setupCard opening missing')
s=s.replace(old,new)
p.write_text(s)

# Claude revision: review this stricter price-first/no-global architecture and Forex quality without forcing trades.
p=Path('cloudflare-worker/dual-ai-intervention.js'); s=p.read_text()
s=s.replace('const REVIEW_REV="FOREX_MARKET_ISOLATION_R4";','const REVIEW_REV="FOREX_PRICE_FIRST_R4_1";')
s=s.replace('Perform FOREX_MARKET_ISOLATION_R4 first.', 'Perform FOREX_PRICE_FIRST_R4_1 first. Verify every single-symbol path fetches a concrete price before technical analysis, no shared/global scan or Live callback can execute, and Forex MARKET_SIGNAL uses the fresh quote while preserving structural RR/news/freshness.')
s=s.replace('lastAction:"FOREX_MARKET_ISOLATION_R4"','lastAction:"FOREX_PRICE_FIRST_R4_1"')
p.write_text(s)

p=Path('cloudflare-worker/index.js'); s=p.read_text().replace('const VERSION="V77.18.36",SERVICE="Trading V77.18.36 Market Isolation + Forex R4";','const VERSION="V77.18.37",SERVICE="Trading V77.18.37 Price First + No Global Actions";').replace('const RELEASE_NAME="Market Isolation + Forex R4";','const RELEASE_NAME="Price First + No Global Actions";'); p.write_text(s)
print('V771837_PATCH_OK')
