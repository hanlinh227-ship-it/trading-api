import baseEngine from "./engine-v77168.js";

const VERSION = "V77.17.0";
const SERVICE = "Trading V77.17.0 Phase-Aware HyroTrader Prop Hub";
const HYRO_PROFILE_KEY = "v7717:hyro:profile";

const json = (body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});

async function telegram(env,method,payload){
  if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");
  const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)});
  const p=await r.json();if(!p.ok)throw new Error(p.description||"Telegram error");return p;
}
async function sendText(env,text,chatId,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🏦 PROP",callback_data:"prop"},{text:"👤 CÁ NHÂN",callback_data:"personal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"books"}]]};}
function propKeyboard(configured=false){const rows=[];if(configured)rows.push([{text:"🟣 TỔNG QUAN HYRO",callback_data:"prop:hyro"}]);else rows.push([{text:"🟣 THIẾT LẬP HYROTRADER",callback_data:"prop:setup"}]);rows.push([{text:"📚 LỆNH HYRO",callback_data:"prop:orders"},{text:"🛡️ RISK HYRO",callback_data:"prop:risk"}]);rows.push([{text:"🔌 KẾT NỐI HYRO",callback_data:"prop:connect"},{text:"⚙️ ĐỔI PHASE",callback_data:"prop:setup"}]);rows.push([{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]);return {inline_keyboard:rows};}
function phaseKeyboard(){return {inline_keyboard:[[{text:"🎯 CHALLENGE",callback_data:"prop:phase:challenge"},{text:"💰 FUNDED",callback_data:"prop:phase:funded"}],[{text:"⬅️ PROP",callback_data:"prop"}]]};}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}

function hyroRiskProfile(phase){
  const base={provider:"HYROTRADER",accountSize:5000,program:"ONE_STEP",drawdownType:"STANDARD_TRAILING",official:{dailyDrawdownPct:4,dailyDrawdownUsd:200,maxLossPct:6,maxLossUsd:300,maxRealizedLossPerTradePct:3,maxRealizedLossPerTradeUsd:150},internal:{dailyCautionUsd:110,dailyDefenseUsd:135,dailyHardStopUsd:145,maxSingleWorstLossUsd:100,maxCombinedOpenRiskUsd:phase==="FUNDED"?100:120,normalRiskUsd:phase==="FUNDED"?35:40,aPlusRiskUsd:phase==="FUNDED"?50:55,givebackGuard:true,slRequiredByBot:true}};
  if(phase==="FUNDED")return {...base,phase:"FUNDED",challenge:null,funded:{profitDistributionRule:false,maxMarginExposurePct:25,maxMarginExposureUsd:1250,maxNotionalMultiple:2,maxNotionalUsd:10000,internalMarginCapUsd:1125,internalNotionalCapUsd:9000}};
  return {...base,phase:"CHALLENGE",challenge:{profitTargetPct:10,profitTargetUsd:500,minTradingDays:5,profitDistributionMaxDayPct:40},funded:null};
}
async function getHyroProfile(env){try{return await env.TRADING_STATE?.get(HYRO_PROFILE_KEY,"json");}catch{return null;}}
async function setHyroPhase(env,phase){const p={...hyroRiskProfile(phase),configuredAt:Date.now(),autoTrade:false,connected:false};await env.TRADING_STATE?.put(HYRO_PROFILE_KEY,JSON.stringify(p));return p;}
function phaseName(p){return p?.phase==="FUNDED"?"FUNDED":"CHALLENGE";}
function riskText(p){if(!p)return "🛡️ HYROTRADER • RISK\n\nChưa chọn CHALLENGE/FUNDED nên Risk Firewall chưa được kích hoạt.";const i=p.internal,o=p.official,L=[`🛡️ HYROTRADER • RISK • ${phaseName(p)}`,"",`Account: $${p.accountSize} • One-Step • Standard/Trailing`,`Official daily DD: ${o.dailyDrawdownPct}% = $${o.dailyDrawdownUsd}`,`Official max loss: ${o.maxLossPct}% = $${o.maxLossUsd}`,`Official max realized loss/trade: ${o.maxRealizedLossPerTradePct}% = $${o.maxRealizedLossPerTradeUsd}`,"",`BOT daily caution: -$${i.dailyCautionUsd}`,`BOT daily defense: -$${i.dailyDefenseUsd}`,`BOT HARD STOP: -$${i.dailyHardStopUsd} (<3%)`,`Max worst-case / trade: $${i.maxSingleWorstLossUsd}`,`Max combined open risk: $${i.maxCombinedOpenRiskUsd}`,`Risk thường: ~$${i.normalRiskUsd} • A+: ~$${i.aPlusRiskUsd}`];if(p.phase==="CHALLENGE")L.push("",`Profit target: +$${p.challenge.profitTargetUsd}`,`Minimum days: ${p.challenge.minTradingDays}`,`40% distribution guard: ON`);else L.push("",`40% distribution guard: OFF`,`Funded margin cap official: $${p.funded.maxMarginExposureUsd}`,`Funded notional cap official: $${p.funded.maxNotionalUsd}`,`Bot margin cap: $${p.funded.internalMarginCapUsd}`,`Bot notional cap: $${p.funded.internalNotionalCapUsd}`);L.push("","Auto trade: OFF cho tới khi API/account telemetry thật được nối.");return L.join("\n");}
function overviewText(p){if(!p)return "🟣 HYROTRADER\n\nChưa cấu hình phase. Hãy chọn CHALLENGE hoặc FUNDED để Hub tự áp đúng luật.";const L=[`🟣 HYROTRADER • ${phaseName(p)}`,"","Program: One-Step 5,000 USDT","Drawdown: Standard / Trailing",`Risk Firewall: ACTIVE • hard-stop nội bộ -$${p.internal.dailyHardStopUsd}`,`Account/API: ${p.connected?"CONNECTED":"CHƯA KẾT NỐI"}`,`Auto trade: ${p.autoTrade?"ON":"OFF"}`];if(p.phase==="CHALLENGE")L.push(`Target: +$${p.challenge.profitTargetUsd} • 40% consistency guard ON • ≥${p.challenge.minTradingDays} ngày`);else L.push(`No profit target • no 40% rule • margin/notional funded guard ON`);L.push("","Bấm ⚙️ ĐỔI PHASE khi pass Challenge để Risk Firewall chuyển sang luật Funded.");return L.join("\n");}

