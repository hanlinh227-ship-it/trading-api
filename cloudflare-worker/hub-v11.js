import baseEngine from './engine-v77168.js';
import {telegramApiRequest} from './providers/telegram-client.js';
import {getV11Accepted,getV11History,getV11Funnel} from './v11/store.js';
import {scanMarketV11,scheduledNativeV11} from './v11/native-runtime.js';
import {huntWholeMarket} from './v11/manual-market-hunter.js';
import {getLiveQuote} from './v11/live-quote.js';
import {symbolsForMarket,marketForSymbol,displaySymbol} from './v11/symbol-catalog.js';

const json=(x,s=200)=>new Response(JSON.stringify(x,null,2),{status:s,headers:{'content-type':'application/json','cache-control':'no-store'}});
const kb=()=>({inline_keyboard:[
 [{text:'🪙 CRYPTO',callback_data:'v11:market:crypto'},{text:'💱 FOREX',callback_data:'v11:market:forex'}],
 [{text:'🟡 GOLD / METAL',callback_data:'v11:market:metal'},{text:'📈 INDEX / FUTURES',callback_data:'v11:market:index'}],
 [{text:'🎯 TẤT CẢ SYMBOL',callback_data:'v11:symbolmarkets'}],
 [{text:'🔥 TOP ENTRY NOW',callback_data:'v11:ai:hunt'}],
 [{text:'📚 LỆNH ĐANG CHẠY',callback_data:'v11:live'},{text:'👀 WATCHLIST',callback_data:'v11:watch'}],
 [{text:'📈 THỐNG KÊ',callback_data:'v11:stats'},{text:'🕘 LỊCH SỬ',callback_data:'v11:history'}],
 [{text:'📊 SYSTEM STATUS',callback_data:'v11:system'}],
 [{text:'🟨 BINANCE AUTO',callback_data:'binance'}]
]});
const marketKb=m=>({inline_keyboard:[
 [{text:'⚡ MARKET NOW',callback_data:`v11:scan:${m}`},{text:'🔥 TOP 3',callback_data:`v11:top3:${m}`}],
 [{text:'🎯 TỪNG SYMBOL',callback_data:`v11:symbols:${m}:0`}],
 [{text:'📈 LONG SETUPS',callback_data:`v11:side:${m}:LONG`},{text:'📉 SHORT SETUPS',callback_data:`v11:side:${m}:SHORT`}],
 [{text:'🏆 MARKET WR',callback_data:`v11:marketwr:${m}`},{text:'📚 LIVE',callback_data:`v11:market:${m}`}],
 [{text:'👀 WATCH',callback_data:`v11:watch:${m}`},{text:'🧠 5 AI • MARKET',callback_data:'v11:ai:hunt'}],
 [{text:'🏠 HUB',callback_data:'menu'}]
]});
const symbolMarketsKb=()=>({inline_keyboard:[
 [{text:'🪙 CRYPTO',callback_data:'v11:symbols:crypto:0'},{text:'💱 FOREX',callback_data:'v11:symbols:forex:0'}],
 [{text:'🟡 GOLD / METAL',callback_data:'v11:symbols:metal:0'},{text:'📈 INDEX / FUTURES',callback_data:'v11:symbols:index:0'}],
 [{text:'🏠 HUB',callback_data:'menu'}]
]});
function symbolPageKb(m,page=0){const symbols=symbolsForMarket(m),per=12,total=Math.max(1,Math.ceil(symbols.length/per)),pg=Math.max(0,Math.min(total-1,Number(page)||0)),slice=symbols.slice(pg*per,(pg+1)*per),rows=[];for(let i=0;i<slice.length;i+=2)rows.push(slice.slice(i,i+2).map(s=>({text:displaySymbol(s,m),callback_data:`v11:symbol:${m}:${s}`})));const nav=[];if(pg>0)nav.push({text:'◀️',callback_data:`v11:symbols:${m}:${pg-1}`});nav.push({text:`${pg+1}/${total}`,callback_data:`v11:symbols:${m}:${pg}`});if(pg<total-1)nav.push({text:'▶️',callback_data:`v11:symbols:${m}:${pg+1}`});rows.push(nav,[{text:'⬅️ MARKET',callback_data:`v11:market:${m}`},{text:'🏠 HUB',callback_data:'menu'}]);return {inline_keyboard:rows};}
function symbolDetailKb(m,s){return {inline_keyboard:[[{text:'🔄 REFRESH LIVE',callback_data:`v11:symbol:${m}:${s}`}],[{text:'⬅️ SYMBOLS',callback_data:`v11:symbols:${m}:0`},{text:'🏠 HUB',callback_data:'menu'}]]};}

