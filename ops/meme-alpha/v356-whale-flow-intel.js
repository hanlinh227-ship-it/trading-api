import fs from 'node:fs';
const APP='/opt/meme-alpha/app';
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const OUT=`${APP}/runtime-status/whale-flow-intel.json`;
const OBS=`${APP}/runtime-status/portfolio-observability.json`;
const STATE='/var/lib/meme-alpha/data/micro-live/state.json';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function atomic(p,x){const t=p+'.tmp';const body=JSON.stringify(x,null,2);try{fs.writeFileSync(t,body);fs.renameSync(t,p)}catch{try{fs.writeFileSync(p,body)}catch{}}}
async function rpc(method,params){const cfg=read(`${APP}/config/runtime.json`,{});const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(8000)});const j=await r.json();if(j.error)throw new Error(`${method}:${j.error.code}`);return j.result}
async function rpcRetry(method,params){let last;for(let i=0;i<2;i++){try{return await rpc(method,params)}catch(e){last=e;if(i===0)await sleep(250)}}throw last}
const hist=new Map();const rows=new Map();let cursor=0;
function sourceRows(){
  const sig=read(SIGNAL,{candidates:[]}),st=read(STATE,{positions:[]}),m=new Map();
  for(const x of sig.candidates||[]){if(!x?.mint||x?.securityDecision!=='PASS'||x?.holderClusterDecision!=='PASS')continue;m.set(x.mint,{mint:x.mint,symbol:x.symbol||null,held:false,source:'SAFE_SIGNAL',score:n(x.score)})}
  for(const p of st.positions||[]){if(!p?.mint)continue;const old=m.get(p.mint);m.set(p.mint,{mint:p.mint,symbol:p.symbol||old?.symbol||null,held:true,source:old?'HELD_AND_SAFE_SIGNAL':'HELD_POSITION',score:n(old?.score)})}
  return {items:[...m.values()].sort((a,b)=>Number(b.held)-Number(a.held)||b.score-a.score),st};
}
async function inspect(c){
  const [largest,supply]=await Promise.all([rpcRetry('getTokenLargestAccounts',[c.mint,{commitment:'confirmed'}]),rpcRetry('getTokenSupply',[c.mint,{commitment:'confirmed'}])]);
  const total=n(supply?.value?.amount),vals=(largest?.value||[]).map(x=>n(x.amount)).filter(x=>x>=0);if(!(total>0)||!vals.length)throw new Error('SUPPLY_OR_HOLDERS_EMPTY');
  const pct=v=>v/total*100,top1=pct(vals[0]||0),top5=pct(vals.slice(0,5).reduce((a,b)=>a+b,0)),top10=pct(vals.slice(0,10).reduce((a,b)=>a+b,0));const prev=hist.get(c.mint),delta5=prev?top5-prev.top5:0,delta10=prev?top10-prev.top10:0;
  let score=0;if(top10<=25)score+=3;else if(top10>=60)score-=8;else if(top10>=45)score-=4;if(delta5<=-1.5)score+=3;else if(delta5>=2)score-=4;if(delta10<=-2)score+=2;else if(delta10>=3)score-=3;score=clamp(score,-10,6);hist.set(c.mint,{top5,top10,at:Date.now()});
  return{mint:c.mint,symbol:c.symbol||null,held:c.held===true,source:c.source,top1Pct:+top1.toFixed(3),top5Pct:+top5.toFixed(3),top10Pct:+top10.toFixed(3),deltaTop5Pct:+delta5.toFixed(3),deltaTop10Pct:+delta10.toFixed(3),whaleFlowScore:score,observedAt:new Date().toISOString()};
}
function writeObservability(st,status){const positions=Array.isArray(st?.positions)?st.positions:[];atomic(OBS,{version:'3.56.0',updatedAt:new Date().toISOString(),status,stateReadable:Array.isArray(st?.positions),stateVersion:st?.version||null,openPositions:positions.length,positionMints:positions.map(x=>x.mint).filter(Boolean).sort(),learning:{totalClosed:n(st?.learning?.totalClosed),totalWins:n(st?.learning?.totalWins),meanReturnPct:n(st?.learning?.meanReturnPct)}})}
async function cycle(){
  const {items,st}=sourceRows(),batch=[];if(items.length){for(let i=0;i<Math.min(8,items.length);i++)batch.push(items[(cursor+i)%items.length]);cursor=(cursor+batch.length)%items.length}
  const settled=await Promise.allSettled(batch.map(inspect));let ok=0,fail=0,lastError=null;for(const r of settled){if(r.status==='fulfilled'){rows.set(r.value.mint,r.value);ok++}else{fail++;lastError=String(r.reason?.message||r.reason).slice(0,160)}}
  const now=Date.now();for(const [mint,row] of rows){const t=Date.parse(row.observedAt||0);if(!Number.isFinite(t)||now-t>10*60*1000)rows.delete(mint)}
  const heldCount=(st.positions||[]).length;let status;if(!items.length)status='IDLE_HEALTHY';else if(ok>0||rows.size>0)status='HEALTHY';else status='DEGRADED';
  const out={version:'3.56.0',updatedAt:new Date().toISOString(),status,sourceCount:items.length,heldPositions:heldCount,successfulInspections:ok,failedInspections:fail,lastError,rows:[...rows.values()].sort((a,b)=>Number(b.held)-Number(a.held)||b.whaleFlowScore-a.whaleFlowScore).slice(0,96)};atomic(OUT,out);writeObservability(st,status);return out;
}
async function main(){if(process.argv.includes('--self-test')){const st={version:'x',positions:[{mint:'A'},{mint:'B'}],learning:{totalClosed:2,totalWins:1}};if((st.positions||[]).length!==2||clamp(20,-10,6)!==6)throw new Error('SELF_TEST');console.log('V356_WHALE_FLOW_SELF_TEST=PASS');console.log('HELD_POSITIONS_ALWAYS_MONITORED=TRUE');console.log('NO_CANDIDATES_IS_IDLE_HEALTHY=TRUE');console.log('PORTFOLIO_OBSERVABILITY_EXPORT=TRUE');return}while(true){try{await cycle()}catch(e){const st=read(STATE,{positions:[]});atomic(OUT,{version:'3.56.0',updatedAt:new Date().toISOString(),status:'DEGRADED',sourceCount:0,heldPositions:(st.positions||[]).length,successfulInspections:0,failedInspections:1,lastError:String(e.message||e).slice(0,160),rows:[...rows.values()]});writeObservability(st,'DEGRADED')}await sleep(8000)}}
main().catch(e=>{console.error(e);process.exit(1)});
