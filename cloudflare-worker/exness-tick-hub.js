// One upstream Exness ticks subscription shared by every consumer inside a single Durable Object.
// Read-only: it never sends anything except the subscribe command supplied by the stream opener.
// The hub is driven by tick() (called from a Durable Object alarm) so a lost timer after eviction
// cannot leave it silently dead, and a quote is only ever LIVE while the socket is up and the
// tick itself is recent. Anything else is reported STALE; a cached price is never promoted.
export const HUB_BACKOFF_MS=[1000,2000,5000,10000,30000,60000];
const MAX_FRAME_CHARS=16384;

export function createExnessTickHub({openStream,instruments,now=Date.now,setTimer=setTimeout,clearTimer=clearTimeout,maxTickAgeMs=5000,stallMs=30000,idleMs=120000,backoffMs=HUB_BACKOFF_MS}={}){
  const allowed=new Set(instruments),ticks=new Map(),listeners=new Set(),waiters=new Set();
  let status='IDLE',everConnected=false,socket=null,generation=0,connecting=null,retryTimer=null,retryAtMs=0,attempts=0,reconnects=0;
  let lastMessageMs=0,connectedAtMs=0,lastError='',lastStatus=503,lastConsumerMs=now();

  const iso=ms=>ms?new Date(ms).toISOString():null;
  const wanted=()=>listeners.size>0||now()-lastConsumerMs<idleMs;
  function health(){
    return {state:status,connected:status==='LIVE',reconnectAttempts:attempts,reconnects,lastError:lastError||null,lastMessageAt:iso(lastMessageMs),silentMs:lastMessageMs?now()-lastMessageMs:null,connectedAt:iso(connectedAtMs),subscribers:listeners.size};
  }
  function closeSocket(){
    const old=socket;socket=null;
    if(old){try{old.close(1000,'hub reset');}catch{}}
  }
  function stop(){
    generation++;connecting=null;closeSocket();
    clearTimer(retryTimer);retryTimer=null;ticks.clear();status='IDLE';
  }
  // Any failure lands here: invalidate the generation so late events from the dead socket are
  // ignored, discard cached ticks, tell consumers, and schedule a bounded-backoff reconnect.
  function drop(code,httpStatus=503){
    generation++;connecting=null;closeSocket();ticks.clear();
    const silentMs=lastMessageMs?now()-lastMessageMs:0;
    lastError=String(code||'EXNESS_STREAM_UNAVAILABLE');lastStatus=Number(httpStatus)||503;
    status='BACKOFF';
    const delay=backoffMs[Math.min(attempts,backoffMs.length-1)];
    attempts++;retryAtMs=now()+delay;
    clearTimer(retryTimer);
    retryTimer=setTimer(()=>{retryTimer=null;if(wanted())connect();else stop();},delay);
    for(const consumer of [...listeners])try{consumer.onDown?.({code:lastError,silentMs});}catch{}
  }
  function accept(message){
    const tick=message?.tick||message?.data?.tick||message?.data||message,instrument=String(tick?.instrument||'');
    if(!allowed.has(instrument))return;
    const bid=Number(tick?.bid),ask=Number(tick?.ask),sourceMs=typeof tick?.timestamp==='number'?tick.timestamp:Date.parse(String(tick?.timestamp||''));
    const receivedMs=now(),age=receivedMs-sourceMs;
    if(!(bid>0&&ask>=bid&&Number.isFinite(sourceMs))||age<-1000||age>10000)return;
    if(ticks.get(instrument)?.sourceMs===sourceMs)return;
    const saved={instrument,bid,ask,sourceMs,receivedMs};
    ticks.set(instrument,saved);
    for(const waiter of [...waiters])if(waiter.instrument===instrument)waiter.resolve();
    const event={...saved,age};
    for(const consumer of [...listeners])try{consumer.onTick?.(event);}catch{}
  }
  function onMessage(mine,event){
    if(mine!==generation)return;
    lastMessageMs=now();
    if(status==='CONNECTING'){status='LIVE';attempts=0;}
    const raw=typeof event?.data==='string'?event.data:'';
    if(!raw||raw.length>MAX_FRAME_CHARS)return;
    let message;try{message=JSON.parse(raw);}catch{return;}
    if(Number.isFinite(Number(message?.code))&&message?.error_message)return drop('EXNESS_UPSTREAM_ERROR');
    accept(message);
  }
  function connect(){
    if(connecting)return connecting;
    if(socket)return Promise.resolve(true);
    status='CONNECTING';clearTimer(retryTimer);retryTimer=null;
    const mine=++generation;
    connecting=(async()=>{
      let stream;
      try{stream=await openStream();}
      catch(error){if(mine===generation)drop(error?.code||'EXNESS_STREAM_UNAVAILABLE',error?.status);return false;}
      if(mine!==generation){try{stream.socket.close(1000,'superseded');}catch{}return false;}
      connecting=null;
      socket=stream.socket;lastMessageMs=now();connectedAtMs=now();
      if(everConnected)reconnects++;
      everConnected=true;
      socket.addEventListener('message',event=>onMessage(mine,event));
      socket.addEventListener('close',()=>{if(mine===generation)drop('EXNESS_STREAM_CLOSED');});
      socket.addEventListener('error',()=>{if(mine===generation)drop('EXNESS_STREAM_ERROR');});
      try{stream.subscribe();}catch{drop('EXNESS_SUBSCRIBE_FAILED');return false;}
      return true;
    })();
    return connecting;
  }
  // Resolves after the first connection attempt. During a backoff window it reports the last
  // failure immediately instead of hammering Exness or the account connection-rate limit.
  async function ensure(){
    lastConsumerMs=now();
    if(connecting)await connecting;
    if(socket)return {ok:true};
    if(status==='BACKOFF'&&now()<retryAtMs)return {ok:false,error:lastError,status:lastStatus};
    const ok=await connect();
    return ok?{ok:true}:{ok:false,error:lastError,status:lastStatus};
  }
  function read(instrument){
    const tick=ticks.get(instrument),t=now(),ageMs=tick?t-tick.sourceMs:null;
    let reason=null;
    if(!socket)reason='DISCONNECTED';
    else if(!tick)reason='NO_TICK';       // connected, no tick for this instrument yet
    else if(ageMs>maxTickAgeMs||ageMs<-1000)reason='TICK_OLD';
    return {state:reason?'STALE':'LIVE',reason,ageMs,tick:reason?null:tick,health:health()};
  }
  function waitForTick(instrument,timeoutMs){
    if(ticks.has(instrument))return Promise.resolve();
    return new Promise(resolve=>{
      const waiter={instrument,resolve:()=>{clearTimer(timer);waiters.delete(waiter);resolve();}};
      const timer=setTimer(()=>{waiters.delete(waiter);resolve();},timeoutMs);
      waiters.add(waiter);
    });
  }
  function subscribe(consumer){
    lastConsumerMs=now();listeners.add(consumer);
    return ()=>{listeners.delete(consumer);lastConsumerMs=now();};
  }
  // Safety-net driver. Called from the Durable Object alarm.
  function tick(){
    const t=now();
    if(!listeners.size&&t-lastConsumerMs>idleMs){if(status!=='IDLE')stop();return status;}
    if(status==='BACKOFF'&&t>=retryAtMs)connect();
    else if(socket&&t-lastMessageMs>stallMs)drop('EXNESS_STREAM_STALLED');
    return status;
  }
  return {ensure,read,waitForTick,subscribe,tick,stop,health,touch(){lastConsumerMs=now();}};
}
