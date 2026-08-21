const HISTORY_KEY="v10:signal:history";
const LEARNING_KEY="v10:signal:learning";
const MAX_HISTORY=1800;
const MAX_SEEN=1800;
const MARKETS=["forex","crypto","metal","index"];

const n=v=>Number.isFinite(Number(v))?Number(v):null;
const norm=s=>String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,"");
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const now=()=>Date.now();
async function get(env,key,def=null){try{return await env.TRADING_STATE?.get(key,"json")??def;}catch{return def;}}
async function put(env,key,value){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(value));}
function bucket(){return {n:0,wins:0,losses:0,sumR:0,rSamples:0,lastAt:null};}
function add(b,win,r,at){b.n++;win?b.wins++:b.losses++;if(Number.isFinite(r)){b.sumR+=r;b.rSamples++;}b.lastAt=Math.max(Number(b.lastAt||0),Number(at||0))||b.lastAt;}
function wilson(wins,total,z=1.281551565545){if(!total)return null;const p=wins/total,z2=z*z,den=1+z2/total,center=p+z2/(2*total),margin=z*Math.sqrt((p*(1-p)+z2/(4*total))/total);return clamp((center-margin)/den,0,1);}
function view(b){const x=b||bucket(),total=Number(x.n||0),wins=Number(x.wins||0),wr=total?wins/total:null,post=(wins+2)/(total+4),lower=wilson(wins,total),avgR=x.rSamples?Number(x.sumR||0)/Number(x.rSamples):null;return {n:total,wins,losses:Number(x.losses||0),observedWinRatePct:wr==null?null:Number((wr*100).toFixed(1)),bayesianWinRatePct:Number((post*100).toFixed(1)),wilsonLowerPct:lower==null?null:Number((lower*100).toFixed(1)),avgR:avgR==null?null:Number(avgR.toFixed(3)),lastAt:x.lastAt||null,label:total<8?"LOW_SAMPLE":total<20?"BUILDING":"MATURE"};}
function init(){return {version:"V10",source:"V10_ONLY_HISTORY",updatedAt:null,processed:0,seen:[],markets:{},symbols:{},strategies:{}};}
function ensure(obj,key){if(!obj[key])obj[key]=bucket();return obj[key];}
function strategyKey(row){return String(row?.strategy||row?.method?.activeMode||row?.method?.profile||"UNKNOWN").toUpperCase().slice(0,60);}
function realizedR(row){const entry=n(row?.entry),sl=n(row?.sl),close=n(row?.closePrice),side=String(row?.side||"").toUpperCase();if(!(entry>0&&sl>0&&close>0)||!["LONG","SHORT"].includes(side))return null;const risk=Math.abs(entry-sl);if(!(risk>0))return null;return ((close-entry)*(side==="LONG"?1:-1))/risk;}

export async function recordSignalV10Outcome(env,event){
  const outcome=String(event?.outcome||"").toUpperCase();
  if(!["WIN","LOSS","EXPIRED"].includes(outcome))return {ok:false,error:"INVALID_OUTCOME"};
  const id=String(event?.id||event?.candidateId||"").trim();
  const symbol=norm(event?.symbol),market=String(event?.market||"").toLowerCase();
  if(!id||!symbol||!MARKETS.includes(market))return {ok:false,error:"INVALID_V10_OUTCOME"};
  const hist=await get(env,HISTORY_KEY,{version:"V10",rows:[]});
  if((hist.rows||[]).some(x=>x.id===id&&String(x.outcome).toUpperCase()===outcome))return {ok:true,duplicate:true};
  const row={version:"V10",source:"SIGNAL_V10",recordedAt:now(),...event,id,symbol,market,outcome};
  row.realizedR=Number.isFinite(Number(event?.realizedR))?Number(event.realizedR):realizedR(row);
  hist.rows=[row,...(hist.rows||[])].slice(0,MAX_HISTORY);hist.updatedAt=now();
  await put(env,HISTORY_KEY,hist);
  return {ok:true,row};
}

