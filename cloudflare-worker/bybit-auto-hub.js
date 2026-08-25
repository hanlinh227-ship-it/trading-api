import {telegramApiRequest} from "./providers/telegram-client.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";
import {bybitExecutionMode} from "./bybit-auto-config.js";
import {bybitV5} from "./bybit-v5-client.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
const money=v=>Number.isFinite(Number(v))?`${Number(v)>=0?"+":""}$${Number(v).toFixed(2)}`:"—";
function px(v,tick=0){const n=Number(v);if(!Number.isFinite(n))return "—";const t=Math.abs(Number(tick||0));let d=8;if(t>0){const s=t.toFixed(12).replace(/0+$/,"");const p=s.indexOf(".");d=p<0?0:s.length-p-1;}else if(Math.abs(n)>=100)d=2;else if(Math.abs(n)>=1)d=4;else if(Math.abs(n)>=.01)d=5;else d=6;return n.toFixed(Math.min(8,d)).replace(/(\.\d*?[1-9])0+$|\.0+$/,"$1");}
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
function positionLines(s){if(!s.positions.length)return ["⚪ Không có vị thế LIVE."];return s.positions.map(x=>{const plan=s.state?.openPlans?.[x.symbol]||{},review=plan.lastReview||{},tick=Number(plan.tickSize||plan.filters?.tickSize||0),risk=Number(plan.riskUsd||0),reward=Number(plan.rewardUsd||0);return `${String(x.side).toLowerCase()==="buy"?"🟢":"🔴"} ${x.symbol} ${String(x.side).toUpperCase()}\nE ${px(x.avgPrice||plan.entry,tick)} • Mark ${px(x.markPrice,tick)}\nSL ${px(x.stopLoss||plan.managedSl||plan.sl,tick)} • -$${risk.toFixed(2)}\nTP ${px(x.takeProfit||plan.tp,tick)} • +$${reward.toFixed(2)}\nPnL ${money(x.unrealisedPnl)} • ${review.verdict||plan.managementPhase||"HOLD"}${Number.isFinite(Number(review.r))?` • R ${fmt(review.r,2)}`:""}`;});}
function dashboard(s){const t=s.state?.profitTarget||{},ai=s.ai||{};return [
 "🤖 BYBIT AUTO TRADE HUB",
 `🟢 ${s.mode} • ${String(s.state?.executionMode||"UNKNOWN")} • ${Number(s.state?.pauseUntil||0)>Date.now()?"PAUSED":"RUNNING"}`,
 `💰 Equity $${fmt(s.account.equity)} • Free $${fmt(s.account.available)}`,
 `📌 Position ${s.positions.length} • Orders ${s.openOrders.length}`,
 `📈 Realized ${money(s.state?.realizedUsd||0)}`,
 `🎯 ${t.status||"OFF"}${t.targetUsd?` • ${money(t.targetPnlUsd||0)} / +$${fmt(t.targetUsd,0)} • còn $${fmt(t.remainingUsd??t.targetUsd,2)}`:""}`,
 `🧠 AI ${ai.ok?"READY":"DEGRADED"} • ${Number(ai.online||0)}/${Number(ai.configured||3)} • ${ai.bridgeMode||"—"}`,
 `🛡️ Loss streak ${Number(s.state?.lossStreak||0)}`,
 `🕒 ${s.checkedAt}`
 ].join("\n");}