async function handleHyroTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  const probe=req.clone();let u;try{u=await probe.json();}catch{return null;}
  const chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID;
  const cb=u?.callback_query?.data,text=String(u?.message?.text||"");
  const handled = cb==="prop" || cb==="prop:setup" || cb==="prop:hyro" || cb==="prop:orders" || cb==="prop:risk" || cb==="prop:connect" || cb?.startsWith("prop:phase:") || cb==="menu" || text==="/start" || text==="/menu";
  if(!handled)return null;
  if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  const profile=await getHyroProfile(env);
  if(cb==="menu"||text==="/start"||text==="/menu")await sendText(env,"🏠 TRADING HUB\n\nChọn khu vực:",chatId,baseKeyboard());
  else if(cb==="prop"){
    if(!profile)await sendText(env,"🏦 PROP • HYROTRADER\n\nChưa cấu hình tài khoản. Bạn đang ở giai đoạn nào?",chatId,phaseKeyboard());
    else await sendText(env,`🏦 PROP • HYROTRADER\n\nPhase hiện tại: ${phaseName(profile)}\nRisk Firewall: ACTIVE\nAuto trade: OFF`,chatId,propKeyboard(true));
  }
  else if(cb==="prop:setup")await sendText(env,"⚙️ HYROTRADER • CHỌN PHASE\n\nChọn đúng trạng thái tài khoản hiện tại. Hub sẽ lưu vào KV và tự đổi rule/risk profile.",chatId,phaseKeyboard());
  else if(cb?.startsWith("prop:phase:")){
    const phase=cb.endsWith(":funded")?"FUNDED":"CHALLENGE",p=await setHyroPhase(env,phase);
    await sendText(env,`✅ ĐÃ CHỌN ${phase}\n\n${overviewText(p)}\n\n${riskText(p)}`,chatId,propKeyboard(true));
  }
  else if(cb==="prop:hyro")await sendText(env,overviewText(profile),chatId,propKeyboard(!!profile));
  else if(cb==="prop:risk")await sendText(env,riskText(profile),chatId,propKeyboard(!!profile));
  else if(cb==="prop:orders")await sendText(env,`📚 HYROTRADER • LỆNH\n\nPhase: ${profile?phaseName(profile):"CHƯA CHỌN"}\nAccount telemetry: CHƯA KẾT NỐI\n\nSau khi nối API, màn hình này sẽ chỉ hiển thị positions/pending orders thật của tài khoản Hyro và đối chiếu chúng với Signal Hub.`,chatId,propKeyboard(!!profile));
  else if(cb==="prop:connect")await sendText(env,`🔌 HYROTRADER • KẾT NỐI\n\nPhase: ${profile?phaseName(profile):"CHƯA CHỌN"}\nTrạng thái: NOT CONNECTED\nAuto trade: OFF\n\nKhông nhập API key vào Telegram. Credentials sẽ được lưu dưới Cloudflare Secret khi bước execution được triển khai.`,chatId,propKeyboard(!!profile));
  return json({ok:true,version:VERSION,hyroPhase:profile?.phase||null});
}

async function patchedStatus(req,env){
  const r=await baseEngine.fetch(req,env);let p;try{p=await r.clone().json();}catch{return r;}const hp=await getHyroProfile(env);
  return json({...p,version:VERSION,service:SERVICE,prop:{provider:"HYROTRADER",phase:hp?.phase||null,program:hp?.program||"ONE_STEP",accountSize:hp?.accountSize||5000,drawdownType:hp?.drawdownType||"STANDARD_TRAILING",connected:!!hp?.connected,autoTrade:!!hp?.autoTrade,riskShell:hp?"ACTIVE":"AWAITING_PHASE"}} ,r.status);
}

export default {
  async fetch(req,env,ctx){
    const u=new URL(req.url),path=u.pathname.replace(/\/$/,"")||"/";
    if(path==="/status")return patchedStatus(req,env);
    if(path==="/prop/hyro/profile"){const p=await getHyroProfile(env);return json({ok:true,version:VERSION,configured:!!p,profile:p});}
    if(path==="/telegram/menu"){
      const hp=await getHyroProfile(env);await sendText(env,`🤖 TRADING HUB ${VERSION}\nChọn khu vực. PROP: HyroTrader${hp?" • "+phaseName(hp):" • chưa chọn phase"}.`,env.TELEGRAM_CHAT_ID,baseKeyboard());
      return json({ok:true,version:VERSION,hyroPhase:hp?.phase||null});
    }
    if(path==="/telegram/webhook"&&req.method==="POST"){
      const handled=await handleHyroTelegram(req,env);if(handled)return handled;
    }
    return baseEngine.fetch(req,env,ctx);
  },
  async scheduled(controller,env,ctx){return baseEngine.scheduled(controller,env,ctx);}
};