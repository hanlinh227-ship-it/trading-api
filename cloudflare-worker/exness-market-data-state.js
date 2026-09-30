import {createExnessReadonlyMarketClient,jsonResponse} from './exness-market-data.js';

const CACHE_LIMIT=3000;
const fixedWindow=(rows,now,windowMs)=>rows.filter(at=>Number(at)>now-windowMs);

export class ExnessMarketDataState{
  constructor(state,env){this.state=state;this.env=env;this.queue=Promise.resolve();}

  async reserve(rule){
    const windowMs=Math.ceil(Number(rule.windowSeconds)*1000),limit=Math.floor(Number(rule.limit)),now=Number(rule.now);
    if(!(windowMs>0&&limit>0&&Number.isFinite(now)))return {allowed:false};
    return this.state.storage.transaction(async txn=>{
      const key=`rate:${rule.key}`;
      if(Number(rule.refillRatePerSecond)>0){
        const previous=await txn.get(key)||{tokens:limit,updatedAt:now};
        const tokens=Math.min(limit,Number(previous.tokens||0)+Math.max(0,now-Number(previous.updatedAt||now))*Number(rule.refillRatePerSecond)/1000);
        if(tokens<1){await txn.put(key,{tokens,updatedAt:now});return {allowed:false};}
        await txn.put(key,{tokens:tokens-1,updatedAt:now});return {allowed:true};
      }
      const history=fixedWindow(await txn.get(key)||[],now,windowMs);
      if(history.length>=limit)return {allowed:false};
      history.push(now);await txn.put(key,history.slice(-CACHE_LIMIT));return {allowed:true};
    });
  }

  async fetch(request){
    const url=new URL(request.url);
    if(request.method!=='GET')return jsonResponse({ok:false,error:'METHOD_NOT_ALLOWED',readOnly:true},405);
    const work=this.queue.then(()=>this.handle(url));
    this.queue=work.catch(()=>undefined);
    return work;
  }

  async handle(url){
    const instrument=String(url.searchParams.get('instrument')||'').trim();
    if(url.pathname!=='/instruments'&&url.pathname!=='/quote')return jsonResponse({ok:false,error:'NOT_FOUND',readOnly:true},404);
    const client=createExnessReadonlyMarketClient(this.env,{store:this.state.storage,reserve:rule=>this.reserve(rule)});
    try{
      if(url.pathname==='/instruments')return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,...await client.instruments()});
      return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,...await client.quote(instrument)});
    }catch(error){return jsonResponse({ok:false,error:String(error?.code||error?.message||'EXNESS_MARKET_DATA_UNAVAILABLE'),readOnly:true},Number(error?.status)||503);}
  }
}
