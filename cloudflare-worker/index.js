import signalHub from "./hub-v77171.js";
import {getHyroProfile,getHyroControl,setHyroPaused,getHyroTelemetry,getHyroDiagnostics,reconcileHyro,cancelHyroPending,hyroExecutionConfig} from "./hyro-execution.js";
import {runHyroAutoCycle,getHyroRuntime} from "./hyro-runtime.js";

const VERSION="V77.18.3";
const SERVICE="Trading V77.18.3 Independent Signal-Prop-Personal Runtime";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});
const money=v=>{const x=Number(v||0),sign=x>0?"+":"";return sign+"$"+x.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});};
const cash=v=>"$"+Number(v||0).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const ago=ts=>{if(!ts)return "—";const s=Math.max(0,Math.round((Date.now()-Number(ts))/1000));if(s<60)return `${s}s trước`;const m=Math.round(s/60);if(m<60)return `${m}m trước`;return `${Math.round(m/60)}h trước`;};

async function tg(env,method,payload){
  const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)}),p=await r.json();
  if(!p.ok)throw new Error(p.description||"Telegram error");
  return p;
}
async function send(env,chatId,text,reply_markup){return tg(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function verify(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}
function phaseName(p){return p?.phase==="FUNDED"?"FUNDED":"CHALLENGE";}
function programName(p){return p?.program==="TWO_STEP"?"Two-Step":"One-Step";}
function ddName(p){return p?.drawdownType==="SWING_STATIC"?"Swing / Static":"Standard / Trailing";}
function propKeyboard(paused=false){return {inline_keyboard:[[{text:"📊 TỔNG QUAN TÀI KHOẢN",callback_data:"prop:dashboard"}],[{text:"📈 VỊ THẾ ĐANG CHẠY",callback_data:"prop:positions"},{text:"🛡️ RISK / DD",callback_data:"prop:risklive"}],[{text:"🔌 KẾT NỐI",callback_data:"prop:connectlive"}],[{text:paused?"▶️ TIẾP TỤC AUTO":"⛔ NGỪNG AUTO",callback_data:paused?"prop:resume":"prop:pause"}],[{text:"⚙️ ĐỔI CẤU HÌNH",callback_data:"prop:setup"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function posLine(p,i){const icon=(p.unrealisedPnl||0)>=0?"🟢":"🔴",side=p.side==="Buy"?"BUY":"SELL";return `${i+1}. ${icon} ${p.symbol} ${side}\n   Entry ${p.avgPrice} → Mark ${p.markPrice}\n   P/L ${money(p.unrealisedPnl)} | Size ${p.size}\n   SL ${p.stopLoss||"—"} | TP ${p.takeProfit||"—"}`;}

async function dashboard(env){
  const profile=await getHyroProfile(env),control=await getHyroControl(env),cfg=hyroExecutionConfig(env),t=await getHyroTelemetry(env);
  if(!profile)return {text:"🏦 PROP • HYROTRADER\n\nChưa cấu hình tài khoản. Bấm ⚙️ ĐỔI CẤU HÌNH để bắt đầu.",kb:propKeyboard(control.manualPaused)};
  if(!t.connected){
    const failed=(t.diagnostics?.endpoints||[]).filter(x=>!x.ok).map(x=>`${x.name}: ${x.retMsg||x.retCode||"FAIL"}`).join(" | ");
    return {text:[`🏦 HYROTRADER • ${phaseName(profile)}`,"",`${cash(profile.accountSize)} • ${programName(profile)} • ${ddName(profile)}`,`API: CHƯA ĐỦ TELEMETRY (${t.reason||"UNKNOWN"})`,failed?`Lỗi: ${failed}`:null,`AUTO: ${control.manualPaused?"PAUSED":cfg.autoExecutionRequested?"ARMED - FAIL CLOSED":"OFF"}`,"","PROP chỉ theo dõi/điều khiển tài khoản Hyro. Không nhận lệnh từ SIGNAL hay CÁ NHÂN."].filter(Boolean).join("\n"),kb:propKeyboard(control.manualPaused)};
  }
  const d=t.day||{},target=Number(profile.accountSize||0)*.05,dayPnl=Number(d.pnlFromDayStart||0),remain=Math.max(0,target-dayPnl);
  return {text:[`🏦 HYROTRADER • ${phaseName(profile)}`,"",`${programName(profile)} • ${ddName(profile)}`,`Equity: ${cash(t.equity)}`,`Wallet: ${cash(t.walletBalance)}`,`Available: ${cash(t.available)}`,"",`📅 P/L equity hôm nay: ${money(dayPnl)}`,`✅ Lãi đã chốt hôm nay: ${money(d.grossProfit||0)}`,`❌ Lỗ đã chốt hôm nay: -${cash(d.grossLoss||0)}`,`🧾 Net đã chốt: ${money(d.netRealized||0)}`,`💹 Floating hiện tại: ${money(t.totalUnrealised||0)}`,`🔢 Lệnh đã đóng: ${Number(d.closedTrades||0)}`,"",`📈 Peak equity: ${cash(d.peakEquity)}`,`📉 DD từ peak: -${cash(d.drawdownFromPeak||0)}`,`🎯 Target ngày +5%: ${cash(target)}`,`Còn tới target: ${cash(remain)}`,"",`Positions: ${t.positions.length} | Pending: ${t.openOrders.length}`,`Open-risk ước tính: ${cash(t.openRiskUsd||0)}`,`AUTO: ${control.manualPaused?"⛔ PAUSED":cfg.autoExecutionRequested?"▶️ ON":"OFF"}`,"",`Auto-trade chạy im lặng. Telegram không phát/nhắc lệnh auto; chỉ hiển thị trạng thái tài khoản và vị thế thật.`].join("\n"),kb:propKeyboard(control.manualPaused)};
}

async function positionsText(env){
  const t=await getHyroTelemetry(env),c=await getHyroControl(env);
  if(!t.connected)return {text:`📈 VỊ THẾ HYRO\n\nKhông thể xác nhận vị thế vì telemetry chưa đủ: ${t.reason||"NOT_CONNECTED"}.\nBot đang fail-closed, không được phép mở lệnh mới.`,kb:propKeyboard(c.manualPaused)};
  const body=t.positions.length?t.positions.map(posLine).join("\n\n"):"Không có vị thế đang mở.";
  return {text:`📈 VỊ THẾ HYRO ĐANG CHẠY\n\n${body}\n\nFloating tổng: ${money(t.totalUnrealised||0)}\nNet đã chốt hôm nay: ${money(t.day?.netRealized||0)}\nP/L equity hôm nay: ${money(t.day?.pnlFromDayStart||0)}`,kb:propKeyboard(c.manualPaused)};
}

async function riskText(env){
  const p=await getHyroProfile(env),t=await getHyroTelemetry(env),c=await getHyroControl(env);
  if(!p)return {text:"🛡️ RISK HYRO\n\nChưa cấu hình account.",kb:propKeyboard(c.manualPaused)};
  if(!t.connected)return {text:[`🛡️ RISK HYRO • ${phaseName(p)}`,"","⚠️ RISK/DD LIVE: UNAVAILABLE",`Telemetry: ${t.reason||"NOT_CONNECTED"}`,"Không hiển thị DD/P&L giả bằng $0 khi dữ liệu chưa đủ.","Bot fail-closed: chặn lệnh mới cho tới khi telemetry PASS."].join("\n"),kb:propKeyboard(c.manualPaused)};
  const i=p.internal||{},o=p.official||{},d=t.day||{};
  return {text:[`🛡️ RISK HYRO • ${phaseName(p)}`,"",`Official daily DD: ${o.dailyDrawdownPct??"—"}% = ${cash(o.dailyDrawdownUsd)}`,`Official max loss: ${o.maxLossPct??"—"}% = ${cash(o.maxLossUsd)}`,`Bot hard stop ngày: ${cash(i.dailyHardStopUsd)} (<3%)`,`Single worst-loss cap: ${cash(i.maxSingleWorstLossUsd)}`,`Combined open-risk cap: ${cash(i.maxCombinedOpenRiskUsd)}`,"",`DD hiện tại từ peak: ${cash(d.drawdownFromPeak||0)}`,`P/L equity hôm nay: ${money(d.pnlFromDayStart||0)}`,`Lãi chốt: ${money(d.grossProfit||0)} | Lỗ chốt: -${cash(d.grossLoss||0)}`,`Manual control: ${c.manualPaused?"PAUSED":"READY"}`].join("\n"),kb:propKeyboard(c.manualPaused)};
}

function endpointLine(x){
  if(x.ok)return `✅ ${x.name}: PASS (${x.elapsedMs}ms)`;
  const detail=x.retCode!=null?`${x.retCode} ${x.retMsg||""}`:(x.retMsg||"FAIL");
  return `❌ ${x.name}: ${detail}`;
}

async function connectText(env){
  const p=await getHyroProfile(env),c=await getHyroControl(env),cfg=hyroExecutionConfig(env),t=await getHyroTelemetry(env),rt=await getHyroRuntime(env);
  const ep=t.diagnostics?.endpoints||[];
  const runtimeState=rt?.reason||(rt?.executed?"ACTIVE":rt?"IDLE":"—");
  const runtimeAt=rt?.startedAt||rt?.at||null;
  return {text:["🔌 HYROTRADER CONNECTION","",`Profile: ${p?phaseName(p)+" • "+programName(p)+" • "+ddName(p):"CHƯA CẤU HÌNH"}`,`Mode: ${cfg.mode}`,`Credentials: ${cfg.credentialsReady?"OK":"MISSING"}`,`Fresh telemetry: ${t.connected?"CONNECTED":"NOT CONNECTED"}`,`Auto execution secret: ${cfg.autoExecutionRequested?"ON":"OFF"}`,`Manual pause: ${c.manualPaused?"ON":"OFF"}`,"",...ep.map(endpointLine),"",`Last auto cycle: ${runtimeState}${runtimeAt?` (${ago(runtimeAt)})`:""}`,rt?.error?`Cycle error: ${String(rt.error).slice(0,180)}`:null,"","Nếu một endpoint telemetry FAIL, execution tự chặn. Không hiển thị candidate/lệnh auto trên Telegram."].filter(Boolean).join("\n"),kb:propKeyboard(c.manualPaused)};
}

async function handlePropTelegram(req,env){
  if(!verify(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  let u;try{u=await req.clone().json();}catch{return null;}
  const cb=u?.callback_query?.data;
  if(!["prop","prop:hyro","prop:dashboard","prop:positions","prop:risklive","prop:connectlive","prop:pause","prop:resume"].includes(cb))return null;
  if(u?.callback_query?.id)tg(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  const chatId=u?.callback_query?.message?.chat?.id??env.TELEGRAM_CHAT_ID;
  if(cb==="prop:pause"){
    const c=await setHyroPaused(env,true);
    await cancelHyroPending(env).catch(()=>{});
    await send(env,chatId,"⛔ HYRO AUTO ĐÃ DỪNG\n\nChỉ chặn PROP mở lệnh mới. SIGNAL, CÁ NHÂN, monitoring tài khoản và quản lý vị thế hiện có vẫn hoạt động.",propKeyboard(c.manualPaused));
    return json({ok:true,version:VERSION,manualPaused:true});
  }
  if(cb==="prop:resume"){
    const c=await setHyroPaused(env,false);
    await send(env,chatId,"▶️ HYRO AUTO ĐÃ CHO PHÉP HOẠT ĐỘNG\n\nChỉ thực sự gửi order nếu API connected + HYRO_AUTO_EXECUTION=true + toàn bộ telemetry + Risk Firewall PASS.",propKeyboard(c.manualPaused));
    return json({ok:true,version:VERSION,manualPaused:false});
  }
  let x;
  if(cb==="prop:positions")x=await positionsText(env);
  else if(cb==="prop:risklive")x=await riskText(env);
  else if(cb==="prop:connectlive")x=await connectText(env);
  else x=await dashboard(env);
  await send(env,chatId,x.text,x.kb);
  return json({ok:true,version:VERSION,propDashboard:true});
}

async function patchedStatus(req,env){
  const r=await signalHub.fetch(req,env);let p;try{p=await r.clone().json();}catch{return r;}
  const cfg=hyroExecutionConfig(env),control=await getHyroControl(env),runtime=await getHyroRuntime(env);
  return json({...p,version:VERSION,service:SERVICE,architecture:{signal:"INDEPENDENT_TELEGRAM_SIGNAL_ONLY",prop:"INDEPENDENT_HYRO_SILENT_AUTO_ACCOUNT_DASHBOARD",personal:"INDEPENDENT_RESERVED_RUNTIME"},hyro:{...cfg,manualPaused:control.manualPaused,silentTelegram:true,lastRuntime:runtime?{ok:runtime.ok,executed:runtime.executed,reason:runtime.reason,error:runtime.error||null,at:runtime.startedAt||runtime.at}:null}},r.status);
}

export default {
  async fetch(req,env,ctx){
    const u=new URL(req.url),path=u.pathname.replace(/\/$/,"")||"/";
    if(path==="/status")return patchedStatus(req,env);
    if(path==="/prop/hyro/telemetry")return json(await getHyroTelemetry(env));
    if(path==="/prop/hyro/diagnostics")return json(await getHyroDiagnostics(env));
    if(path==="/prop/hyro/reconcile")return json(await reconcileHyro(env));
    if(path==="/prop/hyro/runtime")return json({ok:true,version:VERSION,runtime:await getHyroRuntime(env)});
    if(path==="/telegram/webhook"&&req.method==="POST"){
      const handled=await handlePropTelegram(req,env);
      if(handled)return handled;
    }
    return signalHub.fetch(req,env,ctx);
  },
  async scheduled(controller,env,ctx){
    const signalPromise=Promise.resolve(signalHub.scheduled?.(controller,env,ctx)).catch(()=>null);
    const hyroPromise=runHyroAutoCycle(env).catch(async e=>{
      if(env.TRADING_STATE)await env.TRADING_STATE.put("v7718:hyro:runtime",JSON.stringify({ok:false,executed:false,reason:"AUTO_CYCLE_EXCEPTION",error:String(e?.message||e),at:Date.now()}));
      return null;
    });
    if(ctx?.waitUntil){ctx.waitUntil(signalPromise);ctx.waitUntil(hyroPromise);return;}
    await Promise.allSettled([signalPromise,hyroPromise]);
  }
};