function fmt(v){if(v===null||v===undefined||v==='')return '—';const n=Number(v);if(!Number.isFinite(n)||n<=0)return '—';const a=Math.abs(n);let s=a>=1000?n.toFixed(2):a>=1?n.toFixed(4):a>=.01?n.toFixed(5):a>=.0001?n.toFixed(6):n.toPrecision(5);return s.replace(/(\.\d*?[1-9])0+$|\.0+$/,'$1');}
const pnlPct=(side,entry,price)=>{const e=Number(entry),p=Number(price);if(!(e>0)||!(p>0))return null;return (String(side).toUpperCase()==='SHORT'?(e-p):(p-e))/e*100;};
const pnlText=p=>p==null?'⚪ —':p>=0?`🟢 +${p.toFixed(2)}%`:`🔴 ${p.toFixed(2)}%`;
const line=x=>{const c=x.candidate||{},p=pnlPct(c.side,c.entry,x.currentPrice),q=x.currentQuote||{},age=Number.isFinite(Number(q.quoteAgeSec))?`${Math.round(Number(q.quoteAgeSec))}s`:'—';return `${c.side==='LONG'?'🟢':'🔴'} ${x.symbol} ${c.side==='LONG'?'BUY':'SELL'} | ${pnlText(p)}\nE ${fmt(c.entry)} • N ${fmt(x.currentPrice)}\nSL ${fmt(c.sl)} • TP ${fmt(c.tp)} • RR ${Number(c.rr||0).toFixed(1)}\n📡 ${q.source||'NO LIVE'} ${age} • AI CUT ${x.lastAiCutVotes||0}/5`;};
async function send(env,id,text,markup=kb()){return telegramApiRequest(env,'sendMessage',{chat_id:id||env.TELEGRAM_CHAT_ID,text,reply_markup:markup,disable_web_page_preview:true});}
function aiText(x){if(!x)return '—';if(x.status!=='OK')return x.status||'—';const r=x.review||{};return `${r.direction||'WAIT'} ${Number(r.confidence||0)}%`;}
function hunterText(r){if(!r?.best)return `🧠 5 AI MARKET\n⚪ Chưa có entry đủ chuẩn\n${r?.reason||r?.status||'NO_CANDIDATE'}`;const x=r.best,c=x.candidate||{},ai=x.ai||{};return [`🧠 5 AI MARKET`,`${c.side==='LONG'?'🟢 BUY':'🔴 SELL'} ${x.symbol} • ${String(x.market||'').toUpperCase()}`,`E ${fmt(c.entry)} • SL ${fmt(c.sl)} • TP ${fmt(c.tp)} • RR ${Number(c.rr||0).toFixed(1)}`,`AI ${Number(x.consensusCount||0)}/5 ${x.consensus?'✅':'⚠️'} • C:${aiText(ai.claude)} • X:${aiText(ai.codex)}`,`D:${aiText(ai.deepseek)} • Q:${aiText(ai.qwen)} • O:${aiText(ai.openrouter)}`].join('\n');}
function watchRows(f,market){const rows=(f||[]).filter(x=>x.status==='WATCH'&&(!market||x.market===market)),seen=new Set(),out=[];for(const x of rows){const k=`${x.market}:${x.symbol}:${x.reason}`;if(seen.has(k))continue;seen.add(k);out.push(x);if(out.length>=8)break;}return out;}
function watchText(rows){if(!rows.length)return '👀 WATCH • Trống';return ['👀 WATCH',...rows.map(x=>`${String(x.market||'').toUpperCase()} • ${x.symbol} • ${x.reason||'WAIT'}`)].join('\n');}
function marketWrText(h,market){const closed=(h||[]).filter(x=>x.outcome==='WIN'||x.outcome==='LOSS'),wins=closed.filter(x=>x.outcome==='WIN').length,loss=closed.length-wins,cuts=(h||[]).filter(x=>x.outcome==='CUT').length,expired=(h||[]).filter(x=>x.outcome==='EXPIRED').length,wr=closed.length?wins/closed.length*100:null;return `🏆 ${String(market||'V11').toUpperCase()} WR\n✅ ${wins} • ❌ ${loss} • ✂️ ${cuts} • ⌛ ${expired}\n🎯 ${wr==null?'—':wr.toFixed(1)+'%'} • mẫu ${closed.length}`;}
function topRows(a,n=3,side=null){return (a||[]).filter(x=>!side||String(x.candidate?.side||'').toUpperCase()===side).sort((x,y)=>Number(y.candidate?.qualityScore||0)-Number(x.candidate?.qualityScore||0)).slice(0,n);}
async function enrichLive(rows,env){return Promise.all((rows||[]).map(async x=>{try{const q=await getLiveQuote(x.symbol,x.market,env);return {...x,currentPrice:Number(q.price),currentQuote:q};}catch{return {...x,currentPrice:null,currentQuote:{fresh:false,source:'NO_FRESH_LIVE'}};}}));}
async function engineAnalyze(symbol,env){try{const r=await baseEngine.fetch(new Request(`https://v11.symbol/analyze?symbol=${encodeURIComponent(symbol)}`),env);return await r.json();}catch{return null;}}
function symbolMode(a){const st=String(a?.status||'').toUpperCase();if(st==='MARKET_SIGNAL'||st==='MARKET')return 'MARKET';if(st==='LIMIT'||st==='LIMIT_PLAN')return 'LIMIT';return 'WATCH';}
async function symbolDetailText(env,m,s){const [ar,qr]=await Promise.allSettled([engineAnalyze(s,env),getLiveQuote(s,m,env)]),a=ar.status==='fulfilled'?ar.value:null,q=qr.status==='fulfilled'?qr.value:null,live=q?.fresh===true&&Number(q?.price)>0?Number(q.price):null,mode=symbolMode(a),planned=a?.planned||a||{},side=String(a?.side||planned?.side||'').toUpperCase(),score=Number(a?.score??a?.qualityScore??0),rr=Number(planned?.targetRR??a?.targetRR??0),entry=mode==='MARKET'&&live?live:Number(planned?.entry??a?.entry),sl=Number(planned?.sl??a?.sl),tp=Number(planned?.tp2??planned?.tp1??planned?.tp??a?.tp2??a?.tp1??a?.tp),age=Number(q?.quoteAgeSec),cross=Number(q?.crossSourceCount||0),src=q?.source||'NO_FRESH_LIVE',icon=mode==='MARKET'?'⚡':mode==='LIMIT'?'🎯':'👀',sideText=side==='LONG'?'🟢 BUY':side==='SHORT'?'🔴 SELL':'⚪ WAIT';const L=[`🎯 ${displaySymbol(s,m)} • ${String(m).toUpperCase()}`,`💵 LIVE ${fmt(live)} • ${src}${Number.isFinite(age)?` • ${Math.round(age)}s`:''}${cross?` • x${cross}`:''}`];if(!live){L.push('⛔ Không có giá LIVE đủ mới → không phát MARKET.');return L.join('\n');}L.push(`${icon} ${sideText} ${mode}${Number.isFinite(score)&&score>0?` • Q ${Math.round(score)}/100`:''}`,`E ${fmt(entry)} • SL ${fmt(sl)} • TP ${fmt(tp)}${rr>0?` • RR ${rr.toFixed(2)}`:''}`);if(a?.method?.profile)L.push(`🧠 ${a.method.profile}${a.method?.activeMode?` • ${a.method.activeMode}`:''}`);if(a?.reason&&mode==='WATCH')L.push(`↳ ${a.reason}`);L.push('🔄 Bấm REFRESH LIVE để đánh giá lại ngay.');return L.join('\n');}
function symbolsPageText(m,page=0){const xs=symbolsForMarket(m),per=12,total=Math.max(1,Math.ceil(xs.length/per)),pg=Math.max(0,Math.min(total-1,Number(page)||0));return `🎯 ${String(m).toUpperCase()} • SYMBOL ${pg+1}/${total}\n${xs.length} symbol • chọn 1 mã để lấy giá LIVE + đánh giá riêng.`;}

