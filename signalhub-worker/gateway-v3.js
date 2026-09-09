import legacy from './gateway.js';

const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.22.4';
const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_10';
const MT5_QUOTE_TTL = 120;
const MT5_HEARTBEAT_TTL = 180;
const SIGNAL_TTL = 60 * 60 * 24 * 90;
const CRYPTO_LASTGOOD_TTL = 60 * 30;
const CRYPTO_CACHE_MS = 1500;
const PROVIDER_TIMEOUT_MS = 7000;
const BYBIT_BASES = ['https://api.bybit.com', 'https://api.bytick.com'];
const FOREX = [
  'AUDCAD','AUDCHF','AUDJPY','AUDNZD','AUDUSD','CADCHF','CADJPY','CHFJPY',
  'EURAUD','EURCAD','EURCHF','EURGBP','EURJPY','EURNZD','EURUSD',
  'GBPAUD','GBPCAD','GBPCHF','GBPJPY','GBPNZD','GBPUSD',
  'NZDCAD','NZDCHF','NZDJPY','NZDUSD','USDCAD','USDCHF','USDJPY'
];
const V31_RELEASE = {
  versionCode: 30,
  versionName: '3.22.4',
  title: 'SignalHub 3.22.4 Responsive Style Target Read',
  releasedAt: '2026-09-09T00:00:00Z',
  mandatory: false,
  minSupportedVersionCode: 6,
  artifactName: 'SignalHub-Android-v3.22.4-Responsive-Style-Target-Read',
  notes: [
    'V3.22.4 fixes the app-facing SWING target mismatch: active reads now use the canonical 10 SCALP / 5 SWING targets instead of forcing both styles toward 10.',
    'V3.22.4 keeps deep refill asynchronous from interactive signal reads, preventing the 30-second app/API timeout while continuous maintenance still restores missing slots.',
    'V3.22.3 reconnects the existing stable-liquid reference pending builder to the real scan/refill path. When strict immediate structure is absent, the engine may emit only a hard-safety-passing structure-derived LIMIT/STOP wait setup; it does not force a MARKET trade.',
    'V3.22.3 keeps liquidity, spread, invalidation, target path and pending reachability hard checks and adds scan rejection diagnostics for production audit.',
    'V3.22.2 repairs the missing analyzeCryptoBatch runtime helper that caused /v3/scan HTTP 500 and empty active books; batch analysis is now bounded-concurrency and isolates per-symbol failures.',
    'V3.22.2 production audit fails unless both SCALP and SWING scans return ok and the live portfolio contains at least one active signal in each style after refill attempts.',
    'V3.20.1 normalizes OKX swap base-currency 24h volume into quote-USDT turnover before liquidity ranking, preventing tiny-price high-token-count markets from being falsely ranked as the deepest markets.',
    'V3.20 continuously maintains a dynamic top-100 stable USDT perpetual universe. All 100 are refreshed at ticker/liquidity level each server maintenance cycle and on-demand scan; deep candle analysis rotates through the universe while preserving a high-liquidity core.',
    'V3.20 keeps 20 hot-spare candidates per style and continuously refills toward 10 SCALP + 5 SWING without forcing weak-liquidity or MARKET fallback entries.',
    'V3.19 targets exactly 10 SCALP + 5 SWING active reference signals, counting both OPEN market entries and PENDING LIMIT/STOP entries.',
    'V3.19 filters the trading universe for strong turnover, tight spread, sane daily movement/funding and usable open interest when available; weak-liquidity symbols do not consume the 15 reference slots.',
    'V3.19 refreshes the full live perpetual universe every maintenance cycle and keeps larger style-specific hot-spare pools so stronger new candidates can replace invalidated, closed or stale pending ideas.',
    'V3.18 fixes Watchlist keyboard/focus and adds live symbol suggestions. Watchlist remains read-only and never consumes the 15 active reference slots.',
    'Watchlist reports active signal / strict tradeable setup / conditional wait / no-trade separately for SCALP and SWING, with current provider price and Entry/SL/TP when available.',
    'V3.14 stability pass: SCALP no longer accepts a generic EMA trend pullback by itself; it needs a sweep/reclaim, displacement+reclaim, or confirmed breakout story.',
    'V3.14 tightens secondary-exchange confirmation and live execution spread/liquidity conditions without reintroducing a numeric setup score.',
    'V3.14 adds crypto risk-cluster concentration control so correlated meme-beta trades cannot occupy the whole active book.',
    'V3.14 uses provider bid/ask for pending activation and live exit tracking, plus structure invalidation before a pending entry is allowed to fill.',
    'V3.14 adds a stability endpoint separating infrastructure health from trading evidence/sample adequacy.',
    'V3.13 removes Forex signal generation and turns SignalHub into a Crypto-only SCALP/SWING engine.',
    'V3.13 separates Crypto SCALP and SWING quality rules, tightens spread/location/context/target-path checks, and prioritizes liquidity sweeps and aligned structure.',
    'V3.13 keeps provider-pinned LIMIT/STOP lifecycle monitoring server-side and targets at least one qualified active idea per Crypto style when available.',
    'V3.11 Atomic Quality Book reserves every active slot transactionally inside one Durable Object so concurrent scans cannot overbook the portfolio.',
    'V3.11 also caps Forex currency concentration at two active ideas per currency and tightens market-entry location / pending-trigger reachability checks.',
    'V3.10 Disciplined Book keeps the clean market story model and adds portfolio-level concurrency discipline plus a mandatory hard-check assessment for every order.',
    'Only one active idea is allowed per symbol across SCALP/SWING. The whole app is capped at 6 active ideas, 4 per market, 3 per style and 2 new ideas per scan.',
    'No numeric score is used as an admission gate: orders pass or fail explicit structure, context, entry-location, invalidation and target-path checks.',
    'V3.9 Clean Market Story removes permissive transition entries and requires a coherent structure/liquidity narrative before the bot emits an order.',
    'V3.9 uses one realtime lifecycle source of truth; scanner cycles no longer trigger or close orders from mid price.',
    'Pending LIMIT/STOP ideas invalidate immediately by price if the setup fails before entry, and LIMIT ideas retire if the move reaches TP1 without the pullback entry.',
    'V3.8 separation retained: SCALP microstructure execution is distinct from SWING higher-timeframe execution.',
    'LIMIT/STOP activation is event-driven from live prices; Forex uses MT5 Ask for BUY triggers and Bid for SELL triggers.',
    'V3.7 Structure-Liquidity Engine retained: entries, stops and targets are derived from live structure, liquidity/rejection and volatility context.',
    'Stops sit beyond the bot-selected invalidation structure with ATR buffer; targets prefer structure/liquidity objectives before expansion.',
    'V3.6 Market Judgment retained: no score gate, no minimum score, no RR admission threshold and no signal cooldown.',
    'Bot classifies regime and actively chooses MARKET / LIMIT / STOP / NO TRADE from current market structure.',
    'Modern LIVE / LIMIT / STOP UI with yellow pending-entry progress gauge.',
    'Realtime Durable Object price bus + WebSocket stream for Exness MT5 quotes.',
    'LIMIT and STOP pending orders are displayed separately and become LIVE immediately when trigger price is crossed.',
    'Low-latency Exness patch: 500ms bridge target, heartbeat-aware health, faster Android live refresh.',
    'V3.2 rebuild: hard partition integrity for FOREX/CRYPTO and SCALP/SWING.',
    'Signal payloads expose lifecycle plus ENTRY/SL/TP1/TP2/TP3 without changing the final tracked TP.',
    'New Forex V31 signals refuse cross-style symbol overlap while an existing exposure is active.',
    'Unified FOREX / CRYPTO and SCALP / SWING signal partitions.',
    'Exness MT5 remains execution-price authority for Forex and confirms fills/TP/SL.',
    'Crypto market data uses Bybit first with OKX/Binance public-data fallback and never labels fallback quotes as Bybit live.',
    'Crypto signals use multi-timeframe EMA/RSI/ATR structure, liquidity/spread gates, anti-FOMO extension checks and MARKET/LIMIT/STOP routing.',
    'Signal cards show ENTRY / NOW / TP / SL and live R progress; history and win rate are calculated from resolved TP/SL only.',
    'No setup score is generated or displayed; historical win rate remains resolved TP/SL only.'
  ]
};

const json = (body, status = 200, extra = {}) => new Response(JSON.stringify(body, null, 2), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store, no-cache, must-revalidate',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type, authorization, x-signalhub-bridge',
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    ...extra,
  },
});
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const nowIso = () => new Date().toISOString();
const canonical = s => String(s || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
const cryptoRiskCluster = symbol => {
  const base=canonical(symbol).replace(/USDT$/,'');
  if(['DOGE','SHIB','PEPE','BONK','WIF','FLOKI','MEME','NEIRO','BRETT','TURBO','POPCAT','PNUT','FARTCOIN','MOG','BOME','MEW','TRUMP','PENGU'].includes(base))return 'MEME';
  if(['BTC','ETH'].includes(base))return 'MAJOR';
  if(['SOL','BNB','ADA','AVAX','SUI','APT','TON','NEAR','DOT','ATOM','SEI'].includes(base))return 'L1';
  if(['LINK','UNI','AAVE','MKR','CRV','LDO','PENDLE','JUP','RAY','INJ'].includes(base))return 'DEFI';
  return 'ALT';
};
const isFinitePositive = v => Number.isFinite(Number(v)) && Number(v) > 0;
const sleep = ms => new Promise(r => setTimeout(r, ms));


const MARKET_JUDGMENT_POLICY = Object.freeze({
  name:'CRYPTO_QUALITY_JUDGMENT',
  scoreGate:false,
  timeGate:false,
  rrGate:false,
  orderRouting:'DYNAMIC_MARKET_LIMIT_STOP',
  historicalWinRateMode:'RESOLVED_TP_SL_ONLY',
  entryModel:'STRUCTURE_LIQUIDITY_CONTEXT',
  stopModel:'INVALIDATION_STRUCTURE_PLUS_VOLATILITY_BUFFER',
  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION',
  styleSeparation:'SCALP_MICROSTRUCTURE_VS_SWING_HTF_STRUCTURE',
  pendingActivation:'PRICE_TOUCH_EVENT_DRIVEN_NO_COOLDOWN',
  qualityMode:'CRYPTO_STABILITY_STRUCTURE_NO_SCORE',
  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE',
  entryAssessment:'V315_FIXED_2X2_HARD_SAFETY',
  portfolioPolicy:{maxActiveTotal:15,maxActivePerMarket:15,maxActivePerStyle:10,maxNewPerScan:10,minActivePerStyle:5,targetActivePerStyle:10,targetActiveByStyle:{SCALP:10,SWING:5},maxActiveByStyle:{SCALP:10,SWING:5},maxNewPerScanByStyle:{SCALP:10,SWING:5},maxActivePerRiskCluster:5,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:20,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',forexDisabled:true}
});

const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'liquidity sweep/reclaim first; otherwise fully aligned continuation or confirmed breakout',stopFocus:'micro swing/liquidity invalidation + ATR/spread buffer',targetFocus:'clean 15m/1h liquidity with minimum 2.15R geometry',holdModel:'short-horizon; reject extended/chasing market entries'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'H4+D1 alignment mandatory; H1 reclaim/pullback/rejoin or confirmed breakout',stopFocus:'H1/H4 invalidation outside liquidity + wider ATR buffer',targetFocus:'H4/D1 liquidity with minimum 2.75R geometry',holdModel:'multi-session; no H1-only directional trade'})
});

function validSignalStructure(signal){
  if(!signal)return false;
  const entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0&&Math.abs(entry-sl)>0))return false;
  const side=String(signal.side||'').toUpperCase();
  const dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  return ['MARKET','LIMIT','STOP'].includes(String(signal.orderType||'MARKET').toUpperCase());
}
function stampMarketJudgment(signal,market,style){
  signal.decisionMode='BOT_MARKET_JUDGMENT';
  signal.admissionMode='NO_SCORE_NO_TIME_GATE';
  signal.entryState=String(signal.orderType||'MARKET').toUpperCase()==='MARKET'?'LIVE':'PENDING_ENTRY';
  signal.market=String(market||signal.market||'CRYPTO').toUpperCase();
  signal.style=String(style||signal.style||'SCALP').toUpperCase();
  signal.styleProfile=STYLE_EXECUTION_POLICY[signal.style]||STYLE_EXECUTION_POLICY.SCALP;
  delete signal.score;delete signal.qualityGrade;delete signal.scoreMeaning;
  delete signal.admissionGate;
  return signal;
}


