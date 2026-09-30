import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

export async function runExnessProductionCanary({fetchImpl=fetch,baseUrl='https://trading-v77-scanner.hanlinh227.workers.dev',actionKey,requestedInstrument='',nowMs=Date.now()}={}) {
  if(!actionKey) throw new Error('ACTION_KEY_MISSING');
  const root=new URL(baseUrl);
  if(root.protocol!=='https:'||root.hostname!=='trading-v77-scanner.hanlinh227.workers.dev') throw new Error('WORKER_ORIGIN_INVALID');
  const headers={'x-action-key':actionKey};
  const catalogResponse=await fetchImpl(new URL('/exness/instruments',root),{method:'GET',headers,signal:AbortSignal.timeout(15000)});
  if(!catalogResponse.ok) throw new Error('INSTRUMENTS_HTTP_'+catalogResponse.status);
  const catalog=await catalogResponse.json();
  if(catalog?.ok!==true||catalog?.readOnly!==true||catalog?.exchange!=='EXNESS'||!Array.isArray(catalog.instruments)||catalog.instruments.length===0) throw new Error('INSTRUMENTS_CONTRACT_INVALID');
  const instrument=requestedInstrument|| (catalog.instruments.includes('XAUUSD')?'XAUUSD':catalog.instruments[0]);
  if(!catalog.instruments.includes(instrument)) throw new Error('CANARY_INSTRUMENT_NOT_SUPPORTED');
  const quoteResponse=await fetchImpl(new URL('/exness/quote?instrument='+encodeURIComponent(instrument),root),{method:'GET',headers,signal:AbortSignal.timeout(20000)});
  if(!quoteResponse.ok) throw new Error('QUOTE_HTTP_'+quoteResponse.status);
  const quote=await quoteResponse.json();
  const bid=Number(quote?.bid),ask=Number(quote?.ask),sourceMs=Date.parse(String(quote?.sourceTimestamp||'')),receivedMs=Date.parse(String(quote?.receivedAt||''));
  if(quote?.ok!==true||quote?.readOnly!==true||quote?.exchange!=='EXNESS'||quote?.instrument!==instrument||quote?.source!=='EXNESS_WEBSOCKET_TICKS'||!(Number.isFinite(bid)&&bid>0&&Number.isFinite(ask)&&ask>=bid)||!Number.isFinite(sourceMs)||!Number.isFinite(receivedMs)||nowMs-sourceMs>120000||receivedMs<sourceMs-1000) throw new Error('QUOTE_CONTRACT_INVALID');
  return {instrument};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  try{
    const result=await runExnessProductionCanary({actionKey:process.env.GPT_5AI_ACTION_KEY,requestedInstrument:process.env.EXNESS_CANARY_INSTRUMENT||''});
    console.log('EXNESS_READONLY_E2E=PASS instrument='+result.instrument);
  }catch(error){
    const reason=/^[A-Z0-9_]+$/.test(String(error?.message||''))?String(error.message):'CANARY_FAILED';
    console.log('EXNESS_READONLY_E2E=FAIL reason='+reason);
    process.exitCode=1;
  }
}