async function textFor(env,kind,market,side=null){
 const a=await getV11Accepted(env,market),h=await getV11History(env,market),f=await getV11Funnel(env);
 if(kind==='live'||kind==='official'){const picked=market?a.slice(0,5):a.slice(0,20),rows=await enrichLive(picked,env);return [`🔥 ${market?market.toUpperCase():'V11'} LIVE • ${rows.length}${market?'/5':''}`,...rows.map(line)].join('\n\n');}
 if(kind==='top3'){const rows=await enrichLive(topRows(a,3),env);return rows.length?[`🔥 TOP 3 ${String(market||'V11').toUpperCase()}`,...rows.map(line)].join('\n\n'):`🔥 TOP 3 ${String(market||'V11').toUpperCase()} • Trống`;}
 if(kind==='side'){const rows=await enrichLive(topRows(a,5,side),env);return rows.length?[`${side==='LONG'?'📈 LONG':'📉 SHORT'} ${String(market||'V11').toUpperCase()}`,...rows.map(line)].join('\n\n'):`${side} ${String(market||'V11').toUpperCase()} • Trống`;}
 if(kind==='marketwr')return marketWrText(h,market);
 if(kind==='watch')return watchText(watchRows(f,market));
 if(kind==='history')return [`🕘 HISTORY • ${h.length}`,...h.slice(0,12).map(x=>`${x.outcome==='WIN'?'✅':x.outcome==='LOSS'?'❌':x.outcome==='CUT'?'✂️':'⌛'} ${x.symbol} • ${x.outcome} • ${fmt(x.closePrice)}`)].join('\n');
 if(kind==='stats'){const wins=h.filter(x=>x.outcome==='WIN').length,loss=h.filter(x=>x.outcome==='LOSS').length,cuts=h.filter(x=>x.outcome==='CUT').length,n=wins+loss;return `📈 V11 STATS\n✅ ${wins} • ❌ ${loss} • ✂️ ${cuts}\nWR ${n?(wins/n*100).toFixed(1):'—'}%`;}
 if(kind==='system')return `📊 SYSTEM\n✅ Signal V11\n✅ LIVE Quote Router\n✅ 5 AI Gateway\n📌 Max 5 MARKET / thị trường\n✂️ CUT cần ≥4/5 AI`;
 return `🤖 TRADING HUB V11\n🧠 5 AI • 📡 LIVE quote\n🎯 Từng symbol theo V77/V78 navigator\n📌 Max 5 MARKET / thị trường\n✂️ AI CUT 4/5\nChọn thị trường.`;
}
function auth(u,env){const got=String(u?.callback_query?.from?.id??u?.message?.from?.id??''),want=String(env.TELEGRAM_ALLOWED_USER_ID||env.TELEGRAM_CHAT_ID||'');return !want||got===want;}
function marketParam(url){const m=String(url.searchParams.get('market')||'');return ['crypto','forex','metal','index'].includes(m)?m:null;}
async function v11Api(url,env){const market=marketParam(url);if(url.pathname==='/v11/signals'||url.pathname==='/v11/live'){const base=(await getV11Accepted(env,market)).slice(0,market?5:20),rows=await enrichLive(base,env);return json({ok:true,version:'V11',market,signals:rows});}if(url.pathname==='/v11/watch'){const f=await getV11Funnel(env);return json({ok:true,version:'V11',market,watch:watchRows(f,market)});}if(url.pathname==='/v11/history')return json({ok:true,version:'V11',market,history:await getV11History(env,market)});if(url.pathname==='/v11/funnel')return json({ok:true,version:'V11',funnel:await getV11Funnel(env)});if(url.pathname==='/v11/symbol'){const symbol=String(url.searchParams.get('symbol')||'').toUpperCase(),m=market||marketForSymbol(symbol);if(!symbol||!m)return json({ok:false,error:'SYMBOL_OR_MARKET_REQUIRED'},400);return json({ok:true,market:m,symbol,text:await symbolDetailText(env,m,symbol)});}return null;}
async function diagnosticAnalyze(url,env){const symbol=String(url.searchParams.get('symbol')||'').trim().toUpperCase();if(!symbol)return json({ok:false,error:'SYMBOL_REQUIRED'},400);const r=await baseEngine.fetch(new Request(`https://v11.internal/analyze?symbol=${encodeURIComponent(symbol)}`),env);let payload=null;try{payload=await r.json()}catch{payload={error:'NON_JSON_INTERNAL_ANALYSIS'}}return json({ok:r.ok,version:'V11',symbol,httpStatus:r.status,payload},r.ok?200:502);}

