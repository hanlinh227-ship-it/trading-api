import fs from 'node:fs';
const APP='/opt/meme-alpha/app';
const RADAR=`${APP}/runtime-status/new-listing-radar.json`;
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const OBS=`${APP}/runtime-status/portfolio-observability.json`;
const OUT=`${APP}/runtime-status/realtime-pool-pulse.json`;
const CACHE=`${APP}/runtime-status/mint-pair-cache.json`;
const LOCK=`${APP}/runtime-status/realtime-pulse-v374.lock`;
const SELF_TEST=process.argv.includes('--self-test');
const VERSION='3.74.0-held-continuity';
const HOTSET_LIMIT=56;
const DESIRED_REFRESH_MS=250;
const RECONCILE_MS=100;
const SNAPSHOT_MS=250;
const MAX_ADD_PER_TICK=8;
const MAX_REMOVE_PER_TICK=8;
const PENDING_TIMEOUT_MS=5000;
const HEARTBEAT_STALE_MS=15000;
const CONNECT_BACKOFF_MIN_MS=250;
const CONNECT_BACKOFF_MAX_MS=8000;
const CACHE_TTL_MS=7*24*60*60*1000;
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const n=(v,d=0)=>{const x=Number(v);return Number.isFinite(x)?x:d};
const isAddress=v=>typeof v==='string'&&v.length>=32&&v.length<=44&&/^[1-9A-HJ-NP-Za-km-z]+$/.test(v);
let writeErrors=0;
const atomic=(p,x)=>{const t=`${p}.tmp.${process.pid}`;try{fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{};return true}catch{writeErrors++;try{fs.unlinkSync(t)}catch{};return false}};
function wsUrl(){const c=read(`${APP}/config/runtime.json`,{});if(c.wss)return String(c.wss);const u=String(c.rpc||'');return u.replace(/^https:/,'wss:').replace(/^http:/,'ws:')}
function heldSet(){const o=read(OBS,{});return new Set(Array.isArray(o.positionMints)?o.positionMints.filter(isAddress):[])}
function candidatePriority(x,held){
  const age=n(x.pairAgeSec,Infinity),fresh=age<=1800?30:age<=3600?22:age<=6*3600?10:0;
  const velocity=Math.min(42,n(x.buys5m)*0.5)+Math.min(34,n(x.volume5m)/4000)+Math.min(28,Math.abs(n(x.priceChange5m))*0.8);
  return (held.has(x.mint)?10000:0)+(x.fastDiscoveryLane===true?420:0)+fresh+velocity+n(x.discoveryPriority,n(x.preScore))*0.8+n(x.preScore)*0.35;
}
const pairMemoryByMint=new Map();
function remember(mint,pair,source,meta={}){
  if(!isAddress(mint)||!isAddress(pair)||mint===pair)return false;
  const now=Date.now(),old=pairMemoryByMint.get(mint);
  const rec={mint,pair,source:String(source||'UNKNOWN'),symbol:meta.symbol||old?.symbol||null,pairAgeSec:Number.isFinite(Number(meta.pairAgeSec))?Number(meta.pairAgeSec):(old?.pairAgeSec??null),firstSeenAt:old?.firstSeenAt||now,lastSeenAt:now};
  pairMemoryByMint.set(mint,rec);return true;
}
function explicitPair(row){return row?.pairAddress||row?.pair||row?.pairPubkey||row?.pairAccount||null}
function ingestRows(rows,source){for(const r of Array.isArray(rows)?rows:[]){const pair=explicitPair(r);if(r?.mint&&pair)remember(r.mint,pair,source,{symbol:r.symbol,pairAgeSec:r.pairAgeSec})}}
function seedPairMemory(){
  const now=Date.now(),cache=read(CACHE,{entries:[]});
  for(const r of Array.isArray(cache.entries)?cache.entries:[]){if(isAddress(r?.mint)&&isAddress(r?.pair)&&r.mint!==r.pair&&now-n(r.lastSeenAt,0)<=CACHE_TTL_MS)pairMemoryByMint.set(r.mint,{...r,source:r.source||'CACHE'})}
  ingestRows(read(OUT,{rows:[]}).rows,'PREVIOUS_REALTIME');
  ingestRows(read(RADAR,{candidates:[]}).candidates,'RADAR');
  ingestRows(read(SIGNAL,{candidates:[]}).candidates,'SIGNAL');
  persistPairCache();
}
function persistPairCache(){
  const now=Date.now(),entries=[...pairMemoryByMint.values()].filter(r=>now-n(r.lastSeenAt,0)<=CACHE_TTL_MS).sort((a,b)=>n(b.lastSeenAt)-n(a.lastSeenAt));
  atomic(CACHE,{version:1,updatedAt:new Date().toISOString(),ttlMs:CACHE_TTL_MS,entries});
}
function refreshTrustedSources(){
  ingestRows(read(RADAR,{candidates:[]}).candidates,'RADAR');
  ingestRows(read(SIGNAL,{candidates:[]}).candidates,'SIGNAL');
}
function desiredPairs(){
  const held=heldSet(),radar=read(RADAR,{candidates:[]}),rows=Array.isArray(radar.candidates)?radar.candidates:[];
  refreshTrustedSources();
  const byPair=new Map();
  for(const x of rows){
    const pair=explicitPair(x);
    if(!isAddress(pair)||!isAddress(x?.mint)||pair===x.mint||!(x.currentFeed===true||held.has(x.mint)))continue;
    const p={mint:x.mint,symbol:x.symbol||null,pair,preScore:n(x.preScore),fastDiscoveryLane:x.fastDiscoveryLane===true,held:held.has(x.mint),priority:Number(candidatePriority(x,held).toFixed(3)),pairAgeSec:Number.isFinite(Number(x.pairAgeSec))?Number(x.pairAgeSec):null,pairSource:'RADAR'};
    const old=byPair.get(p.pair);if(!old||p.priority>old.priority)byPair.set(p.pair,p);
  }
  for(const mint of held){
    if([...byPair.values()].some(x=>x.mint===mint))continue;
    const m=pairMemoryByMint.get(mint);if(m?.pair)byPair.set(m.pair,{mint,symbol:m.symbol||null,pair:m.pair,preScore:0,fastDiscoveryLane:false,held:true,priority:10000,pairAgeSec:m.pairAgeSec??null,memoryFallback:true,pairSource:m.source||'CACHE'});
  }
  const arr=[...byPair.values()].sort((a,b)=>b.priority-a.priority||b.preScore-a.preScore);
  const heldRows=arr.filter(x=>x.held),nonHeld=arr.filter(x=>!x.held).slice(0,Math.max(0,HOTSET_LIMIT-heldRows.length));
  return [...heldRows,...nonHeld].sort((a,b)=>b.priority-a.priority);
}
function heldCoverage(pairs){
  const held=[...heldSet()],resolved=new Set(pairs.filter(x=>x.held).map(x=>x.mint)),unresolved=held.filter(m=>!resolved.has(m));
  return {heldTotal:held.length,heldResolved:resolved.size,heldUnresolved:unresolved.length,heldCoveragePct:held.length?Number((resolved.size*100/held.length).toFixed(1)):100,heldUnresolvedMints:unresolved};
}
function reconnectDelay(fails){const exp=Math.min(CONNECT_BACKOFF_MAX_MS,CONNECT_BACKOFF_MIN_MS*Math.pow(2,Math.min(5,Math.max(0,fails))));return Math.round(exp*(0.85+Math.random()*0.30))}
const events=new Map();
const desiredByPair=new Map();
const activeByPair=new Map();
const pairBySubId=new Map();
const pendingById=new Map();
const pendingByPair=new Map();
let ws=null,open=false,connecting=false,generation=0,reqSeq=0,lastConnectAt=0,lastOpenAt=0,lastCloseAt=0,lastError=null,nextConnectAt=0,reconnectFailures=0,reconnectCount=0,lastDesiredRefreshAt=0,lastReconcileAt=0,lastSnapshotAt=0,lastHeartbeatAt=0,heartbeatSubId=null,lastEventAt=0,subscriptionAdds=0,subscriptionRemoves=0,staleAcks=0,pendingTimeouts=0,reconcileCount=0,reconcileErrors=0,lastReconcileDurationMs=0,lockToken=null,shuttingDown=false,lastCachePersistAt=0;
function note(mint){const now=Date.now(),a=events.get(mint)||[];a.push(now);while(a.length&&now-a[0]>30000)a.shift();events.set(mint,a);lastEventAt=now}
function acquireLock(){
  lockToken=`${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const body=()=>JSON.stringify({pid:process.pid,token:lockToken,startedAt:new Date().toISOString()});
  for(let attempt=0;attempt<2;attempt++){
    try{fs.writeFileSync(LOCK,body(),{flag:'wx'});return}
    catch(e){
      if(e?.code!=='EEXIST')throw e;
      const old=read(LOCK,{}),pid=Number(old.pid);let alive=false;if(Number.isInteger(pid)&&pid>1){try{process.kill(pid,0);alive=true}catch{}}
      if(alive&&pid!==process.pid)throw new Error(`REALTIME_SINGLETON_ACTIVE_PID_${pid}`);
      try{fs.unlinkSync(LOCK)}catch{}
    }
  }
  throw new Error('REALTIME_SINGLETON_LOCK_FAILED');
}
function releaseLock(){if(!lockToken)return;try{const old=read(LOCK,{});if(old.token===lockToken)fs.unlinkSync(LOCK)}catch{};lockToken=null}
function refreshDesired(){
  const pairs=desiredPairs(),next=new Map(pairs.map(x=>[x.pair,x]));
  desiredByPair.clear();for(const [k,v] of next)desiredByPair.set(k,v);
  lastDesiredRefreshAt=Date.now();
  if(lastDesiredRefreshAt-lastCachePersistAt>=5000){persistPairCache();lastCachePersistAt=lastDesiredRefreshAt}
}
function requestId(){reqSeq=(reqSeq+1)%900000;return generation*1000000+reqSeq}
function sendRequest(kind,pair,mint,method,params){
  if(!ws||!open)return false;const id=requestId();
  try{ws.send(JSON.stringify({jsonrpc:'2.0',id,method,params}));pendingById.set(id,{kind,pair,mint,generation,at:Date.now()});if(pair)pendingByPair.set(pair,kind);return true}catch(e){lastError=`SEND_${kind}_${String(e?.message||e).slice(0,120)}`;return false}
}
function subscribePair(p){return sendRequest('SUB',p.pair,p.mint,'accountSubscribe',[p.pair,{encoding:'base64',commitment:'processed'}])}
function unsubscribePair(pair,a){return sendRequest('UNSUB',pair,a.mint,'accountUnsubscribe',[a.subId])}
function cleanupPending(){const now=Date.now();for(const [id,p] of pendingById){if(now-p.at<=PENDING_TIMEOUT_MS)continue;pendingById.delete(id);if(p.pair&&pendingByPair.get(p.pair)===p.kind)pendingByPair.delete(p.pair);pendingTimeouts++}}
function reconcile(){
  if(!open||!ws)return;const started=Date.now();cleanupPending();const held=heldSet();let adds=0,removes=0;
  const addRows=[...desiredByPair.values()].filter(p=>!activeByPair.has(p.pair)&&!pendingByPair.has(p.pair)).sort((a,b)=>(b.held?1:0)-(a.held?1:0)||b.priority-a.priority);
  for(const p of addRows){if(adds>=MAX_ADD_PER_TICK)break;if(subscribePair(p)){adds++;subscriptionAdds++}}
  const removeRows=[...activeByPair.entries()].filter(([pair,a])=>!desiredByPair.has(pair)&&!held.has(a.mint)&&!pendingByPair.has(pair));
  for(const [pair,a] of removeRows){if(removes>=MAX_REMOVE_PER_TICK)break;if(unsubscribePair(pair,a)){removes++;subscriptionRemoves++}}
  reconcileCount++;lastReconcileAt=Date.now();lastReconcileDurationMs=lastReconcileAt-started;
}
function scheduleReconnect(reason){lastError=reason||lastError;reconnectFailures=Math.min(10,reconnectFailures+1);nextConnectAt=Date.now()+reconnectDelay(reconnectFailures)}
function dropConnection(reason='CONNECTION_RESET'){
  lastError=reason;if(!ws){open=false;connecting=false;scheduleReconnect(reason);return}
  const s=ws;try{s.close()}catch{try{s.terminate?.()}catch{};if(ws===s){ws=null;open=false;connecting=false;scheduleReconnect(reason)}}
}
function connect(){
  if(shuttingDown||ws||connecting||Date.now()<nextConnectAt)return false;const url=wsUrl();if(!url){lastError='WSS_MISSING';scheduleReconnect(lastError);return false}
  connecting=true;lastConnectAt=Date.now();generation++;const gen=generation;let sock;
  try{sock=new WebSocket(url);ws=sock}catch(e){connecting=false;ws=null;lastError=String(e?.message||e);scheduleReconnect(lastError);return false}
  sock.onopen=()=>{if(ws!==sock||gen!==generation)return;open=true;connecting=false;lastOpenAt=Date.now();lastHeartbeatAt=Date.now();lastError=null;reconnectFailures=0;nextConnectAt=0;activeByPair.clear();pairBySubId.clear();pendingById.clear();pendingByPair.clear();heartbeatSubId=null;sendRequest('HEARTBEAT',null,null,'slotSubscribe',[]);reconcile()};
  sock.onmessage=e=>{if(ws!==sock||gen!==generation)return;try{
    const j=JSON.parse(String(e.data));
    if(j.id&&pendingById.has(j.id)){
      const p=pendingById.get(j.id);pendingById.delete(j.id);if(p.pair&&pendingByPair.get(p.pair)===p.kind)pendingByPair.delete(p.pair);
      if(p.generation!==generation){staleAcks++;return}
      if(j.error){lastError=`RPC_${p.kind}_${String(j.error?.message||j.error).slice(0,120)}`;return}
      if(p.kind==='HEARTBEAT'){if(Number.isFinite(Number(j.result)))heartbeatSubId=Number(j.result);lastHeartbeatAt=Date.now();return}
      if(p.kind==='SUB'&&Number.isFinite(Number(j.result))){const sid=Number(j.result),meta=desiredByPair.get(p.pair)||{pair:p.pair,mint:p.mint};activeByPair.set(p.pair,{subId:sid,mint:p.mint,subscribedAt:Date.now(),held:meta.held===true});pairBySubId.set(sid,p.pair);return}
      if(p.kind==='UNSUB'){const a=activeByPair.get(p.pair);if(a)pairBySubId.delete(a.subId);activeByPair.delete(p.pair);return}
      return;
    }
    const sid=Number(j?.params?.subscription);
    if(j?.method==='slotNotification'||(heartbeatSubId!==null&&sid===heartbeatSubId)){lastHeartbeatAt=Date.now();return}
    if(Number.isFinite(sid)&&pairBySubId.has(sid)){const pair=pairBySubId.get(sid),a=activeByPair.get(pair);if(a?.mint)note(a.mint)}
  }catch(e){lastError=`MESSAGE_PARSE_${String(e?.message||e).slice(0,100)}`}};
  sock.onerror=()=>{if(ws===sock&&gen===generation)lastError='WEBSOCKET_ERROR'};
  sock.onclose=()=>{if(ws!==sock||gen!==generation)return;open=false;connecting=false;activeByPair.clear();pairBySubId.clear();pendingById.clear();pendingByPair.clear();heartbeatSubId=null;ws=null;lastCloseAt=Date.now();reconnectCount++;scheduleReconnect(lastError||'WEBSOCKET_CLOSED')};
  return true;
}
function snapshot(){
  const now=Date.now(),pairs=[...desiredByPair.values()],coverage=heldCoverage(pairs),rows=pairs.map(p=>{const a=events.get(p.mint)||[];const c1=a.filter(t=>now-t<=1000).length,c5=a.filter(t=>now-t<=5000).length,c15=a.filter(t=>now-t<=15000).length,last=a.length?a[a.length-1]:0;const r5=c5/5,r15=Math.max(.05,c15/15),momentum=Math.min(6,r5/r15),active=activeByPair.get(p.pair);return {...p,subscribed:!!active,subscriptionAgeMs:active?now-active.subscribedAt:null,events1s:c1,events5s:c5,events15s:c15,eventRate5s:Number(r5.toFixed(3)),eventMomentum:Number(momentum.toFixed(3)),lastEventAgeMs:last?now-last:null}});
  const heartbeatAge=lastHeartbeatAt?now-lastHeartbeatAt:null;const healthy=open&&heartbeatAge!==null&&heartbeatAge<=HEARTBEAT_STALE_MS;const status=healthy?'HEALTHY':connecting?'CONNECTING':open?'DEGRADED':'RECONNECTING';
  atomic(OUT,{version:VERSION,schemaVersion:3,updatedAt:new Date().toISOString(),status,policy:'INCREMENTAL_SUBSCRIPTIONS_HELD_CONTINUITY',websocketOpen:open,connecting,generation,subscriptions:activeByPair.size,pendingSubscriptions:pendingById.size,hotsetLimit:HOTSET_LIMIT,desiredRefreshMs:DESIRED_REFRESH_MS,reconcileMs:RECONCILE_MS,snapshotMs:SNAPSHOT_MS,maxAddsPerTick:MAX_ADD_PER_TICK,maxRemovesPerTick:MAX_REMOVE_PER_TICK,...coverage,heldSubscriptions:pairs.filter(x=>x.held&&activeByPair.has(x.pair)).length,fastSubscriptions:pairs.filter(x=>x.fastDiscoveryLane&&activeByPair.has(x.pair)).length,pairCacheEntries:pairMemoryByMint.size,pairCacheTtlMs:CACHE_TTL_MS,lastConnectAt:lastConnectAt?new Date(lastConnectAt).toISOString():null,lastOpenAt:lastOpenAt?new Date(lastOpenAt).toISOString():null,lastCloseAt:lastCloseAt?new Date(lastCloseAt).toISOString():null,lastEventAt:lastEventAt?new Date(lastEventAt).toISOString():null,lastHeartbeatAt:lastHeartbeatAt?new Date(lastHeartbeatAt).toISOString():null,heartbeatAgeMs:heartbeatAge,lastError,reconnectFailures,reconnectCount,nextConnectInMs:Math.max(0,nextConnectAt-now),desiredSetSize:desiredByPair.size,activeSetSize:activeByPair.size,subscriptionAdds,subscriptionRemoves,staleAcks,pendingTimeouts,reconcileCount,reconcileErrors,lastReconcileDurationMs,writeErrors,rows});lastSnapshotAt=now
}
async function main(){
  if(SELF_TEST){
    if(wsUrl().startsWith('http'))throw new Error('WSS_DERIVE');
    for(let i=0;i<20;i++){const d=reconnectDelay(i);if(d<Math.round(CONNECT_BACKOFF_MIN_MS*.85)||d>Math.round(CONNECT_BACKOFF_MAX_MS*1.15))throw new Error('BACKOFF_SELF_TEST')}
    if(HOTSET_LIMIT!==56||DESIRED_REFRESH_MS!==250||RECONCILE_MS!==100)throw new Error('REACTIVE_POLICY_SELF_TEST');
    const h=new Set(['11111111111111111111111111111111']);const a={mint:'11111111111111111111111111111111',preScore:1,pairAgeSec:99999},b={mint:'22222222222222222222222222222222',preScore:100,pairAgeSec:10,fastDiscoveryLane:true};if(candidatePriority(a,h)<=candidatePriority(b,h))throw new Error('HELD_PRIORITY_SELF_TEST');
    if(MAX_ADD_PER_TICK>8||MAX_REMOVE_PER_TICK>8)throw new Error('BURST_BOUND_SELF_TEST');
    if(remember('11111111111111111111111111111111','11111111111111111111111111111111','TEST'))throw new Error('PAIR_EQUALS_MINT_ACCEPTED');
    if(!remember('11111111111111111111111111111111','22222222222222222222222222222222','TEST'))throw new Error('EXPLICIT_PAIR_REJECTED');
    console.log('V374_HELD_CONTINUITY_SELF_TEST=PASS');
    console.log('TRUSTED_MINT_PAIR_CACHE=TRUE');
    console.log('NO_PAIR_GUESSING=TRUE');
    console.log('HELD_RESOLVED_UNRESOLVED_OBSERVABILITY=TRUE');
    console.log('INCREMENTAL_SUBSCRIPTIONS=TRUE');
    console.log('HOTSET_CHANGE_RECONNECT=FALSE');
    console.log('FAST_DISCOVERY_PRIORITY=TRUE');
    console.log('EXIT_PATH_UNTOUCHED=TRUE');
    return;
  }
  acquireLock();seedPairMemory();refreshDesired();
  while(!shuttingDown){
    const now=Date.now();
    if(now-lastDesiredRefreshAt>=DESIRED_REFRESH_MS)refreshDesired();
    if(!ws&&!connecting)connect();
    if(open&&lastHeartbeatAt&&now-lastHeartbeatAt>HEARTBEAT_STALE_MS)dropConnection('RPC_HEARTBEAT_STALE');
    if(open&&now-lastReconcileAt>=RECONCILE_MS){try{reconcile()}catch(e){reconcileErrors++;lastError=`RECONCILE_${String(e?.message||e).slice(0,120)}`}}
    if(now-lastSnapshotAt>=SNAPSHOT_MS)snapshot();
    await sleep(50);
  }
}
function shutdown(sig){if(shuttingDown)return;shuttingDown=true;lastError=sig;try{persistPairCache()}catch{};try{snapshot()}catch{};try{ws?.close()}catch{};releaseLock();setTimeout(()=>process.exit(0),50)}
process.on('SIGTERM',()=>shutdown('SIGTERM'));
process.on('SIGINT',()=>shutdown('SIGINT'));
process.on('uncaughtException',e=>{lastError='UNCAUGHT_'+String(e?.message||e).slice(0,180);try{snapshot()}catch{};releaseLock();setTimeout(()=>process.exit(1),50)});
process.on('unhandledRejection',e=>{lastError='UNHANDLED_'+String(e?.message||e).slice(0,180);try{snapshot()}catch{};releaseLock();setTimeout(()=>process.exit(1),50)});
main().catch(e=>{lastError='MAIN_'+String(e?.message||e).slice(0,180);try{snapshot()}catch{};releaseLock();console.error(e);process.exit(1)});
