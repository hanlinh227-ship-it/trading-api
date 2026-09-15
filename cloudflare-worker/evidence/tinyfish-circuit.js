const TRANSIENT=new Set(['RATE_LIMITED','REGION_UNAVAILABLE','TIMEOUT','PROVIDER_5XX','UNKNOWN_SANITIZED']);
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
export class TinyFishCircuit{
  constructor(ctx){this.storage=ctx.storage;}
  async fetch(request){
    const url=new URL(request.url);if(request.method!=='POST')return json({ok:false},405);
    let body;try{body=await request.json();}catch{return json({ok:false},400);}const now=Number(body.nowMs)||Date.now();
    if(url.pathname==='/acquire')return this.storage.transaction(async txn=>{const row=await txn.get('state')||{failures:0,openUntil:0,nextAllowedAt:0};if(row.openUntil>now)return json({allowed:false,state:'OPEN',retryAfterMs:row.openUntil-now},429);if(row.nextAllowedAt>now)return json({allowed:false,state:'RATE_LIMITED',retryAfterMs:row.nextAllowedAt-now},429);await txn.put('state',{...row,nextAllowedAt:now+2000});return json({allowed:true,state:'CLOSED'});});
    if(url.pathname==='/record')return this.storage.transaction(async txn=>{const row=await txn.get('state')||{failures:0,openUntil:0,nextAllowedAt:0};const counted=body.ok!==true&&TRANSIENT.has(String(body.category||'')),failures=body.ok===true?0:counted?Math.min(10,(Number(row.failures)||0)+1):Number(row.failures)||0,openUntil=failures>=3?now+5*60*1000:0;await txn.put('state',{failures,openUntil,nextAllowedAt:Number(row.nextAllowedAt)||0,lastCategory:body.ok?null:String(body.category||'UNKNOWN_SANITIZED'),updatedAt:new Date(now).toISOString()});return json({ok:true,state:openUntil?'OPEN':'CLOSED'});});
    return json({ok:false},404);
  }
}