export class MT5LiveState {
  constructor(state, env) {
    this.state=state;this.env=env;this.clients=new Set();this.signalRegistry=null;
  }
  async registry(){if(this.signalRegistry===null)this.signalRegistry=(await this.state.storage.get('signalRegistry'))||{};return this.signalRegistry;}
  async persistRegistry(){await this.state.storage.put('signalRegistry',this.signalRegistry||{});}
  broadcast(obj){const msg=JSON.stringify(obj);for(const ws of [...this.clients]){try{ws.send(msg);}catch{this.clients.delete(ws);}}}
  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO');}
  portfolioFrom(reg){
    const active=this.activeRows(reg),counts={FOREX:0,CRYPTO:0},styles={SCALP:0,SWING:0};
    for(const s of active){const m=String(s.market||'').toUpperCase(),st=String(s.style||'').toUpperCase();if(m in counts)counts[m]++;if(st in styles)styles[st]++;}
    return {activeTotal:active.length,counts,styles,uniqueSymbols:new Set(active.map(x=>`${String(x.market||'').toUpperCase()}:${canonical(x.symbol)}`)).size,policy:PORTFOLIO_POLICY};
  }
  async portfolioSnapshot(){return this.portfolioFrom(await this.registry());}
  async ensureCryptoMonitor(delayMs=25){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(!active.length){try{await this.state.storage.deleteAlarm();}catch{}return {ok:true,running:false,activeCrypto:0};}
    const target=Date.now()+Math.max(25,Number(delayMs)||25),old=await this.state.storage.getAlarm();
    if(old===null||Number(old)>target+250)await this.state.storage.setAlarm(target);
    return {ok:true,running:true,activeCrypto:active.length,nextAlarmMs:target};
  }
  async claimCoverage(){
    const now=Date.now();let out={claimed:[],portfolio:null};
    await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},portfolio=this.portfolioFrom(reg),locks=(await txn.get('coverageLocks'))||{},claimed=[];
      for(const market of ['FOREX','CRYPTO']){
        const lock=locks[market],stale=lock&&now-Number(lock.claimedAt||0)>30000;
        if(stale)delete locks[market];
        if(Number(portfolio.counts?.[market]||0)<PORTFOLIO_POLICY.minActivePerMarket&&!locks[market]){locks[market]={claimedAt:now};claimed.push(market);}
      }
      await txn.put('coverageLocks',locks);out={claimed,portfolio};
    });
    return out;
  }
  async releaseCoverage(payload){
    const market=String(payload?.market||'').toUpperCase();if(!['FOREX','CRYPTO'].includes(market))return {ok:false,error:'BAD_MARKET'};
    await this.state.storage.transaction(async txn=>{const locks=(await txn.get('coverageLocks'))||{};delete locks[market];await txn.put('coverageLocks',locks);});return {ok:true,market};
  }
  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    const previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){const status={ok:true,running:false,cycle,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[];let quotes=0;
    for(const provider of providers){
      try{const snap=await cryptoSnapshotForProvider(this.env,provider);if(snap.live===false||!snap.rows?.length){errors.push(`${provider}:NO_LIVE_ROWS`);continue;}quotes+=snap.rows.length;events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));}
      catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];
    for(const style of depleted){const r=await this.promoteStandby(style,'LIFECYCLE_EVENT');if(r?.promoted?.length)replacements.push({style,...r});}
    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,events:events.length,replacements,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }
  async alarm(){
    try{await this.cryptoMonitorCycle();}catch(e){await this.state.storage.put('cryptoMonitorStatus',{ok:false,running:true,error:String(e?.message||e),receivedAt:nowIso()});}
    const reg=await this.registry(),still=this.activeRows(reg).some(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(still)await this.state.storage.setAlarm(Date.now()+1000);else try{await this.state.storage.deleteAlarm();}catch{}
  }
  async registerSignal(payload){
    const s=payload?.signal||payload,id=String(s?.id||s?.signalId||'');if(!id)return {ok:false,accepted:false,error:'NO_SIGNAL_ID'};
    const result=await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},activeStatus=s.status==='PENDING'||s.status==='OPEN';
      if(!activeStatus){delete reg[id];await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,removed:true,reg};}
      const kvKey=String(payload?.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),existing=reg[id];
      if(existing){reg[id]={...s,kvKey};await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,idempotent:true,reg};}
      const active=this.activeRows(reg);
      const market=String(s.market||'').toUpperCase(),style=String(s.style||'').toUpperCase(),symbol=canonical(s.symbol),policy=PORTFOLIO_POLICY;
      const reject=reason=>({ok:true,accepted:false,id,status:s.status,reason,activeTotal:active.length,reg});
      if(market!=='CRYPTO')return reject('CRYPTO_ONLY_FOREX_DISABLED');
      const duplicate=active.find(x=>String(x.market||'').toUpperCase()===market&&canonical(x.symbol)===symbol);
      if(duplicate)return reject(`SYMBOL_ALREADY_ACTIVE:${duplicate.id||duplicate.symbol}`);
      if(active.length>=policy.maxActiveTotal)return reject('MAX_ACTIVE_TOTAL');
      if(active.filter(x=>String(x.market||'').toUpperCase()===market).length>=policy.maxActivePerMarket)return reject('MAX_ACTIVE_MARKET');
      if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=styleMax(style))return reject('MAX_ACTIVE_STYLE');
      const cluster=cryptoRiskCluster(symbol),clusterCount=active.filter(x=>cryptoRiskCluster(x.symbol)===cluster).length;
      if(cluster==='MEME'&&clusterCount>=policy.maxMemeActiveTotal)return reject('MAX_MEME_CLUSTER');
      if(clusterCount>=policy.maxActivePerRiskCluster)return reject(`MAX_RISK_CLUSTER:${cluster}`);
      s.riskCluster=cluster;
      if(market==='FOREX'&&symbol.length===6){
        const ccys=[symbol.slice(0,3),symbol.slice(3,6)];
        for(const ccy of ccys){
          const exposure=active.filter(x=>String(x.market||'').toUpperCase()==='FOREX').filter(x=>{const z=canonical(x.symbol);return z.length===6&&(z.slice(0,3)===ccy||z.slice(3,6)===ccy);}).length;
          if(exposure>=policy.maxForexPerCurrency)return reject(`MAX_FOREX_CURRENCY:${ccy}`);
        }
      }
      reg[id]={...s,kvKey};await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,activeTotal:active.length+1,reg};
    });
    this.signalRegistry=result.reg||this.signalRegistry;delete result.reg;
    if(result.accepted&&(s.status==='PENDING'||s.status==='OPEN')&&String(s.market||'').toUpperCase()==='CRYPTO')try{await this.ensureCryptoMonitor(25);}catch{}
    return result;
  }
  async unregisterSignal(payload){
    const id=String(payload?.id||payload?.signalId||'');if(!id)return {ok:false};
    let next={};await this.state.storage.transaction(async txn=>{const reg=(await txn.get('signalRegistry'))||{};delete reg[id];await txn.put('signalRegistry',reg);next=reg;});this.signalRegistry=next;return {ok:true,id};
  }
  async setStandbys(payload){
    const style=String(payload?.style||'').toUpperCase();if(!['SCALP','SWING'].includes(style))return {ok:false,error:'BAD_STYLE'};
    const key=`standby:${style}`,old=(await this.state.storage.get(key))||{rows:[]},reg=await this.registry(),active=this.activeRows(reg),activeSymbols=new Set(active.map(x=>canonical(x.symbol))),rows=[],seen=new Set(),incoming=Array.isArray(payload?.signals)?payload.signals:[];
    const combined=[...incoming,...(Array.isArray(old.rows)?old.rows:[])];
    for(const raw of combined){
      if(rows.length>=Number(PORTFOLIO_POLICY.standbyPerStyle||3))break;
      const s={...(raw||{})},symbol=canonical(s.symbol),order=String(s.orderType||'').toUpperCase();
      if(!symbol||seen.has(symbol)||activeSymbols.has(symbol))continue;
      if(String(s.market||'CRYPTO').toUpperCase()!=='CRYPTO'||String(s.style||style).toUpperCase()!==style)continue;
      if(!['LIMIT','STOP'].includes(order)||!validSignalStructure(s))continue;
      const assessment=assessCoverageSetup(s);if(assessment?.verdict!=='PASS')continue;
      rows.push({...s,market:'CRYPTO',style,status:'PENDING',entryState:'PENDING_ENTRY',coverageFallback:true,coverageTier:s.coverageTier||'HOT_SPARE_CONDITIONAL',entryAssessment:assessment,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,standbyPreparedAt:s.standbyPreparedAt||nowIso()});seen.add(symbol);
    }
    const pack={style,preparedAt:Date.now(),receivedAt:nowIso(),rows};await this.state.storage.put(key,pack);return {ok:true,style,count:rows.length,symbols:rows.map(x=>x.symbol)};
  }
  async standbySnapshot(){
    const out={};for(const style of ['SCALP','SWING']){const p=(await this.state.storage.get(`standby:${style}`))||{style,preparedAt:null,rows:[]};out[style]={preparedAt:p.preparedAt||null,ageMs:p.preparedAt?Math.max(0,Date.now()-Number(p.preparedAt)):null,count:Array.isArray(p.rows)?p.rows.length:0,symbols:Array.isArray(p.rows)?p.rows.map(x=>x.symbol):[]};}return out;
  }
  async promoteStandby(style,reason='AUTO_REPLACE'){
    style=String(style||'').toUpperCase();if(!['SCALP','SWING'].includes(style))return {ok:false,promoted:[],error:'BAD_STYLE'};
    const key=`standby:${style}`,pack=(await this.state.storage.get(key))||{style,preparedAt:0,rows:[]},pool=Array.isArray(pack.rows)?[...pack.rows]:[],promoted=[];
    let reg=await this.registry(),active=this.activeRows(reg),styleCount=active.filter(x=>String(x.style||'').toUpperCase()===style).length;
    const maxAge=style==='SCALP'?10*60*1000:60*60*1000;if(pack.preparedAt&&Date.now()-Number(pack.preparedAt)>maxAge)pool.splice(0,pool.length);
    while(styleCount<styleTarget(style)&&pool.length){
      const raw=pool.shift(),symbol=canonical(raw?.symbol),order=String(raw?.orderType||'').toUpperCase();if(!symbol||!['LIMIT','STOP'].includes(order)||!validSignalStructure(raw))continue;
      active=this.activeRows(reg);if(active.some(x=>canonical(x.symbol)===symbol))continue;
      const cluster=cryptoRiskCluster(symbol),clusterCount=active.filter(x=>cryptoRiskCluster(x.symbol)===cluster).length;if(cluster==='MEME'&&clusterCount>=PORTFOLIO_POLICY.maxMemeActiveTotal)continue;if(clusterCount>=PORTFOLIO_POLICY.maxActivePerRiskCluster)continue;
      if(active.length>=PORTFOLIO_POLICY.maxActiveTotal||active.filter(x=>String(x.style||'').toUpperCase()===style).length>=styleMax(style))break;
      const issuedAt=nowIso(),id=`V319R-CRYPTO-${style}-${symbol}-${Date.now().toString(36)}`,s={...raw,id,signalId:id,market:'CRYPTO',style,symbol,status:'PENDING',entryState:'PENDING_ENTRY',lifecycle:'PENDING_ENTRY',issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,riskCluster:cluster,coverageReplacement:true,replacementReason:reason,reservationMode:'DURABLE_OBJECT_HOT_SPARE_PROMOTION',portfolioPolicy:PORTFOLIO_POLICY};
      const kvKey=`v31:signal:CRYPTO:${style}:${id}`;reg[id]={...s,kvKey};styleCount++;promoted.push(s);
      if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:CRYPTO:${style}:${symbol}`,id,{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:any:CRYPTO:${symbol}`,id,{expirationTtl:SIGNAL_TTL});}
      this.broadcast({type:'signal_event',event:'HOT_SPARE_PROMOTED',signal:s,receivedAt:issuedAt});
    }
    this.signalRegistry=reg;await this.state.storage.put('signalRegistry',reg);await this.state.storage.put(key,{...pack,rows:pool,updatedAt:Date.now()});return {ok:true,style,promoted:promoted.map(x=>({id:x.id,symbol:x.symbol,orderType:x.orderType})),remaining:pool.length};
  }
  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);const provider=String(q?.exchange||q?.provider||'').toUpperCase();if(provider)by.set(`${provider}:${sym}`,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='PENDING'&&s.status!=='OPEN'){delete reg[id];dirty=true;continue;}
      const sym=canonical(s.symbol),authority=String(s.executionPriceAuthority||s.provider||s.exchange||'').toUpperCase();
      const q=String(market).toUpperCase()==='CRYPTO'&&authority?by.get(`${authority}:${sym}`):by.get(sym);if(!q)continue;
      const dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
      let entryPx,exitPx;
      if(String(market).toUpperCase()==='FOREX'){
        const bid=Number(q.bid||q.mid||0),ask=Number(q.ask||q.mid||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;
      }else{const last=Number(q.lastPrice||q.last||q.mid||0),bid=Number(q.bid||last||0),ask=Number(q.ask||last||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;}
      if(!(entryPx>0&&exitPx>0))continue;
      const entry=Number(s.entry),sl=Number(s.sl),tp1=Number(s.tp1||s.tp3||s.tp),tp=Number(s.tp3||s.tp);let mutated=false,eventType='';
      if(s.status==='PENDING'){
        const type=String(s.orderType||'').toUpperCase();
        const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        const structureInvalidation=Number(s.invalidationLevel||sl),invalidated=dir>0?exitPx<=structureInvalidation:exitPx>=structureInvalidation;
        const missedMove=type==='LIMIT'&&tp1>0&&(dir>0?exitPx>=tp1:exitPx<=tp1);
        const issued=Date.parse(s.issuedAt||s.standbyPreparedAt||''),pendingAge=Number.isFinite(issued)?Math.max(0,Date.now()-issued):0,maxPendingAge=String(s.style||'').toUpperCase()==='SWING'?6*60*60*1000:20*60*1000;
        const stalePending=pendingAge>maxPendingAge;
        const qTurn=Number(q.turnover24h||s?.technicalAtIssue?.turnover24h||0),qSpread=Number(q.spreadBps??s?.technicalAtIssue?.spreadBps??999),rule=stableUniverseRule(s.style),liquidityDegraded=qTurn<rule.minTurnover||qSpread>rule.maxSpread*1.35;
        if(invalidated||missedMove||stalePending||liquidityDegraded){
          s.status='CANCELLED';s.lifecycle=invalidated?'INVALIDATED_BEFORE_ENTRY':missedMove?'MISSED_MOVE_BEFORE_ENTRY':stalePending?'STALE_PENDING_REFRESH':'LIQUIDITY_DEGRADED_BEFORE_ENTRY';s.entryState='CANCELLED';s.cancelledAt=at;s.outcome=s.lifecycle;s.resolution='REALTIME_PENDING_INVALIDATION_REFRESH';eventType='CANCELLED';mutated=true;delete reg[id];dirty=true;
        }else if(trigger){
          s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=entryPx;s.executionStatus='PROVIDER_BID_ASK_TRIGGERED';eventType='TRIGGERED';mutated=true;
        }
      }
      if(s.status==='OPEN'){
        const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
        if(hitTp||hitSl){const ae=Number(s.actualEntry||entry),risk=Math.abs(ae-sl),exit=hitTp?tp:sl;s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=exit;s.resultR=risk>0?Number((dir*(exit-ae)/risk).toFixed(4)):(hitTp?Number(s.targetRR||0):-1);s.resolution='PROVIDER_BID_ASK_REALTIME_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}
      }
      if(mutated){
        s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;
        const active=clean.status==='PENDING'||clean.status==='OPEN';
        if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(active){await this.env.SIGNALS_KV.put(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`,clean.id,{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:any:${clean.market}:${clean.symbol}`,clean.id,{expirationTtl:SIGNAL_TTL});}else{await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyId=await this.env.SIGNALS_KV.get(`v31:active:any:${clean.market}:${clean.symbol}`);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(`v31:active:any:${clean.market}:${clean.symbol}`);}}
        if(active)reg[id]={...clean,kvKey};else delete reg[id];dirty=true;
        changed.push({type:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,at});this.broadcast({type:'signal_event',event:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,receivedAt:at});
      }
    }
    if(dirty)await this.persistRegistry();return changed;
  }
  async fetch(req) {
    const url=new URL(req.url);
    if(req.headers.get('Upgrade')==='websocket'){
      const pair=new WebSocketPair(),client=pair[0],server=pair[1];server.accept();this.clients.add(server);const drop=()=>this.clients.delete(server);server.addEventListener('close',drop);server.addEventListener('error',drop);
      try{const quotes=await this.state.storage.get('quotes'),heartbeat=await this.state.storage.get('heartbeat');if(quotes)server.send(JSON.stringify({type:'quotes',...quotes,heartbeat:heartbeat||null}));}catch{}
      return new Response(null,{status:101,webSocket:client});
    }
    if(req.method==='POST'&&url.pathname==='/register-signal'){const p=await req.json();return new Response(JSON.stringify(await this.registerSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/set-standbys'){const p=await req.json();return new Response(JSON.stringify(await this.setStandbys(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/promote-standby'){const p=await req.json();return new Response(JSON.stringify(await this.promoteStandby(p?.style,p?.reason||'EXTERNAL_REFILL')),{headers:{'content-type':'application/json'}});}
    if(req.method==='GET'&&url.pathname==='/standbys'){return new Response(JSON.stringify(await this.standbySnapshot()),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/kick-crypto-monitor'){return new Response(JSON.stringify(await this.ensureCryptoMonitor(25)),{headers:{'content-type':'application/json'}});}
    if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0};return new Response(JSON.stringify(status),{headers:{'content-type':'application/json'}});}
    if(req.method==='GET'&&url.pathname==='/portfolio-snapshot'){return new Response(JSON.stringify(await this.portfolioSnapshot()),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/release-coverage'){const p=await req.json();return new Response(JSON.stringify(await this.releaseCoverage(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/evaluate'){const p=await req.json(),events=await this.evaluate(p.market,p.rows||[],p.receivedAt);return new Response(JSON.stringify({ok:true,events}),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/prices'){
      const packet=await req.json();await this.state.storage.put('quotes',packet);this.broadcast({type:'quotes',...packet});const events=await this.evaluate('FOREX',packet.quotes||[],packet.receivedAt),coverage=await this.claimCoverage();return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt,events:events.length,coverageClaims:coverage.claimed,portfolio:coverage.portfolio}),{headers:{'content-type':'application/json'}});
    }
    if(req.method==='POST'&&url.pathname==='/heartbeat'){const heartbeat=await req.json();await this.state.storage.put('heartbeat',heartbeat);this.broadcast({type:'heartbeat',heartbeat});return new Response(JSON.stringify({ok:true,receivedAt:heartbeat.receivedAt}),{headers:{'content-type':'application/json'}});}
    if(url.pathname==='/snapshot'){const [quotes,heartbeat]=await Promise.all([this.state.storage.get('quotes'),this.state.storage.get('heartbeat')]);return new Response(JSON.stringify({ok:!!quotes,quotes:quotes||null,heartbeat:heartbeat||null}),{headers:{'content-type':'application/json','cache-control':'no-store'}});}
    return new Response('not found',{status:404});
  }
}
function mt5LiveStub(env){
  if(!env?.MT5_LIVE)return null;
  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));
}
async function realtimePortfolioSnapshot(env){
  const stub=mt5LiveStub(env);if(!stub)return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0}};
  try{const r=await stub.fetch('https://mt5-live/portfolio-snapshot');if(r.ok)return await r.json();}catch{}return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0}};
}
async function releaseCoverageClaim(env,market){const stub=mt5LiveStub(env);if(!stub)return;try{await stub.fetch('https://mt5-live/release-coverage',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market})});}catch{}}
async function setCryptoStandbys(env,style,signals){const stub=mt5LiveStub(env);if(!stub)return {ok:false,count:0};try{const r=await stub.fetch('https://mt5-live/set-standbys',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,signals})});return r.ok?await r.json():{ok:false,count:0};}catch(e){return {ok:false,count:0,error:String(e?.message||e)};}}
async function promoteCryptoStandby(env,style,reason='EXTERNAL_REFILL'){const stub=mt5LiveStub(env);if(!stub)return {ok:false,promoted:[]};try{const r=await stub.fetch('https://mt5-live/promote-standby',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,reason})});return r.ok?await r.json():{ok:false,promoted:[]};}catch(e){return {ok:false,promoted:[],error:String(e?.message||e)};}}
async function cryptoStandbyStatus(env){const stub=mt5LiveStub(env);if(!stub)return {};try{const r=await stub.fetch('https://mt5-live/standbys');return r.ok?await r.json():{};}catch{return {};}}
async function kickCryptoServerMonitor(env){const stub=mt5LiveStub(env);if(!stub)return {ok:false,running:false};try{const r=await stub.fetch('https://mt5-live/kick-crypto-monitor',{method:'POST'});return r.ok?await r.json():{ok:false,running:false};}catch(e){return {ok:false,running:false,error:String(e?.message||e)};}}
async function cryptoServerMonitorStatus(env){const stub=mt5LiveStub(env);if(!stub)return {ok:false,running:false};try{const r=await stub.fetch('https://mt5-live/crypto-monitor-status');return r.ok?await r.json():{ok:false,running:false};}catch(e){return {ok:false,running:false,error:String(e?.message||e)};}}
async function refillMarketCoverage(env,market){
  const m=String(market||'').toUpperCase();let success=false;
  try{
    let p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.[m]||0)>=PORTFOLIO_POLICY.minActivePerMarket){success=true;return;}
    if(m==='FOREX'){
      await scanForexScalp(env).catch(()=>{});p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.FOREX||0)<PORTFOLIO_POLICY.minActivePerMarket)await scanForexSwing(env).catch(()=>{});
    }else if(m==='CRYPTO'){
      await scanCrypto(env,'SCALP').catch(()=>{});p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.CRYPTO||0)<PORTFOLIO_POLICY.minActivePerMarket)await scanCrypto(env,'SWING').catch(()=>{});await kickCryptoServerMonitor(env);
    }
    p=await realtimePortfolioSnapshot(env);success=Number(p.counts?.[m]||0)>=PORTFOLIO_POLICY.minActivePerMarket;
  }finally{await releaseCoverageClaim(env,m);}
  return success;
}

