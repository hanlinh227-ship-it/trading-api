const KEY='binance:auto:daily-session:v1';

const nowIso=()=>new Date().toISOString();
const bangkokDate=(d=new Date())=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);

async function getKv(env){try{return await env.TRADING_STATE?.get(KEY,{type:'json'})||null;}catch{return null;}}
async function putKv(env,value){if(!env.TRADING_STATE)throw new Error('TRADING_STATE_UNAVAILABLE');await env.TRADING_STATE.put(KEY,JSON.stringify(value));}

export async function getDailySession(env){
  const x=await getKv(env),today=bangkokDate();
  if(!x||x.sessionDate!==today)return {active:false,sessionDate:today,status:'WAITING_FOR_DAILY_TARGET',targetUsd:0,mode:null,createdAt:null,updatedAt:null};
  return {...x,active:x.status==='ACTIVE'};
}

export async function setDailySessionTarget(env,{targetUsd,mode='HARD_ATTEMPT'}={}){
  const t=Number(targetUsd);if(!(t>0))throw new Error('INVALID_DAILY_TARGET_USD');
  const m=String(mode||'HARD_ATTEMPT').toUpperCase()==='FLEXIBLE'?'FLEXIBLE':'HARD_ATTEMPT';
  const session={sessionDate:bangkokDate(),status:'ACTIVE',targetUsd:t,mode:m,createdAt:nowIso(),updatedAt:nowIso()};
  await putKv(env,session);return {...session,active:true};
}

export async function closeDailySession(env,reason='MANUAL_CLOSE'){
  const cur=await getDailySession(env),next={...cur,status:'CLOSED',closeReason:String(reason),updatedAt:nowIso()};
  await putKv(env,next);return {...next,active:false};
}

export function dailySessionPolicy(session,state={}){
  const realized=Number(state.realizedUsd||0),targetUsd=Number(session?.targetUsd||0),active=session?.status==='ACTIVE'&&targetUsd>0,reached=active&&realized>=targetUsd;
  return {active,targetUsd,mode:session?.mode||null,realizedUsd:realized,remainingUsd:Math.max(0,targetUsd-realized),reached,status:!active?'WAITING_FOR_DAILY_TARGET':reached?'DAILY_TARGET_REACHED':'ACTIVE'};
}
