import {telegramApiRequest} from "./providers/telegram-client.js";

const PREFIX="auto:futures:v6";
const K={
  runtime:`${PREFIX}:runtime`,
  pending:`${PREFIX}:pending`,
  positions:`${PREFIX}:positions`,
  pnl:`${PREFIX}:pnl`,
  feed:`${PREFIX}:confirmation_feed`,
};
const enc=new TextEncoder();
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});

async function tg(env,method,payload){
  if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");
  return telegramApiRequest(env,method,payload);
}
async function answer(env,id,text){try{await tg(env,"answerCallbackQuery",{callback_query_id:id,text,show_alert:false});}catch{}}
async function send(env,chatId,text,reply_markup){return tg(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}
function authorizedUser(update,env){
  const got=String(update?.callback_query?.from?.id??update?.message?.from?.id??"");
  const want=String(env.TELEGRAM_ALLOWED_USER_ID||env.TELEGRAM_CHAT_ID||"");
  return !want||got===want;
}
function mainKeyboard(){return {inline_keyboard:[
  [{text:"📡 SIGNAL CENTER",callback_data:"signal"}],
  [{text:"💱 Forex",callback_data:"market:forex"},{text:"🪙 Crypto",callback_data:"market:crypto"}],
  [{text:"🥇 Metal",callback_data:"market:metal"},{text:"📊 Index Cash",callback_data:"market:index"}],
  [{text:"🧭 Entry Intel",callback_data:"intel"},{text:"📊 Coverage",callback_data:"intel:coverage"}],
  [{text:"🟨 BINANCE",callback_data:"binance"}],
  [{text:"••• Hệ thống",callback_data:"hub:more"}],
]};}
const binanceKeyboard=()=>({inline_keyboard:[
  [{text:"📋 LỆNH CHỜ",callback_data:"binance:pending"},{text:"📈 VỊ THẾ",callback_data:"binance:positions"}],
  [{text:"📊 PNL",callback_data:"binance:pnl"},{text:"🔄 REFRESH",callback_data:"binance"}],
  [{text:"⬅️ HUB",callback_data:"menu"}],
]});
const pendingKeyboard=(items=[])=>{
  const rows=[];
  for(const x of items.slice(0,5)){
    rows.push([{text:`✅ ${x.symbol} ${x.action}`,callback_data:`binance:confirm:${x.id}`},{text:"❌ BỎ",callback_data:`binance:reject:${x.id}`}]);
  }
  rows.push([{text:"🔄 REFRESH",callback_data:"binance:pending"},{text:"⬅️ BINANCE",callback_data:"binance"}]);
  return {inline_keyboard:rows};
};

async function kvGet(env,key,def){
  try{const x=await env.TRADING_STATE?.get(key,{type:"json"});return x??def;}catch{return def;}
}
async function kvPut(env,key,val){if(!env.TRADING_STATE)throw new Error("TRADING_STATE unavailable");await env.TRADING_STATE.put(key,JSON.stringify(val));}
function iso(){return new Date().toISOString();}
function activePending(payload){
  const now=Date.now();
  return (payload?.items||[]).filter(x=>x?.status==="PENDING"&&(!x.expires_at||Date.parse(x.expires_at)>now));
}
async function dashboard(env){
  const runtime=await kvGet(env,K.runtime,{}),pending=activePending(await kvGet(env,K.pending,{items:[]})),positions=await kvGet(env,K.positions,{positions:[]}),pnl=await kvGet(env,K.pnl,{});
  const online=runtime?.reported_at&&Date.now()-Date.parse(runtime.reported_at)<90000;
  return ["🟨 BINANCE","━━━━━━━━━━━━",`${online?"🟢":"🔴"} Engine: ${online?"ONLINE":"STALE/OFFLINE"}`,`🔐 Mode: CONFIRM PER TRADE`,`🤖 AI: ${runtime.ai_status||"—"}`,`⏱ Scan: ${runtime.scan_status||"—"}`,`📋 Pending: ${pending.length}`,`📈 Open positions: ${(positions.positions||[]).length}`,`💰 Realized PNL: ${pnl.realized_pnl??"—"}`,"","Mỗi lệnh phải được xác nhận trên Hub và sẽ được VPS revalidate trước execution."].join("\n");
}
function pendingText(items){
  const L=["📋 BINANCE • LỆNH CHỜ","━━━━━━━━━━━━"];
  if(!items.length)L.push("⚪ Không có setup đang chờ xác nhận.");
  for(const x of items.slice(0,5))L.push("",`${x.symbol} • ${x.action} • ${x.strategy||"—"}`,`Entry ${x.entry??"—"} • SL ${x.stop_loss??"—"}`,`TP1 ${x.tp1??"—"} • TP2 ${x.tp2??"—"} • TP3 ${x.tp3??"—"}`,`AI ${x.ai_confidence??"—"} • hết hạn ${x.expires_at||"—"}`);
  L.push("","Nếu setup hết TTL trước khi VPS nhận xác nhận: KHÔNG TRADE.");return L.join("\n");
}
async function positionsText(env){const x=await kvGet(env,K.positions,{positions:[]}),L=["📈 BINANCE • VỊ THẾ","━━━━━━━━━━━━"];if(!(x.positions||[]).length)L.push("⚪ Không có vị thế mở.");for(const p of (x.positions||[]).slice(0,12))L.push(`${p.symbol||"—"} • ${p.side||p.action||"—"} • qty ${p.qty??p.quantity??"—"} • PNL ${p.unrealized_pnl??p.pnl??"—"}`);return L.join("\n");}
async function pnlText(env){const x=await kvGet(env,K.pnl,{});return ["📊 BINANCE • PNL","━━━━━━━━━━━━",`Realized: ${x.realized_pnl??"—"}`,`Unrealized: ${x.unrealized_pnl??"—"}`,`Closed trades: ${x.closed_trades??"—"}`,`Updated: ${x.updated_at||"—"}`].join("\n");}

async function addDecision(env,item,decision,userId){
  const feed=await kvGet(env,K.feed,{events:[]});
  const event={seq:Date.now(),created_at:iso(),trade_id:item.id,decision,symbol:item.symbol,action:item.action,strategy:item.strategy,fingerprint:item.fingerprint,telegram_user_id:String(userId||"")};
  feed.events=[...(feed.events||[]),event].slice(-100);
  await kvPut(env,K.feed,feed);
  return event;
}

export async function handleUnifiedTelegram(req,env){
  const path=new URL(req.url).pathname;
  if(path!=="/telegram/webhook")return null;
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  let u;try{u=await req.clone().json();}catch{return null;}
  const text=String(u?.message?.text||"").trim();
  const cb=String(u?.callback_query?.data||"");
  const chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID;
  if(text==="/start"||text==="/menu"||cb==="menu"){
    if(cb)await answer(env,u.callback_query.id,"Hub");
    await send(env,chatId,["◈ TRADING HUB","━━━━━━━━━━━━","Signal Center + Binance approval control","","Chọn khu vực:"].join("\n"),mainKeyboard());
    return json({ok:true,handled:"unified-menu"});
  }
  if(!cb.startsWith("binance"))return null;
  if(!authorizedUser(u,env)){await answer(env,u.callback_query.id,"Không có quyền xác nhận lệnh.");return json({ok:true,handled:"unauthorized"});}
  if(cb==="binance"){
    await answer(env,u.callback_query.id,"BINANCE");
    await send(env,chatId,await dashboard(env),binanceKeyboard());return json({ok:true,handled:cb});
  }
  if(cb==="binance:pending"){
    const items=activePending(await kvGet(env,K.pending,{items:[]}));await answer(env,u.callback_query.id,"Pending");await send(env,chatId,pendingText(items),pendingKeyboard(items));return json({ok:true,handled:cb});
  }
  if(cb==="binance:positions"){
    await answer(env,u.callback_query.id,"Positions");await send(env,chatId,await positionsText(env),binanceKeyboard());return json({ok:true,handled:cb});
  }
  if(cb==="binance:pnl"){
    await answer(env,u.callback_query.id,"PNL");await send(env,chatId,await pnlText(env),binanceKeyboard());return json({ok:true,handled:cb});
  }
  const m=cb.match(/^binance:(confirm|reject):([A-Za-z0-9_-]{6,40})$/);
  if(!m){await answer(env,u.callback_query.id,"Lệnh không hợp lệ.");return json({ok:true,handled:"invalid"});}
  const [,verb,id]=m,all=await kvGet(env,K.pending,{items:[]}),item=(all.items||[]).find(x=>x.id===id);
  if(!item||item.status!=="PENDING"||item.expires_at&&Date.parse(item.expires_at)<=Date.now()){
    await answer(env,u.callback_query.id,"Setup đã hết hạn/không còn hợp lệ.");return json({ok:true,handled:"expired"});
  }
  const decision=verb==="confirm"?"CONFIRMED":"REJECTED";
  await addDecision(env,item,decision,u.callback_query.from?.id);
  item.status=decision;item.resolved_at=iso();await kvPut(env,K.pending,all);
  await answer(env,u.callback_query.id,decision==="CONFIRMED"?"Đã xác nhận. VPS sẽ revalidate.":"Đã bỏ lệnh.");
  await send(env,chatId,`${decision==="CONFIRMED"?"✅":"❌"} BINANCE ${item.symbol} ${item.action}\n${decision==="CONFIRMED"?"Đã chuyển xác nhận tới execution bridge. Chỉ trade nếu revalidation còn PASS.":"Setup đã bị loại."}`,binanceKeyboard());
  return json({ok:true,handled:decision,trade_id:id});
}

async function hmacHex(key,text){
  const k=await crypto.subtle.importKey("raw",enc.encode(key),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const sig=await crypto.subtle.sign("HMAC",k,enc.encode(text));return [...new Uint8Array(sig)].map(x=>x.toString(16).padStart(2,"0")).join("");
}
async function verifyBridge(req,env,rawBody=""){
  const ts=req.headers.get("x-auto-futures-timestamp")||"",sig=req.headers.get("x-auto-futures-signature")||"";
  const n=Number(ts);if(!env.TELEGRAM_BOT_TOKEN||!Number.isFinite(n)||Math.abs(Date.now()/1000-n)>90)return false;
  const u=new URL(req.url),base=`${req.method}\n${u.pathname}\n${ts}\n${rawBody}`;
  const expected=await hmacHex(env.TELEGRAM_BOT_TOKEN,base);
  if(sig.length!==expected.length)return false;let diff=0;for(let i=0;i<sig.length;i++)diff|=sig.charCodeAt(i)^expected.charCodeAt(i);return diff===0;
}

export async function handleControlApi(req,env){
  const u=new URL(req.url);
  if(u.pathname==="/binance/control/report"&&req.method==="POST"){
    const raw=await req.text();if(!await verifyBridge(req,env,raw))return json({ok:false,error:"unauthorized"},401);
    let body;try{body=JSON.parse(raw);}catch{return json({ok:false,error:"invalid json"},400);}
    const reported_at=body.reported_at||iso();
    await Promise.all([
      kvPut(env,K.runtime,{...(body.runtime||{}),reported_at}),
      kvPut(env,K.pending,body.pending||{items:[]}),
      kvPut(env,K.positions,body.positions||{positions:[]}),
      kvPut(env,K.pnl,body.pnl||{}),
    ]);
    return json({ok:true,reported_at});
  }
  if(u.pathname==="/binance/control/feed"&&req.method==="GET"){
    if(!await verifyBridge(req,env,""))return json({ok:false,error:"unauthorized"},401);
    const after=Number(u.searchParams.get("after")||0),feed=await kvGet(env,K.feed,{events:[]});
    return json({ok:true,events:(feed.events||[]).filter(x=>Number(x.seq)>after).slice(-50)});
  }
  return null;
}