async function syncRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub||!s)return;
  try{
    if(s.status==='PENDING'||s.status==='OPEN')await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});
    else await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:s.id||s.signalId})});
  }catch{}
}

async function readMt5Realtime(env){
  const stub=mt5LiveStub(env);
  if(stub){
    try{const r=await stub.fetch('https://mt5-live/snapshot');if(r.ok)return await r.json()}catch{}
  }
  let quotes=null,heartbeat=null;
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:quotes:latest');if(raw)quotes=JSON.parse(raw)}catch{}
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:heartbeat:latest');if(raw)heartbeat=JSON.parse(raw)}catch{}
  return {ok:!!quotes,quotes,heartbeat};
}

async function fetchJson(url, init = {}, timeoutMs = PROVIDER_TIMEOUT_MS) {
  const c = new AbortController();
  const id = setTimeout(() => c.abort('timeout'), timeoutMs);
  try {
    const r = await fetch(url, {
      ...init,
      signal: c.signal,
      headers: {
        accept: 'application/json',
        'user-agent': 'SignalHub-V3/3.1',
        ...(init.headers || {}),
      },
      cf: { cacheTtl: 0, cacheEverything: false, ...(init.cf || {}) },
    });
    if (!r.ok) throw new Error(`HTTP_${r.status}`);
    return await r.json();
  } finally { clearTimeout(id); }
}

