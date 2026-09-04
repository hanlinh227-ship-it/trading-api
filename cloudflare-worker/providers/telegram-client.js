// BTC runtime Telegram transport. A Telegram HTTP 200 with {ok:false} is still a failure.
// Callers rely on thrown errors so notifications are never marked delivered unless Telegram confirms them.
export async function telegramApiRequest(env,method,payload={}){
  const token=String(env?.TELEGRAM_BOT_TOKEN||'').trim();
  if(!token)throw new Error('TELEGRAM_BOT_TOKEN_MISSING');
  if(String(method)==='sendMessage'&&!String(payload?.chat_id||'').trim())throw new Error('TELEGRAM_CHAT_ID_MISSING');
  let r,j=null;
  try{
    r=await fetch(`https://api.telegram.org/bot${token}/${method}`,{
      method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(10000)
    });
    j=await r.json().catch(()=>null);
  }catch(e){throw new Error(`TELEGRAM_TRANSPORT_FAILED: ${String(e?.message||e).slice(0,220)}`);}
  if(!r.ok||j?.ok!==true){
    const d=String(j?.description||j?.error_code||`HTTP_${r.status}`).slice(0,240);
    const e=new Error(`TELEGRAM_API_FAILED: ${d}`);e.telegram={httpStatus:r.status,errorCode:j?.error_code??null,description:j?.description||null,method};throw e;
  }
  return j;
}