export default {
 async fetch(req,env,ctx){
  const url=new URL(req.url);
  if(url.pathname==='/v11/status')return json({ok:true,version:'V11',telegram:true,maxOpenPerMarket:5,reevaluationCut:true,aiCutConsensusRequired:4,canonicalLiveQuoteRouter:true,symbolNavigator:'V77_V78_STYLE'});
  const api=await v11Api(url,env);if(api)return api;
  if(url.pathname.startsWith('/v11/')){if(url.pathname==='/v11/diagnostic/analyze'&&req.method==='GET')return diagnosticAnalyze(url,env);if(url.pathname==='/v11/scan'&&req.method==='POST'){const body=await req.json().catch(()=>({})),market=String(body.market||'');if(!['crypto','forex','metal','index'].includes(market))return json({ok:false,error:'INVALID_MARKET'},400);return json(await scanMarketV11(env,market));}if(url.pathname==='/v11/ai-hunt'&&req.method==='POST')return json(await huntWholeMarket(env));return json({ok:false,error:'V11_ENDPOINT_NOT_FOUND'},404);}
  if(url.pathname==='/telegram/webhook'&&req.method==='POST'){
   let u;try{u=await req.clone().json()}catch{return json({ok:false},400)}if(!auth(u,env))return json({ok:false},403);
   const cb=String(u?.callback_query?.data||''),msg=String(u?.message?.text||'');
   if(cb.startsWith('v11:')||msg==='/start'||msg==='/v11'||cb==='menu'){
    const id=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID;
    if(cb==='v11:ai:hunt'){await send(env,id,'⏳ 5 AI đang quét…');const r=await huntWholeMarket(env);await send(env,id,hunterText(r));return json({ok:true,owner:'V11',hunter:r.status});}
    if(cb==='v11:symbolmarkets'){await send(env,id,'🎯 CHỌN THỊ TRƯỜNG\nMỗi symbol có nút riêng • bấm để lấy LIVE + đánh giá.',symbolMarketsKb());return json({ok:true,owner:'V11'});}
    if(cb.startsWith('v11:symbols:')){const p=cb.split(':'),m=p[2],page=Number(p[3]||0);await send(env,id,symbolsPageText(m,page),symbolPageKb(m,page));return json({ok:true,owner:'V11',market:m,page});}
    if(cb.startsWith('v11:symbol:')){const p=cb.split(':'),m=p[2],s=p[3];await send(env,id,await symbolDetailText(env,m,s),symbolDetailKb(m,s));return json({ok:true,owner:'V11',market:m,symbol:s});}
    let kind='menu',market=null,side=null;
    if(cb.startsWith('v11:scan:')){market=cb.split(':')[2];await send(env,id,`⏳ Quét ${market.toUpperCase()}…`,marketKb(market));const r=await scanMarketV11(env,market);await send(env,id,`🔍 ${market.toUpperCase()} • +${r.notified||0} signal • WATCH ${r.watch||0} • reject ${r.rejected||0}`,marketKb(market));return json({ok:true,owner:'V11',scan:r});}
    if(cb.startsWith('v11:marketwr:')){market=cb.split(':')[2];kind='marketwr';}
    else if(cb.startsWith('v11:top3:')){market=cb.split(':')[2];kind='top3';}
    else if(cb.startsWith('v11:side:')){const p=cb.split(':');market=p[2];side=p[3];kind='side';}
    else if(cb.startsWith('v11:watch:')){market=cb.split(':')[2];kind='watch';}
    else if(cb.startsWith('v11:market:')){market=cb.split(':')[2];kind='live';}
    else if(cb==='v11:live')kind='live';else if(cb==='v11:watch')kind='watch';else if(cb==='v11:history')kind='history';else if(cb==='v11:stats')kind='stats';else if(cb==='v11:system')kind='system';
    await send(env,id,await textFor(env,kind,market,side),market?marketKb(market):kb());return json({ok:true,owner:'V11'});
   }
   return json({ok:false,owner:'V11',error:'LEGACY_TELEGRAM_DISABLED'},404);
  }
  if(url.pathname==='/'||url.pathname==='/hub')return json({ok:true,version:'V11',service:'SIGNAL_V11',binanceAutoSeparate:true});
  return json({ok:false,version:'V11',error:'LEGACY_PUBLIC_ENDPOINT_DISABLED'},410);
 },
 async scheduled(event,env,ctx){return scheduledNativeV11(event,env,ctx);}
};
