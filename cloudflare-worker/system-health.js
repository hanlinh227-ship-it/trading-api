import {hyroHubSnapshot} from "./hyro-multi-account.js";

const HEALTH_KEY="v771817:health:last";
const ALERT_KEY="v771817:health:alert_state";
const LAST_FULL_KEY="v771817:health:last_full";
const SCAN_PREFIX="v7712:scan:";
const BOOKS_KEY="v775:books";
const GROUPS=["crypto","forex","metal","future"];
const now=()=>Date.now();
const ageMin=ts=>{const t=typeof ts==="number"?ts:Date.parse(ts||"");return Number.isFinite(t)?Math.max(0,(now()-t)/60000):null;};
async function getJson(kv,key,fallback=null){try{return await kv?.get(key,"json")??fallback;}catch{return fallback;}}
async function putJson(kv,key,v,ttl){try{if(kv)await kv.put(key,JSON.stringify(v),ttl?{expirationTtl:ttl}:undefined);}catch{}}
async function tg(env,text){if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return false;try{const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true})});const p=await r.json().catch(()=>null);return !!p?.ok;}catch{return false;}}
function add(arr,level,code,msg,extra={}){arr.push({level,code,msg,...extra});}
function scanLimit(group){return group==="crypto"?12:group==="future"?35:95;}
function compact(items){return items.map(x=>`${x.level==="ERROR"?"❌":x.level==="WARN"?"⚠️":"✅"} ${x.msg}`).join("\n");}
function signature(items){return items.filter(x=>x.level!=="OK").map(x=>`${x.level}:${x.code}`).sort().join("|")||"HEALTHY";}

