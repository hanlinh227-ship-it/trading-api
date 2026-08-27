import {telegramApiRequest} from "./providers/telegram-client.js";
import {FOREX_AUTO_VERSION,forexAutoConfig} from "./forex-auto-config.js";
import {forexAutonomous2AiHealth} from "./forex-autonomous-2ai-trader.js";

const json=(b,s=200)=>new Response(JSON.stringify(b,null,2),{status:s,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
const money=v=>Number.isFinite(Number(v))?`${Number(v)>=0?"+":""}$${Number(v).toFixed(2)}`:"—";
const px=v=>Number.isFinite(Number(v))?Number(v).toPrecision(7).replace(/0+$/,'').replace(/\.$/,''):"—";

// ─── MENU ─────────────────────────────────────────────────────────────────────
const forexMenu=()=>({inline_keyboard:[
  [{text:"💱 DASHBOARD",callback_data:"forex:dashboard"}],
  [{text:"🧠 AI",callback_data:"forex:ai"},{text:"🛡️ RULES",callback_data:"forex:rules"}],
  [{text:"🖥️ MT5",callback_data:"forex:mt5"},{text:"🎯 LAST DECISION",callback_data:"forex:decision"}],
  [{text:"🏠 HUB",callback_data:"hub:home"},{text:"🔄 REFRESH",callback_data:"forex:dashboard"}]
]});

const auth=(u,e)=>{const got=String(u?.callback_query?.from?.id??u?.message?.from?.id??""),want=String(e.TELEGRAM_ALLOWED_USER_ID||e.TELEGRAM_CHAT_ID||"");return !want||got===want;};
async function send(e,id,text,menu=forexMenu()){return telegramApiRequest(e,"sendMessage",{chat_id:id||e.TELEGRAM_CHAT_ID,text,reply_markup:menu,disable_web_page_preview:true});}
async function answer(e,id,text=""){if(!id)return;try{await telegramApiRequest(e,"answerCallbackQuery",{callback_query_id:id,text,show_alert:false});}catch{}}
function store(e){return e.FOREX_STATE||e.TRADING_STATE||null;}
async function kv(e,k){try{return await store(e)?.get(k,{type:"json"})||null}catch{return null}}
function ageSec(ts){const t=Date.parse(String(ts||""));return Number.isFinite(t)?Math.max(0,(Date.now()-t)/1000):Infinity;}
function heartbeatStatus(hb){const age=ageSec(hb?.receivedAt),canonical=hb?.canonicalEa===true&&String(hb?.eaVersion||"").startsWith("1.")&&Number(hb?.balance)>0&&Number(hb?.equity)>0,fresh=age<=30,brokerConnected=hb?.connected===true;return {canonical,brokerConnected,fresh,connected:canonical&&brokerConnected&&fresh,ageSec:age,pulseAt:hb?.receivedAt||null,status:!hb?"NO_CANONICAL_HEARTBEAT":!canonical?"INVALID_OR_LEGACY_STATE":!fresh?"STALE_HEARTBEAT":!brokerConnected?"BROKER_DISCONNECTED":"CONNECTED"};}

async function snap(e){
 const cfg=forexAutoConfig(e),ai=forexAutonomous2AiHealth(e),heartbeat=await kv(e,"forex:mt5:heartbeat:last"),legacyLast=await kv(e,"forex:mt5:last"),terminalId=heartbeat?.terminalId||legacyLast?.terminalId||null,state=terminalId?await kv(e,`forex:mt5:${terminalId}`):null;
 const allAi=!!ai?.chatgpt?.configured&&!!ai?.claude?.configured,mt5=heartbeatStatus(heartbeat);
 return {cfg,ai,heartbeat,last:legacyLast,state,mt5,terminalId,allAi,mode:cfg.execution.liveEnabled?"LIVE":"PAPER"};}

function accountView(s){const a=s.state?.account||{},h=s.heartbeat||{};return {balance:a.balance??h.balance,equity:a.equity??h.equity,freeMargin:a.freeMargin??h.freeMargin,marginLevelPct:a.marginLevelPct??h.marginLevelPct,openPositions:a.openPositions??h.openPositions??0};}

// ─── STATUS BADGE ─────────────────────────────────────────────────────────────
function forexStatusLine(s){
  if(!s.mt5.connected)return `Status: ❌ BLOCKED — MT5_${s.mt5.status}`;
  if(!s.allAi)return `Status: ❌ BLOCKED — AI_NOT_CONFIGURED`;
  if(s.mode!=="LIVE")return `Status: ⚪ PAPER`;
  const a=accountView(s);
  if(!(Number(a.balance)>0))return `Status: ⚠️ DEGRADED — NO_ACCOUNT_DATA`;
  return Number(a.openPositions)>0?`Status: 🟢 LIVE — ${a.openPositions} position${a.openPositions!==1?"s":""}`:
`Status: 🟢 READY — IDLE`;}

// ─── FOREX DASHBOARD ──────────────────────────────────────────────────────────
function dash(s){
  const st=s.state||{},a=accountView(s),d=st.dailyObjective||{},t=st.target||{};
  const shortVer=String(FOREX_AUTO_VERSION||"—").split("-").slice(0,3).join("-")||FOREX_AUTO_VERSION;
  const mt5Icon=s.mt5.connected?"✅":s.mt5.fresh?"⚠️":"❌";
  const aiIcon=s.allAi?"✅":"❌";
  const ageStr=Number.isFinite(s.mt5.ageSec)?` (${fmt(s.mt5.ageSec,0)}s ago)`:"";
  const todayLine=Number.isFinite(Number(d.profitPct))
    ?`📈 Today: ${Number(d.profitPct)>=0?"+":""}${fmt(d.profitPct,2)}%  •  ${money(d.profitUsd)}`
    :"📈 Today: —";
  const goalLine=`   Goal: >${fmt(d.minProfitPct??s.cfg.dailyObjective?.minProfitPct,2)}%`;
  const campaignLine=t?.enabled
    ?`🎯 Campaign: ${money(t.profitUsd)} / +$${fmt(t.targetUsd)}  •  ${fmt(t.progressPct,1)}%  •  ${t.targetDays||s.cfg.target?.targetDays||"—"} days`
    :`🎯 Campaign: $0.00 / +$${fmt(s.cfg.target?.targetUsd)}  •  ${s.cfg.target?.targetDays||"—"} days`;
  return [
    `💱 FOREX — ${s.mode==="LIVE"?"LIVE ✅":"PAPER ⚪"}`,
    shortVer,
    "",
    `🖥️ MT5: ${mt5Icon} ${s.mt5.connected?"CONNECTED":s.mt5.status}${ageStr}`,
    `🧠 AI:  ${aiIcon} Claude ${s.ai?.claude?.configured?"✅":"❌"} | Codex ${s.ai?.chatgpt?.configured?"✅":"❌"}`,
    "",
    `💰 Balance: $${fmt(a.balance)}`,
    `💰 Equity:  $${fmt(a.equity)}`,
    `📊 Positions: ${a.openPositions}`,
    "",
    todayLine,
    goalLine,
    campaignLine,
    "",
    forexStatusLine(s)
  ].join("\n");}

// ─── FOREX AI ─────────────────────────────────────────────────────────────────
function aiText(s){
  const a=s.ai||{};
  return [
    "🧠 AI COUNCIL — FOREX",
    "",
    `Claude: ${a.claude?.configured?"✅ READY":"❌ MISSING"}`,
    `Codex:  ${a.chatgpt?.configured?"✅ READY":"❌ MISSING"}`,
    "",
    "Quorum: 2/2 • bắt buộc cùng ENTER và cùng symbol/side.",
    "Hard rules chỉ có quyền chặn an toàn, không tạo entry."
  ].join("\n");}

// ─── RULES (data display unchanged) ──────────────────────────────────────────
function rulesText(s){const r=s.cfg.rules||{},m=s.state?.rules?.metrics||{};return ["🛡️ THE5ERS HARD SAFETY",`Official daily max ${fmt(r.maxDailyLossPct)}% • max loss ${fmt(r.maxTotalLossPct)}%`,`Internal/projected stop ${fmt(r.internalDailyStopPct)}% / ${fmt(r.projectedDailyStopPct)}%`,`Current daily loss ${fmt(m.dailyLossPct,2)}% • total ${fmt(m.totalLossPct,2)}%`,`News hard lock ±${Math.round(Number(r.officialNewsBlockBeforeSec||0)/60)}m / +${Math.round(Number(r.officialNewsBlockAfterSec||0)/60)}m`,`Alternation BUY→SELL→BUY→SELL • không ép lệnh`,`HFT/arbitrage/martingale/grid recovery: BLOCK`].join("\n");}

// ─── MT5 ──────────────────────────────────────────────────────────────────────
function mt5Text(s){const a=accountView(s),h=s.heartbeat||{};return ["🖥️ MT5 WINDOWS",`Connection ${s.mt5.connected?"🟢 CONNECTED":"🔴 "+s.mt5.status}`,`EA version ${h.eaVersion||"—"} • pulse age ${Number.isFinite(s.mt5.ageSec)?fmt(s.mt5.ageSec,1)+"s":"—"}`,`Terminal ${s.terminalId||"—"}`,`Last pulse ${s.mt5.pulseAt||"—"}`,`Balance $${fmt(a.balance)} • Equity $${fmt(a.equity)}`,`Free margin $${fmt(a.freeMargin)} • Margin level ${fmt(a.marginLevelPct)}%`,`Open positions ${a.openPositions}`,`Required next side ${s.state?.requiredSide||s.last?.requiredSide||"—"}`].join("\n");}

// ─── DECISION (unchanged) ─────────────────────────────────────────────────────
function decisionText(s){const st=s.state||{},d=st.decision||{},mg=st.manageDecision||{};return ["🎯 FOREX LAST DECISION",`Action ${d.action||s.last?.decision||"—"}`,`Reason ${d.reason||"—"}`,d.symbol?`${d.symbol} • ${String(d.side||"").toUpperCase()} • Entry ${px(d.entry)}`:"Symbol —",d.symbol?`SL ${px(d.sl)} • TP ${px(d.tp)} • RR ${fmt(d.rr,2)} • Risk ${fmt(d.riskPct,2)}%`:"",mg.manageAction?`Manage ${mg.manageAction} • ticket ${mg.manageTicket||"—"}\n${mg.manageReason||""}`:"Manage: HOLD / none",`Required side ${st.requiredSide||s.last?.requiredSide||"—"}`,`At ${st.receivedAt||s.mt5.pulseAt||s.last?.receivedAt||"—"}`].filter(Boolean).join("\n");}

// ─── HANDLER ──────────────────────────────────────────────────────────────────
export async function handleForexTelegramHub(req,e){
 const u=new URL(req.url);if(u.pathname!=="/telegram/webhook"||req.method!=="POST")return null;
 if(e.TELEGRAM_WEBHOOK_SECRET&&req.headers.get("x-telegram-bot-api-secret-token")!==e.TELEGRAM_WEBHOOK_SECRET)return null;
 let body;try{body=await req.clone().json()}catch{return null}
 const cb=String(body?.callback_query?.data||"");if(!(cb==="hub:forex"||cb==="market:forex"||cb.startsWith("forex:")))return null;
 if(!auth(body,e))return json({ok:false,error:"FORBIDDEN"},403);
 const chatId=body?.callback_query?.message?.chat?.id||body?.message?.chat?.id||e.TELEGRAM_CHAT_ID;
 await answer(e,body?.callback_query?.id);
 const s=await snap(e);
 if(cb==="hub:forex"||cb==="market:forex"||cb==="forex:dashboard")await send(e,chatId,dash(s));
 else if(cb==="forex:ai")await send(e,chatId,aiText(s));
 else if(cb==="forex:rules")await send(e,chatId,rulesText(s));
 else if(cb==="forex:mt5")await send(e,chatId,mt5Text(s));
 else if(cb==="forex:decision")await send(e,chatId,decisionText(s));
 else return null;
 return json({ok:true,view:cb,forexStateStore:e.FOREX_STATE?"FOREX_STATE":"TRADING_STATE",twoAi:true,mt5:s.mt5,terminalId:s.terminalId});}
