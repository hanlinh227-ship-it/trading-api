import {getHyroProfile,getHyroTelemetry,getHyroControl,hyroDynamicRiskView} from "./hyro-execution.js";
import {getHyroRuntime} from "./hyro-runtime.js";

const HEALTH_KEY="v771817:health:last";
const ALERT_KEY="v771817:health:alert_state";
const LAST_FULL_KEY="v771817:health:last_full";
const SCAN_MEMORY_KEY="v771824:health:scan_memory";
const SCAN_PREFIX="v7712:scan:";
const BOOKS_KEY="v775:books";
const PROP_RUNTIME_KEY="v7718:hyro:runtime";
const GROUPS=["crypto","forex","metal","future"];
const WARNING_ALERT_COOLDOWN_MS=30*60*1000;
const now=()=>Date.now();
const ageMin=ts=>{const t=typeof ts==="number"?ts:Date.parse(ts||"");return Number.isFinite(t)?Math.max(0,(now()-t)/60000):null;};
async function getJson(kv,key,fallback=null){try{return await kv?.get(key,"json")??fallback;}catch{return fallback;}}
async function putJson(kv,key,v,ttl){try{if(kv)await kv.put(key,JSON.stringify(v),ttl?{expirationTtl:ttl}:undefined);}catch{}}
async function tg(env,text){if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return false;try{const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true})});const p=await r.json().catch(()=>null);return !!p?.ok;}catch{return false;}}
function add(arr,level,code,msg,extra={}){arr.push({level,code,msg,...extra});}
function scanLimit(group){return group==="crypto"?12:group==="future"?35:95;}
function compact(items){return items.map(x=>`${x.level==="ERROR"?"❌":x.level==="WARN"?"⚠️":"✅"} ${x.msg}`).join("\n");}
function signature(items){return items.filter(x=>x.level!=="OK").map(x=>`${x.level}:${x.code}`).sort().join("|")||"HEALTHY";}
function runtimeIssue(issues,rt){const age=ageMin(rt?.finishedAt||rt?.startedAt);if(!rt){add(issues,"WARN","HYRO_RUNTIME_MISSING","PROP chưa có runtime state");return;}if(age!=null&&age>4)add(issues,"WARN","HYRO_RUNTIME_LATE",`PROP runtime ${age.toFixed(1)}m`);else add(issues,"OK","HYRO_RUNTIME_OK",`PROP runtime ${age==null?"—":age.toFixed(1)+"m"}`);}
async function propEnv(env){const p=await getHyroProfile(env);return p?.phase==="CHALLENGE"?new Proxy(env,{get(t,k){if(k==="HYRO_BYBIT_MODE")return "DEMO";return t[k];}}):env;}

