from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
s=p.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start)
    assert i>=0, f'{name}: start marker missing'
    j=text.find(end,i)
    assert j>i, f'{name}: end marker missing'
    return text[:i]+replacement+text[j:]

cycle=r'''  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO'),previousStatus=(await this.state.storage.get('cryptoMonitorStatus'))||{},previousPack=(await this.state.storage.get('cryptoLiveQuotes'))||{},cycle=Number(previousStatus.cycle||0)+1,seq=Number(previousPack.seq||0)+1,at=nowIso();
    if(!active.length){const pack={type:'crypto_quotes',ok:true,seq,receivedAt:at,count:0,freshCount:0,staleCount:0,failoverCount:0,quotes:[],transportState:'IDLE_NO_ACTIVE'};await this.state.storage.put('cryptoLiveQuotes',pack);const status={ok:true,running:false,cycle,seq,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast(pack);this.broadcast({type:'crypto_monitor',...status});return status;}

    const primaryProviders=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],successful=new Map(),errors=[],events=[];let rawRows=0;
    const loadProvider=async provider=>{
      if(successful.has(provider))return successful.get(provider);
      let snap=null,lastErr=null;
      for(let attempt=0;attempt<3;attempt++){
        try{const x=await cryptoSnapshotForProvider(this.env,provider);if(x?.live!==false&&Array.isArray(x?.rows)&&x.rows.length){snap=x;break;}lastErr=new Error('NO_LIVE_ROWS');}catch(e){lastErr=e;}
        if(attempt<2)await sleep(120*(attempt+1));
      }
      if(!snap){errors.push(`${provider}:${String(lastErr?.message||'NO_LIVE_ROWS')}`);return null;}
      successful.set(provider,snap);rawRows+=snap.rows.length;return snap;
    };

    // First preserve the provider pinned to each signal. Terminal TP/SL/AUTO_CUT
    // evaluation still runs only from that authority's fresh snapshot.
    for(const provider of primaryProviders){const snap=await loadProvider(provider);if(snap)events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));}

    const quoteFrom=(provider,symbol)=>{const snap=successful.get(provider);if(!snap)return null;const q=(snap.rows||[]).find(z=>canonical(z.symbol)===symbol);return q?{q,snap,provider}:null;};
    const primaryQuote=new Map();
    for(const sig of active){const authority=String(sig.executionPriceAuthority||sig.provider||sig.exchange||'BYBIT').toUpperCase(),symbol=canonical(sig.symbol),found=quoteFrom(authority,symbol);if(found)primaryQuote.set(String(sig.signalId||sig.id||''),found);}

    // Continuity fallback is loaded only when a primary quote is missing. It is
    // display/transport failover, not a silent venue change for terminal exits.
    let missing=active.filter(sig=>!primaryQuote.has(String(sig.signalId||sig.id||'')));
    if(missing.length){
      for(const provider of ['BYBIT','OKX','BINANCE']){
        if(!successful.has(provider))await loadProvider(provider);
        if(successful.has(provider)&&missing.every(sig=>[...successful.values()].some(snap=>(snap.rows||[]).some(z=>canonical(z.symbol)===canonical(sig.symbol)))))break;
      }
    }

    const oldById=new Map((previousPack.quotes||[]).map(q=>[String(q.signalId||''),q])),liveQuotes=[],now=Date.now();let failoverCount=0;
    for(const sig of active){
      const id=String(sig.signalId||sig.id||''),symbol=canonical(sig.symbol),authority=String(sig.executionPriceAuthority||sig.provider||sig.exchange||'BYBIT').toUpperCase();let found=primaryQuote.get(id)||null;
      if(!found){
        for(const provider of ['BYBIT','OKX','BINANCE',...successful.keys()]){if(provider===authority)continue;const x=quoteFrom(provider,symbol);if(x){found=x;break;}}
      }
      if(found){
        const {q,snap,provider}=found,received=snap.receivedAt||at,failover=provider!==authority;if(failover)failoverCount++;
        liveQuotes.push({signalId:id,symbol,style:String(sig.style||'').toUpperCase(),provider,executionPriceAuthority:authority,continuityFailover:failover,terminalLifecycleAuthority:authority,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),receivedAt:received,stale:false,sourceState:failover?'FRESH_FAILOVER_DISPLAY_ONLY':'FRESH'});
        continue;
      }
      const old=oldById.get(id),oldAt=Date.parse(old?.receivedAt||''),age=Number.isFinite(oldAt)?now-oldAt:Infinity;
      if(old&&Number(old.lastPrice)>0&&age<=30000)liveQuotes.push({...old,executionPriceAuthority:authority,terminalLifecycleAuthority:authority,stale:true,sourceState:'LAST_GOOD',quoteAgeMs:age});
    }

    const freshCount=liveQuotes.filter(x=>!x.stale).length,staleCount=liveQuotes.length-freshCount,complete=liveQuotes.length===active.length,transportState=!complete?'DEGRADED_MISSING':staleCount?'DEGRADED_LAST_GOOD':failoverCount?'DEGRADED_PROVIDER_FAILOVER':'LIVE',pack={type:'crypto_quotes',ok:liveQuotes.length>0,seq,receivedAt:at,count:liveQuotes.length,freshCount,staleCount,failoverCount,complete,quotes:liveQuotes,providers:[...successful.keys()],primaryProviders,errors,transportState};
    await this.state.storage.put('cryptoLiveQuotes',pack);this.broadcast(pack);
    const activeNow=this.activeRows(await this.registry()),underfilledStyles=['SWING','SCALP'].filter(st=>activeNow.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),terminal=events.filter(e=>['CANCELLED','TP','SL','AUTO_CUT'].includes(String(e?.type||'')));
    if(underfilledStyles.length||terminal.length)this.broadcast({type:'book_refill_needed',styles:underfilledStyles.length?underfilledStyles:[...new Set(terminal.map(e=>String(e?.signal?.style||'').toUpperCase()).filter(Boolean))],receivedAt:at});
    const status={ok:complete,running:true,cycle,seq,activeCrypto:activeNow.length,providers:[...successful.keys()],primaryProviders,quotes:rawRows,liveSignalQuotes:liveQuotes.length,freshSignalQuotes:freshCount,staleSignalQuotes:staleCount,failoverSignalQuotes:failoverCount,complete,transportState,underfilledStyles,events:events.length,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }
'''

s=block(s,'  async cryptoMonitorCycle(){','  async alarm(){',cycle,'cryptoMonitorCycle provider failover')
assert "FRESH_FAILOVER_DISPLAY_ONLY" in s
assert "terminalLifecycleAuthority" in s
assert "for(const provider of ['BYBIT','OKX','BINANCE'])" in s
assert "sourceState:'LAST_GOOD'" in s
p.write_text(s)
print('V3.23.0 provider continuity failover patched')
