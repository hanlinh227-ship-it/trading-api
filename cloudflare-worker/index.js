import baseEngine from "./engine-v77168.js";

const VERSION = "V77.16.9";
const SERVICE = "Trading V77.16.9 Hyro-Only Prop Shell";

const json = (body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});

async function telegram(env,method,payload){
  if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");
  const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)});
  const p=await r.json();if(!p.ok)throw new Error(p.description||"Telegram error");return p;
}
async function sendText(env,text,chatId,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🏦 PROP",callback_data:"prop"},{text:"👤 CÁ NHÂN",callback_data:"personal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"books"}]]};}
function propKeyboard(){return {inline_keyboard:[[{text:"🟣 HYROTRADER",callback_data:"prop:hyro"}],[{text:"📚 LỆNH HYRO",callback_data:"prop:orders"},{text:"🛡️ RISK HYRO",callback_data:"prop:risk"}],[{text:"🔌 KẾT NỐI HYRO",callback_data:"prop:connect"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}

async function handleHyroTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  const probe=req.clone();let u;try{u=await probe.json();}catch{return null;}
  const chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID;
  const cb=u?.callback_query?.data,text=String(u?.message?.text||"");
  const handled = cb==="prop" || cb==="prop:hyro" || cb==="prop:orders" || cb==="prop:risk" || cb==="prop:connect" || cb==="menu" || text==="/start" || text==="/menu";
  if(!handled)return null;
  if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  if(cb==="menu"||text==="/start"||text==="/menu")await sendText(env,"🏠 TRADING HUB\n\nChọn khu vực:",chatId,baseKeyboard());
  else if(cb==="prop")await sendText(env,"🏦 PROP • HYROTRADER\n\nKhu vực PROP hiện chỉ dành cho HyroTrader. Signal Hub vẫn hoạt động độc lập.\n\nAUTO TRADE: OFF\nACCOUNT/API: CHƯA KẾT NỐI",chatId,propKeyboard());
  else if(cb==="prop:hyro")await sendText(env,"🟣 HYROTRADER • TỔNG QUAN\n\nKết nối account/API: CHƯA\nBalance/Equity telemetry: CHƯA\nPositions telemetry: CHƯA\nRisk firewall: SHELL READY\nAuto trade: OFF\n\nKhông có MARKET/LIMIT nào từ Signal Hub được route sang HyroTrader ở giai đoạn này.",chatId,propKeyboard());
  else if(cb==="prop:orders")await sendText(env,"📚 HYROTRADER • LỆNH\n\nChưa kết nối account nên chưa có positions/pending orders thật từ HyroTrader.\nLIVE ORDERS của Signal Hub vẫn được lưu riêng và không bị coi là lệnh HyroTrader.",chatId,propKeyboard());
  else if(cb==="prop:risk")await sendText(env,"🛡️ HYROTRADER • RISK\n\nRisk shell đã sẵn sàng nhưng chưa có balance/equity/account limits thật.\nAuto execution vẫn OFF. Sau khi kết nối, mọi lệnh phải qua daily loss, max loss, exposure, position risk và kill switch trước execution.",chatId,propKeyboard());
  else if(cb==="prop:connect")await sendText(env,"🔌 HYROTRADER • KẾT NỐI\n\nTrạng thái: NOT CONNECTED\nAuto trade: OFF\n\nBước tiếp theo mới nghiên cứu API/execution chính thức, rule quỹ, secrets và account telemetry. Không nhập API key vào Telegram.",chatId,propKeyboard());
  return json({ok:true,version:VERSION,hyroShell:true});
}

async function patchedStatus(req,env){
  const r=await baseEngine.fetch(req,env);let p;try{p=await r.clone().json();}catch{return r;}
  return json({...p,version:VERSION,service:SERVICE,prop:{provider:"HYROTRADER",connected:false,autoTrade:false,riskShell:"READY"}} ,r.status);
}

export default {
  async fetch(req,env,ctx){
    const u=new URL(req.url),path=u.pathname.replace(/\/$/,"")||"/";
    if(path==="/status")return patchedStatus(req,env);
    if(path==="/telegram/menu"){
      await sendText(env,`🤖 TRADING HUB ${VERSION}\nChọn khu vực. PROP hiện chỉ dành cho HyroTrader.`,env.TELEGRAM_CHAT_ID,baseKeyboard());
      return json({ok:true,version:VERSION});
    }
    if(path==="/telegram/webhook"&&req.method==="POST"){
      const handled=await handleHyroTelegram(req,env);if(handled)return handled;
    }
    return baseEngine.fetch(req,env,ctx);
  },
  async scheduled(controller,env,ctx){return baseEngine.scheduled(controller,env,ctx);}
};
