import baseEngine from "./engine-v77168.js";

const VERSION = "V77.17.1";
const SERVICE = "Trading V77.17.1 HyroTrader Adaptive Account Wizard";
const HYRO_PROFILE_KEY = "v7717:hyro:profile";
const HYRO_DRAFT_KEY = "v77171:hyro:draft";
const ACCOUNT_SIZES = [5000,10000,25000,50000,100000,200000];

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});
const money=v=>"$"+Number(v||0).toLocaleString("en-US",{maximumFractionDigits:0});
async function telegram(env,method,payload){if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)}),p=await r.json();if(!p.ok)throw new Error(p.description||"Telegram error");return p;}
async function sendText(env,text,chatId,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🏦 PROP",callback_data:"prop"},{text:"👤 CÁ NHÂN",callback_data:"personal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"books"}]]};}
function propKeyboard(configured=false){const rows=[];rows.push([{text:configured?"🟣 TỔNG QUAN HYRO":"🟣 THIẾT LẬP HYROTRADER",callback_data:configured?"prop:hyro":"prop:setup"}]);rows.push([{text:"📚 LỆNH HYRO",callback_data:"prop:orders"},{text:"🛡️ RISK HYRO",callback_data:"prop:risk"}]);rows.push([{text:"🔌 KẾT NỐI HYRO",callback_data:"prop:connect"},{text:"⚙️ ĐỔI CẤU HÌNH",callback_data:"prop:setup"}]);rows.push([{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]);return {inline_keyboard:rows};}
function phaseKeyboard(){return {inline_keyboard:[[{text:"🎯 CHALLENGE",callback_data:"prop:wiz:phase:CHALLENGE"},{text:"💰 FUNDED",callback_data:"prop:wiz:phase:FUNDED"}],[{text:"⬅️ PROP",callback_data:"prop"}]]};}
function sizeKeyboard(){const r=[];for(let i=0;i<ACCOUNT_SIZES.length;i+=2)r.push(ACCOUNT_SIZES.slice(i,i+2).map(v=>({text:money(v),callback_data:`prop:wiz:size:${v}`})));r.push([{text:"⬅️ Chọn lại phase",callback_data:"prop:setup"}]);return {inline_keyboard:r};}
function drawdownKeyboard(){return {inline_keyboard:[[{text:"📉 STANDARD / TRAILING",callback_data:"prop:wiz:dd:STANDARD_TRAILING"}],[{text:"🛟 SWING / STATIC",callback_data:"prop:wiz:dd:SWING_STATIC"}],[{text:"⬅️ Chọn lại size",callback_data:"prop:wiz:back:size"}]]};}
function stepKeyboard(){return {inline_keyboard:[[{text:"1️⃣ ONE-STEP",callback_data:"prop:wiz:step:ONE_STEP"},{text:"2️⃣ TWO-STEP",callback_data:"prop:wiz:step:TWO_STEP"}],[{text:"⬅️ Chọn lại drawdown",callback_data:"prop:wiz:back:dd"}]]};}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}
async function getHyroProfile(env){try{return await env.TRADING_STATE?.get(HYRO_PROFILE_KEY,"json");}catch{return null;}}
async function getDraft(env){try{return await env.TRADING_STATE?.get(HYRO_DRAFT_KEY,"json")||{};}catch{return {};}}
async function saveDraft(env,d){await env.TRADING_STATE?.put(HYRO_DRAFT_KEY,JSON.stringify({...d,updatedAt:Date.now()}),{expirationTtl:1800});}
async function clearDraft(env){try{await env.TRADING_STATE?.delete(HYRO_DRAFT_KEY);}catch{}}

