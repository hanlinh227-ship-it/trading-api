import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

async function httpFailureReason(response,label){
  let detail='';
  try{const body=await response.clone().json();const code=String(body?.error||'');if(/^[A-Z0-9_]{1,64}$/.test(code))detail='_'+code;}catch{}
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

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  try{
    const result=await runExnessProductionCanary({requestedInstrument:process.env.EXNESS_CANARY_INSTRUMENT||''});
    console.log('EXNESS_READONLY_E2E=PASS instrument='+result.instrument);
  }catch(error){
    const reason=/^[A-Z0-9_]+$/.test(String(error?.message||''))?String(error.message):'CANARY_FAILED';
    console.log('EXNESS_READONLY_E2E=FAIL reason='+reason);
    process.exitCode=1;
  }
}