export async function refreshSignalV10Learning(env){
  const hist=await get(env,HISTORY_KEY,{version:"V10",rows:[]}),state=await get(env,LEARNING_KEY,init()),seen=new Set(Array.isArray(state.seen)?state.seen:[]);let changed=0;
  for(const row of Array.isArray(hist?.rows)?hist.rows:[]){
    const outcome=String(row?.outcome||"").toUpperCase();
    if(!["WIN","LOSS"].includes(outcome)||String(row?.version||"").toUpperCase()!=="V10")continue;
    const id=`${row.id}|${outcome}|${row.recordedAt||""}`;if(seen.has(id))continue;
    const symbol=norm(row.symbol),market=String(row.market||"").toLowerCase();if(!symbol||!MARKETS.includes(market))continue;
    const r=Number.isFinite(Number(row.realizedR))?Number(row.realizedR):realizedR(row),win=outcome==="WIN",at=row.recordedAt||now();
    add(ensure(state.markets,market),win,r,at);add(ensure(state.symbols,symbol),win,r,at);add(ensure(state.strategies,`${market}:${strategyKey(row)}`),win,r,at);seen.add(id);changed++;
  }
  state.version="V10";state.source="V10_ONLY_HISTORY";state.updatedAt=now();state.processed=Number(state.processed||0)+changed;state.seen=[...seen].slice(-MAX_SEEN);await put(env,LEARNING_KEY,state);return {changed,state};
}

export async function getSignalV10Stats(env,{market=null,symbol=null}={}){
  const {state}=await refreshSignalV10Learning(env);const markets={};for(const g of MARKETS)markets[g]=view(state.markets?.[g]);const sym=symbol?view(state.symbols?.[norm(symbol)]):null;
  const topSymbols=Object.entries(state.symbols||{}).map(([name,b])=>({symbol:name,...view(b)})).filter(x=>x.n>0).sort((a,b)=>b.n-a.n||Number(b.observedWinRatePct||0)-Number(a.observedWinRatePct||0)).slice(0,12);
  return {version:"V10",source:"V10_ONLY_HISTORY",updatedAt:state.updatedAt,processed:state.processed||0,markets,symbol:sym,symbolName:symbol?norm(symbol):null,market:market?String(market).toLowerCase():null,topSymbols,disclaimer:"Observed V10 closed-signal outcomes only; not a guaranteed future win probability."};
}
export async function getSymbolLearning(env,symbol){const {state}=await refreshSignalV10Learning(env);return view(state.symbols?.[norm(symbol)]);}
export async function getSignalV10History(env,limit=100){const h=await get(env,HISTORY_KEY,{version:"V10",rows:[]});return (h.rows||[]).slice(0,Math.max(1,Math.min(500,Number(limit)||100)));}

export function learningAdjustment(stat){if(!stat||stat.n<6)return 0;let adj=0;if(stat.n>=8&&stat.observedWinRatePct<42)adj-=6;else if(stat.n>=8&&stat.observedWinRatePct<48)adj-=3;if(stat.n>=12&&stat.wilsonLowerPct!=null&&stat.wilsonLowerPct>=48&&stat.avgR!=null&&stat.avgR>0)adj+=3;if(stat.n>=20&&stat.observedWinRatePct>=62&&stat.avgR!=null&&stat.avgR>0.15)adj+=2;return clamp(adj,-8,5);}
export function formatMarketStats(stats){const names={forex:"💱 FOREX",crypto:"🪙 CRYPTO",metal:"🥇 METAL",index:"📊 INDEX"},L=["📈 V10 • OBSERVED SIGNAL STATS","━━━━━━━━━━━━"];for(const g of MARKETS){const s=stats?.markets?.[g]||{};L.push(`${names[g]} • WR ${s.observedWinRatePct==null?"—":s.observedWinRatePct+"%"} • n=${s.n||0}${s.avgR==null?"":` • AvgR ${s.avgR}`}${s.wilsonLowerPct==null?"":` • LB80 ${s.wilsonLowerPct}%`}`);}const top=(stats?.topSymbols||[]).filter(x=>x.n>=4).slice(0,5);if(top.length){L.push("","🎯 Symbol có nhiều mẫu:");for(const s of top)L.push(`• ${s.symbol} • WR ${s.observedWinRatePct}% • n=${s.n} • AvgR ${s.avgR??"—"}`);}L.push("","Nguồn: chỉ outcome Signal V10 đã đóng.","WR = thống kê lịch sử quan sát, KHÔNG phải xác suất thắng tương lai.");return L.join("\n");}