export async function runSystemHealthAudit(env,{version="UNKNOWN",full=false,notify=true}={}){
  const startedAt=now(),issues=[],kv=env.TRADING_STATE;
  if(!kv)add(issues,"ERROR","KV_MISSING","KV TRADING_STATE missing");
  else{
    const books=await getJson(kv,BOOKS_KEY,null);
    if(!books)add(issues,"WARN","BOOKS_UNREADABLE","Signal LIVE ORDERS state unreadable/missing");
    else add(issues,"OK","BOOKS_OK","Signal LIVE ORDERS state OK");
    for(const g of GROUPS){
      const s=await getJson(kv,SCAN_PREFIX+g,null),age=ageMin(s?.scannedAt);
      if(age==null)add(issues,"WARN",`SCAN_${g.toUpperCase()}_MISSING`,`${g.toUpperCase()} chưa có scan snapshot`);
      else if(age>scanLimit(g)*2)add(issues,"ERROR",`SCAN_${g.toUpperCase()}_STALE`,`${g.toUpperCase()} scan stale ${age.toFixed(0)}m`,{ageMin:age});
      else if(age>scanLimit(g))add(issues,"WARN",`SCAN_${g.toUpperCase()}_LATE`,`${g.toUpperCase()} scan chậm ${age.toFixed(0)}m`,{ageMin:age});
      else add(issues,"OK",`SCAN_${g.toUpperCase()}_OK`,`${g.toUpperCase()} scan ${age.toFixed(0)}m`,{ageMin:age});
    }
  }
  if(!env.TELEGRAM_BOT_TOKEN)add(issues,"ERROR","TELEGRAM_TOKEN_MISSING","Telegram token missing");
  if(!env.TELEGRAM_CHAT_ID)add(issues,"ERROR","TELEGRAM_CHAT_MISSING","Telegram chat missing");
  if(!env.TWELVE_DATA_API_KEY)add(issues,"ERROR","TWELVE_MISSING","Twelve Data key missing");
  if(!env.MASSIVE_API_KEY)add(issues,"WARN","MASSIVE_MISSING","Massive Futures key missing");

  let accounts=[];
  try{accounts=await hyroHubSnapshot(env);}catch(e){add(issues,"ERROR","HYRO_HUB_ERROR","Hyro hub snapshot lỗi");}
  for(const a of accounts){
    const label=a.label||a.id,configured=!!a.configured,t=a.telemetry||{},rt=a.runtime||{},rtAge=ageMin(rt.finishedAt||rt.startedAt);
    if(!configured){add(issues,"WARN",`HYRO_${a.id}_UNCONFIGURED`,`${label} chưa cấu hình`);continue;}
    if(a.id==="B"&&!env.HYRO_B_BYBIT_API_KEY){add(issues,"WARN","HYRO_B_KEY_MISSING","TK2 chưa có API key");continue;}
    if(!t.connected)add(issues,"ERROR",`HYRO_${a.id}_OFF`,`${label} telemetry OFF: ${t.reason||"unknown"}`);
    else{
      add(issues,"OK",`HYRO_${a.id}_CONNECTED`,`${label} connected • $${Number(t.equity||0).toFixed(2)}`);
      const bad=(t.diagnostics?.endpoints||[]).filter(x=>!x.ok);if(bad.length)add(issues,"ERROR",`HYRO_${a.id}_ENDPOINT`,`${label} endpoint lỗi: ${bad.map(x=>x.name).join(",")}`);
      if(rtAge!=null&&rtAge>4)add(issues,"WARN",`HYRO_${a.id}_RUNTIME_LATE`,`${label} runtime ${rtAge.toFixed(1)}m`);
      if(a.autoRequested&&a.control?.manualPaused)add(issues,"WARN",`HYRO_${a.id}_PAUSED`,`${label} AUTO requested nhưng đang pause`);
      if(Number(t.openRiskUsd||0)>Number(a.dynamicRisk?.maxCombinedOpenRiskUsd||Infinity))add(issues,"ERROR",`HYRO_${a.id}_RISK`,`${label} open risk vượt cap`);
    }
  }

  if(full&&env.TELEGRAM_BOT_TOKEN){
    try{const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/getMe`),p=await r.json();if(!p?.ok)add(issues,"ERROR","TELEGRAM_API_FAIL","Telegram API không phản hồi");else add(issues,"OK","TELEGRAM_API_OK","Telegram API OK");}catch{add(issues,"ERROR","TELEGRAM_API_FAIL","Telegram API không phản hồi");}
  }

  const errors=issues.filter(x=>x.level==="ERROR"),warns=issues.filter(x=>x.level==="WARN"),sig=signature(issues),prev=await getJson(kv,ALERT_KEY,null),out={ok:errors.length===0,version,startedAt,finishedAt:now(),full,errors:errors.length,warnings:warns.length,signature:sig,issues,accounts:accounts.map(a=>({id:a.id,label:a.label,configured:a.configured,connected:!!a.telemetry?.connected,equity:Number(a.telemetry?.equity||0),positions:a.telemetry?.positions?.length||0,orders:a.telemetry?.openOrders?.length||0,autoRequested:!!a.autoRequested,paused:!!a.control?.manualPaused,runtimeReason:a.runtime?.reason||null,runtimeAt:a.runtime?.finishedAt||null}))};
  await putJson(kv,HEALTH_KEY,out);
  if(full)await putJson(kv,LAST_FULL_KEY,{at:now(),version});
  if(notify&&sig!==prev?.signature){
    const recovered=sig==="HEALTHY"&&prev?.signature&&prev.signature!=="HEALTHY";
    const text=recovered?`✅ SYSTEM HEALTH • PHỤC HỒI\n${version}\nTất cả gate kiểm tra chính đã OK.`:[`🩺 SYSTEM HEALTH • ${errors.length?"CÓ LỖI":"CẢNH BÁO"}`,`${version} • Error ${errors.length} • Warn ${warns.length}`,compact([...errors,...warns].slice(0,8))].join("\n");
    await tg(env,text);await putJson(kv,ALERT_KEY,{signature:sig,at:now(),errors:errors.length,warnings:warns.length},604800);
  }
  return out;
}

export async function shouldRunFullHealth(env,intervalMs=5*60*1000){const x=await getJson(env.TRADING_STATE,LAST_FULL_KEY,null);return !x?.at||now()-Number(x.at)>=intervalMs;}
export async function getSystemHealth(env){return getJson(env.TRADING_STATE,HEALTH_KEY,null);}
