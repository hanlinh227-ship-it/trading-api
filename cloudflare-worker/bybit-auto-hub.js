import {telegramApiRequest} from "./providers/telegram-client.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";
import {bybitExecutionMode} from "./bybit-auto-config.js";
import {bybitV5} from "./bybit-v5-client.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
const money=v=>Number.isFinite(Number(v))?`${Number(v)>=0?"+":""}$${Number(v).toFixed(2)}`:"—";
const auth=(u,env)=>{const got=String(u?.callback_query?.from?.id??u?.message?.from?.id??""),want=String(env.TELEGRAM_ALLOWED_USER_ID||env.TELEGRAM_CHAT_ID||"");return !want||got===want;};
const menu=()=>({inline_keyboard:[
 [{text:"🤖 AUTO DASHBOARD",callback_data:"auto:dashboard"}],
 [{text:"📌 VỊ THẾ LIVE",callback_data:"auto:positions"},{text:"🎯 TARGET",callback_data:"auto:target"}],
 [{text:"🧠 3 AI",callback_data:"auto:ai"},{text:"🛡️ RISK / SAFETY",callback_data:"auto:risk"}],
 [{text:"📈 PNL / LEARNING",callback_data:"auto:stats"},{text:"⚙️ RUNTIME",callback_data:"auto:runtime"}],
 [{text:"🔄 REFRESH",callback_data:"auto:dashboard"}]
]});
async function send(env,id,text,markup=menu()){return telegramApiRequest(env,"sendMessage",{chat_id:id||env.TELEGRAM_CHAT_ID,text,reply_markup:markup,disable_web_page_preview:true});}
async function snapshot(env){
 const state=await getBybitAutoV1State(env),api=bybitV5(env);
 const [w,p,o,ai]=await Promise.allSettled([api.wallet(),api.positions(),api.openOrders(),probeBybitAiBridge(env)]);
 const acct=w.status==="fulfilled"?(w.value?.result?.list?.[0]||{}):{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};
 const positions=p.status==="fulfilled"?(p.value?.result?.list||[]).filter(x=>Number(x.size||0)>0):[];
 const orders=o.status==="fulfilled"?(o.value?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus))):[];
 return {state,mode:bybitExecutionMode(env),account:{equity:Number(acct.totalEquity||coin.equity||0),wallet:Number(acct.totalWalletBalance||coin.walletBalance||0),available:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)},positions,openOrders:orders,ai:ai.status==="fulfilled"?ai.value:{ok:false,error:String(ai.reason||"AI_PROBE_FAILED")},checkedAt:new Date().toISOString()};
}
function positionLines(s){if(!s.positions.length)return ["⚪ Không có vị thế LIVE."];return s.positions.map(x=>{const plan=s.state?.openPlans?.[x.symbol]||{},review=plan.lastReview||{};return `${String(x.side).toLowerCase()==="buy"?"🟢":"🔴"} ${x.symbol} ${String(x.side).toUpperCase()} • qty ${x.size}\nE ${x.avgPrice||plan.entry||"—"} • Mark ${x.markPrice||"—"}\nPnL ${money(x.unrealisedPnl)} • SL ${x.stopLoss||plan.sl||"—"} • TP ${x.takeProfit||plan.tp||"—"}\nManager ${review.verdict||plan.managementPhase||"HOLD"}${Number.isFinite(Number(review.r))?` • R ${fmt(review.r,2)}`:""}`;});}
function dashboard(s){const t=s.state?.profitTarget||{},ai=s.ai||{};return [
 "🤖 BYBIT AUTO TRADE HUB",
 `🟢 Mode: ${s.mode} • Auto: ${String(s.state?.executionMode||"UNKNOWN")}`,
 `💰 Equity $${fmt(s.account.equity)} • Available $${fmt(s.account.available)}`,
 `📌 Position ${s.positions.length} • Orders ${s.openOrders.length}`,
 `📈 Realized ${money(s.state?.realizedUsd||0)}`,
 `🎯 Target ${t.status||"OFF"}${t.targetUsd?` • ${money(t.targetPnlUsd||0)} / +$${fmt(t.targetUsd,0)} • còn $${fmt(t.remainingUsd??t.targetUsd,2)}`:""}`,
 `🧠 AI ${ai.ok?"READY":"DEGRADED"} • ${Number(ai.online||0)}/${Number(ai.configured||3)} online • ${ai.bridgeMode||"—"}`,
 `🛡️ Loss streak ${Number(s.state?.lossStreak||0)} • ${Number(s.state?.pauseUntil||0)>Date.now()?"PAUSED":"RUNNING"}`,
 `🕒 ${s.checkedAt}`
 ].join("\n");}
