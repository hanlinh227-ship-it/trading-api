import fs from 'node:fs';
const path='cloudflare-worker/hyro-execution.js';
let s=fs.readFileSync(path,'utf8');
function extractFunction(src,name){
  const re=new RegExp(`(?:export\\s+)?(?:async\\s+)?function\\s+${name}\\s*\\(`),m=re.exec(src);if(!m)throw new Error(`${name} missing`);let i=src.indexOf('{',m.index),depth=0,inStr=null,esc=false,inLine=false,inBlock=false;
  for(let j=i;j<src.length;j++){const c=src[j],n=src[j+1];if(inLine){if(c==='\n')inLine=false;continue;}if(inBlock){if(c==='*'&&n==='/'){inBlock=false;j++;}continue;}if(inStr){if(esc){esc=false;continue;}if(c==='\\'){esc=true;continue;}if(c===inStr){inStr=null;}continue;}if(c==='/'&&n==='/'){inLine=true;j++;continue;}if(c==='/'&&n==='*'){inBlock=true;j++;continue;}if(c==='"'||c==="'"||c==='`'){inStr=c;continue;}if(c==='{')depth++;else if(c==='}'){depth--;if(depth===0)return src.slice(m.index,j+1);}}throw new Error(`unterminated ${name}`);
}
const old=extractFunction(s,'executeHyroPlan');
if(!old.includes('const t=await getHyroTelemetry(env),gate=await evaluateHyroGate(env,plan,t);'))throw new Error('expected pre-fix H1 execute body not found');
const body=`export async function executeHyroPlan(env,plan){
  const planSymbol=String(plan?.symbol||"").toUpperCase(),planSide=sideOf(plan),planEntry=entryOf(plan),
        key=String(plan.setupId||plan.id||\`${'${planSymbol}:${planSide}:${planEntry}'}\`),idKey=IDEMPOTENCY_PREFIX+key;
  let existing=await kvGet(env,idKey,null);

  // Reconcile an already-submitted intent BEFORE current account gates. If the
  // venue accepted the prior order but the response was lost, telemetry may now
  // show this symbol active; gating first would prevent the required lookup.
  if(existing){
    const st=existing.state||"ACKNOWLEDGED";
    if(st==="ACKNOWLEDGED")return {ok:true,executed:false,idempotent:true,existing};
    if(st==="SUBMITTING"||st==="RECONCILE_REQUIRED"){
      const r=await reconcileIntentByOrderLinkId(env,idKey,existing);
      if(r.state==="ACKNOWLEDGED")return {ok:true,executed:false,idempotent:true,existing:r.record};
      if(!r.ok)return {ok:false,executed:false,gate:{reason:"RECONCILE_REQUIRED",detail:r.error||null}};
      existing=r.record;
    }
  }

  const t=await getHyroTelemetry(env),gate=await evaluateHyroGate(env,plan,t);
  if(!gate.ok)return {ok:false,executed:false,gate};

  const accountId=String(env.HYRO_ACCOUNT_ID||"A"),
        scanId=String(plan.scanId||plan.lineage?.scanId||"unknown-scan"),
        deterministicOrderLinkId="h"+(await sha256Hex(\`${'${accountId}|${gate.symbol}|${gate.side}|${key}|${scanId}'}\`)).slice(0,32),
        orderLinkId=existing?.orderLinkId||deterministicOrderLinkId;

  const order=await normalizedOrder(env,plan,gate);
  const prepared={id:key,orderLinkId,symbol:order.symbol,side:order.side,orderType:order.orderType,qty:order.qty,entry:gate.entry,sl:gate.sl,tp:gate.tp,rr:gate.rr,riskBudget:gate.riskBudget,riskMultiplier:gate.riskMultiplier,riskScale:gate.riskScale,capitalBasis:gate.dynamicRisk?.capitalBasis,riskPolicy:gate.dynamicRisk?.policy,mode:mode(env),accountId,scanId,createdAt:existing?.createdAt||Date.now(),state:"PREPARED"};
  await kvPut(env,idKey,prepared,604800);
  const submitting={...prepared,state:"SUBMITTING",submittedAt:Date.now()};
  await kvPut(env,idKey,submitting,604800);

  let resp;
  try{resp=await signedBybit(env,"POST","/v5/order/create",{...order,orderLinkId});}
  catch(e){
    const bybit=e?.bybit;
    if(bybit&&Number.isFinite(bybit.retCode)&&RETRYABLE_REJECTION_CODES.has(bybit.retCode)){
      const failed={...submitting,state:"FAILED_RETRYABLE",failReason:bybit.retMsg||String(e?.message||e),retCode:bybit.retCode,failedAt:Date.now()};
      await kvPut(env,idKey,failed,86400);await appendHistory(env,{type:"SUBMIT_REJECTED",id:key,orderLinkId,retCode:bybit.retCode,retMsg:bybit.retMsg,at:Date.now()});
      return {ok:false,executed:false,gate:{reason:"ORDER_REJECTED",retCode:bybit.retCode,retMsg:bybit.retMsg}};
    }
    const pending={...submitting,state:"RECONCILE_REQUIRED",ambiguousError:String(e?.message||e),ambiguousAt:Date.now()};
    await kvPut(env,idKey,pending,604800);await appendHistory(env,{type:"SUBMIT_AMBIGUOUS",id:key,orderLinkId,error:String(e?.message||e),bybit:bybit||null,at:Date.now()});
    return {ok:false,executed:false,gate:{reason:"RECONCILE_REQUIRED",detail:String(e?.message||e)}};
  }

  const orderId=resp?.result?.orderId||null;
  if(!orderId){
    const pending={...submitting,state:"RECONCILE_REQUIRED",ambiguousError:"ACK_WITHOUT_ORDER_ID",ambiguousAt:Date.now()};
    await kvPut(env,idKey,pending,604800);await appendHistory(env,{type:"SUBMIT_AMBIGUOUS",id:key,orderLinkId,error:"ACK_WITHOUT_ORDER_ID",at:Date.now()});
    return {ok:false,executed:false,gate:{reason:"RECONCILE_REQUIRED",detail:"ACK_WITHOUT_ORDER_ID"}};
  }
  const record={...submitting,state:"ACKNOWLEDGED",orderId,acknowledgedAt:Date.now(),status:"SUBMITTED"};
  await kvPut(env,idKey,record,604800);await appendHistory(env,{type:"SUBMIT",...record});
  return {ok:true,executed:true,order:record,silentTelegram:true};
}`;
s=s.replace(old,body);
fs.writeFileSync(path,s);
console.log('V78-026 pre-gate reconciliation safety correction applied');