async function readJson(req, maxBytes = 1_000_000) {
  const raw = await req.text();
  if (raw.length > maxBytes) throw new Error('PAYLOAD_TOO_LARGE');
  try { return JSON.parse(raw || '{}'); }
  catch { throw new Error('INVALID_JSON'); }
}
function bridgeAllowed(req, env) {
  const expected = String(env?.MT5_BRIDGE_TOKEN || '').trim();
  if (!expected) return String(req.headers.get('x-signalhub-bridge') || '').startsWith('SIGNALHUB-EXNESS-BRIDGE-');
  return String(req.headers.get('authorization') || '') === `Bearer ${expected}`;
}
function sanitizeQuote(q) {
  const symbol = canonical(q?.symbol), brokerSymbol = String(q?.brokerSymbol || '').trim();
  const bid = num(q?.bid), ask = num(q?.ask), last = num(q?.last), spreadPoints = num(q?.spreadPoints), tickTimeMsc = Number(q?.tickTimeMsc || 0);
  if (!symbol || !isFinitePositive(bid) || !isFinitePositive(ask) || ask < bid) return null;
  return {symbol,brokerSymbol,bid,ask,mid:(bid+ask)/2,last:isFinitePositive(last)?last:null,spreadPoints:Number.isFinite(spreadPoints)?spreadPoints:null,tickTimeMsc:tickTimeMsc>0?tickTimeMsc:null};
}
async function mt5Prices(req, env, ctx) {
  if (!bridgeAllowed(req,env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req,2_000_000), quotes=(Array.isArray(body?.quotes)?body.quotes:[]).slice(0,120).map(sanitizeQuote).filter(Boolean), receivedAt=nowIso();
  const packet={ok:true,version:V3_VERSION,source:'EXNESS_MT5',bridgeVersion:String(body?.bridgeVersion||''),server:String(body?.server||''),receivedAt,quotes,count:quotes.length};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/prices',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(packet)});
    if(r.ok){let state={};try{state=await r.json();}catch{}for(const market of state.coverageClaims||[])if(ctx?.waitUntil)ctx.waitUntil(Promise.resolve(refillMarketCoverage(env,market)).catch(()=>{}));return json({ok:true,accepted:quotes.length,receivedAt,transport:'DURABLE_OBJECT_REALTIME',coverageClaims:state.coverageClaims||[]});}
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:quotes:latest',JSON.stringify(packet),{expirationTtl:MT5_QUOTE_TTL});
  return json({ok:true,accepted:quotes.length,receivedAt,transport:'KV_FALLBACK'});
}
async function mt5Heartbeat(req,env){
  if(!bridgeAllowed(req,env))return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req),receivedAt=nowIso();
  const heartbeat={bridgeVersion:String(body?.bridgeVersion||''),status:String(body?.status||''),server:String(body?.server||''),company:String(body?.company||''),terminalConnected:body?.terminalConnected===true,tradeAllowed:body?.tradeAllowed===true,resolvedSymbols:Number(body?.resolvedSymbols||0),positions:Number(body?.positions||0),orders:Number(body?.orders||0),queuedEvents:Number(body?.queuedEvents||0),receivedAt};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/heartbeat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(heartbeat)});
    if(r.ok)return json({ok:true,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:heartbeat:latest',JSON.stringify(heartbeat),{expirationTtl:MT5_HEARTBEAT_TTL});
  return json({ok:true,receivedAt,transport:'KV_FALLBACK'});
}
async function loadSignalById(kv,id){
  const parts=String(id||'').split('-'),partition=(parts.length>3&&/^V3\d+$/.test(parts[0]))?`v31:signal:${parts[1]}:${parts[2]}:${id}`:null;
  for(const key of [`signal:${id}`,`v31:signal:${id}`,partition].filter(Boolean)){
    const raw=await kv.get(key); if(!raw)continue; try{return {key,signal:JSON.parse(raw)}}catch{}
  }
  return null;
}
async function patchSignalFromBrokerEvent(env,evt,receivedAt){
  const id=String(evt?.signalId||'').trim(); if(!id||!env?.SIGNALS_KV)return {patched:false,reason:'NO_SIGNAL_ID'};
  const found=await loadSignalById(env.SIGNALS_KV,id); if(!found)return {patched:false,reason:'SIGNAL_NOT_FOUND'};
  const s=found.signal,event=String(evt?.event||'').toUpperCase(),price=num(evt?.price);
  if(event==='BROKER_FILL_CONFIRMED'){
    s.status='OPEN';s.triggeredAt=s.triggeredAt||receivedAt;s.brokerFilledAt=receivedAt;s.brokerConfirmed=true;s.executionSource='EXNESS_MT5_DEAL';
    if(isFinitePositive(price)){s.actualEntry=price;s.entry=price;s.lastPrice=price;}
    s.brokerSymbol=String(evt?.brokerSymbol||s.brokerSymbol||'');s.brokerDealTicket=String(evt?.dealTicket||'');s.brokerOrderTicket=String(evt?.orderTicket||'');
  }else if(event==='BROKER_CLOSE_CONFIRMED'){
    const reason=String(evt?.dealReason||'BROKER_CLOSE').toUpperCase();s.brokerClosedAt=receivedAt;s.brokerClosePrice=isFinitePositive(price)?price:null;s.brokerCloseConfirmed=true;s.brokerCloseReason=reason;s.executionSource='EXNESS_MT5_DEAL';
    if((reason==='TP'||reason==='SL')&&isFinitePositive(price)){
      const entry=num(s.actualEntry??s.entry),stop=num(s.sl),risk=isFinitePositive(entry)&&isFinitePositive(stop)?Math.abs(entry-stop):null,dir=String(s.side||'').toUpperCase()==='LONG'?1:-1;
      s.status='CLOSED';s.outcome=reason;s.closedAt=receivedAt;s.exitPrice=price;if(risk&&risk>0)s.resultR=Number((dir*(price-entry)/risk).toFixed(4));s.resolution='BROKER_CONFIRMED_'+reason;
    }
  }else return {patched:false,reason:'EVENT_NOT_PATCHABLE'};
  s.lastCheckedAt=receivedAt;await env.SIGNALS_KV.put(found.key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});await syncRealtimeSignal(env,s,found.key);
  return {patched:true,status:s.status,outcome:s.outcome||null};
}
async function mt5Event(req,env){
  if(!bridgeAllowed(req,env))return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_KV'},503);
  const evt=await readJson(req),receivedAt=nowIso(),deal=String(evt?.dealTicket||'').trim(),eventId=deal||`${Date.now()}-${Math.random().toString(36).slice(2)}`,record={...evt,receivedAt,eventId,source:'EXNESS_MT5'};
  await env.SIGNALS_KV.put(`v3:mt5:event:${eventId}`,JSON.stringify(record),{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put('v3:mt5:event:latest',JSON.stringify(record),{expirationTtl:SIGNAL_TTL});
  return json({ok:true,eventId,receivedAt,signalPatch:await patchSignalFromBrokerEvent(env,evt,receivedAt)});
}
async function mt5Live(env){
  const snap=await readMt5Realtime(env),quotes=snap?.quotes||null,heartbeat=snap?.heartbeat||null;
  let lastEvent=null;try{const er=await env?.SIGNALS_KV?.get('v3:mt5:event:latest');if(er)lastEvent=JSON.parse(er)}catch{}
  const qAt=Date.parse(quotes?.receivedAt||''),hAt=Date.parse(heartbeat?.receivedAt||''),quoteAgeMs=Number.isFinite(qAt)?Math.max(0,Date.now()-qAt):null,heartbeatAgeMs=Number.isFinite(hAt)?Math.max(0,Date.now()-hAt):null;
  const terminalConnected=heartbeat?.terminalConnected!==false;
  const state=quoteAgeMs===null?'OFFLINE':!terminalConnected?'OFFLINE':heartbeatAgeMs!==null&&heartbeatAgeMs>10000?'OFFLINE':quoteAgeMs<=1800?'LIVE':quoteAgeMs<=4000?'DELAYED':quoteAgeMs<=10000?'STALE':'OFFLINE';
  return json({ok:!!quotes,version:V3_VERSION,market:'FOREX_EXNESS',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME':'KV_FALLBACK',stream:'/v3/forex/stream',state,quoteAgeMs,heartbeatAgeMs,quotes:quotes?.quotes||[],count:quotes?.count||0,heartbeat,lastEvent:lastEvent?{event:lastEvent.event,signalId:lastEvent.signalId||'',brokerSymbol:lastEvent.brokerSymbol||'',price:num(lastEvent.price),dealReason:lastEvent.dealReason||'',receivedAt:lastEvent.receivedAt}:null},quotes?200:503);
}
async function mt5Stream(req,env){
  const stub=mt5LiveStub(env);if(!stub)return new Response('realtime stream unavailable',{status:503});
  const headers=new Headers(req.headers);headers.set('Upgrade','websocket');
  return stub.fetch(new Request('https://mt5-live/stream',{method:'GET',headers}));
}

function cleanBybitTicker(x){
  const bid=num(x?.bid1Price),ask=num(x?.ask1Price),last=num(x?.lastPrice),turn=num(x?.turnover24h),oi=num(x?.openInterestValue),fr=num(x?.fundingRate),ch=num(x?.price24hPcnt),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;
  return {symbol:canonical(x?.symbol),lastPrice:last,markPrice:num(x?.markPrice),indexPrice:num(x?.indexPrice),bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:turn,volume24h:num(x?.volume24h),openInterestValue:oi,fundingRate:fr,change24hPct:Number.isFinite(ch)?ch*100:null,nextFundingTime:Number(x?.nextFundingTime||0)||null,exchange:'BYBIT',source:'BYBIT_V5'};
}
async function bybitFetch(path){
  let lastErr=null;for(const base of BYBIT_BASES){try{const data=await fetchJson(base+path);if(Number(data?.retCode||0)!==0)throw new Error(`BYBIT_${data?.retCode}:${data?.retMsg||''}`);return data}catch(e){lastErr=e;}}
  throw lastErr||new Error('BYBIT_UNAVAILABLE');
}
async function bybitTickers(){
  const raw=await bybitFetch('/v5/market/tickers?category=linear');
  const rows=(raw?.result?.list||[]).map(cleanBybitTicker).filter(x=>x.symbol.endsWith('USDT')&&isFinitePositive(x.lastPrice));rows.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));
  return {rows,provider:'BYBIT',exchangeTime:Number(raw?.time||0),receivedAt:nowIso(),live:true};
}
async function okxTickers(){
  const raw=await fetchJson('https://www.okx.com/api/v5/market/tickers?instType=SWAP');if(String(raw?.code||'0')!=='0')throw new Error(`OKX_${raw?.code}:${raw?.msg||''}`);
  const rows=[];for(const x of raw?.data||[]){const inst=String(x?.instId||'');if(!inst.endsWith('-USDT-SWAP'))continue;const last=num(x?.last),bid=num(x?.bidPx),ask=num(x?.askPx),baseVol=num(x?.vol24h),quoteVol=num(x?.volCcy24h),open=num(x?.open24h),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;rows.push({symbol:canonical(inst.replace('-SWAP','')),lastPrice:last,bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:isFinitePositive(quoteVol)&&isFinitePositive(last)?quoteVol*last:null,volume24h:quoteVol,contractVolume24h:baseVol,turnoverModel:'OKX_BASE_CCY_VOL_X_LAST',openInterestValue:null,fundingRate:null,change24hPct:isFinitePositive(open)&&isFinitePositive(last)?(last/open-1)*100:null,exchange:'OKX',source:'OKX_V5'});}
  const filtered=rows.filter(x=>x.symbol.endsWith('USDT')&&isFinitePositive(x.lastPrice));filtered.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));return {rows:filtered,provider:'OKX',exchangeTime:Date.now(),receivedAt:nowIso(),live:true};
}
async function binanceTickers(){
  const raw=await fetchJson('https://fapi.binance.com/fapi/v1/ticker/24hr');if(!Array.isArray(raw))throw new Error('BINANCE_BAD_JSON');
  const rows=raw.filter(x=>String(x?.symbol||'').endsWith('USDT')).map(x=>{const last=num(x.lastPrice),bid=num(x.bidPrice),ask=num(x.askPrice),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;return {symbol:canonical(x.symbol),lastPrice:last,bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:num(x.quoteVolume),volume24h:num(x.volume),openInterestValue:null,fundingRate:null,change24hPct:num(x.priceChangePercent),exchange:'BINANCE',source:'BINANCE_FAPI'};}).filter(x=>isFinitePositive(x.lastPrice));rows.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));return {rows,provider:'BINANCE',exchangeTime:Date.now(),receivedAt:nowIso(),live:true};
}
async function loadCryptoSnapshot(env){
  const errors=[];for(const fn of [bybitTickers,okxTickers,binanceTickers]){try{const snap=await fn();if(snap.rows.length){if(env?.SIGNALS_KV)await env.SIGNALS_KV.put('v321:crypto:tickers:lastgood:schema3',JSON.stringify(snap),{expirationTtl:CRYPTO_LASTGOOD_TTL});return {...snap,errors};}}catch(e){errors.push(String(e?.message||e));}}
  if(env?.SIGNALS_KV){const raw=await env.SIGNALS_KV.get('v321:crypto:tickers:lastgood:schema3');if(raw){try{const old=JSON.parse(raw),ageMs=Math.max(0,Date.now()-Date.parse(old.receivedAt||''));return {...old,live:false,staleFallback:true,ageMs,errors};}catch{}}}
  throw new Error('CRYPTO_ALL_PROVIDERS_UNAVAILABLE:'+errors.join('|'));
}
async function cryptoSnapshotForProvider(env,provider){
  const p=String(provider||'BYBIT').toUpperCase();
  try{
    const snap=p==='OKX'?await okxTickers():p==='BINANCE'?await binanceTickers():await bybitTickers();
    return {...snap,provider:p,live:true};
  }catch(e){return {rows:[],provider:p,live:false,receivedAt:nowIso(),error:String(e?.message||e)};}
}
async function cryptoTickers(url,env){
  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000)));
  if(snap.live!==false){const stub=mt5LiveStub(env);if(stub){try{await stub.fetch('https://mt5-live/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market:'CRYPTO',rows:snap.rows,receivedAt:snap.receivedAt})});}catch{}}}
  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:snap.live!==false,staleFallback:snap.staleFallback===true,ageMs:snap.ageMs??0,count:snap.rows.length,tickers:snap.rows.slice(0,limit),exchangeTime:snap.exchangeTime,receivedAt:snap.receivedAt,providerErrors:snap.errors||[],note:'Bybit is preferred. Live snapshots also drive pending-order activation; fallback exchange is explicitly labeled.'});
}
async function cryptoDiscovery(url,env){
  const style=String(url.searchParams.get('style')||'scalp').toUpperCase()==='SWING'?'SWING':'SCALP';
  const limit=Math.min(100,Math.max(5,Number(url.searchParams.get('limit')||40))),snap=await loadCryptoSnapshot(env),all=snap.rows;
  const candidates=all.filter(t=>stableUniverseEligible(t,style)).sort(stableUniverseCompare).slice(0,limit).map(t=>({...t,marketRead:'STABLE_LIQUID_UNIVERSE_DISCOVERY'}));
  return json({ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,candidates,classification:'DISCOVERY_ONLY_NOT_TRADE_SIGNAL',decisionMode:'BOT_MARKET_JUDGMENT',note:'No composite score gate is used. Discovery first removes weak-liquidity / wide-spread / extreme-move symbols, then hands the stable live universe to the structure/liquidity engine.',receivedAt:snap.receivedAt});
}

function ema(values,period){if(!Array.isArray(values)||values.length<period)return null;const k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;for(let i=period;i<values.length;i++)x=values[i]*k+x*(1-k);return x;}
function emaSeries(values,period){if(values.length<period)return[];const out=new Array(values.length).fill(null),k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;out[period-1]=x;for(let i=period;i<values.length;i++){x=values[i]*k+x*(1-k);out[i]=x;}return out;}
function rsi(values,period=14){if(values.length<period+1)return null;let g=0,l=0;for(let i=values.length-period;i<values.length;i++){const d=values[i]-values[i-1];if(d>=0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/period)/(l/period);return 100-100/(1+rs);}
function atr(rows,period=14){if(rows.length<period+1)return null;const trs=[];for(let i=1;i<rows.length;i++){const p=rows[i-1].c,r=rows[i];trs.push(Math.max(r.h-r.l,Math.abs(r.h-p),Math.abs(r.l-p)));}const a=trs.slice(-period);return a.reduce((x,y)=>x+y,0)/a.length;}
function tfStats(rows){
  if(!rows||rows.length<55)return null;
  const closes=rows.map(x=>x.c),e20s=emaSeries(closes,20),e50=ema(closes,50),e20=e20s.at(-1),e20Prev=e20s[Math.max(19,e20s.length-6)],rr=rsi(closes,14),aa=atr(rows,14),last=rows.at(-1),prev=rows.at(-2);
  const prior=rows.slice(-34,-2),recent=rows.slice(-9,-1);
  const priorHigh=Math.max(...prior.map(x=>x.h)),priorLow=Math.min(...prior.map(x=>x.l)),recentHigh=Math.max(...recent.map(x=>x.h)),recentLow=Math.min(...recent.map(x=>x.l));
  if(![e20,e50,rr,aa,last?.c,priorHigh,priorLow,recentHigh,recentLow].every(Number.isFinite)||aa<=0)return null;
  const trend=last.c>e20&&e20>e50?1:last.c<e20&&e20<e50?-1:0,slope=e20Prev?((e20-e20Prev)/aa):0,momentum=rr>=52?1:rr<=48?-1:0;
  const body=Math.max(Math.abs(last.c-last.o),aa*.04),upperWick=Math.max(0,last.h-Math.max(last.o,last.c)),lowerWick=Math.max(0,Math.min(last.o,last.c)-last.l);
  const sweepHigh=last.h>priorHigh&&last.c<priorHigh&&upperWick>body*.65,sweepLow=last.l<priorLow&&last.c>priorLow&&lowerWick>body*.65;
  const bosUp=last.c>priorHigh,bosDown=last.c<priorLow,range=Math.max(priorHigh-priorLow,aa*.25),rangePosition=Math.max(0,Math.min(1,(last.c-priorLow)/range));
  const impulse=Math.abs(last.c-last.o)/aa,extensionAtr=Math.abs(last.c-e20)/aa,bodyAtr=body/aa;
  const bullDisplacement=last.c>last.o&&bodyAtr>=.30&&last.c>e20&&last.c>Number(prev?.h||e20),bearDisplacement=last.c<last.o&&bodyAtr>=.30&&last.c<e20&&last.c<Number(prev?.l||e20);
  const emaReclaimUp=Number(prev?.c||last.c)<=e20&&last.c>e20&&last.c>last.o,emaReclaimDown=Number(prev?.c||last.c)>=e20&&last.c<e20&&last.c<last.o;
  return {close:last.c,open:last.o,high:last.h,low:last.l,prevClose:prev?.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,recentHigh,recentLow,extensionAtr,momentum,sweepHigh,sweepLow,bosUp,bosDown,rangePosition,impulse,bodyAtr,bullDisplacement,bearDisplacement,emaReclaimUp,emaReclaimDown,upperWickAtr:upperWick/aa,lowerWickAtr:lowerWick/aa};
}
const intervalMap={SCALP:['5m','15m','1h'],SWING:['1h','4h','1d']};
async function bybitCandles(symbol,interval,limit=120){const m={"5m":'5',"15m":'15',"1h":'60',"4h":'240',"1d":'D'}[interval],raw=await bybitFetch(`/v5/market/kline?category=linear&symbol=${encodeURIComponent(symbol)}&interval=${m}&limit=${limit}`),rows=(raw?.result?.list||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('BYBIT_CANDLES_SHORT');return rows;}
async function okxCandles(symbol,interval,limit=120){const inst=symbol.replace(/USDT$/,'-USDT-SWAP'),bar={"5m":'5m',"15m":'15m',"1h":'1H',"4h":'4H',"1d":'1D'}[interval],raw=await fetchJson(`https://www.okx.com/api/v5/market/candles?instId=${encodeURIComponent(inst)}&bar=${bar}&limit=${limit}`);if(String(raw?.code||'0')!=='0')throw new Error('OKX_CANDLES_'+raw?.code);const rows=(raw?.data||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('OKX_CANDLES_SHORT');return rows;}
async function binanceCandles(symbol,interval,limit=120){const raw=await fetchJson(`https://fapi.binance.com/fapi/v1/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`);if(!Array.isArray(raw))throw new Error('BINANCE_CANDLES_BAD');const rows=raw.map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c));if(rows.length<55)throw new Error('BINANCE_CANDLES_SHORT');return rows;}
async function providerCandles(symbol,interval,preferred){
  const order=preferred==='OKX'?[okxCandles,bybitCandles,binanceCandles]:preferred==='BINANCE'?[binanceCandles,bybitCandles,okxCandles]:[bybitCandles,okxCandles,binanceCandles];let last=null;for(const fn of order){try{return await fn(symbol,interval)}catch(e){last=e;}}throw last||new Error('NO_CANDLES');
}
function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,spread=Number(t.spreadBps??0),atr1=a.atr;
  const breakoutUp=(a.bosUp||((a.priorHigh-px)/atr1>=-.05&&(a.priorHigh-px)/atr1<=.14))&&a.bullDisplacement&&a.momentum>=0;
  const breakoutDown=(a.bosDown||((px-a.priorLow)/atr1>=-.05&&(px-a.priorLow)/atr1<=.14))&&a.bearDisplacement&&a.momentum<=0;
  let dir=0,regime='NO_TRADE',story='',reclaimed=false,displacement=false,liquidityEvent=false,coverageFallback=false;
  if(style==='SWING'){
    const htf=b.trend!==0&&b.trend===c.trend?b.trend:0;if(!htf)return null;
    if(htf===1&&a.sweepLow&&a.close>a.priorLow&&(a.bullDisplacement||a.close>a.ema20)){dir=1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bullish + H1 sweep/reclaim with bullish recovery';reclaimed=true;liquidityEvent=true;displacement=a.bullDisplacement;}
    else if(htf===-1&&a.sweepHigh&&a.close<a.priorHigh&&(a.bearDisplacement||a.close<a.ema20)){dir=-1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bearish + H1 sweep/reclaim with bearish recovery';reclaimed=true;liquidityEvent=true;displacement=a.bearDisplacement;}
    else if(htf===1&&(a.emaReclaimUp||a.bosUp)&&a.bullDisplacement&&a.momentum===1){dir=1;regime='HTF_TREND_RECLAIM';story='H4/D1 bullish + H1 displacement reclaims execution structure';reclaimed=true;displacement=true;}
    else if(htf===-1&&(a.emaReclaimDown||a.bosDown)&&a.bearDisplacement&&a.momentum===-1){dir=-1;regime='HTF_TREND_RECLAIM';story='H4/D1 bearish + H1 displacement reclaims execution structure';reclaimed=true;displacement=true;}
    else if(htf===1&&breakoutUp){dir=1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bullish + H1 displacement confirms breakout';reclaimed=a.bosUp;displacement=true;}
    else if(htf===-1&&breakoutDown){dir=-1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bearish + H1 displacement confirms breakdown';reclaimed=a.bosDown;displacement=true;}
    else{
      const vote=Number(c.trend||0)*3+Number(b.trend||0)*2+Number(a.trend||0)+Number(b.momentum||0)+Number(a.momentum||0);
      dir=vote>0?1:vote<0?-1:(px>=Number(b.ema20||px)?1:-1);
      regime='HTF_COVERAGE_CONDITIONAL';story='Best-available H4/D1 context; wait for a conditional pending trigger instead of forcing a market entry';coverageFallback=true;
    }
  }else{
    const bullCtx=b.trend!==-1&&c.trend!==-1&&(b.trend===1||c.trend===1),bearCtx=b.trend!==1&&c.trend!==1&&(b.trend===-1||c.trend===-1),allBull=a.trend===1&&b.trend===1&&c.trend===1,allBear=a.trend===-1&&b.trend===-1&&c.trend===-1;
    if(a.sweepLow&&bullCtx&&a.close>a.priorLow&&(a.bullDisplacement||a.close>a.ema20)){dir=1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m downside sweep/reclaim + supportive 15m/1h context';reclaimed=true;liquidityEvent=true;displacement=a.bullDisplacement;}
    else if(a.sweepHigh&&bearCtx&&a.close<a.priorHigh&&(a.bearDisplacement||a.close<a.ema20)){dir=-1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m upside sweep/reclaim + supportive 15m/1h context';reclaimed=true;liquidityEvent=true;displacement=a.bearDisplacement;}
    else if(b.trend===1&&c.trend===1&&a.emaReclaimUp&&a.bullDisplacement&&a.momentum===1){dir=1;regime='TREND_RECLAIM_CONFIRMED';story='15m/1h bullish + 5m displacement reclaims EMA structure';reclaimed=true;displacement=true;}
    else if(b.trend===-1&&c.trend===-1&&a.emaReclaimDown&&a.bearDisplacement&&a.momentum===-1){dir=-1;regime='TREND_RECLAIM_CONFIRMED';story='15m/1h bearish + 5m displacement reclaims EMA structure';reclaimed=true;displacement=true;}
    else if(allBull&&a.bullDisplacement&&a.extensionAtr<=.24){dir=1;regime='TREND_CONTINUATION_CONFIRMED';story='5m/15m/1h bullish alignment + fresh 5m displacement';displacement=true;reclaimed=a.bosUp||a.close>a.recentHigh;}
    else if(allBear&&a.bearDisplacement&&a.extensionAtr<=.24){dir=-1;regime='TREND_CONTINUATION_CONFIRMED';story='5m/15m/1h bearish alignment + fresh 5m displacement';displacement=true;reclaimed=a.bosDown||a.close<a.recentLow;}
    else if(breakoutUp&&b.trend===1&&c.trend!==-1){dir=1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakout edge + bullish 15m context';reclaimed=a.bosUp;displacement=true;}
    else if(breakoutDown&&b.trend===-1&&c.trend!==1){dir=-1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakdown edge + bearish 15m context';reclaimed=a.bosDown;displacement=true;}
    else{
      const vote=Number(c.trend||0)*2+Number(b.trend||0)*2+Number(a.trend||0)+Number(a.momentum||0)+Number(b.momentum||0);
      dir=vote>0?1:vote<0?-1:(px>=Number(a.ema20||px)?1:-1);
      regime='MICRO_COVERAGE_CONDITIONAL';story='Best-available 5m/15m/1h context; wait for a conditional pending trigger instead of forcing a market entry';coverageFallback=true;
    }
  }

  const spreadPx=Math.max(0,px*spread/10000),entryBuffer=Math.max(atr1*(style==='SCALP'?.045:.08),spreadPx*(style==='SCALP'?2.5:3.0));
  const tooExtended=Math.abs(a.extensionAtr)>(style==='SCALP'?.28:.24),badMarketLocation=dir>0?a.rangePosition>.78:a.rangePosition<.22;
  let orderType='MARKET',entry=px,entryModel=liquidityEvent?'SWEEP_RECLAIM_MARKET':'CONFIRMED_STRUCTURE_MARKET';
  if(coverageFallback){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.34*atr1):Math.min(a.ema20,a.recentHigh-.34*atr1);
    if((dir>0&&raw<px-entryBuffer*.20)||(dir<0&&raw>px+entryBuffer*.20)){orderType='LIMIT';entry=raw;entryModel='COVERAGE_PULLBACK_TRIGGER';}
    else{orderType='STOP';entry=dir>0?Math.max(a.priorHigh,a.recentHigh)+entryBuffer:Math.min(a.priorLow,a.recentLow)-entryBuffer;entryModel='COVERAGE_BREAKOUT_TRIGGER';}
  }else if(regime.includes('BREAKOUT')){orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='CONFIRMED_BREAKOUT_TRIGGER';}
  else if(!liquidityEvent&&(tooExtended||badMarketLocation||regime.includes('RECLAIM'))){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.42*atr1):Math.min(a.ema20,a.recentHigh-.42*atr1);
    if((dir>0&&raw<px-entryBuffer*.35)||(dir<0&&raw>px+entryBuffer*.35)){orderType='LIMIT';entry=raw;entryModel='RETEST_AFTER_DISPLACEMENT_RECLAIM';}
    else if(tooExtended||style==='SWING')return null;
  }

  const stopBuffer=Math.max(atr1*(style==='SCALP'?.22:.34),spreadPx*(style==='SCALP'?3.0:3.5));
  let anchor;
  if(dir>0){anchor=Math.min(a.low,a.recentLow,a.ema50-.08*atr1);if(liquidityEvent)anchor=Math.min(anchor,a.priorLow);if(style==='SWING')anchor=Math.min(anchor,a.priorLow,b.low,b.recentLow,b.ema50-.10*b.atr);}
  else{anchor=Math.max(a.high,a.recentHigh,a.ema50+.08*atr1);if(liquidityEvent)anchor=Math.max(anchor,a.priorHigh);if(style==='SWING')anchor=Math.max(anchor,a.priorHigh,b.high,b.recentHigh,b.ema50+.10*b.atr);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr1*(style==='SCALP'?.75:1.12),maxRisk=atr1*(style==='SCALP'?2.10:4.0);
  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;if(risk>maxRisk){if(!coverageFallback)return null;risk=maxRisk;sl=entry-dir*risk;}
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;
  if(dir>0){tp1=above([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=above([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=above([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}
  else{tp1=below([a.priorLow,a.recentLow],entry-risk*.95);tp2=below([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=below([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const rr=Math.abs(tp3-entry)/risk,spreadState=spread>(style==='SCALP'?8:18)?'WIDE':'NORMAL',cluster=cryptoRiskCluster(t.symbol);
  const qualityEvidence={contextAligned:true,liquidityEvent,displacementConfirmed:displacement,structureReclaimed:reclaimed,secondaryProviderConfirmed:false,entryNotChasing:orderType!=='MARKET'||!tooExtended,invalidationStructural:Number.isFinite(anchor),targetPathClear:dir>0?sl<entry&&entry<tp1&&tp1<tp2&&tp2<tp3:sl>entry&&entry>tp1&&tp1>tp2&&tp2>tp3,coverageConditional:coverageFallback};
  const judgment=coverageFallback?`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • CONDITIONAL COVERAGE`:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • EVIDENCE CONFIRMED`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment,entryModel,coverageFallback,coverageTier:coverageFallback?'BEST_AVAILABLE_CONDITIONAL':'STRICT_CONFIRMED',slModel:'STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,qualityEvidence,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),change24hPct:Number(t.change24hPct||0),openInterestValue:t.openInterestValue==null?null:Number(t.openInterestValue),fundingRate:t.fundingRate==null?null:Number(t.fundingRate),sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,bullDisplacement:a.bullDisplacement,bearDisplacement:a.bearDisplacement,emaReclaimUp:a.emaReclaimUp,emaReclaimDown:a.emaReclaimDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,`SL outside structural invalidation ${Number(anchor.toPrecision(8))} plus volatility/spread buffer`,`TP ladder targets local/context/HTF liquidity before expansion`,`risk cluster ${cluster} • RSI ${a.rsi.toFixed(1)} • extension ${a.extensionAtr.toFixed(2)} ATR • spread ${spread.toFixed(2)} bps`]},'CRYPTO',style);
}
function buildStableReferenceSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t?.lastPrice||0);if(!stableUniverseEligible(t,style)||!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,atr1=Number(a.atr),spread=Number(t.spreadBps??999),spreadPx=Math.max(0,px*spread/10000);
  let dir=0;const vote=2*Number(b.trend||0)+2*Number(c.trend||0)+Number(a.trend||0)+Number(a.momentum||0)+Number(b.momentum||0);
  if(style==='SWING'){if(b.trend!==0&&b.trend===c.trend&&a.trend!==-b.trend)dir=b.trend;else return null;}
  else{if(Math.abs(vote)>=2)dir=vote>0?1:-1;else return null;if(a.trend===-dir&&a.momentum===-dir)return null;}
  const entryBuffer=Math.max(atr1*(style==='SCALP'?.055:.10),spreadPx*3.0),pullback=dir>0?Math.max(a.ema20,a.recentLow+.30*atr1):Math.min(a.ema20,a.recentHigh-.30*atr1);
  let orderType,entry,entryModel;
  const pullbackCorrect=dir>0?pullback<px-entryBuffer*.20:pullback>px+entryBuffer*.20;
  if(pullbackCorrect&&Math.abs(px-pullback)<=atr1*(style==='SCALP'?1.25:1.80)){orderType='LIMIT';entry=pullback;entryModel='STABLE_UNIVERSE_PULLBACK_LIMIT';}
  else{orderType='STOP';entry=dir>0?Math.max(a.recentHigh,a.high)+entryBuffer:Math.min(a.recentLow,a.low)-entryBuffer;entryModel='STABLE_UNIVERSE_CONFIRMATION_STOP';}
  const stopBuffer=Math.max(atr1*(style==='SCALP'?.22:.34),spreadPx*(style==='SCALP'?3.2:3.8));
  const anchor=dir>0?Math.min(a.recentLow,a.low,a.ema50-.06*atr1):Math.max(a.recentHigh,a.high,a.ema50+.06*atr1);
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr1*(style==='SCALP'?.72:1.05),maxRisk=atr1*(style==='SCALP'?2.65:4.20);
  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;if(dir>0){tp1=above([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=above([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=above([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}else{tp1=below([a.priorLow,a.recentLow],entry-risk*.95);tp2=below([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=below([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const cluster=cryptoRiskCluster(t.symbol),story=style==='SCALP'?'Stable-liquid 15m/1h context; wait for 5m pullback or confirmation trigger':'Stable-liquid H4/D1 context; wait for H1 pullback or confirmation trigger',regime=style==='SCALP'?'STABLE_LIQUID_REFERENCE_WAIT':'HTF_STABLE_LIQUID_REFERENCE_WAIT',rr=Math.abs(tp3-entry)/risk;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • REFERENCE WAIT`,entryModel,coverageFallback:true,coverageTier:'STABLE_LIQUID_REFERENCE_PENDING',referenceFallback:true,slModel:'RECENT_STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'NORMAL',qualityEvidence:{contextAligned:true,liquidityEvent:false,displacementConfirmed:false,structureReclaimed:false,secondaryProviderConfirmed:false,entryNotChasing:true,invalidationStructural:true,targetPathClear:true,coverageConditional:true,stableUniverse:true},technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),change24hPct:Number(t.change24hPct||0),openInterestValue:t.openInterestValue==null?null:Number(t.openInterestValue),fundingRate:t.fundingRate==null?null:Number(t.fundingRate),sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,`liquidity floor passed: turnover ${Math.round(Number(t.turnover24h||0))} • spread ${spread.toFixed(2)} bps`,`SL beyond recent execution structure plus ATR/spread buffer`,`pending trigger only — no forced market entry`]},'CRYPTO',style);
}

const WATCH_TF_CACHE_SCHEMA='V3221_WATCH_TF_STATS_1';
function watchTfTtlMs(interval){return interval==='5m'?15*60*1000:interval==='15m'?45*60*1000:interval==='1h'?2*60*60*1000:interval==='4h'?8*60*60*1000:36*60*60*1000;}
function watchTfCacheKey(symbol,interval){return `v3221:watch:tf:${WATCH_TF_CACHE_SCHEMA}:${canonical(symbol)}:${interval}`;}
async function okxHistoryCandlesV3221(symbol,interval,limit=100){
  const inst=symbol.replace(/USDT$/,'-USDT-SWAP'),bar={"5m":'5m',"15m":'15m',"1h":'1H',"4h":'4H',"1d":'1D'}[interval],raw=await fetchJson(`https://www.okx.com/api/v5/market/history-candles?instId=${encodeURIComponent(inst)}&bar=${bar}&limit=${Math.min(100,limit)}`,{},9000);
  if(String(raw?.code||'0')!=='0')throw new Error('OKX_HISTORY_CANDLES_'+raw?.code);
  const rows=(raw?.data||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('OKX_HISTORY_CANDLES_SHORT');return rows;
}
async function readWatchTfCacheV3221(env,symbol,interval){
  if(!env?.SIGNALS_KV)return null;try{const raw=await env.SIGNALS_KV.get(watchTfCacheKey(symbol,interval));if(!raw)return null;const x=JSON.parse(raw),ageMs=Math.max(0,Date.now()-Number(x.fetchedAt||0));if(x.schema!==WATCH_TF_CACHE_SCHEMA||x.interval!==interval||canonical(x.symbol)!==canonical(symbol)||!x.stats||ageMs>watchTfTtlMs(interval))return null;return {...x,ageMs};}catch{return null;}
}
async function putWatchTfCacheV3221(env,symbol,interval,stats,provider){
  if(!env?.SIGNALS_KV||!stats)return;try{await env.SIGNALS_KV.put(watchTfCacheKey(symbol,interval),JSON.stringify({schema:WATCH_TF_CACHE_SCHEMA,symbol:canonical(symbol),interval,stats,provider,fetchedAt:Date.now()}),{expirationTtl:172800});}catch{}
}
async function watchTfStatsV3221(t,interval,env){
  const symbol=canonical(t?.symbol),preferred=String(t?.exchange||t?.venue||t?.provider||'').toUpperCase(),order=[preferred,'OKX','BYBIT','BINANCE'].filter((x,i,a)=>['OKX','BYBIT','BINANCE'].includes(x)&&a.indexOf(x)===i),errors=[];
  for(const provider of order){
    const fns=provider==='OKX'?[okxCandles,okxHistoryCandlesV3221]:provider==='BYBIT'?[bybitCandles]:[binanceCandles];
    for(const fn of fns){try{const rows=await fn(symbol,interval);const stats=tfStats(rows);if(!stats)throw new Error('TF_STATS_INVALID');await putWatchTfCacheV3221(env,symbol,interval,stats,provider);return {stats,provider,mode:'FRESH_CANDLES',ageMs:0,errors};}catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}}
  }
  const cached=await readWatchTfCacheV3221(env,symbol,interval);if(cached)return {stats:cached.stats,provider:cached.provider||preferred||null,mode:'RECENT_VALID_TF_CACHE',ageMs:cached.ageMs,errors};
  return {stats:null,provider:preferred||null,mode:'UNAVAILABLE',ageMs:null,errors};
}
async function watchStatsBundleV3221(t,style,env){
  const frames=intervalMap[style],items=[];for(const frame of frames){items.push(await watchTfStatsV3221(t,frame,env));if(items.at(-1)?.stats==null)break;await sleep(65);}
  if(items.length!==frames.length||items.some(x=>!x.stats))return {ok:false,stats:null,frames:items,mode:'UNAVAILABLE',ageMs:null};
  const cached=items.some(x=>x.mode!=='FRESH_CANDLES'),ageMs=Math.max(...items.map(x=>Number(x.ageMs||0)));return {ok:true,stats:items.map(x=>x.stats),frames:items,mode:cached?'RECENT_VALID_TF_CACHE':'FRESH_CANDLES',ageMs};
}
function buildWatchIdealReference(t,style,stats){
  const [a,b,c]=stats,px=Number(t?.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,atr=Number(a.atr),spread=Math.max(0,Number(t.spreadBps||0)),spreadPx=px*spread/10000;
  let dir=0,contextState='MIXED',aligned=false;
  if(style==='SWING'){
    if(b.trend!==0&&b.trend===c.trend){dir=b.trend;aligned=true;contextState='H4_D1_ALIGNED';}
    else{const vote=3*Number(c.trend||0)+2*Number(b.trend||0)+Number(c.momentum||0)+Number(b.momentum||0);dir=vote>0?1:vote<0?-1:(px>=Number(b.ema50||px)?1:-1);contextState='H4_D1_MIXED_CONFIRMATION_REQUIRED';}
  }else{
    const vote=2*Number(c.trend||0)+2*Number(b.trend||0)+Number(a.trend||0)+Number(b.momentum||0)+Number(a.momentum||0);dir=vote>0?1:vote<0?-1:(px>=Number(b.ema50||px)?1:-1);aligned=(b.trend===dir&&c.trend!==-dir)||(c.trend===dir&&b.trend!==-dir);contextState=aligned?'M15_H1_SUPPORTIVE':'M15_H1_MIXED_CONFIRMATION_REQUIRED';
  }
  const entryBuffer=Math.max(atr*(style==='SCALP'?.07:.12),spreadPx*3.2),structurePullback=dir>0?Math.max(Number(a.ema20||px),Number(a.recentLow||a.low)+.30*atr):Math.min(Number(a.ema20||px),Number(a.recentHigh||a.high)-.30*atr),pb=dir>0?Math.min(px-entryBuffer,structurePullback):Math.max(px+entryBuffer,structurePullback),pbDistance=Math.abs(px-pb);
  const execEvent=dir>0?(a.sweepLow||a.emaReclaimUp||a.bullDisplacement):(a.sweepHigh||a.emaReclaimDown||a.bearDisplacement),preferLimit=aligned&&pbDistance<=atr*(style==='SCALP'?1.35:1.85)&&Math.abs(Number(a.extensionAtr||0))<=1.25;
  const orderType=preferLimit?'LIMIT':'STOP',entry=preferLimit?pb:(dir>0?Math.max(px+entryBuffer,Number(a.recentHigh||a.high)+entryBuffer):Math.min(px-entryBuffer,Number(a.recentLow||a.low)-entryBuffer)),entryModel=preferLimit?'WATCH_IDEAL_STRUCTURE_PULLBACK_LIMIT':'WATCH_IDEAL_CONFIRMATION_STOP';
  const stopBuffer=Math.max(atr*(style==='SCALP'?.28:.44),spreadPx*(style==='SCALP'?3.6:4.4)),anchor=dir>0?Math.min(Number(a.recentLow||a.low),Number(a.low),Number(a.ema50||a.low)-.08*atr):Math.max(Number(a.recentHigh||a.high),Number(a.high),Number(a.ema50||a.high)+.08*atr);
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.82:1.18);if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;
  const hi=(vals,f)=>Math.max(...vals.filter(Number.isFinite),f),lo=(vals,f)=>Math.min(...vals.filter(Number.isFinite),f);let tp1,tp2,tp3;
  if(dir>0){tp1=hi([a.priorHigh,a.recentHigh],entry+risk*1.0);tp2=hi([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.65));tp3=hi([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.25:2.90)));}
  else{tp1=lo([a.priorLow,a.recentLow],entry-risk*1.0);tp2=lo([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.65));tp3=lo([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.25:2.90)));}
  const distance=Math.abs(entry-px),distancePct=distance/px*100,rr=Math.abs(tp3-entry)/risk,regime=style==='SCALP'?'WATCH_V322_MICROSTRUCTURE':'WATCH_V322_HTF_STRUCTURE',story=style==='SCALP'?'SCALP: 5m execution, 15m structure, 1h direction; ưu tiên sweep/reclaim, displacement và vị trí không đuổi giá.':'SWING: H4/D1 định hướng, H1 thực thi; ưu tiên pullback/reclaim hoặc STOP xác nhận khi bối cảnh còn trộn.';
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'REFERENCE',lifecycle:'REFERENCE_ONLY',entryState:'REFERENCE_ONLY',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cryptoRiskCluster(t.symbol),marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STUDY ONLY`,entryModel,slModel:'WATCH_STRUCTURE_INVALIDATION_PLUS_ATR_SPREAD_BUFFER_V322',tpModel:'WATCH_STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION_V322',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'REFERENCE_ONLY',watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,referenceReason:'V322_STYLE_SPECIFIC_IDEAL_PLAN_NOT_ACTIVE_SIGNAL',distanceToEntryAbs:Number(distance.toPrecision(8)),distanceToEntryPct:Number(distancePct.toFixed(4)),watchMarketRead:{contextState,contextAligned:aligned,executionEvent:execEvent,extensionAtr:Number(Math.abs(Number(a.extensionAtr||0)).toFixed(3)),spreadBps:spread,turnover24h:Number(t.turnover24h||0),planType:preferLimit?'PULLBACK_LIMIT':'CONFIRMATION_STOP'},technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),tfTrend:[a.trend,b.trend,c.trend],tfMomentum:[a.momentum,b.momentum,c.momentum],spreadBps:spread,turnover24h:Number(t.turnover24h||0),recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`context ${contextState}`,`execution event ${execEvent?'present':'wait confirmation'}`,`entry ${entryModel}`,'SL ngoài invalidation structure + ATR/spread buffer','TP1/TP2/TP3 theo liquidity/structure rồi mới expansion','Watchlist reference only — không chiếm active slot, không tính performance']},'CRYPTO',style);
}
async function analyzeWatchIdealReference(t,style,env){
  try{const bundle=await watchStatsBundleV3221(t,style,env);if(!bundle.ok)return null;const ideal=buildWatchIdealReference(t,style,bundle.stats);if(!ideal)return null;ideal.watchDataMode=bundle.mode;ideal.watchDataAgeMs=bundle.ageMs;ideal.watchTimeframes=intervalMap[style].map((frame,i)=>({frame,provider:bundle.frames[i]?.provider||null,mode:bundle.frames[i]?.mode||'UNAVAILABLE',ageMs:Number(bundle.frames[i]?.ageMs||0)}));ideal.rationale=[...(ideal.rationale||[]),bundle.mode==='FRESH_CANDLES'?'Watch TF data fresh on all required frames':`Watch uses recent validated TF cache; max age ${Math.round(bundle.ageMs/60000)}m`];return ideal;}catch{return null;}
}
async function findWatchTickerMulti(symbol,primarySnap,env){
  let t=(primarySnap?.rows||[]).find(x=>canonical(x.symbol)===symbol);if(t&&primarySnap?.live!==false)return {ticker:t,snap:primarySnap};
  const primary=String(primarySnap?.provider||'').toUpperCase();for(const p of ['BYBIT','OKX','BINANCE']){if(p===primary)continue;const s=await cryptoSnapshotForProvider(env,p);t=(s.rows||[]).find(x=>canonical(x.symbol)===symbol);if(t&&s.live!==false)return {ticker:t,snap:s};}
  return {ticker:null,snap:primarySnap};
}

function v322MarketRead(t,style,stats,setup){
  const [a,b,c]=stats,side=String(setup?.side||'').toUpperCase(),dir=side==='LONG'||side==='BUY'?1:-1;
  const spread=Math.max(0,Number(t?.spreadBps||0)),turnover=Math.max(0,Number(t?.turnover24h||t?.turnover24hQuote||0)),move=Math.abs(Number(t?.change24hPct||0)),fund=t?.fundingRate==null?null:Math.abs(Number(t.fundingRate)),oi=t?.openInterestValue==null?null:Number(t.openInterestValue);
  const execEvent=dir>0?(a.sweepLow||a.bullDisplacement||a.emaReclaimUp||a.bosUp):(a.sweepHigh||a.bearDisplacement||a.emaReclaimDown||a.bosDown);
  const execMomentum=a.momentum!==-dir,midMomentum=b.momentum!==-dir,execSlope=dir>0?a.slope>=-.08:a.slope<=.08;
  const extension=Math.abs(Number(a.extensionAtr||0));
  let contextAligned=false,contextStrong=false,marketEntryReady=false,hardConflict=false,contextLabel='MIXED';
  if(style==='SWING'){
    contextAligned=b.trend===dir&&c.trend===dir;
    contextStrong=contextAligned&&(b.momentum===dir||c.momentum===dir)&&(dir>0?b.slope>=-.05:b.slope<=.05);
    hardConflict=b.trend===-dir||c.trend===-dir||!contextAligned;
    marketEntryReady=contextStrong&&execMomentum&&midMomentum&&execSlope&&execEvent&&extension<=.18&&spread<=12&&turnover>=35_000_000&&move<=35;
    contextLabel=contextStrong?'H4_D1_ALIGNED':contextAligned?'H4_D1_ALIGNED_SOFT':'H4_D1_CONFLICT';
  }else{
    const noOpposition=b.trend!==-dir&&c.trend!==-dir,oneAligned=b.trend===dir||c.trend===dir;
    contextAligned=noOpposition&&oneAligned;contextStrong=contextAligned&&b.trend===dir&&(c.trend===dir||c.trend===0);
    hardConflict=b.trend===-dir||c.trend===-dir;
    marketEntryReady=contextAligned&&execMomentum&&midMomentum&&execSlope&&execEvent&&extension<=.22&&spread<=7&&turnover>=50_000_000&&move<=25;
    contextLabel=contextStrong?'M15_H1_ALIGNED':contextAligned?'M15_H1_SUPPORTIVE':'M15_H1_CONFLICT';
  }
  const liquidityOk=style==='SCALP'?(turnover>=20_000_000&&spread<=10):(turnover>=15_000_000&&spread<=18),fundingOk=fund==null||!Number.isFinite(fund)||fund<.02,oiOk=oi==null||!Number.isFinite(oi)||oi<=0||oi>=250_000;
  if(!liquidityOk||!fundingOk||!oiOk)hardConflict=true;
  const state=marketEntryReady?'CONFIRMED':hardConflict?'CONFLICT':'PENDING_PREFERRED';
  const reasons=[`context ${contextLabel}`,`execution ${execEvent?'STRUCTURE_EVENT':'NO_FRESH_STRUCTURE_EVENT'}`,`momentum ${execMomentum&&midMomentum?'CLEAN':'MIXED'}`,`extension ${extension.toFixed(2)} ATR`,`spread ${spread.toFixed(2)} bps`,`turnover ${Math.round(turnover)}`];
  return {version:'V322_STYLE_READ',state,contextLabel,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:execMomentum&&midMomentum,extensionAtr:Number(extension.toFixed(3)),liquidityOk,fundingOk,openInterestOk:oiOk,marketEntryReady,hardConflict,reasons};
}
async function analyzeCryptoCandidate(t,style){
  try{
    const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;
    let setup=buildCryptoSetup(t,style,stats);if(!setup)setup=buildStableReferenceSetup(t,style,stats);if(!setup)return null;
    const read=v322MarketRead(t,style,stats,setup),dir=String(setup.side||'').toUpperCase()==='LONG'?1:-1,contextInterval=intervalMap[style][1],primary=String(t.exchange||'').toUpperCase();
    setup.marketReadV322=read;setup.executionRead=read.state;setup.qualityEvidence={...(setup.qualityEvidence||{}),v322ContextAligned:read.contextAligned,v322ExecutionEvent:read.executionEvent,v322ExecutionMomentum:read.executionMomentum,v322LiquidityOk:read.liquidityOk,v322MarketEntryReady:read.marketEntryReady};
    setup.technicalAtIssue={...(setup.technicalAtIssue||{}),v322Context:read.contextLabel,v322Read:read.state};setup.rationale=[...(setup.rationale||[]),...read.reasons.map(x=>'V3.22 '+x)];
    const probes=[['BYBIT',bybitCandles],['OKX',okxCandles],['BINANCE',binanceCandles]].filter(x=>x[0]!==primary);let checked=0,confirmed=0,opposed=0,details=[];
    for(const [provider,fn] of probes){
      try{const sec=tfStats(await fn(t.symbol,contextInterval));if(!sec)continue;checked++;const opposing=sec.trend===-dir||sec.momentum===-dir,supporting=sec.trend===dir||sec.momentum===dir;if(opposing)opposed++;else if(supporting)confirmed++;details.push({provider,trend:sec.trend,momentum:sec.momentum,confirmed:!opposing&&supporting});}catch{}
    }
    const crossState=opposed>0?'OPPOSED':confirmed>0?'CONFIRMED':checked>0?'NEUTRAL':'UNAVAILABLE';
    setup.crossProviderConfirmation=crossState==='CONFIRMED';setup.crossProviderConsensus={state:crossState,checked,confirmed,opposed,details};setup.qualityEvidence.secondaryProviderConfirmed=crossState==='CONFIRMED';setup.technicalAtIssue.crossProviderConsensus=crossState;setup.rationale.push(`secondary venue consensus ${crossState} (${confirmed} confirm / ${opposed} oppose / ${checked} checked)`);
    if(opposed>0&&String(setup.orderType||'').toUpperCase()==='MARKET')return null;
    if(read.hardConflict&&String(setup.orderType||'').toUpperCase()==='MARKET')return null;
    return setup;
  }catch{return null;}
}

function v31Prefix(market,style){return `v31:signal:${market}:${style}:`;}
function activePointer(market,style,symbol){return `v31:active:${market}:${style}:${symbol}`;}
function activeAnyPointer(market,symbol){return `v31:active:any:${market}:${symbol}`;}
async function getV31Signals(env,market,style){
  if(!env?.SIGNALS_KV)return[];const prefix=v31Prefix(market,style),listing=await env.SIGNALS_KV.list({prefix,limit:1000}),out=[];for(let i=0;i<listing.keys.length;i+=50){const raws=await Promise.all(listing.keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));for(const raw of raws){if(!raw)continue;try{out.push(JSON.parse(raw))}catch{}}}out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));return out;
}
async function writeV31Signal(env,s){
  const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});
  const active=s.status==='PENDING'||s.status==='OPEN',styleKey=activePointer(s.market,s.style,s.symbol),anyKey=activeAnyPointer(s.market,s.symbol);
  if(active){await env.SIGNALS_KV.put(styleKey,s.id,{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put(anyKey,s.id,{expirationTtl:SIGNAL_TTL});}
  else{await env.SIGNALS_KV.delete(styleKey);const anyId=await env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===s.id)await env.SIGNALS_KV.delete(anyKey);}
  await syncRealtimeSignal(env,s,key);
}
async function trackV31Signals(env,market,style,priceMap){
  return [];
}
const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:15,maxActivePerMarket:15,maxActivePerStyle:10,maxNewPerScan:10,minActivePerStyle:5,targetActivePerStyle:10,targetActiveByStyle:{SCALP:10,SWING:5},maxActiveByStyle:{SCALP:10,SWING:5},maxNewPerScanByStyle:{SCALP:10,SWING:5},maxActivePerRiskCluster:5,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:20,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STABLE_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES',forexDisabled:true});
function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?5:10;}
function styleMax(style){return styleTarget(style);}
function styleNewLimit(style){return styleTarget(style);}
const STABLE_BASE_EXCLUDE=new Set(['USDC','USDE','FDUSD','DAI','TUSD','USDP','BUSD','EUR','EURC','PYUSD']);
function stableUniverseRule(style){return String(style||'').toUpperCase()==='SWING'?{minTurnover:35_000_000,maxSpread:12,maxMove:30,minOi:3_000_000,maxFunding:.005}:{minTurnover:50_000_000,maxSpread:6,maxMove:22,minOi:5_000_000,maxFunding:.003};}
function stableUniverseEligible(t,style){
  if(!t||!(Number(t.lastPrice)>0))return false;const symbol=canonical(t.symbol),base=symbol.replace(/USDT$/,''),r=stableUniverseRule(style),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Math.abs(Number(t.change24hPct||0)),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  if(!symbol.endsWith('USDT')||STABLE_BASE_EXCLUDE.has(base))return false;if(!(turn>=r.minTurnover)||!(spread>=0&&spread<=r.maxSpread)||move>r.maxMove)return false;if(oi!=null&&Number.isFinite(oi)&&oi>0&&oi<r.minOi)return false;if(fund!=null&&Number.isFinite(fund)&&fund>r.maxFunding)return false;return true;
}
function stableUniverseCompare(a,b){const at=Number(a.turnover24h||0),bt=Number(b.turnover24h||0);if(at!==bt)return bt-at;const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;return Math.abs(Number(a.change24hPct||0))-Math.abs(Number(b.change24hPct||0));}
const STABLE100_SIZE=100;
const CRYPTO_DATA_SCHEMA='CRYPTO_MARKET_ROW_V3';
const CRYPTO_NORMALIZATION_VERSION='2026-09-STANDARDIZED-LIQUIDITY-V3';
const STABLE100_CACHE_KEY='v321:crypto:stable100:schema3';
const STABLE100_RANKING='QUALITY_TIER_THEN_QUOTE_TURNOVER_OI_SPREAD_MOVE';
const NON_CRYPTO_BASE_EXCLUDE=new Set([
  'AAPL','NVDA','TSLA','INTC','MU','MSTR','SOXL','SPCX','SKHYNIX','SKHY','SNDK','GOOGL','GOOG','META','AMZN','MSFT','AMD','NFLX','COIN','HOOD','PLTR','AVGO','TSM','ARM','ORCL','QCOM','SMCI','MARA','RIOT','QQQ','SPY','DIA','IWM','XAU','XAG','PAXG','XAUT','GOLD','SILVER','WTI','BRENT','USOIL','UKOIL'
]);
function cryptoOnlyUniverseRow(t){
  const symbol=canonical(t?.symbol||''),base=symbol.replace(/USDT$/,'');
  return !!symbol&&symbol.endsWith('USDT')&&!STABLE_BASE_EXCLUDE.has(base)&&!NON_CRYPTO_BASE_EXCLUDE.has(base)&&!/^(AAPL|NVDA|TSLA|MSFT|AMZN|META|GOOG|INTC|AMD|MSTR|XAU|XAG)/.test(base);
}
function normalizeStable100Row(t){
  if(!t||!(Number(t.lastPrice)>0)||!cryptoOnlyUniverseRow(t))return null;
  const symbol=canonical(t.symbol),venue=String(t.exchange||t.provider||'UNKNOWN').toUpperCase(),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Number(t.change24hPct||0),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Number(t.fundingRate);
  if(!['BYBIT','OKX','BINANCE'].includes(venue)||!(turn>0)||!(spread>=0)||!Number.isFinite(move))return null;
  return {...t,symbol,canonicalSymbol:symbol,assetClass:'CRYPTO',schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,venue,exchange:venue,provider:venue,source:String(t.source||venue),turnover24hQuote:turn,turnover24h:turn,spreadBps:spread,change24hPct:move,openInterestValue:oi,fundingRate:fund,sourceReceivedAt:t.receivedAt||null};
}
function stable100QualityTier(t){
  const turn=Number(t?.turnover24hQuote||0),spread=Number(t?.spreadBps??999),move=Math.abs(Number(t?.change24hPct||0)),oi=t?.openInterestValue==null?null:Number(t.openInterestValue),fund=t?.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  const oiOk=(floor)=>oi==null||!Number.isFinite(oi)||oi<=0||oi>=floor, fundOk=(cap)=>fund==null||!Number.isFinite(fund)||fund<=cap;
  if(turn>=20_000_000&&spread<=15&&move<=35&&oiOk(1_000_000)&&fundOk(.008))return 'A';
  if(turn>=5_000_000&&spread<=20&&move<=45&&oiOk(500_000)&&fundOk(.012))return 'B';
  if(turn>=250_000&&spread<=50&&move<=80&&oiOk(50_000)&&fundOk(.050))return 'C';
  return null;
}
function stable100Compare(a,b){
  const q={A:0,B:1,C:2},qa=q[a.qualityTier]??9,qb=q[b.qualityTier]??9;if(qa!==qb)return qa-qb;
  const at=Number(a.turnover24hQuote||0),bt=Number(b.turnover24hQuote||0);if(at!==bt)return bt-at;
  const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;
  const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;
  const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;
  return String(a.symbol||'').localeCompare(String(b.symbol||''));
}
function bestVenueRow(rows){return [...rows].sort((a,b)=>{const at=Number(a.turnover24hQuote||0),bt=Number(b.turnover24hQuote||0);if(at!==bt)return bt-at;const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;return Number(b.openInterestValue||0)-Number(a.openInterestValue||0);})[0];}
function buildStable100Universe(rows){
  const grouped=new Map();
  for(const raw of rows||[]){const n=normalizeStable100Row(raw);if(!n)continue;const tier=stable100QualityTier(n);if(!tier)continue;n.qualityTier=tier;const arr=grouped.get(n.symbol)||[];arr.push(n);grouped.set(n.symbol,arr);}
  const picked=[];for(const arr of grouped.values()){const best=bestVenueRow(arr),venues=[...new Set(arr.map(x=>x.venue))];picked.push({...best,venueCandidates:venues,venueCount:venues.length});}
  return picked.sort(stable100Compare).slice(0,STABLE100_SIZE).map((x,i)=>({...x,rank:i+1}));
}
async function loadStable100CompositeSnapshot(env){
  const providers=['BYBIT','OKX','BINANCE'],snaps=await Promise.all(providers.map(p=>cryptoSnapshotForProvider(env,p))),live=snaps.filter(s=>s?.live!==false&&Array.isArray(s.rows)&&s.rows.length>0),rows=[];
  for(const s of live)for(const r of s.rows)rows.push({...r,exchange:String(r.exchange||s.provider).toUpperCase(),provider:String(s.provider).toUpperCase(),receivedAt:s.receivedAt});
  if(!rows.length)throw new Error('ALL_STABLE100_PROVIDERS_UNAVAILABLE');
  const receivedAt=live.map(s=>s.receivedAt).filter(Boolean).sort().pop()||nowIso();
  return {provider:'MULTI_VENUE_COMPOSITE',providers:live.map(s=>String(s.provider).toUpperCase()),receivedAt,rows};
}
function stable100PayloadValid(p){
  if(!p||p.version!==V3_VERSION||p.schemaVersion!==CRYPTO_DATA_SCHEMA||p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||p.target!==STABLE100_SIZE||p.count!==STABLE100_SIZE||p.complete!==true)return false;
  if(!Array.isArray(p.rows)||!Array.isArray(p.symbols)||p.rows.length!==STABLE100_SIZE||p.symbols.length!==STABLE100_SIZE||new Set(p.symbols).size!==STABLE100_SIZE)return false;
  if(p.rows.some((r,i)=>r.assetClass!=='CRYPTO'||r.schemaVersion!==CRYPTO_DATA_SCHEMA||r.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||canonical(r.symbol)!==r.canonicalSymbol||!cryptoOnlyUniverseRow(r)||r.rank!==i+1||!['A','B','C'].includes(r.qualityTier)))return false;
  const age=Date.now()-Date.parse(p.refreshedAt||0);return Number.isFinite(age)&&age>=0&&age<=180000;
}
async function readStable100(env){
  if(!env?.SIGNALS_KV)return null;const raw=await env.SIGNALS_KV.get(STABLE100_CACHE_KEY);if(!raw)return null;try{const p=JSON.parse(raw);return stable100PayloadValid(p)?p:null;}catch{return null;}
}
async function persistStable100(env,snap,rows){
  const cached=await readStable100(env),cacheAge=cached?Date.now()-Date.parse(cached.refreshedAt||0):Infinity;if(cached&&cacheAge<45000)return cached.rows;
  let composite=null;try{composite=await loadStable100CompositeSnapshot(env);}catch{}
  const sourceRows=composite?.rows?.length?composite.rows:(rows||[]),universe=buildStable100Universe(sourceRows),providers=composite?.providers||[snap?.provider].filter(Boolean),at=nowIso();
  if(universe.length<STABLE100_SIZE){if(cached&&cacheAge<=180000)return cached.rows;return universe;}
  const payload={version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,assetClass:'CRYPTO',provider:composite?.provider||snap?.provider||null,providers,receivedAt:composite?.receivedAt||snap?.receivedAt||at,refreshedAt:at,target:STABLE100_SIZE,count:STABLE100_SIZE,complete:true,ranking:STABLE100_RANKING,turnoverNormalization:'BYBIT_QUOTE_TURNOVER|OKX_BASE_VOL_X_LAST|BINANCE_QUOTE_VOLUME',symbols:universe.map(x=>x.symbol),rows:universe};
  if(env?.SIGNALS_KV)await env.SIGNALS_KV.put(STABLE100_CACHE_KEY,JSON.stringify(payload),{expirationTtl:240});
  return universe;
}
function stable100Integrity(p){
  const problems=[];if(!p)problems.push('NO_VALID_STANDARDIZED_STABLE100');else{if(p.version!==V3_VERSION)problems.push('VERSION_MISMATCH');if(p.schemaVersion!==CRYPTO_DATA_SCHEMA)problems.push('SCHEMA_MISMATCH');if(p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION)problems.push('NORMALIZATION_MISMATCH');if(p.count!==STABLE100_SIZE)problems.push('COUNT_NOT_100');if((p.rows||[]).some(r=>!cryptoOnlyUniverseRow(r)))problems.push('NON_CRYPTO_ROW');}
  return {ok:problems.length===0,problems};
}
function rotatingStableCandidates(rows,style,limit){
  const sorted=[...(rows||[])].sort(stableUniverseCompare),n=sorted.length;if(n<=limit)return sorted;
  const coreCount=Math.min(style==='SWING'?14:18,Math.max(8,Math.floor(limit*.35))),core=sorted.slice(0,coreCount),rest=sorted.slice(coreCount);
  const wanted=Math.max(0,limit-core.length),epoch=Math.floor(Date.now()/60000),offset=rest.length?((epoch*(style==='SWING'?17:23))%rest.length):0,rot=[];
  for(let i=0;i<Math.min(wanted,rest.length);i++)rot.push(rest[(offset+i)%rest.length]);
  return [...core,...rot];
}
function signalLiquidityFacts(s){const t=s?.technicalAtIssue||{};return {turnover:Number(t.turnover24h||0),spread:Number(t.spreadBps??999),move:Math.abs(Number(t.change24hPct||0)),oi:t.openInterestValue==null?null:Number(t.openInterestValue),funding:t.fundingRate==null?null:Math.abs(Number(t.fundingRate))};}

function signOf(v){const n=Number(v);return n>0?1:n<0?-1:0;}
function assessEntrySetup(raw){
  const s=raw||{},dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{};
  const style=String(s.style||'SCALP').toUpperCase(),order=String(s.orderType||'').toUpperCase(),regime=String(s.marketRegime||''),expectedStyle=style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE',trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(signOf):[];
  const targetPath=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3,contextAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir);
  const ext=Math.abs(Number(tech.extensionAtr||0)),risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999,maxMarketExt=style==='SWING'?.16:.22;
  const marketLocation=order==='MARKET'?(regime.includes('LIQUIDITY')||ext<=maxMarketExt):order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false,pendingReachable=order==='MARKET'||triggerDistance<=(order==='LIMIT'?(style==='SWING'?.90:.75):(style==='SWING'?.50:.45));
  const spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),rsi=Number(tech.rsi||50),rule=stableUniverseRule(style),move=Math.abs(Number(tech.change24hPct||0)),oi=tech.openInterestValue==null?null:Number(tech.openInterestValue),funding=tech.fundingRate==null?null:Math.abs(Number(tech.fundingRate)),spreadQuality=spread>=0&&spread<=rule.maxSpread,liquidityQuality=turnover>=rule.minTurnover,dailyMoveSanity=move<=rule.maxMove,openInterestSanity=oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingSanity=funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding,momentumSanity=dir>0?rsi<=70:rsi>=30;
  const confirmationStory=regime.includes('SWEEP')||regime.includes('RECLAIM')||regime.includes('CONFIRMATION'),displacementOrLiquidity=Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),structureEvidence=Boolean(ev.structureReclaimed)||Boolean(ev.liquidityEvent)||regime.includes('BREAKOUT');
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===expectedStyle,contextAligned,confirmationStory,displacementOrLiquidity,structureEvidence,secondaryProvider:s.crossProviderConfirmation===true,entryLocation:src>0&&marketLocation,pendingReachable,invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadQuality,liquidityQuality,dailyMoveSanity,openInterestSanity,fundingSanity,momentumSanity,executionConditions:String(s.executionCaution||'NORMAL').toUpperCase()!=='WIDE',liveSource:src>0};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;s.qualityEvidence={...ev,contextAligned,secondaryProviderConfirmed:s.crossProviderConfirmation===true,entryNotChasing:src>0&&marketLocation,invalidationStructural:checks.invalidation,targetPathClear:targetPath};
  return {verdict:pass?'PASS':'NO_TRADE',method:'V319_CRYPTO_STABLE_LIQUIDITY_STRUCTURE_CHECKS_NO_NUMERIC_SCORE',checks,failed,executionFacts:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,change24hPct:move,openInterestValue:oi,fundingAbs:funding,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};
}
function assessCoverageSetup(raw){
  const s=raw||{},dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{};
  const style=String(s.style||'SCALP').toUpperCase(),order=String(s.orderType||'').toUpperCase(),risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999;
  const targetPath=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3;
  const entryLocation=order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false;
  const spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),rule=stableUniverseRule(style),move=Math.abs(Number(tech.change24hPct||0)),oi=tech.openInterestValue==null?null:Number(tech.openInterestValue),funding=tech.fundingRate==null?null:Math.abs(Number(tech.fundingRate));
  const reference=Boolean(s.referenceFallback),checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(reference?(style==='SWING'?2.10:1.75):(style==='SWING'?1.80:1.40)),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=rule.maxSpread,liquidityHard:turnover>=rule.minTurnover,dailyMoveHard:move<=rule.maxMove,openInterestHard:oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingHard:funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'V319_STABLE_LIQUIDITY_CONDITIONAL_HARD_SAFETY',tier:'BEST_AVAILABLE_CONDITIONAL',checks,failed,executionFacts:{triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,change24hPct:move,openInterestValue:oi,fundingAbs:funding,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};
}
function toStandbyCandidate(raw){
  if(!raw)return null;const s={...raw,technicalAtIssue:{...(raw.technicalAtIssue||{})},qualityEvidence:{...(raw.qualityEvidence||{})}},style=String(s.style||'SCALP').toUpperCase(),dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,src=Number(s.sourcePrice||s.lastPrice||0);if(!(src>0))return null;
  let entry=Number(s.entry||src),sl=Number(s.sl||0),risk=Math.abs(entry-sl),order=String(s.orderType||'').toUpperCase();if(!(risk>0))return null;
  if(!['LIMIT','STOP'].includes(order)){
    const spreadPx=Math.max(0,src*Number(s.technicalAtIssue?.spreadBps||0)/10000),offset=Math.max(risk*(style==='SWING'?.16:.11),spreadPx*2.5);
    order='STOP';entry=src+dir*offset;
    if((dir>0&&!(sl<entry))||(dir<0&&!(sl>entry)))sl=entry-dir*risk;
    risk=Math.abs(entry-sl);if(!(risk>0))return null;
    const minRR=style==='SWING'?2.85:2.20;
    s.tp1=entry+dir*risk*.92;s.tp2=entry+dir*risk*1.58;s.tp3=entry+dir*risk*minRR;s.tp=s.tp3;s.targetRR=minRR;s.entryModel='HOT_SPARE_CONFIRMATION_STOP';
  }
  s.orderType=order;s.entry=entry;s.sl=sl;s.status='PENDING';s.entryState='PENDING_ENTRY';s.lifecycle='PENDING_ENTRY';s.coverageFallback=true;s.coverageTier='HOT_SPARE_CONDITIONAL';s.standbySource='DERIVED_FROM_CURRENT_ANALYSIS';s.qualityEvidence.coverageConditional=true;
  if(!Number.isFinite(Number(s.invalidationLevel))||Number(s.invalidationLevel)<=0)s.invalidationLevel=sl;
  const a=assessCoverageSetup(s);if(a.verdict!=='PASS')return null;s.entryAssessment=a;return s;
}
function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('RECLAIM')?1:r.includes('BREAKOUT')?2:r.includes('CONTINUATION')?3:4,read=String(s.executionRead||s.marketReadV322?.state||''),readRank=read==='CONFIRMED'?0:read==='PENDING_PREFERRED'?1:2,cross=String(s.crossProviderConsensus?.state||''),crossRank=cross==='CONFIRMED'?0:cross==='NEUTRAL'?1:cross==='UNAVAILABLE'?2:3,spread=Number(s?.technicalAtIssue?.spreadBps||999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),turnover=Number(s?.technicalAtIssue?.turnover24h||0);
  return [readRank,crossRank,family,spread,ext,-turnover];
}
function compareSetupPriority(a,b){const x=setupPriority(a),y=setupPriority(b);for(let i=0;i<x.length;i++){if(x[i]!==y[i])return x[i]-y[i];}return String(a.symbol).localeCompare(String(b.symbol));}
async function getActiveBook(env){
  const out=[];for(const style of ['SCALP','SWING']){const rows=await getV31Signals(env,'CRYPTO',style);for(const s of rows)if((s.status==='PENDING'||s.status==='OPEN')&&String(s.engineVersion||'')===V3_VERSION)out.push(s);}return out;
}
async function retireLegacyActiveSignals(env,market,style){
  if(!env?.SIGNALS_KV)return[];const all=await getV31Signals(env,market,style),events=[],at=nowIso();
  for(const s of all){
    if((s.status!=='PENDING'&&s.status!=='OPEN')||String(s.engineVersion||'')===V3_VERSION)continue;
    s.status='CANCELLED';s.entryState='CANCELLED';s.lifecycle='REPLACED_BY_V314_STABILITY_ENGINE';s.outcome='CONTEXT_REFRESH';s.cancelledAt=at;s.resolution='V314_STABILITY_RESET';s.lastCheckedAt=at;s.resultR=null;s.brokerAction='NONE_SIGNAL_FEED_ONLY';
    await writeV31Signal(env,s);events.push({type:'CANCELLED',id:s.id,symbol:s.symbol,reason:s.lifecycle});
  }
  return events;
}
async function retireAllLegacyActiveSignals(env){
  const events=[];for(const m of ['FOREX','CRYPTO'])for(const s of ['SCALP','SWING'])events.push(...await retireLegacyActiveSignals(env,m,s));return events;
}
async function reserveRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub)return {accepted:false,reason:'NO_ATOMIC_RESERVATION_BUS'};
  try{const r=await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});if(!r.ok)return {accepted:false,reason:`RESERVATION_HTTP_${r.status}`};return await r.json();}catch(e){return {accepted:false,reason:`RESERVATION_ERROR:${String(e?.message||e)}`};}
}
async function releaseRealtimeSignal(env,id){const stub=mt5LiveStub(env);if(!stub)return;try{await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id})});}catch{}}
async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(x=>{const strict=assessEntrySetup(x);if(strict.verdict==='PASS')return {...x,coverageTier:'STRICT_CONFIRMED',entryAssessment:strict};const fallback=Boolean(x.coverageFallback)?assessCoverageSetup(x):strict;return {...x,entryAssessment:fallback};}).filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const activeTotal=()=>book.length,marketCount=()=>book.filter(x=>x.market===market).length,styleCount=()=>book.filter(x=>x.style===style).length;
  for(const rawSetup of candidates){
    if(made.length>=styleNewLimit(style)||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||marketCount()>=PORTFOLIO_POLICY.maxActivePerMarket||styleCount()>=styleMax(style))break;
    const setup=stampMarketJudgment({...rawSetup},market,style);if(!validSignalStructure(setup))continue;
    if(book.some(x=>x.market===market&&x.symbol===setup.symbol))continue;
    const issuedAt=nowIso(),id=`V319-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,portfolioPolicy:PORTFOLIO_POLICY,reservationMode:'DURABLE_OBJECT_ATOMIC'},market,style),kvKey=v31Prefix(market,style)+id;
    const reservation=await reserveRealtimeSignal(env,s,kvKey);if(!reservation?.accepted)continue;
    s.portfolioReservation={accepted:true,mode:'DURABLE_OBJECT_ATOMIC',activeTotal:Number(reservation.activeTotal||0)};
    try{await writeV31Signal(env,s);}catch(e){await releaseRealtimeSignal(env,id);throw e;}
    made.push(s);book.push(s);
  }
  return made;
}
async function analyzeCryptoBatch(rows,style,concurrency=6){
  const source=Array.isArray(rows)?rows.filter(Boolean):[];
  if(!source.length)return[];
  const out=new Array(source.length).fill(null);let cursor=0;
  const workers=Math.max(1,Math.min(Number(concurrency)||6,source.length,8));
  async function run(){
    while(true){
      const i=cursor++;if(i>=source.length)return;
      try{out[i]=await analyzeCryptoCandidate(source[i],style);}catch(e){out[i]=null;}
    }
  }
  await Promise.all(Array.from({length:workers},()=>run()));
  return out.filter(Boolean);
}

async function scanCrypto(env,style){
  style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const trackerEvents=await retireAllLegacyActiveSignals(env);
  const snap=await loadCryptoSnapshot(env);if(snap.live===false)return {ok:true,version:V3_VERSION,market:'CRYPTO',style,status:'NO_FRESH_CRYPTO_SNAPSHOT',created:0,provider:snap.provider,live:false,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
  const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);
  const liquid=stable100.filter(x=>stableUniverseEligible(x,style));
  const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(72,liquid.length):Math.min(52,liquid.length)):(styleUnderfilled?Math.min(58,liquid.length):Math.min(42,liquid.length));
  const ranked=rotatingStableCandidates(liquid,style,rankedLimit);
  const rawAnalyses=await analyzeCryptoBatch(ranked,style,6),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority),assessmentFailures=assessed.filter(x=>x.entryAssessment.verdict!=='PASS').slice(0,12).map(x=>({symbol:x.symbol,coverageFallback:Boolean(x.coverageFallback),orderType:x.orderType,failed:x.entryAssessment.failed||[]}));
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<styleTarget(style))promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,stable100Symbols:stable100.map(x=>x.symbol),liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,assessmentFailures,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),standby,promotion,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.19 stable-universe 15-slot engine: target 10 SCALP + 5 SWING. Full live universe is refreshed every maintenance cycle; weak-liquidity/high-spread/fragile candidates are excluded before deep analysis; strict signals are preferred and fresh conditional LIMIT/STOP reserves refill depleted slots.'};
}

async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'REFILL_TO_TARGET':'STABLE100_ROTATION_REFRESH'}`);
    await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<target){await promoteCryptoStandby(env,style,'CONTINUOUS_STABLE100_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'STABLE100_CONTINUOUS',stableUniverse:await readStable100(env),attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}

async function exnessQuoteMap(env){
  const snap=await readMt5Realtime(env),p=snap?.quotes||null;if(!p)return {map:new Map(),state:'OFFLINE',ageMs:null};
  const ageMs=Math.max(0,Date.now()-Date.parse(p.receivedAt||'')),state=ageMs<=1800?'LIVE':ageMs<=4000?'DELAYED':'STALE',map=new Map((p.quotes||[]).map(q=>[canonical(q.symbol),Number(q.mid)]));return {map,state,ageMs};
}
async function tvForexFrames(style){
  const f=style==='SCALP'?['5','15','60']:['60','240','1D'];
  const cols=['name','close','change'];for(const x of f)cols.push(`Recommend.All|${x}`);for(const x of f.slice(0,2))cols.push(`RSI|${x}`);for(const x of f.slice(0,2)){cols.push(`EMA20|${x}`);cols.push(`EMA50|${x}`);cols.push(`ATR|${x}`);cols.push(`open|${x}`);cols.push(`high|${x}`);cols.push(`low|${x}`);}
  const body={symbols:{tickers:FOREX.map(s=>`OANDA:${s}`),query:{types:[]}},columns:cols};
  const raw=await fetchJson('https://scanner.tradingview.com/forex/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},9000);if(!Array.isArray(raw?.data))throw new Error('TV_FOREX_BAD_JSON');
  return raw.data.map(r=>{const d=r.d||[];let i=0;const symbol=canonical(d[i++]||String(r.s||'').split(':').pop()),close=num(d[i++]),change=num(d[i++]),recA=num(d[i++]),recB=num(d[i++]),recC=num(d[i++]),rsiA=num(d[i++]),rsiB=num(d[i++]);const a={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])},b={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])};return {symbol,close,change,recA,recB,recC,rsiA,rsiB,ema20A:a.ema20,ema50A:a.ema50,atrA:a.atr,openA:a.open,highA:a.high,lowA:a.low,ema20B:b.ema20,ema50B:b.ema50,atrB:b.atr,openB:b.open,highB:b.high,lowB:b.low,frames:f};});
}
function forexJudgmentSetup(r,px,style){
  if(!(px>0&&r.atrA>0&&r.atrB>0&&r.ema20A>0&&r.ema50A>0&&r.ema20B>0&&r.ema50B>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP;
  const emaA=r.ema20A>r.ema50A?1:r.ema20A<r.ema50A?-1:0,emaB=r.ema20B>r.ema50B?1:r.ema20B<r.ema50B?-1:0;
  const recA=r.recA>0?1:r.recA<0?-1:0,recB=r.recB>0?1:r.recB<0?-1:0,recC=r.recC>0?1:r.recC<0?-1:0;
  const atr=Math.max(r.atrA,r.atrB*(style==='SCALP'?.34:.50)),ext=(px-r.ema20A)/atr;
  const highA=r.highA>0?r.highA:px+.55*atr,lowA=r.lowA>0?r.lowA:px-.55*atr,openA=r.openA>0?r.openA:px;
  const highB=r.highB>0?r.highB:r.ema20B+r.atrB*.8,lowB=r.lowB>0?r.lowB:r.ema20B-r.atrB*.8;
  const body=Math.max(Math.abs(px-openA),atr*.04),lowerWick=Math.max(0,Math.min(px,openA)-lowA),upperWick=Math.max(0,highA-Math.max(px,openA));
  const bullReject=px>=openA&&lowerWick>Math.max(body*.95,atr*.18),bearReject=px<=openA&&upperWick>Math.max(body*.95,atr*.18);
  const range=Math.max(highA-lowA,atr*.55),pos=Math.max(0,Math.min(1,(px-lowA)/range));
  const contextDir=emaB!==0&&recB===emaB&&(recC===0||recC===emaB)?emaB:0;
  let dir=0,regime='NO_TRADE',story='';
  if(style==='SWING'){
    const htfDir=contextDir;
    if(bullReject&&htfDir===1&&emaA>=0){dir=1;regime='HTF_LIQUIDITY_REJECTION';story='H4/D1 bullish context + H1 downside rejection/reclaim';}
    else if(bearReject&&htfDir===-1&&emaA<=0){dir=-1;regime='HTF_LIQUIDITY_REJECTION';story='H4/D1 bearish context + H1 upside rejection/reclaim';}
    else if(htfDir!==0&&emaA===htfDir&&recA===htfDir){dir=htfDir;regime=Math.abs(ext)>.32?'HTF_TREND_PULLBACK':'HTF_TREND_REJOIN';story='H4/D1 directional context aligned with H1 EMA structure and recommendation';}
    else return null;
  }else{
    if(bullReject&&contextDir===1){dir=1;regime='LIQUIDITY_REJECTION';story='5m rejection/reclaim aligned with 15m/1h bullish context';}
    else if(bearReject&&contextDir===-1){dir=-1;regime='LIQUIDITY_REJECTION';story='5m rejection/reclaim aligned with 15m/1h bearish context';}
    else if(contextDir!==0&&emaA===contextDir&&recA===contextDir){dir=contextDir;regime=Math.abs(ext)>.34?'TREND_PULLBACK':'TREND_CONTINUATION';story='5m EMA and recommendation aligned with 15m/1h context';}
    else return null;
  }

  const strongImpulse=Math.abs(Number(r.recA||0))>.48&&Math.abs(Number(r.recB||0))>.28&&body>atr*.22;
  const atBreakEdge=dir>0?pos>.72:pos<.28,entryBuffer=atr*(style==='SCALP'?.05:.10);
  let orderType='MARKET',entry=px,entryModel='MARKET_AFTER_CLEAN_STRUCTURE_CONFIRMATION';
  if(strongImpulse&&atBreakEdge&&regime!=='LIQUIDITY_REJECTION'&&regime!=='HTF_LIQUIDITY_REJECTION'){
    orderType='STOP';entry=dir>0?highA+entryBuffer:lowA-entryBuffer;regime=style==='SCALP'?'BREAKOUT_CONFIRMATION':'HTF_BREAKOUT_CONFIRMATION';entryModel='BREAKOUT_TRIGGER_OUTSIDE_CURRENT_STRUCTURE';story+=' + execution waits for structure break';
  }else if(!regime.includes('LIQUIDITY')&&(style==='SWING'||Math.abs(ext)>.30||(dir>0?pos>.68:pos<.32)||regime.includes('PULLBACK'))){
    const raw=dir>0?Math.max(r.ema20A,lowA+.34*atr):Math.min(r.ema20A,highA-.34*atr);
    if((dir>0&&raw<px-entryBuffer*.25)||(dir<0&&raw>px+entryBuffer*.25)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_VALIDATED_EMA_STRUCTURE';}
    else if(style==='SWING'){return null;}
  }else if(regime.includes('LIQUIDITY'))entryModel='REJECTION_RECLAIM_MARKET_ENTRY';

  const stopBuffer=atr*(style==='SCALP'?.17:.30);let anchor;
  if(dir>0){anchor=Math.min(lowA,r.ema50A-.06*atr);if(style==='SWING')anchor=Math.min(anchor,lowB,r.ema50B-.10*r.atrB);}
  else{anchor=Math.max(highA,r.ema50A+.06*atr);if(style==='SWING')anchor=Math.max(anchor,highB,r.ema50B+.10*r.atrB);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.62:1.05);if(!(risk>=minRisk)){risk=minRisk;sl=entry-dir*risk;}
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;
  if(dir>0){tp1=above([highA],entry+risk*.90);tp2=above([highB],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=Math.max(tp2+risk*.38,entry+risk*(style==='SCALP'?2.15:3.00));}
  else{tp1=below([lowA],entry-risk*.90);tp2=below([lowB],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=Math.min(tp2-risk*.38,entry-risk*(style==='SCALP'?2.15:3.00));}
  const rr=Math.abs(tp3-entry)/risk,judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • CLEAN STORY`;
  return stampMarketJudgment({market:'FOREX',style,symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp1,tp2,tp3,tp:tp3,targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',marketRegime:regime,marketStory:story,judgment,entryModel,slModel:'VALIDATED_LIQUIDITY_STRUCTURE_INVALIDATION_PLUS_VOLATILITY_BUFFER',tpModel:'LOCAL_HTF_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:anchor,styleExecutionModel:profile.name,executionFrames:profile.frames,technicalAtIssue:{frames:r.frames,recommend:[r.recA,r.recB,r.recC],rsi:[r.rsiA,r.rsiB],atr:[r.atrA,r.atrB],ema20:[r.ema20A,r.ema20B],ema50:[r.ema50A,r.ema50B],extensionAtr:Number(ext.toFixed(2)),localStructure:[lowA,highA],htfStructure:[lowB,highB],bullReject,bearReject,rangePosition:Number(pos.toFixed(2))},rationale:[story,`entry ${entryModel}`,`SL outside invalidation ${Number(anchor.toPrecision(8))} plus volatility buffer`,`TP1/TP2 use local and HTF liquidity; TP3 expands only beyond those objectives`,`RSI ${Number(r.rsiA).toFixed(1)} / ${Number(r.rsiB).toFixed(1)}`]},'FOREX',style);
}
async function scanForexJudgment(env,style){
  const trackerEvents=await retireAllLegacyActiveSignals(env);
  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'NO_CURRENT_EXNESS_QUOTE',created:0,state:ex.state,ageMs:ex.ageMs,trackerEvents,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time gate is applied, but stale data is never treated as a current market price.'};
  const rows=await tvForexFrames(style),priceMap=ex.map,rawSetups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),assessed=rawSetups.map(x=>({...x,entryAssessment:assessEntrySetup(x)})),setups=assessed.filter(x=>x.entryAssessment.verdict==='PASS'),created=await maybeCreateV31(env,'FOREX',style,setups);
  return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,evaluated:rawSetups.length,actionable:setups.length,rejectedByAssessment:rawSetups.length-setups.length,noTrade:Math.max(0,rows.length-setups.length),created:created.length,portfolioBlocked:Math.max(0,setups.length-created.length),newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
}
async function scanForexScalp(env){return scanForexJudgment(env,'SCALP');}
async function scanForexSwing(env){return scanForexJudgment(env,'SWING');}
function normalizeDisplaySignal(input,market,style){
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
  s.decisionMode=String(s.decisionMode||'BOT_MARKET_JUDGMENT');
  s.admissionMode=String(s.admissionMode||'NO_SCORE_NO_TIME_GATE');
  delete s.score;delete s.qualityGrade;delete s.scoreMeaning;
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


function normalizeWatchSymbol(raw){
  let s=canonical(raw);if(!s)return'';if(!s.endsWith('USDT'))s+='USDT';return s.length<=24?s:'';
}
function watchFlatSignal(src,state,assessment){
  const s=src||{},a=assessment||s.entryAssessment||{};
  return {state,activeSignal:state==='ACTIVE_SIGNAL',symbol:s.symbol||null,side:s.side||null,orderType:s.orderType||null,status:s.status||null,entry:num(s.actualEntry??s.entry),sl:num(s.sl),tp1:num(s.tp1),tp2:num(s.tp2),tp3:num(s.tp3??s.tp),targetRR:num(s.targetRR),marketRegime:s.marketRegime||null,marketStory:s.marketStory||null,judgment:s.judgment||null,entryModel:s.entryModel||null,coverageTier:s.coverageTier||null,coverageFallback:Boolean(s.coverageFallback),assessmentMethod:a.method||null,failedChecks:Array.isArray(a.failed)?a.failed:[],rationale:Array.isArray(s.rationale)?s.rationale.slice(0,6):[],provider:s.executionPriceAuthority||s.provider||s.exchange||null,issuedAt:s.issuedAt||null,lastCheckedAt:s.lastCheckedAt||null,watchReference:Boolean(s.watchReference),studyOnly:Boolean(s.studyOnly),occupiesActiveSlot:s.occupiesActiveSlot===false?false:state==='ACTIVE_SIGNAL',performanceEligible:s.performanceEligible===false?false:state==='ACTIVE_SIGNAL',distanceToEntryAbs:num(s.distanceToEntryAbs),distanceToEntryPct:num(s.distanceToEntryPct)};
}
async function loadWatchSnapshot(env){
  let last=null,lastError=null;
  for(let i=0;i<3;i++){
    try{const snap=await loadCryptoSnapshot(env);last=snap;if(snap?.live!==false&&Array.isArray(snap?.rows)&&snap.rows.length)return snap;}catch(e){lastError=String(e?.message||e);}
    if(i<2)await sleep(250*(i+1));
  }
  if(last)return last;
  return {rows:[],provider:null,live:false,staleFallback:false,receivedAt:null,errors:lastError?[lastError]:['NO_WATCH_SNAPSHOT']};
}
function watchUnavailable(symbol,provider,reason){return {state:'DATA_UNAVAILABLE',activeSignal:false,symbol,side:null,orderType:null,status:null,entry:null,sl:null,tp1:null,tp2:null,tp3:null,targetRR:null,marketRegime:'DATA_UNAVAILABLE',marketStory:'Dữ liệu thị trường tạm thời chưa đủ mới để phân tích an toàn. Không suy diễn tín hiệu từ giá cũ.',judgment:'DATA_UNAVAILABLE',entryModel:null,coverageTier:null,coverageFallback:false,assessmentMethod:null,failedChecks:[reason||'FRESH_DATA_UNAVAILABLE'],rationale:[],provider:provider||null};}
async function watchAnalyze(url,env){
  const symbol=normalizeWatchSymbol(url.searchParams.get('symbol')||'');if(!symbol)return json({ok:false,version:V3_VERSION,error:'BAD_WATCH_SYMBOL'},400);
  const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,fresh=snap?.live!==false;
  if(!ticker){const unavailable=watchUnavailable(symbol,snap?.provider,'SYMBOL_NOT_AVAILABLE_ON_LIVE_CRYPTO_VENUES');return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:null,dataHealth:{state:'UNAVAILABLE',live:false,staleFallback:false,provider:snap?.provider||null,providerErrors:snap?.errors||[]},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist is read-only and never consumes active slots.'},analyzedAt:nowIso()});}
  const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null};
  if(!fresh){const unavailable=watchUnavailable(symbol,baseTicker.provider,'FRESH_TICKER_UNAVAILABLE');return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'STALE',live:false,staleFallback:true,receivedAt:snap.receivedAt||null,provider:baseTicker.provider},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist is read-only and never consumes active slots.'},analyzedAt:nowIso()});}
  const activeBook=await getActiveBook(env),styles={};
  await Promise.all(['SCALP','SWING'].map(async style=>{
    const active=activeBook.find(x=>String(x.style||'').toUpperCase()===style&&canonical(x.symbol)===symbol);if(active){styles[style]=watchFlatSignal(active,'ACTIVE_SIGNAL',active.entryAssessment);return;}
    const setup=await analyzeCryptoCandidate(ticker,style);
    if(setup){const strict=assessEntrySetup(setup),conditional=setup.coverageFallback?assessCoverageSetup(setup):strict,state=strict.verdict==='PASS'?'TRADEABLE_NOW':conditional.verdict==='PASS'?'CONDITIONAL_WAIT':'NO_TRADE';if(state!=='NO_TRADE'){const projected={...setup,watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false};styles[style]=watchFlatSignal(projected,state,state==='TRADEABLE_NOW'?strict:conditional);return;}}
    const ideal=await analyzeWatchIdealReference(ticker,style,env);if(ideal){styles[style]=watchFlatSignal(ideal,'IDEAL_REFERENCE',null);return;}
    styles[style]=watchUnavailable(symbol,baseTicker.provider,'ANALYSIS_CANDLES_UNAVAILABLE');
  }));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]},styles,activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist ideal plans are study-only; they never consume or replace the 15 active slots and never enter performance history.'},analyzedAt:nowIso()});
}

async function unifiedSignals(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',status=String(url.searchParams.get('status')||'active').toLowerCase(),limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  let rows=await getV31Signals(env,market,style);rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  const targetActive=styleTarget(style);
  if(status==='active'&&rows.length<targetActive){
    // One bounded refill attempt is enough for an interactive read. Continuous/server
    // maintenance owns deeper refill work; the app request must stay responsive.
    await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL').catch(()=>{});
    let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
    if(rows.length<targetActive&&ctx?.waitUntil){
      ctx.waitUntil(Promise.resolve(scanCrypto(env,style)).then(()=>promoteCryptoStandby(env,style,'ACTIVE_READ_BACKGROUND_REFILL')).catch(()=>{}));
    }
  }
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,targetActive,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
}

async function unifiedPerformance(url,env){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31Signals(env,market,style),active=rows.filter(s=>s.status==='PENDING'||s.status==='OPEN'),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  try{const body=await scanCrypto(env,style);return json(body,body?.ok===false?503:200);}
  catch(e){return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,error:'SCAN_RUNTIME_ERROR',detail:String(e?.message||e),portfolio:await realtimePortfolioSnapshot(env).catch(()=>null)},503);}
}

async function v315Stability(env){
  const portfolio=await realtimePortfolioSnapshot(env),monitor=await cryptoServerMonitorStatus(env),styles={};let totalResolved=0,totalTp=0,totalSl=0,totalNetR=0;
  for(const style of ['SCALP','SWING']){
    const rows=await getV31Signals(env,'CRYPTO',style),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
    styles[style]={resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,evidenceState:resolved.length>=30?'MATURE_SAMPLE':resolved.length>=10?'BUILDING_SAMPLE':'INSUFFICIENT_SAMPLE'};totalResolved+=resolved.length;totalTp+=tp;totalSl+=sl;totalNetR+=netR;
  }
  const monitorHealthy=monitor?.ok!==false&&monitor?.running!==false&&Array.isArray(monitor?.errors)&&monitor.errors.length===0,infrastructureState=monitorHealthy?'STABLE':'DEGRADED',warnings=[];
  if(styles.SCALP.resolved>0&&styles.SCALP.netRResolved<0)warnings.push('SCALP_RESOLVED_NET_R_NEGATIVE');if(styles.SCALP.resolved<30)warnings.push('SCALP_SAMPLE_SMALL');if(styles.SWING.resolved<30)warnings.push('SWING_SAMPLE_SMALL');if(!monitorHealthy)warnings.push('CRYPTO_MONITOR_DEGRADED');
  return json({ok:true,version:V3_VERSION,checkpoint:CHECKPOINT,mode:'CRYPTO_ONLY_STABILITY',infrastructure:{state:infrastructureState,monitor,portfolio},tradingEvidence:{state:totalResolved>=60?'MATURE':'NOT_YET_PROVEN',resolved:totalResolved,tp:totalTp,sl:totalSl,winRateResolved:totalResolved?totalTp/totalResolved*100:null,netRResolved:Number(totalNetR.toFixed(2)),styles},warnings,note:'Infrastructure stability and trading performance are separate. Win rate is descriptive only from closed TP/SL trades; it is not a predicted probability.'});
}

async function v3Status(env,ctx){
  const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<styleTarget(st));
  if(missing.length&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',service:'SignalHub Crypto 10 SCALP + 5 SWING Stable Universe + Watchlist gateway',checkpoint:CHECKPOINT,app:V31_RELEASE,crypto:{priceAuthority:'PROVIDER_PINNED_BYBIT_PREFERRED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'FIXED_10_ACTIVE_STABLE_LIQUID_UNIVERSE_5M_15M_1H',swing:'FIXED_5_ACTIVE_STABLE_LIQUID_UNIVERSE_1H_4H_1D',pendingLifecycle:'DURABLE_OBJECT_ALARM_1S',crossProviderContextCheck:true,marketReadVersion:'V322_STYLE_SPECIFIC_CONTEXT_STRUCTURE_LIQUIDITY',watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'},engines:{cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},forexDisabled:true,portfolio,missingStyles:missing,cryptoMonitor,decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'});
}
async function handleV3(req,env,ctx){
  const url=new URL(req.url);if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'content-type, authorization, x-signalhub-bridge','access-control-allow-methods':'GET,POST,OPTIONS'}});
  try{
    if(url.pathname==='/v3/status'&&req.method==='GET')return v3Status(env,ctx);
    if(url.pathname==='/v3/stability'&&req.method==='GET')return v315Stability(env);
    if(url.pathname==='/v3/app-version'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',checkpoint:CHECKPOINT,app:V31_RELEASE});
    if(url.pathname.startsWith('/v3/mt5/')&&req.method==='POST')return json({ok:true,version:V3_VERSION,ignored:true,mode:'CRYPTO_ONLY_STABILITY',reason:'FOREX_BRANCH_DISABLED'});
    if(url.pathname.startsWith('/v3/forex/'))return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
    if(url.pathname==='/v3/crypto/tickers'&&req.method==='GET')return cryptoTickers(url,env);
    if(url.pathname==='/v3/crypto/stable100'&&req.method==='GET'){let cached=await readStable100(env);if(!cached){const snap=await loadCryptoSnapshot(env);await persistStable100(env,snap,snap.rows);cached=await readStable100(env);}if(cached)return json({ok:true,...cached,integrity:stable100Integrity(cached)});return json({ok:false,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,error:'NO_VALID_STANDARDIZED_STABLE100'},503);}
    if(url.pathname==='/v3/data-integrity'&&req.method==='GET'){const p=await readStable100(env),audit=stable100Integrity(p);return json({ok:audit.ok,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,stable100:p?{count:p.count,target:p.target,provider:p.provider,providers:p.providers,refreshedAt:p.refreshedAt,complete:p.complete}:null,problems:audit.problems});}
    if(url.pathname==='/v3/crypto/monitor'&&req.method==='GET'){const kick=url.searchParams.get('kick')==='1'?await kickCryptoServerMonitor(env):null;if(ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',status:await cryptoServerMonitorStatus(env),kick,portfolio:await realtimePortfolioSnapshot(env)});}
    if(url.pathname==='/v3/portfolio'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',portfolio:await realtimePortfolioSnapshot(env),policy:PORTFOLIO_POLICY});
    if(url.pathname==='/v3/standbys'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',standbys:await cryptoStandbyStatus(env)});
    if(url.pathname==='/v3/crypto/discovery'&&req.method==='GET')return cryptoDiscovery(url,env);
    if(url.pathname==='/v3/watch/analyze'&&req.method==='GET')return watchAnalyze(url,env);
    if(url.pathname==='/v3/scan'&&req.method==='GET')return scanRoute(url,env,ctx);
    if(url.pathname==='/v3/signals'&&req.method==='GET')return unifiedSignals(url,env,ctx);
    if(url.pathname==='/v3/performance'&&req.method==='GET')return unifiedPerformance(url,env);
    if(url.pathname==='/v3/decision-policy'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',policy:MARKET_JUDGMENT_POLICY,stylePolicy:STYLE_EXECUTION_POLICY,portfolioPolicy:PORTFOLIO_POLICY});
    return null;
  }catch(e){const msg=String(e?.message||e),code=msg==='INVALID_JSON'?400:msg==='PAYLOAD_TOO_LARGE'?413:503;return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:msg},code);}
}

export default {
  async fetch(req,env,ctx){const v3=await handleV3(req,env,ctx);if(v3)return v3;return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'CRYPTO_ONLY_ENDPOINT_NOT_FOUND'},404);},
  async scheduled(event,env,ctx){ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));},
};