function buildHyroProfile({phase,accountSize,drawdownType,program}){
  const size=Number(accountSize),isOne=program!=="TWO_STEP",dailyPct=isOne?4:5,maxLossPct=isOne?6:10;
  const official={dailyDrawdownPct:dailyPct,dailyDrawdownUsd:size*dailyPct/100,maxLossPct,maxLossUsd:size*maxLossPct/100,maxRealizedLossPerTradePct:3,maxRealizedLossPerTradeUsd:size*.03};
  const internalDailyHardPct=2.9,internal={dailyCautionUsd:Math.round(size*.022),dailyDefenseUsd:Math.round(size*.027),dailyHardStopUsd:Math.round(size*internalDailyHardPct/100),maxSingleWorstLossUsd:Math.round(size*.02),maxCombinedOpenRiskUsd:Math.round(size*(phase==="FUNDED"?.02:.024)),normalRiskUsd:Math.round(size*(phase==="FUNDED"?.007:.008)),aPlusRiskUsd:Math.round(size*(phase==="FUNDED"?.010:.011)),givebackGuard:true,slRequiredByBot:true};
  const challenge=phase==="CHALLENGE"?{profitTargetPhase1Pct:10,profitTargetPhase1Usd:size*.10,profitTargetPhase2Pct:isOne?null:5,profitTargetPhase2Usd:isOne?null:size*.05,minTradingDays:5,profitDistributionMaxDayPct:40}:null;
  const funded=phase==="FUNDED"?{profitDistributionRule:false,maxMarginExposurePct:25,maxMarginExposureUsd:size*.25,maxNotionalMultiple:2,maxNotionalUsd:size*2,internalMarginCapUsd:size*.225,internalNotionalCapUsd:size*1.8}:null;
  return {provider:"HYROTRADER",phase,accountSize:size,program:isOne?"ONE_STEP":"TWO_STEP",drawdownType,official,internal,challenge,funded,configuredAt:Date.now(),connected:false,autoTrade:false};
}
async function commitProfile(env,d){const p=buildHyroProfile(d);await env.TRADING_STATE?.put(HYRO_PROFILE_KEY,JSON.stringify(p));await clearDraft(env);return p;}
function phaseName(p){return p?.phase==="FUNDED"?"FUNDED":"CHALLENGE";}
function ddName(p){return p?.drawdownType==="SWING_STATIC"?"Swing / Static":"Standard / Trailing";}
function programName(p){return p?.program==="TWO_STEP"?"Two-Step":"One-Step";}
function overviewText(p){if(!p)return "🟣 HYROTRADER\n\nChưa cấu hình tài khoản. Bấm ⚙️ để bắt đầu wizard.";const L=[`🟣 HYROTRADER • ${phaseName(p)}`,"",`Account: ${money(p.accountSize)}`,`Program: ${programName(p)}`,`Drawdown: ${ddName(p)}`,`Risk Firewall: ACTIVE • hard-stop ${money(p.internal.dailyHardStopUsd)} / ngày`, `Account/API: ${p.connected?"CONNECTED":"CHƯA KẾT NỐI"}`,`Auto trade: ${p.autoTrade?"ON":"OFF"}`];if(p.challenge){L.push(`Target P1: +${money(p.challenge.profitTargetPhase1Usd)}`);if(p.challenge.profitTargetPhase2Usd)L.push(`Target P2: +${money(p.challenge.profitTargetPhase2Usd)}`);L.push(`40% distribution guard: ON`);}else L.push(`Funded exposure guards: ON`);return L.join("\n");}
function riskText(p){if(!p)return "🛡️ HYROTRADER • RISK\n\nChưa cấu hình account.";const o=p.official,i=p.internal,L=[`🛡️ HYROTRADER • RISK • ${phaseName(p)}`,"",`${money(p.accountSize)} • ${programName(p)} • ${ddName(p)}`,`Official daily DD: ${o.dailyDrawdownPct}% = ${money(o.dailyDrawdownUsd)}`,`Official max loss: ${o.maxLossPct}% = ${money(o.maxLossUsd)}`,`Official max realized loss/trade: 3% = ${money(o.maxRealizedLossPerTradeUsd)}`,"",`BOT caution: -${money(i.dailyCautionUsd)}`,`BOT defense: -${money(i.dailyDefenseUsd)}`,`BOT HARD STOP: -${money(i.dailyHardStopUsd)} (<3%)`,`Worst-case / trade cap: ${money(i.maxSingleWorstLossUsd)}`,`Combined open-risk cap: ${money(i.maxCombinedOpenRiskUsd)}`,`Risk thường: ~${money(i.normalRiskUsd)} • A+: ~${money(i.aPlusRiskUsd)}`];if(p.challenge){L.push("",`40% distribution guard: ON`,`Minimum trading days: ${p.challenge.minTradingDays}`);}else L.push("",`40% distribution guard: OFF`,`Funded margin cap official: ${money(p.funded.maxMarginExposureUsd)}`,`Funded notional cap official: ${money(p.funded.maxNotionalUsd)}`);L.push("","Auto trade vẫn OFF cho tới khi account/API telemetry thật được nối.");return L.join("\n");}

async function handleWizard(cb,env,chatId){
  let d=await getDraft(env);
  if(cb==="prop:setup"){d={};await saveDraft(env,d);await sendText(env,"⚙️ HYROTRADER • BƯỚC 1/4\n\nTài khoản hiện đang ở giai đoạn nào?",chatId,phaseKeyboard());return true;}
  if(cb?.startsWith("prop:wiz:phase:")){d={phase:cb.split(":").at(-1)};await saveDraft(env,d);await sendText(env,"⚙️ HYROTRADER • BƯỚC 2/4\n\nTài khoản có quy mô bao nhiêu?",chatId,sizeKeyboard());return true;}
  if(cb?.startsWith("prop:wiz:size:")){d={...d,accountSize:Number(cb.split(":").at(-1))};await saveDraft(env,d);await sendText(env,"⚙️ HYROTRADER • BƯỚC 3/4\n\nDrawdown của tài khoản là loại nào?\n\nStandard = trailing theo peak trong ngày.\nSwing = static theo equity đầu ngày.",chatId,drawdownKeyboard());return true;}
  if(cb?.startsWith("prop:wiz:dd:")){d={...d,drawdownType:cb.split(":").at(-1)};await saveDraft(env,d);if(d.phase==="FUNDED"){const old=await getHyroProfile(env),program=old?.program||"ONE_STEP",p=await commitProfile(env,{...d,program});await sendText(env,"✅ ĐÃ LƯU CẤU HÌNH FUNDED\n\n"+overviewText(p)+"\n\n"+riskText(p),chatId,propKeyboard(true));}else await sendText(env,"⚙️ HYROTRADER • BƯỚC 4/4\n\nChallenge này là 1-Step hay 2-Step?",chatId,stepKeyboard());return true;}
  if(cb?.startsWith("prop:wiz:step:")){d={...d,program:cb.split(":").at(-1)};const p=await commitProfile(env,d);await sendText(env,"✅ ĐÃ LƯU CẤU HÌNH CHALLENGE\n\n"+overviewText(p)+"\n\n"+riskText(p),chatId,propKeyboard(true));return true;}
  if(cb==="prop:wiz:back:size"){await sendText(env,"⚙️ HYROTRADER • CHỌN LẠI SIZE",chatId,sizeKeyboard());return true;}
  if(cb==="prop:wiz:back:dd"){await sendText(env,"⚙️ HYROTRADER • CHỌN LẠI DRAWDOWN",chatId,drawdownKeyboard());return true;}
  return false;
}

