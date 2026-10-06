// Off-host, read-only probe of the deployed Exness market-data routes.
// GET only: /exness/instruments and /exness/quote?instrument=. No credential is read or sent,
// no trading/order/account route is touched. Output is limited to price, timing and health fields.
import {appendFileSync} from 'node:fs';

const ORIGIN='https://trading-v77-scanner.hanlinh227.workers.dev';
const instrument=String(process.env.INSTRUMENT||'EURUSD').trim().toUpperCase();
const minutes=Math.min(Math.max(Number(process.env.MINUTES||6),1),15);
const intervalMs=Math.min(Math.max(Number(process.env.INTERVAL_SECONDS||10),5),60)*1000;
const idleGapMs=Math.min(Math.max(Number(process.env.IDLE_GAP_SECONDS||0),0),600)*1000;
if(!/^[A-Z0-9]{3,11}$/.test(instrument))throw new Error('INSTRUMENT_INVALID');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const lines=[];
const say=text=>{console.log(text);lines.push(text);};

async function getJson(path){
  const startedMs=Date.now();
  try{
    const response=await fetch(ORIGIN+path,{method:'GET',signal:AbortSignal.timeout(25000)});
    let body=null;try{body=await response.json();}catch{}
    return {status:response.status,body,roundTripMs:Date.now()-startedMs};
  }catch{return {status:0,body:null,roundTripMs:Date.now()-startedMs};}
}

async function sample(label){
  const result=await getJson('/exness/quote?instrument='+encodeURIComponent(instrument));
  const b=result.body||{},nowMs=Date.now(),sourceMs=Date.parse(String(b.sourceTimestamp||'')),receivedMs=Date.parse(String(b.receivedAt||''));
  const bid=Number(b.bid),ask=Number(b.ask);
  const priced=b.ok===true&&Number.isFinite(sourceMs);
  const row={
    label,at:new Date(nowMs).toISOString(),http:result.status,rttMs:result.roundTripMs,ok:b.ok===true,
    state:b.state||null,error:b.error||null,source:b.source||null,exchange:b.exchange||null,
    bid:Number.isFinite(bid)?bid:null,ask:Number.isFinite(ask)?ask:null,
    sourceTimestamp:b.sourceTimestamp||null,receivedAt:b.receivedAt||null,
    reportedAgeMs:Number.isFinite(Number(b.quoteAgeMs))?Number(b.quoteAgeMs):null,
    runnerAgeMs:priced?nowMs-sourceMs:null,
    receiveMinusSourceMs:priced&&Number.isFinite(receivedMs)?receivedMs-sourceMs:null,
    sharedHub:Boolean(b.connection),connState:b.connection?.state||null,reconnects:b.connection?.reconnects??null,
    subscribers:b.connection?.subscribers??null,
    valid:priced&&b.exchange==='EXNESS'&&b.source==='EXNESS_WEBSOCKET_TICKS'&&bid>0&&ask>=bid,
  };
  say(JSON.stringify(row));
  return row;
}

const stats=values=>{
  const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);
  if(!sorted.length)return null;
  const pick=q=>sorted[Math.min(sorted.length-1,Math.floor(q*sorted.length))];
  return {n:sorted.length,min:sorted[0],p50:pick(0.5),p95:pick(0.95),max:sorted.at(-1)};
};

say('PROBE_START '+new Date().toISOString()+' instrument='+instrument+' minutes='+minutes+' interval_s='+intervalMs/1000+' idle_gap_s='+idleGapMs/1000);
const catalog=await getJson('/exness/instruments');
const listed=Array.isArray(catalog.body?.instruments)?catalog.body.instruments:[];
say('INSTRUMENTS http='+catalog.status+' ok='+(catalog.body?.ok===true)+' exchange='+(catalog.body?.exchange||null)+' count='+listed.length+' contains_'+instrument+'='+listed.includes(instrument)+' rttMs='+catalog.roundTripMs);

const main=[],recovery=[];
const endMs=Date.now()+minutes*60_000;
while(Date.now()<endMs){main.push(await sample('main'));await sleep(intervalMs);}
if(idleGapMs>0){
  say('IDLE_GAP_START '+new Date().toISOString()+' seconds='+idleGapMs/1000+' (no requests; shared upstream may shut down and must reconnect on demand)');
  await sleep(idleGapMs);
  for(let i=0;i<4;i++){recovery.push(await sample('recovery'));await sleep(Math.min(intervalMs,10_000));}
}

const live=rows=>rows.filter(r=>r.valid);
const summary={
  instrumentsOk:catalog.status===200&&catalog.body?.ok===true&&catalog.body?.exchange==='EXNESS'&&listed.length>0,
  instrumentListed:listed.includes(instrument),
  mainSamples:main.length,mainValid:live(main).length,
  mainErrors:main.filter(r=>!r.ok).map(r=>r.error||('HTTP_'+r.http)).reduce((acc,key)=>({...acc,[key]:(acc[key]||0)+1}),{}),
  sharedHubSamples:main.filter(r=>r.sharedHub).length,
  reportedAgeMs:stats(live(main).map(r=>r.reportedAgeMs)),
  runnerAgeMs:stats(live(main).map(r=>r.runnerAgeMs)),
  receiveMinusSourceMs:stats(live(main).map(r=>r.receiveMinusSourceMs)),
  rttMs:stats(main.map(r=>r.rttMs)),
  distinctSourceTimestamps:new Set(live(main).map(r=>r.sourceTimestamp)).size,
  maxReconnectsSeen:Math.max(0,...main.map(r=>r.reconnects??0)),
  recoverySamples:recovery.length,recoveryValid:live(recovery).length,
  recoveryFirstValidIndex:recovery.findIndex(r=>r.valid),
};
say('SUMMARY '+JSON.stringify(summary));
if(process.env.GITHUB_STEP_SUMMARY){
  appendFileSync(process.env.GITHUB_STEP_SUMMARY,'## Exness read-only probe ('+instrument+')\n```json\n'+JSON.stringify(summary,null,2)+'\n```\n');
}
const pass=summary.instrumentsOk&&summary.instrumentListed&&summary.mainValid>=Math.ceil(main.length*0.8)&&(idleGapMs===0||summary.recoveryValid>0);
say('EXNESS_PROBE='+(pass?'PASS':'FAIL'));
process.exitCode=pass?0:1;