function targetText(s){const t=s.state?.profitTarget;return !t?"🎯 TARGET\n⚪ Chưa có target active.":["🎯 PROFIT TARGET",`Status: ${t.status}`,`Mục tiêu: +$${fmt(t.targetUsd,0)}`,`Đã đạt: ${money(t.targetPnlUsd||0)}`,`Còn lại: $${fmt(t.remainingUsd??Math.max(0,Number(t.targetUsd||0)-Number(t.targetPnlUsd||0)),2)}`,`Baseline: ${money(t.baselineRealizedUsd||0)}`,`Kết thúc: ${t.endAt}`,"Đạt target → dừng entry mới; vẫn HOLD/TIGHTEN/CUT."].join("\n");}
function aiText(s){const a=s.ai||{},ps=a.providers||{};return ["🧠 3 AI CORE",`Bridge: ${a.ok?"✅ READY":"⚠️ DEGRADED"} • ${a.bridgeMode||"—"}`,`Claude: ${ps.claude?.state||"—"}`,`Codex/ChatGPT: ${ps.codex?.state||"—"}`,`DeepSeek: ${ps.deepseek?.state||"—"}`,`Grace ${a.fastFirstGraceSec??"—"}s • budget ${a.bridgeBudgetSec??"—"}s`,s.state?.lastAiReview?`Last: ${s.state.lastAiReview.symbol} ${s.state.lastAiReview.side} • ${s.state.lastAiReview.mode} • usable ${s.state.lastAiReview.usable}`:"Last review: —"].join("\n");}
function riskText(s){const lp=s.state?.lastPnlReconcile||{},pm=s.state?.lastPositionManagement||{};return ["🛡️ RISK / SAFETY",`Mode ${s.mode} • ${Number(s.state?.pauseUntil||0)>Date.now()?"⏸ PAUSED":"▶️ RUNNING"}`,`Loss streak ${Number(s.state?.lossStreak||0)}`,`Realized ${money(s.state?.realizedUsd||0)}`,`Open plans ${Object.keys(s.state?.openPlans||{}).length}`,`PnL reconcile ${lp.at||"—"}`,`Position review ${pm.at||"—"}`,"post-AI drift • risk-by-balance • native SL/TP • HOLD/TIGHTEN/CUT"].join("\n");}
async function statsText(env,s){let l={};try{l=await getBybitLearningState(env)||{};}catch{}return ["📈 PNL / LEARNING",`Realized ${money(s.state?.realizedUsd||0)} • Trades ${Number(s.state?.trades||0)}`,`Closed ${Number(s.state?.lastPnlReconcile?.closedTrades||0)}`,`Learning ${Number(l.summary?.sampleSize||0)} • ${l.providerSet||"AUTO_CORE_3"}`,`Last trade ${s.state?.lastTradeAt?new Date(Number(s.state.lastTradeAt)).toISOString():"—"}`].join("\n");}
function runtimeText(s){const pm=s.state?.lastPositionManagement?.results||[],last=pm.at?.(-1)||{};return ["⚙️ AUTO RUNTIME",`Execution ${s.mode} / ${s.state?.executionMode||"UNKNOWN"}`,`Positions ${s.positions.length} • orders ${s.openOrders.length}`,`AI ${s.ai?.ok?"OK":"DEGRADED"}`,`Leverage ${s.state?.lastLeverageSet?.requested?`${s.state.lastLeverageSet.requested}x`:"AUTO 1-5x"}`,`Last AI ${s.state?.lastAiReview?.at||"—"}`,`Last quote ${s.state?.lastPostAiQuote?.at||"—"}`,`Last manager ${s.state?.lastPositionManagement?.at||"—"}${last.verdict?` • ${last.verdict}`:""}`,`Telegram entry ${s.state?.lastTelegramEntryAt||"—"}`,`Checked ${s.checkedAt}`].join("\n");}

export default {
 async fetch(req,env){
  const u=new URL(req.url);
  if(u.pathname==="/auto-hub/status")return json({ok:true,service:"BYBIT_AUTO_TRADE_HUB",readOnly:true,signalHub:false,telegramEntryAlerts:true,compactPrices:true});
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
  if(u.pathname==="/"||u.pathname==="/hub"||u.pathname==="/auto-hub")return json({ok:true,service:"BYBIT_AUTO_TRADE_HUB",mode:bybitExecutionMode(env),readOnly:true,signalHub:false,telegram:"/telegram/webhook",telegramEntryAlerts:true,compactPrices:true,dashboardButtons:["AUTO_DASHBOARD","LIVE_POSITIONS","TARGET","3_AI","RISK_SAFETY","PNL_LEARNING","RUNTIME"]});
  return null;
 }
};