async function handleHyroTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);const probe=req.clone();let u;try{u=await probe.json();}catch{return null;}const chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID,cb=u?.callback_query?.data,text=String(u?.message?.text||"");const handled=cb==="prop"||cb==="prop:setup"||cb==="prop:hyro"||cb==="prop:orders"||cb==="prop:risk"||cb==="prop:connect"||cb?.startsWith("prop:wiz:")||cb==="menu"||text==="/start"||text==="/menu";if(!handled)return null;if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  if(cb==="menu"||text==="/start"||text==="/menu"){await sendText(env,"🏠 TRADING HUB\n\nChọn khu vực:",chatId,baseKeyboard());return json({ok:true,version:VERSION});}
  if(await handleWizard(cb,env,chatId))return json({ok:true,version:VERSION,wizard:true});
  const p=await getHyroProfile(env);
  if(cb==="prop"){if(!p)await sendText(env,"🏦 PROP • HYROTRADER\n\nChưa cấu hình. Bắt đầu thiết lập account:",chatId,propKeyboard(false));else await sendText(env,overviewText(p),chatId,propKeyboard(true));}
  else if(cb==="prop:hyro")await sendText(env,overviewText(p),chatId,propKeyboard(!!p));
  else if(cb==="prop:risk")await sendText(env,riskText(p),chatId,propKeyboard(!!p));
  else if(cb==="prop:orders")await sendText(env,`📚 HYROTRADER • LỆNH\n\nAccount: ${p?money(p.accountSize):"CHƯA CẤU HÌNH"}\nPhase: ${p?phaseName(p):"—"}\nTelemetry: CHƯA KẾT NỐI\n\nSau khi nối API, đây sẽ là positions/pending thật và reconciliation với Signal Hub.`,chatId,propKeyboard(!!p));
  else if(cb==="prop:connect")await sendText(env,`🔌 HYROTRADER • KẾT NỐI\n\nProfile: ${p?phaseName(p)+" • "+money(p.accountSize)+" • "+programName(p)+" • "+ddName(p):"CHƯA CẤU HÌNH"}\nStatus: NOT CONNECTED\nAuto trade: OFF\n\nKhông nhập API key vào Telegram. Credentials sẽ đặt trong Cloudflare Secret ở bước execution.`,chatId,propKeyboard(!!p));
  return json({ok:true,version:VERSION,hyroConfigured:!!p});
}
async function patchedStatus(req,env){const r=await baseEngine.fetch(req,env);let p;try{p=await r.clone().json();}catch{return r;}const hp=await getHyroProfile(env);return json({...p,version:VERSION,service:SERVICE,prop:{provider:"HYROTRADER",phase:hp?.phase||null,program:hp?.program||null,accountSize:hp?.accountSize||null,drawdownType:hp?.drawdownType||null,connected:!!hp?.connected,autoTrade:!!hp?.autoTrade,riskShell:hp?"ACTIVE":"AWAITING_WIZARD"}},r.status);}

export default {async fetch(req,env,ctx){const u=new URL(req.url),path=u.pathname.replace(/\/$/,"")||"/";if(path==="/status")return patchedStatus(req,env);if(path==="/prop/hyro/profile"){const p=await getHyroProfile(env);return json({ok:true,version:VERSION,configured:!!p,profile:p});}if(path==="/telegram/menu"){const hp=await getHyroProfile(env);await sendText(env,`🤖 TRADING HUB ${VERSION}\nPROP: HyroTrader${hp?" • "+phaseName(hp)+" • "+money(hp.accountSize):" • chưa cấu hình"}.`,env.TELEGRAM_CHAT_ID,baseKeyboard());return json({ok:true,version:VERSION});}if(path==="/telegram/webhook"&&req.method==="POST"){const handled=await handleHyroTelegram(req,env);if(handled)return handled;}return baseEngine.fetch(req,env,ctx);},async scheduled(controller,env,ctx){return baseEngine.scheduled(controller,env,ctx);}};
