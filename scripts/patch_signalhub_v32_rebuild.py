from pathlib import Path

P = Path('signalhub-worker/gateway-v3.js')
s = P.read_text(encoding='utf-8')

if "versionName: '3.2.0'" not in s:
    s = s.replace("versionCode: 7,\n  versionName: '3.1.0',\n  title: 'SignalHub 3.1.0',",
                  "versionCode: 8,\n  versionName: '3.2.0',\n  title: 'SignalHub 3.2.0',")
    s = s.replace("notes: [\n    'Unified FOREX / CRYPTO and SCALP / SWING signal partitions.',",
                  "notes: [\n    'V3.2 rebuild: hard partition integrity for FOREX/CRYPTO and SCALP/SWING.',\n    'Signal payloads expose lifecycle plus ENTRY/SL/TP1/TP2/TP3 without changing the final tracked TP.',\n    'New Forex V31 signals refuse cross-style symbol overlap while an existing exposure is active.',\n    'Unified FOREX / CRYPTO and SCALP / SWING signal partitions.',")

start = s.index('async function maybeCreateV31(env,market,style,setups,maxNew=1){')
end = s.index('async function scanCrypto(env,style){', start)
new_maybe = r'''async function maybeCreateV31(env,market,style,setups,maxNew=1){
  if(!env?.SIGNALS_KV)return[];
  const current=await getV31Signals(env,market,style),active=current.filter(x=>x.status==='PENDING'||x.status==='OPEN');
  if(active.length>=6)return[];
  const lastKey=`v31:lastnew:${market}:${style}`,raw=await env.SIGNALS_KV.get(lastKey),last=raw?Date.parse(raw):0,minGap=style==='SCALP'?10*60*1000:30*60*1000;
  if(Number.isFinite(last)&&Date.now()-last<minGap)return[];
  const made=[];
  for(const setup of setups){
    if(made.length>=maxNew)break;
    if(active.some(x=>x.symbol===setup.symbol))continue;
    const ptr=await env.SIGNALS_KV.get(activePointer(market,style,setup.symbol));
    if(ptr)continue;
    if(market==='FOREX'){
      const legacyPtr=await env.SIGNALS_KV.get(`active:${setup.symbol}`);
      const otherStyle=style==='SCALP'?'SWING':'SCALP';
      const otherStylePtr=await env.SIGNALS_KV.get(activePointer('FOREX',otherStyle,setup.symbol));
      if(legacyPtr||otherStylePtr)continue;
    }
    const issuedAt=nowIso(),id=`V31-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT},market,style);
    await writeV31Signal(env,s);made.push(s);active.push(s);
    await env.SIGNALS_KV.put(lastKey,issuedAt,{expirationTtl:SIGNAL_TTL});
  }
  return made;
}
'''
s = s[:start] + new_maybe + s[end:]

start = s.index('async function legacyScalpSignals(env){')
end = s.index('async function unifiedPerformance(url,env){', start)
new_partition = r'''function normalizeDisplaySignal(input,market,style){
  const s={...(input||{})};
  s.market=String(market||s.market||'FOREX').toUpperCase();
  s.style=String(style||s.style||'SCALP').toUpperCase();
  s.signalId=String(s.signalId||s.id||'');
  const side=String(s.side||'').toUpperCase(),dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  const entry=num(s.actualEntry??s.entry),sl=num(s.sl);
  let finalTp=num(s.tp3??s.tp2??s.tp1??s.tp),rr=num(s.targetRR??s.rr);
  const risk=isFinitePositive(entry)&&isFinitePositive(sl)?Math.abs(entry-sl):null;
  if(risk&&risk>0&&dir){
    if(!(rr>0)&&isFinitePositive(finalTp))rr=Math.abs(finalTp-entry)/risk;
    if(!(rr>0))rr=2.0;
    if(!isFinitePositive(finalTp))finalTp=entry+dir*risk*rr;
    const tp1=num(s.tp1),tp2=num(s.tp2),tp3=num(s.tp3);
    s.tp1=isFinitePositive(tp1)?tp1:entry+dir*risk*Math.min(1.0,rr);
    s.tp2=isFinitePositive(tp2)?tp2:entry+dir*risk*Math.min(1.5,rr);
    s.tp3=isFinitePositive(tp3)?tp3:finalTp;
    s.tp=s.tp3;
    s.targetRR=Number(rr.toFixed(4));
  }
  const st=String(s.status||'').toUpperCase(),out=String(s.outcome||'').toUpperCase();
  s.lifecycle=st==='PENDING'?'PENDING_ENTRY':st==='OPEN'?'ACTIVE':st==='CLOSED'&&out==='TP'?'TP3_HIT':st==='CLOSED'&&out==='SL'?'STOP_LOSS_HIT':st==='CLOSED'&&out==='CANCELLED'?'CANCELLED':st==='CLOSED'?'CLOSED':st||'WATCHING';
  const score=Number(s.score||0);
  s.qualityGrade=score>=95?'A+':score>=90?'A':score>=85?'A-':score>=80?'B+':'B';
  s.scoreMeaning='SETUP_QUALITY_NOT_WIN_PROBABILITY';
  return s;
}

async function legacyScalpSignals(env){
  if(!env?.SIGNALS_KV)return[];
  const listing=await env.SIGNALS_KV.list({prefix:'signal:',limit:1000}),out=[];
  for(let i=0;i<listing.keys.length;i+=50){
    const raws=await Promise.all(listing.keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));
    for(const raw of raws){
      if(!raw)continue;
      try{
        const s=JSON.parse(raw),explicitMarket=String(s.market||'').toUpperCase(),explicitStyle=String(s.style||'').toUpperCase(),group=String(s.group||'').toLowerCase(),id=String(s.id||'');
        if(explicitMarket&&explicitMarket!=='FOREX')continue;
        if(explicitStyle&&explicitStyle!=='SCALP')continue;
        if(group&&!['forex','metal','energy'].includes(group))continue;
        if(id.startsWith('V31-'))continue;
        out.push(normalizeDisplaySignal(s,'FOREX','SCALP'));
      }catch{}
    }
  }
  out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));
  return out;
}

async function unifiedSignals(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX';
  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const status=String(url.searchParams.get('status')||'active').toLowerCase();
  const limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  let rows=market==='FOREX'&&style==='SCALP'?await legacyScalpSignals(env):await getV31Signals(env,market,style);
  rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  let dataHealth=null;
  if(market==='FOREX'){
    const ex=await exnessQuoteMap(env);
    dataHealth={provider:'EXNESS_MT5',state:ex.state,quoteAgeMs:ex.ageMs};
  }
  return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,signals:rows});
}

'''
s = s[:start] + new_partition + s[end:]

P.write_text(s, encoding='utf-8')
print('PATCHED', P, 'bytes', len(s.encode('utf-8')))
