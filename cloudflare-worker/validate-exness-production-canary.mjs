import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

async function httpFailureReason(response,label){
  let detail='';
  try{
    const body=await response.clone().json();
    const code=String(body?.error||'');if(/^[A-Z0-9_]{1,64}$/.test(code))detail='_'+code;
    // Sanitized classification only, never the upstream body or any credential value.
    const shape=String(body?.upstreamClass||'').toUpperCase().replace(/[^A-Z0-9]+/g,'_').replace(/^_+|_+$/g,'');
    if(shape)detail+='_'+shape.slice(0,90);
  }catch{}
  return label+'_HTTP_'+response.status+detail;
}

export async function runExnessProductionCanary({fetchImpl=fetch,baseUrl='https://trading-v77-scanner.hanlinh227.workers.dev',requestedInstrument='',nowMs=Date.now()}={}) {
  const root=new URL(baseUrl);
  if(root.protocol!=='https:'||root.hostname!=='trading-v77-scanner.hanlinh227.workers.dev') throw new Error('WORKER_ORIGIN_INVALID');
  const catalogResponse=await fetchImpl(new URL('/exness/instruments',root),{method:'GET',signal:AbortSignal.timeout(15000)});
  if(!catalogResponse.ok) throw new Error(await httpFailureReason(catalogResponse,'INSTRUMENTS'));
  const catalog=await catalogResponse.json();
  if(catalog?.ok!==true||catalog?.readOnly!==true||catalog?.exchange!=='EXNESS'||!Array.isArray(catalog.instruments)||catalog.instruments.length===0) throw new Error('INSTRUMENTS_CONTRACT_INVALID');
  const instrument=requestedInstrument|| (catalog.instruments.includes('XAUUSD')?'XAUUSD':catalog.instruments[0]);
  if(!catalog.instruments.includes(instrument)) throw new Error('CANARY_INSTRUMENT_NOT_SUPPORTED');
  const quoteResponse=await fetchImpl(new URL('/exness/quote?instrument='+encodeURIComponent(instrument),root),{method:'GET',signal:AbortSignal.timeout(20000)});
  if(!quoteResponse.ok) throw new Error(await httpFailureReason(quoteResponse,'QUOTE'));
  const quote=await quoteResponse.json();
  const bid=Number(quote?.bid),ask=Number(quote?.ask),sourceMs=Date.parse(String(quote?.sourceTimestamp||'')),receivedMs=Date.parse(String(quote?.receivedAt||''));
  if(quote?.ok!==true||quote?.readOnly!==true||quote?.exchange!=='EXNESS'||quote?.instrument!==instrument||quote?.source!=='EXNESS_WEBSOCKET_TICKS'||!(Number.isFinite(bid)&&bid>0&&Number.isFinite(ask)&&ask>=bid)||!Number.isFinite(sourceMs)||!Number.isFinite(receivedMs)||nowMs-sourceMs>120000||receivedMs<sourceMs-1000) throw new Error('QUOTE_CONTRACT_INVALID');
  return {instrument};
}

// Advisory observation of GET /exness/quotes. It never throws and never changes the canary result:
// with the market closed every pair is legitimately STALE, which must not block a deploy. It only
// records what the deployed batch route returned, with no prices or credentials in the output.
export async function observeExnessBatch({fetchImpl=fetch,baseUrl='https://trading-v77-scanner.hanlinh227.workers.dev'}={}){
  try{
    const root=new URL(baseUrl);
    if(root.protocol!=='https:'||root.hostname!=='trading-v77-scanner.hanlinh227.workers.dev')return {http:0,state:'ORIGIN_INVALID',pairs:0,live:0,maxAgeMs:null,valid:false};
    const response=await fetchImpl(new URL('/exness/quotes',root),{method:'GET',signal:AbortSignal.timeout(20000)});
    const body=await response.json().catch(()=>null);
    const quotes=body&&typeof body.quotes==='object'&&body.quotes?body.quotes:{};
    const rows=Object.values(quotes),live=rows.filter(q=>q?.state==='LIVE');
    const ages=live.map(q=>Number(q.quoteAgeMs)).filter(Number.isFinite);
    const stalePrice=rows.some(q=>q?.state!=='LIVE'&&q&&('bid' in q||'ask' in q));
    return {http:response.status,state:String(body?.state||'NONE').replace(/[^A-Z_]/g,'').slice(0,12)||'NONE',pairs:rows.length,live:live.length,maxAgeMs:ages.length?Math.max(...ages):null,valid:body?.exchange==='EXNESS'&&live.length>0&&live.every(q=>q.bid>0&&q.ask>=q.bid)&&!stalePrice};
  }catch{return {http:0,state:'UNREACHABLE',pairs:0,live:0,maxAgeMs:null,valid:false};}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  try{
    const result=await runExnessProductionCanary({requestedInstrument:process.env.EXNESS_CANARY_INSTRUMENT||''});
    console.log('EXNESS_READONLY_E2E=PASS instrument='+result.instrument);
    const batch=await observeExnessBatch();
    console.log('EXNESS_BATCH_OBSERVED http='+batch.http+' state='+batch.state+' pairs='+batch.pairs+' live='+batch.live+' max_age_ms='+batch.maxAgeMs+' valid='+batch.valid);
  }catch(error){
    const reason=/^[A-Z0-9_]+$/.test(String(error?.message||''))?String(error.message):'CANARY_FAILED';
    console.log('EXNESS_READONLY_E2E=FAIL reason='+reason);
    process.exitCode=1;
  }
}
