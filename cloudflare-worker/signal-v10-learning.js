const ORDER_HISTORY_KEY="v7712:order_history";
const LEARNING_KEY="v10:signal:learning";
const MAX_SEEN=1200;
const MARKETS=["forex","crypto","metal","index"];

const n=v=>Number.isFinite(Number(v))?Number(v):null;
const norm=s=>String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,"");
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const now=()=>Date.now();
async function get(env,key,def=null){try{return await env.TRADING_STATE?.get(key,"json")??def;}catch{return def;}}
async function put(env,key,value){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(value));}
function marketOf(row){const g=String(row?.group||row?.market||"").toLowerCase();if(MARKETS.includes(g))return g;const s=norm(row?.position?.symbol||row?.symbol);if(s.endsWith("USDT"))return "crypto";if(["XAUUSD","XAGUSD"].includes(s))return "metal";if(["NAS100","US30","US500","DEX","JP225"].includes(s))return "index";if(/^[A-Z]{6}$/.test(s))return "forex";return "unknown";}
function outcome(row){const e=String(row?.event||row?.status||row?.outcome||"").toUpperCase();if(["SIGNAL_TP","TP","TAKE_PROFIT","WIN"].includes(e))return "WIN";if(["SIGNAL_SL","SL","STOP_LOSS","LOSS"].includes(e))return "LOSS";return null;}
function eventId(row){const p=row?.position||{};return [row?.event,row?.recordedAt,row?.id,p?.id,p?.symbol,p?.openedAt,row?.closePrice].map(x=>String(x??"")).join("|");}
function realizedR(row){const p=row?.position||row||{},entry=n(p.entry),sl=n(p.sl??p.stop_loss),close=n(row?.closePrice??p.closePrice),side=String(p.side||p.action||"").toUpperCase();if(!(entry>0&&sl>0&&close>0)||!["LONG","SHORT"].includes(side))return null;const risk=Math.abs(entry-sl);if(!(risk>0))return null;return ((close-entry)*(side==="LONG"?1:-1))/risk;}
function bucket(){return {n:0,wins:0,losses:0,sumR:0,rSamples:0,lastAt:null};}
function add(b,win,r,at){b.n++;win?b.wins++:b.losses++;if(Number.isFinite(r)){b.sumR+=r;b.rSamples++;}b.lastAt=Math.max(Number(b.lastAt||0),Number(at||0))||b.lastAt;}
function wilson(wins,total,z=1.281551565545){if(!total)return null;const p=wins/total,z2=z*z,den=1+z2/total,center=p+z2/(2*total),margin=z*Math.sqrt((p*(1-p)+z2/(4*total))/total);return clamp((center-margin)/den,0,1);}
function view(b){const x=b||bucket(),total=Number(x.n||0),wins=Number(x.wins||0),wr=total?wins/total:null,post=(wins+2)/(total+4),lower=wilson(wins,total),avgR=x.rSamples?Number(x.sumR||0)/Number(x.rSamples):null;return {n:total,wins,losses:Number(x.losses||0),observedWinRatePct:wr==null?null:Number((wr*100).toFixed(1)),bayesianWinRatePct:Number((post*100).toFixed(1)),wilsonLowerPct:lower==null?null:Number((lower*100).toFixed(1)),avgR:avgR==null?null:Number(avgR.toFixed(3)),lastAt:x.lastAt||null,label:total<8?"LOW_SAMPLE":total<20?"BUILDING":"MATURE"};}
function init(){return {version:"V10",updatedAt:null,processed:0,seen:[],markets:{},symbols:{},strategies:{}};}
function ensure(obj,key){if(!obj[key])obj[key]=bucket();return obj[key];}
function strategyKey(row){const p=row?.position||{};return String(p.strategy||p.method?.activeMode||p.method?.profile||p.mode||p.origin||"UNKNOWN").toUpperCase().slice(0,60);}

export async function refreshSignalV10Learning(env){
  const hist=await get(env,ORDER_HISTORY_KEY,{rows:[]}),state=await get(env,LEARNING_KEY,init()),seen=new Set(Array.isArray(state.seen)?state.seen:[]);let changed=0;
  for(const row of Array.isArray(hist?.rows)?hist.rows:[]){const out=outcome(row);if(!out)continue;const id=eventId(row);if(seen.has(id))continue;const p=row?.position||{},symbol=norm(p.symbol||row.symbol),market=marketOf(row);if(!symbol||market==="unknown")continue;const r=realizedR(row),win=out==="WIN",at=row?.recordedAt||p?.closedAt||now();add(ensure(state.markets,market),win,r,at);add(ensure(state.symbols,symbol),win,r,at);add(ensure(state.strategies,`${market}:${strategyKey(row)}`),win,r,at);seen.add(id);changed++;}
  state.version="V10";state.updatedAt=now();state.processed=Number(state.processed||0)+changed;state.seen=[...seen].slice(-MAX_SEEN);await put(env,LEARNING_KEY,state);return {changed,state};
}

export async function getSignalV10Stats(env,{market=null,symbol=null}={}){const {state}=await refreshSignalV10Learning(env);const markets={};for(const g of MARKETS)markets[g]=view(state.markets?.[g]);const sym=symbol?view(state.symbols?.[norm(symbol)]):null;return {version:"V10",updatedAt:state.updatedAt,processed:state.processed||0,markets,symbol:sym,symbolName:symbol?norm(symbol):null,market:market?String(market).toLowerCase():null,disclaimer:"Observed closed-signal outcomes only; not a guaranteed future win probability."};}

export async function getSymbolLearning(env,symbol){const {state}=await refreshSignalV10Learning(env);return view(state.symbols?.[norm(symbol)]);}

export function learningAdjustment(stat){if(!stat||stat.n<6)return 0;let adj=0;if(stat.n>=8&&stat.observedWinRatePct<42)adj-=6;else if(stat.n>=8&&stat.observedWinRatePct<48)adj-=3;if(stat.n>=12&&stat.wilsonLowerPct!=null&&stat.wilsonLowerPct>=48&&stat.avgR!=null&&stat.avgR>0)adj+=3;if(stat.n>=20&&stat.observedWinRatePct>=62&&stat.avgR!=null&&stat.avgR>0.15)adj+=2;return clamp(adj,-8,5);}

export function formatMarketStats(stats){const names={forex:"💱 FOREX",crypto:"🪙 CRYPTO",metal:"🥇 METAL",index:"📊 INDEX"},L=["📈 V10 • OBSERVED SIGNAL STATS","━━━━━━━━━━━━"];for(const g of MARKETS){const s=stats?.markets?.[g]||{};L.push(`${names[g]} • WR ${s.observedWinRatePct==null?"—":s.observedWinRatePct+"%"} • n=${s.n||0}${s.avgR==null?"":` • AvgR ${s.avgR}`}${s.wilsonLowerPct==null?"":` • LB80 ${s.wilsonLowerPct}%`}`);}L.push("","WR = kết quả signal đã đóng TP/SL, KHÔNG phải xác suất thắng tương lai.");return L.join("\n");}