export async function runSystemHealthAudit(env,{version="UNKNOWN",full=false,notify=true}={}){
  const startedAt=now(),issues=[],kv=env.TRADING_STATE,scanMemory=await getJson(kv,SCAN_MEMORY_KEY,{groups:{}});scanMemory.groups=scanMemory.groups||{};
  if(!kv)add(issues,"ERROR","KV_MISSING","KV TRADING_STATE missing");
  else{
    const books=await getJson(kv,BOOKS_KEY,null);
    if(!books)add(issues,"WARN","BOOKS_UNREADABLE","Signal LIVE ORDERS state unreadable/missing");
    else add(issues,"OK","BOOKS_OK","Signal LIVE ORDERS state OK");
    for(const g of GROUPS){
      const s=await getJson(kv,SCAN_PREFIX+g,null);if(s?.scannedAt)scanMemory.groups[g]=s.scannedAt;
      const last=s?.scannedAt||scanMemory.groups[g]||null,age=ageMin(last);
      if(age==null)add(issues,"WARN",`SCAN_${g.toUpperCase()}_MISSING`,`${g.toUpperCase()} chưa từng có scan snapshot`);
      else if(age>scanLimit(g)*2)add(issues,"ERROR",`SCAN_${g.toUpperCase()}_STALE`,`${g.toUpperCase()} scan stale ${age.toFixed(0)}m`,{ageMin:age,lastSeen:last});
      else if(age>scanLimit(g))add(issues,"WARN",`SCAN_${g.toUpperCase()}_LATE`,`${g.toUpperCase()} scan chậm ${age.toFixed(0)}m`,{ageMin:age,lastSeen:last});
      else add(issues,"OK",`SCAN_${g.toUpperCase()}_OK`,`${g.toUpperCase()} scan ${age.toFixed(0)}m`,{ageMin:age,lastSeen:last});
    }
    await putJson(kv,SCAN_MEMORY_KEY,{groups:scanMemory.groups,updatedAt:now()},604800);
    runtimeIssue(issues,await getJson(kv,PROP_RUNTIME_KEY,null));
  }
  if(!env.TELEGRAM_BOT_TOKEN)add(issues,"ERROR","TELEGRAM_TOKEN_MISSING","Telegram token missing");
  if(!env.TELEGRAM_CHAT_ID)add(issues,"ERROR","TELEGRAM_CHAT_MISSING","Telegram chat missing");
  if(!env.TWELVE_DATA_API_KEY)add(issues,"ERROR","TWELVE_MISSING","Twelve Data key missing");
  if(!env.ANTHROPIC_API_KEY)add(issues,"WARN","CLAUDE_KEY_MISSING","Claude Co-engineer API key missing");
  else add(issues,"OK","CLAUDE_CONFIGURED","Claude Co-engineer configured");

  let account=null;
  if(full){
    try{
      const pe=await propEnv(env),profile=await getHyroProfile(pe),control=await getHyroControl(pe),telemetry=await getHyroTelemetry(pe),runtime=await getHyroRuntime(pe),dynamicRisk=profile&&telemetry?.connected?hyroDynamicRiskView(profile,telemetry):null;
      account={configured:!!profile,profile,control,telemetry,runtime,dynamicRisk,autoRequested:String(pe.HYRO_AUTO_EXECUTION||"false").toLowerCase()==="true"};
      if(!profile)add(issues,"WARN","HYRO_UNCONFIGURED","PROP chưa cấu hình");
      else if(!telemetry?.connected)add(issues,"ERROR","HYRO_OFF",`PROP telemetry OFF: ${telemetry?.reason||"unknown"}`);
      else{
        const eq=Number(telemetry.equity||0),pos=telemetry.positions?.length||0;
        if(eq<=0)add(issues,"WARN","HYRO_EQUITY_ZERO",`PROP equity chưa khả dụng • Pos ${pos}`);
        else add(issues,"OK","HYRO_CONNECTED",`PROP connected • $${eq.toFixed(2)} • Pos ${pos}`);
        const bad=(telemetry.diagnostics?.endpoints||[]).filter(x=>!x.ok);if(bad.length)add(issues,"ERROR","HYRO_ENDPOINT",`PROP endpoint lỗi: ${bad.map(x=>x.name).join(",")}`);
        if(account.autoRequested&&control?.manualPaused)add(issues,"WARN","HYRO_PAUSED","PROP AUTO requested nhưng đang pause");
        if(dynamicRisk&&Number(telemetry.openRiskUsd||0)>Number(dynamicRisk.maxCombinedOpenRiskUsd||Infinity))add(issues,"ERROR","HYRO_RISK","PROP open risk vượt cap");
      }
    }catch(e){add(issues,"ERROR","HYRO_HEALTH_ERROR",`PROP health lỗi: ${String(e?.message||e)}`);}
    if(env.TELEGRAM_BOT_TOKEN){try{const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/getMe`),p=await r.json();if(!p?.ok)add(issues,"ERROR","TELEGRAM_API_FAIL","Telegram API không phản hồi");else add(issues,"OK","TELEGRAM_API_OK","Telegram API OK");}catch{add(issues,"ERROR","TELEGRAM_API_FAIL","Telegram API không phản hồi");}}
  }

  const errors=issues.filter(x=>x.level==="ERROR"),warns=issues.filter(x=>x.level==="WARN"),sig=signature(issues),prev=await getJson(kv,ALERT_KEY,null),t=account?.telemetry||{},out={ok:errors.length===0,version,startedAt,finishedAt:now(),full,errors:errors.length,warnings:warns.length,signature:sig,issues,account:account?{configured:account.configured,connected:!!t.connected,equity:Number(t.equity||0),positions:t.positions?.length||0,orders:t.openOrders?.length||0,autoRequested:!!account.autoRequested,paused:!!account.control?.manualPaused,runtimeReason:account.runtime?.reason||null,runtimeAt:account.runtime?.finishedAt||null}:null};
  await putJson(kv,HEALTH_KEY,out);if(full)await putJson(kv,LAST_FULL_KEY,{at:now(),version});
  const changed=sig!==prev?.signature,recovered=sig==="HEALTHY"&&prev?.signature&&prev.signature!=="HEALTHY",errorNow=errors.length>0,errorWas=Number(prev?.errors||0)>0,warningCooldownOk=!prev?.at||now()-Number(prev.at)>=WARNING_ALERT_COOLDOWN_MS,shouldNotify=notify&&changed&&(errorNow||errorWas||recovered||warningCooldownOk);
  if(shouldNotify){const text=recovered?`✅ SYSTEM HEALTH • PHỤC HỒI\n${version}\nTất cả gate kiểm tra chính đã OK.`:[`🩺 SYSTEM HEALTH • ${errors.length?"CÓ LỖI":"CẢNH BÁO"}`,`${version} • Error ${errors.length} • Warn ${warns.length}`,compact([...errors,...warns].slice(0,8))].join("\n");await tg(env,text);await putJson(kv,ALERT_KEY,{signature:sig,at:now(),errors:errors.length,warnings:warns.length},604800);}else if(changed&&!prev){await putJson(kv,ALERT_KEY,{signature:sig,at:now(),errors:errors.length,warnings:warns.length},604800);}
  return out;
}
export async function shouldRunFullHealth(env,intervalMs=5*60*1000){const x=await getJson(env.TRADING_STATE,LAST_FULL_KEY,null);return !x?.at||now()-Number(x.at)>=intervalMs;}
export async function getSystemHealth(env){return getJson(env.TRADING_STATE,HEALTH_KEY,null);}