function targetText(s){const t=s.state?.profitTarget;return !t?"🎯 TARGET\n⚪ Chưa có target active.":["🎯 PROFIT TARGET",`Status: ${t.status}`,`Mục tiêu: +$${fmt(t.targetUsd,0)}`,`Đã đạt từ baseline: ${money(t.targetPnlUsd||0)}`,`Còn lại: $${fmt(t.remainingUsd??Math.max(0,Number(t.targetUsd||0)-Number(t.targetPnlUsd||0)),2)}`,`Baseline realized: ${money(t.baselineRealizedUsd||0)}`,`Kết thúc: ${t.endAt}`,"Đạt target → dừng entry mới; vẫn HOLD/TIGHTEN/CUT lệnh đang mở."].join("\n");}
function aiText(s){const a=s.ai||{},ps=a.providers||{};return ["🧠 3 AI CORE",`Bridge: ${a.ok?"✅ READY":"⚠️ DEGRADED"} • ${a.bridgeMode||"—"}`,`Claude: ${ps.claude?.state||"—"}`,`Codex/ChatGPT: ${ps.codex?.state||"—"}`,`DeepSeek: ${ps.deepseek?.state||"—"}`,`Fast-first grace: ${a.fastFirstGraceSec??"—"}s • budget ${a.bridgeBudgetSec??"—"}s`,s.state?.lastAiReview?`Last: ${s.state.lastAiReview.symbol} ${s.state.lastAiReview.side} • ${s.state.lastAiReview.mode} • usable ${s.state.lastAiReview.usable}`:"Last review: —"].join("\n");}
function riskText(s){const lp=s.state?.lastPnlReconcile||{},pm=s.state?.lastPositionManagement||{};return ["🛡️ RISK / SAFETY",`Mode ${s.mode} • ${Number(s.state?.pauseUntil||0)>Date.now()?"⏸ PAUSED":"▶️ RUNNING"}`,`Loss streak ${Number(s.state?.lossStreak||0)}`,`Realized ${money(s.state?.realizedUsd||0)}`,`Open plans ${Object.keys(s.state?.openPlans||{}).length}`,`PnL reconcile ${lp.at||"—"}`,`Position review ${pm.at||"—"}`,"Safety: post-AI drift • risk-by-balance • native SL/TP • HOLD/TIGHTEN/CUT"].join("\n");}
async function statsText(env,s){let l={};try{l=await getBybitLearningState(env)||{};}catch{}return ["📈 PNL / LEARNING",`Realized ${money(s.state?.realizedUsd||0)} • Trades ${Number(s.state?.trades||0)}`,`Closed reconcile ${Number(s.state?.lastPnlReconcile?.closedTrades||0)}`,`Learning samples ${Number(l.sampleCount??l.samples?.length??0)}`,`Last trade ${s.state?.lastTradeAt?new Date(Number(s.state.lastTradeAt)).toISOString():"—"}`].join("\n");}
function runtimeText(s){return ["⚙️ AUTO RUNTIME",`Execution ${s.mode} / state ${s.state?.executionMode||"UNKNOWN"}`,`Positions ${s.positions.length} • orders ${s.openOrders.length}`,`AI bridge ${s.ai?.ok?"OK":"DEGRADED"}`,`Last AI ${s.state?.lastAiReview?.at||"—"}`,`Last quote ${s.state?.lastPostAiQuote?.at||"—"}`,`Last manager ${s.state?.lastPositionManagement?.at||"—"}`,`Checked ${s.checkedAt}`].join("\n");}

export default {
 async fetch(req,env){
  const u=new URL(req.url);
  if(u.pathname==="/auto-hub/status")return json({ok:true,service:"BYBIT_AUTO_TRADE_HUB",readOnly:true,signalHub:false});
  if(u.pathname==="/telegram/webhook"&&req.method==="POST"){
   let update;try{update=await req.json();}catch{return json({ok:false,error:"BAD_JSON"},400);}if(!auth(update,env))return json({ok:false,error:"FORBIDDEN"},403);
   const cb=String(update?.callback_query?.data||""),msg=String(update?.message?.text||"");
   if(!(cb.startsWith("auto:")||["/start","/auto","/hub"].includes(msg)))return json({ok:false,error:"AUTO_HUB_ONLY"},404);
   const id=update?.callback_query?.message?.chat?.id??update?.message?.chat?.id??env.TELEGRAM_CHAT_ID,s=await snapshot(env);
   if(cb==="auto:positions")await send(env,id,["📌 VỊ THẾ LIVE",...positionLines(s)].join("\n\n"));
   else if(cb==="auto:target")await send(env,id,targetText(s));
   else if(cb==="auto:ai")await send(env,id,aiText(s));
   else if(cb==="auto:risk")await send(env,id,riskText(s));
   else if(cb==="auto:stats")await send(env,id,await statsText(env,s));
   else if(cb==="auto:runtime")await send(env,id,runtimeText(s));
   else await send(env,id,dashboard(s));
   return json({ok:true,owner:"BYBIT_AUTO_TRADE_HUB",readOnly:true});
  }
  if(u.pathname==="/"||u.pathname==="/hub"||u.pathname==="/auto-hub")return json({ok:true,service:"BYBIT_AUTO_TRADE_HUB",mode:bybitExecutionMode(env),readOnly:true,signalHub:false,telegram:"/telegram/webhook",dashboardButtons:["AUTO_DASHBOARD","LIVE_POSITIONS","TARGET","3_AI","RISK_SAFETY","PNL_LEARNING","RUNTIME"]});
  return null;
 }
};
