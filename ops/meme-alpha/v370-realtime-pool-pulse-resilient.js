import fs from 'node:fs';
const APP='/opt/meme-alpha/app';
const RADAR=`${APP}/runtime-status/new-listing-radar.json`;
const OUT=`${APP}/runtime-status/realtime-pool-pulse.json`;
const SELF_TEST=process.argv.includes('--self-test');
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const atomic=(p,x)=>{const t=p+'.tmp';try{fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}catch{try{fs.writeFileSync(p,JSON.stringify(x,null,2))}catch{}}};
function wsUrl(){const c=read(`${APP}/config/runtime.json`,{});if(c.wss)return String(c.wss);const u=String(c.rpc||'');return u.replace(/^https:/,'wss:').replace(/^http:/,'ws:')}
function topPairs(){return (read(RADAR,{candidates:[]}).candidates||[]).filter(x=>x.pairAddress&&x.mint).sort((a,b)=>(Number(b.preScore)||0)-(Number(a.preScore)||0)).slice(0,32).map(x=>({mint:x.mint,symbol:x.symbol||null,pair:x.pairAddress,preScore:Number(x.preScore)||0}))}
function reconnectDelay(fails){return Math.min(30000,1000*Math.pow(2,Math.min(5,Math.max(0,fails))))}
function setSignature(pairs){return pairs.map(x=>x.pair).sort().join('|')}
const events=new Map();
let ws=null,open=false,connecting=false,subs=new Map(),pending=new Map(),activeSet='',desiredSet='',lastConnectAt=0,lastOpenAt=0,lastCloseAt=0,lastError=null,nextConnectAt=0,reconnectFailures=0,lastRotationAt=0,connectionSeq=0;
function note(mint){const now=Date.now(),a=events.get(mint)||[];a.push(now);while(a.length&&now-a[0]>30000)a.shift();events.set(mint,a)}
function snapshot(){const now=Date.now(),pairs=topPairs(),rows=pairs.map(p=>{const a=events.get(p.mint)||[];const c1=a.filter(t=>now-t<=1000).length,c5=a.filter(t=>now-t<=5000).length,c15=a.filter(t=>now-t<=15000).length,last=a.length?a[a.length-1]:0;const r5=c5/5,r15=Math.max(.05,c15/15),momentum=Math.min(6,r5/r15);return {...p,events1s:c1,events5s:c5,events15s:c15,eventRate5s:Number(r5.toFixed(3)),eventMomentum:Number(momentum.toFixed(3)),lastEventAgeMs:last?now-last:null}});const status=open&&subs.size?'HEALTHY':(connecting?'CONNECTING':'DEGRADED');atomic(OUT,{version:'3.70.0-resilient-realtime',updatedAt:new Date().toISOString(),status,websocketOpen:open,connecting,subscriptions:subs.size,pendingSubscriptions:pending.size,lastConnectAt:lastConnectAt?new Date(lastConnectAt).toISOString():null,lastOpenAt:lastOpenAt?new Date(lastOpenAt).toISOString():null,lastCloseAt:lastCloseAt?new Date(lastCloseAt).toISOString():null,lastError,reconnectFailures,nextConnectInMs:Math.max(0,nextConnectAt-now),connectionSeq,activeSetSize:activeSet?activeSet.split('|').filter(Boolean).length:0,desiredSetSize:pairs.length,rows})}
function scheduleReconnect(reason){lastError=reason||lastError;reconnectFailures=Math.min(10,reconnectFailures+1);nextConnectAt=Date.now()+reconnectDelay(reconnectFailures);}
function closeSocket(reason='ROTATE_SET'){
  if(!ws)return;
  lastError=reason;
  try{ws.close()}catch{ws=null;open=false;connecting=false;scheduleReconnect(reason)}
}
function connect(){
  if(ws||connecting||Date.now()<nextConnectAt)return false;
  const url=wsUrl();if(!url){lastError='WSS_MISSING';scheduleReconnect(lastError);return false}
  const pairs=topPairs();desiredSet=setSignature(pairs);if(!pairs.length){lastError='NO_PAIRS';scheduleReconnect(lastError);return false}
  connecting=true;lastConnectAt=Date.now();const seq=++connectionSeq;let sock;
  try{sock=new WebSocket(url);ws=sock}catch(e){connecting=false;ws=null;lastError=String(e?.message||e);scheduleReconnect(lastError);return false}
  sock.onopen=()=>{if(ws!==sock)return;try{open=true;connecting=false;lastOpenAt=Date.now();lastError=null;reconnectFailures=0;nextConnectAt=0;subs.clear();pending.clear();activeSet=desiredSet;lastRotationAt=Date.now();let id=seq*10000;for(const p of pairs){id++;pending.set(id,p.mint);sock.send(JSON.stringify({jsonrpc:'2.0',id,method:'accountSubscribe',params:[p.pair,{encoding:'base64',commitment:'processed'}]}))}}catch(e){lastError='OPEN_HANDLER_'+String(e?.message||e);try{sock.close()}catch{}}};
  sock.onmessage=e=>{if(ws!==sock)return;try{const j=JSON.parse(String(e.data));if(j.id&&pending.has(j.id)){if(Number.isFinite(Number(j.result)))subs.set(Number(j.result),pending.get(j.id));pending.delete(j.id);return}const sid=Number(j?.params?.subscription);if(Number.isFinite(sid)&&subs.has(sid))note(subs.get(sid))}catch{}};
  sock.onerror=()=>{if(ws===sock)lastError='WEBSOCKET_ERROR'};
  sock.onclose=()=>{if(ws!==sock)return;open=false;connecting=false;subs.clear();pending.clear();ws=null;lastCloseAt=Date.now();scheduleReconnect(lastError||'WEBSOCKET_CLOSED')};
  return true;
}
async function main(){
  if(SELF_TEST){
    if(wsUrl().startsWith('http'))throw new Error('WSS_DERIVE');
    if(reconnectDelay(0)!==1000||reconnectDelay(10)!==30000)throw new Error('BACKOFF_SELF_TEST');
    if(setSignature([{pair:'B'},{pair:'A'}])!=='A|B')throw new Error('SET_SIGNATURE_SELF_TEST');
    console.log('V370_REALTIME_RESILIENT_SELF_TEST=PASS');
    console.log('SINGLE_CONNECT_IN_FLIGHT=TRUE');
    console.log('EXPONENTIAL_RECONNECT_BACKOFF=TRUE');
    console.log('SET_ROTATION_THROTTLED_30S=TRUE');
    return;
  }
  while(true){
    const pairs=topPairs();desiredSet=setSignature(pairs);
    if(!ws&&!connecting)connect();
    if(open&&activeSet&&desiredSet!==activeSet&&Date.now()-lastRotationAt>=30000)closeSocket('PAIR_SET_ROTATION');
    snapshot();
    await sleep(500);
  }
}
process.on('uncaughtException',e=>{lastError='UNCAUGHT_'+String(e?.message||e).slice(0,180);snapshot();setTimeout(()=>process.exit(1),50)});
process.on('unhandledRejection',e=>{lastError='UNHANDLED_'+String(e?.message||e).slice(0,180);snapshot();setTimeout(()=>process.exit(1),50)});
main().catch(e=>{lastError='MAIN_'+String(e?.message||e).slice(0,180);snapshot();console.error(e);process.exit(1)});
