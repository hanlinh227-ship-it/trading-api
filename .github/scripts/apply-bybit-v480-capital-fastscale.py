from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def replace(path,old,new,count=1):
    p=ROOT/path;s=p.read_text()
    if old not in s:
        raise SystemExit(f'MISSING_PATTERN {path}: {old[:180]}')
    s=s.replace(old,new,count)
    p.write_text(s)

# -----------------------------------------------------------------------------
# Capital authority: separate state from BTC symbol state, paginate transaction
# logs, recognize positive capital shocks immediately and downside instantly.
# -----------------------------------------------------------------------------
capital = r'''import {bybitV5} from './bybit-v5-client.js';

const KEY='bybit:capital:intelligence:v1';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const iso=()=>new Date().toISOString();
const DAY=86400000;
const MIN_SHOCK_USD=.25;
const SHOCK_PCT=.005;
const UPSIDE_HALF_LIFE_MS=90_000;

async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:'json'})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}

function walletSnapshot(w={}){
  const a=w?.result?.list?.[0]||{},coin=(a.coin||[]).find(x=>String(x.coin)==='USDT')||{};
  const walletBalance=num(coin.walletBalance||a.totalWalletBalance),equity=num(a.totalEquity||coin.equity||walletBalance),available=num(a.totalAvailableBalance||coin.availableToWithdraw||coin.availableBalance);
  const unrealised=num(coin.unrealisedPnl||a.totalPerpUPL),cumRealised=num(coin.cumRealisedPnl);
  return {walletBalanceUsd:walletBalance,equityUsd:equity,availableUsd:available,unrealisedPnlUsd:unrealised,cumRealisedPnlUsd:cumRealised};
}
function transferDirection(type=''){
  const t=String(type||'').toUpperCase();
  if(t==='TRANSFER_IN'||t.endsWith('_TRANSFER_IN')||t.includes('TRANSFER_IN_')||t==='DBS_CASH_IN')return 1;
  if(t==='TRANSFER_OUT'||t.endsWith('_TRANSFER_OUT')||t.includes('TRANSFER_OUT_')||t==='DBS_CASH_OUT')return -1;
  return 0;
}
function classifyTransfer(row={}){
  const type=String(row.type||'').toUpperCase(),direction=transferDirection(type);if(!direction)return null;
  const raw=num(row.cashFlow||row.change),amount=Math.abs(raw);if(!(amount>0))return null;
  return {id:String(row.id||`${row.transactionTime}:${type}:${amount}`),type,amountUsd:amount,signedUsd:direction*amount,at:num(row.transactionTime),cashBalanceUsd:num(row.cashBalance),displayType:String(row.displayType||'')};
}
async function transactionPages(api,startTime,endTime){
  const rows=[];let cursor='';let pages=0;
  for(let i=0;i<8;i++){
    const q={accountType:'UNIFIED',currency:'USDT',startTime,endTime,limit:50};if(cursor)q.cursor=cursor;
    const x=await api.signed('GET','/v5/account/transaction-log',q),r=x?.result||{},list=Array.isArray(r.list)?r.list:[];rows.push(...list);pages++;
    const next=String(r.nextPageCursor||'');if(!next||next===cursor)break;cursor=next;
  }
  return {rows,pages};
}
function applySnapshot(state,snap,{forceUpside=false,reason='NORMAL'}={}){
  const now=Date.now(),prevAt=Date.parse(state.lastBalanceObservedAt||'')||now,dt=Math.max(0,now-prevAt),alpha=dt<=0?1:1-Math.exp(-dt/UPSIDE_HALF_LIFE_MS),prevEq=num(state.smoothedEquityUsd)||snap.equityUsd,prevWallet=num(state.smoothedWalletBalanceUsd)||snap.walletBalanceUsd,prevObserved=num(state.lastEquityUsd)||snap.equityUsd,prevWalletObserved=num(state.lastWalletBalanceUsd)||snap.walletBalanceUsd,prevAvailable=num(state.lastAvailableUsd)||snap.availableUsd,hours=Math.max(dt/3600000,1/3600),walletDelta=snap.walletBalanceUsd-prevWalletObserved,equityDelta=snap.equityUsd-prevObserved,availableDelta=snap.availableUsd-prevAvailable,threshold=Math.max(MIN_SHOCK_USD,Math.abs(prevWalletObserved)*SHOCK_PCT),positiveShock=forceUpside||walletDelta>=threshold,negativeShock=walletDelta<=-threshold||equityDelta<=-threshold;
  let smEq=prevEq+(snap.equityUsd-prevEq)*alpha,smWallet=prevWallet+(snap.walletBalanceUsd-prevWallet)*alpha;
  const hardCapital=Math.max(0,Math.min(snap.equityUsd,snap.walletBalanceUsd>0?snap.walletBalanceUsd:snap.equityUsd));
  let continuous;
  if(positiveShock){smEq=snap.equityUsd;smWallet=snap.walletBalanceUsd;continuous=hardCapital;}
  else if(negativeShock){continuous=hardCapital;}
  else continuous=Math.max(0,Math.min(snap.equityUsd,smEq,snap.walletBalanceUsd>0?Math.max(smWallet,snap.walletBalanceUsd*.90):smEq));
  state.smoothedEquityUsd=smEq;state.smoothedWalletBalanceUsd=smWallet;state.continuousCapitalUsd=continuous;state.equityVelocityUsdPerHour=(snap.equityUsd-prevObserved)/hours;
  state.capitalRecognition={at:new Date(now).toISOString(),reason,positiveShock,negativeShock,forceUpside,walletDeltaUsd:walletDelta,equityDeltaUsd:equityDelta,availableDeltaUsd:availableDelta,shockThresholdUsd:threshold,continuousCapitalUsd:continuous,hardCapitalUsd:hardCapital,lagUsd:Math.max(0,hardCapital-continuous)};
  state.continuousScaleAuthority='CAPITAL_INTELLIGENCE_V4_INSTANT_EXTERNAL_UPSIDE_INSTANT_DOWNSIDE_90S_ORGANIC_SMOOTH';
  state.lastWalletBalanceUsd=snap.walletBalanceUsd;state.lastEquityUsd=snap.equityUsd;state.lastAvailableUsd=snap.availableUsd;state.lastUnrealisedPnlUsd=snap.unrealisedPnlUsd;state.lastCumRealisedPnlUsd=snap.cumRealisedPnlUsd;state.lastBalanceObservedAt=new Date(now).toISOString();state.balanceAuthority='BYBIT_WALLET_PLUS_PAGINATED_TRANSACTION_LOG_SEPARATE_CAPITAL_STATE';state.depositWithdrawalAware=true;state.capitalStateVersion=4;return state;
}

export async function reconcileBtcAccountBalance(env){
  const api=bybitV5(env),now=Date.now(),[wallet,state0]=await Promise.all([api.wallet(),get(env)]),snap=walletSnapshot(wallet),state={...state0};
  if(!(snap.equityUsd>0))return {ok:false,reason:'BALANCE_EQUITY_INVALID',snapshot:snap,state};
  const previousScan=num(state.cashFlowScanAt)||0,startTime=Math.max(now-7*DAY,previousScan>0?previousScan-5*60000:now-DAY);
  let tx={rows:[],pages:0};
  try{tx=await transactionPages(api,startTime,now);}catch(e){
    state.lastBalanceReconcileError={at:iso(),error:String(e?.message||e).slice(0,240)};applySnapshot(state,snap,{reason:'TRANSACTION_LOG_UNAVAILABLE'});if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;await put(env,state);return {ok:true,reason:'WALLET_UPDATED_TRANSACTION_LOG_UNAVAILABLE',snapshot:snap,state,error:state.lastBalanceReconcileError};
  }
  const seen=new Set((state.cashFlowSeenIds||[]).map(String)),parsed=tx.rows.map(classifyTransfer).filter(Boolean);
  // V4 uses a dedicated capital state. First observation intentionally establishes a fresh
  // baseline from the live account, preventing legacy BTC symbol high-water from double-counting deposits.
  if(previousScan<=0){
    for(const e of parsed)seen.add(e.id);applySnapshot(state,snap,{forceUpside:true,reason:'V4_FRESH_CAPITAL_BASELINE'});state.highWaterUsd=snap.equityUsd;state.protectedEquityUsd=snap.walletBalanceUsd;state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-1000);state.cumulativeExternalCashFlowUsd=0;state.lastBalanceBaselineAt=iso();state.migrationAuthority='FRESH_LIVE_ACCOUNT_BASELINE_SEPARATE_FROM_SYMBOL_STATE';state.transactionLogPages=tx.pages;state.transactionLogRows=tx.rows.length;state.lastBalanceReconcileError=null;await put(env,state);return {ok:true,reason:'CAPITAL_V4_BASELINE_ESTABLISHED',snapshot:snap,netExternalCashFlowUsd:0,events:[],state};
  }
  const events=[];for(const e of parsed){if(seen.has(e.id))continue;if(e.at>0&&e.at<previousScan-5*60000)continue;events.push(e);seen.add(e.id);}events.sort((a,b)=>a.at-b.at);const netExternalCashFlowUsd=events.reduce((s,x)=>s+x.signedUsd,0),oldHigh=num(state.highWaterUsd)||snap.equityUsd,oldProtected=num(state.protectedEquityUsd)||snap.walletBalanceUsd;
  if(Math.abs(netExternalCashFlowUsd)>1e-12){state.highWaterUsd=Math.max(0,oldHigh+netExternalCashFlowUsd);state.protectedEquityUsd=Math.max(0,oldProtected+netExternalCashFlowUsd);state.lastExternalCashFlow={at:iso(),netUsd:netExternalCashFlowUsd,events};state.cumulativeExternalCashFlowUsd=num(state.cumulativeExternalCashFlowUsd)+netExternalCashFlowUsd;}else if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;
  applySnapshot(state,snap,{forceUpside:netExternalCashFlowUsd>0,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED'});state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-1000);state.transactionLogPages=tx.pages;state.transactionLogRows=tx.rows.length;state.lastBalanceReconcileError=null;await put(env,state);return {ok:true,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED',snapshot:snap,netExternalCashFlowUsd,events,state};
}
export const BTC_BALANCE_RECONCILER_VERSION='BTC_BALANCE_RECONCILER_V4_CAPITAL_INTELLIGENCE';
'''
(ROOT/'cloudflare-worker/bybit-btc-balance-reconciler.js').write_text(capital)

# Faster controlled compounding. Higher leverage lowers margin use; stop-distance risk remains authoritative.
replace('cloudflare-worker/bybit-auto-config.js',
"      {equityUsd:0,normal:11,strong:14,aPlus:18,max:20},\n      {equityUsd:50,normal:10,strong:13,aPlus:17,max:20},\n      {equityUsd:100,normal:9,strong:12,aPlus:16,max:18},\n      {equityUsd:250,normal:7.5,strong:10.5,aPlus:14,max:16},\n      {equityUsd:500,normal:6.5,strong:9.5,aPlus:12.5,max:14},\n      {equityUsd:1000,normal:5.5,strong:8.5,aPlus:11.5,max:13},\n      {equityUsd:2500,normal:4.5,strong:7.5,aPlus:10,max:12},\n      {equityUsd:5000,normal:4,strong:6.5,aPlus:9,max:10}",
"      {equityUsd:0,normal:16,strong:22,aPlus:30,max:35},\n      {equityUsd:50,normal:15,strong:21,aPlus:29,max:34},\n      {equityUsd:100,normal:14,strong:19,aPlus:27,max:32},\n      {equityUsd:250,normal:11,strong:16,aPlus:23,max:28},\n      {equityUsd:500,normal:9,strong:14,aPlus:20,max:24},\n      {equityUsd:1000,normal:8,strong:12,aPlus:18,max:22},\n      {equityUsd:2500,normal:7,strong:11,aPlus:16,max:20},\n      {equityUsd:5000,normal:6,strong:10,aPlus:14,max:18}")
replace('cloudflare-worker/bybit-auto-config.js',"    minPlannedNetProfitUsd:.25,\n    preferredRunnerNetProfitUsd:1.05,\n    minPlannedNetProfitPct:.35,","    minPlannedNetProfitUsd:.40,\n    preferredRunnerNetProfitUsd:1.50,\n    minPlannedNetProfitPct:.55,")
replace('cloudflare-worker/bybit-auto-config.js',"      {equityUsd:0,minNetUsd:.25},{equityUsd:50,minNetUsd:.35},{equityUsd:75,minNetUsd:.50},\n      {equityUsd:100,minNetUsd:.70},{equityUsd:150,minNetUsd:1.00},{equityUsd:250,minNetUsd:1.50},\n      {equityUsd:500,minNetUsd:3.00},{equityUsd:1000,minNetUsd:6.00},{equityUsd:2500,minNetUsd:14.00},\n      {equityUsd:5000,minNetUsd:30.00},{equityUsd:10000,minNetUsd:60.00}","      {equityUsd:0,minNetUsd:.40},{equityUsd:50,minNetUsd:.55},{equityUsd:75,minNetUsd:.75},\n      {equityUsd:100,minNetUsd:1.00},{equityUsd:150,minNetUsd:1.40},{equityUsd:250,minNetUsd:2.00},\n      {equityUsd:500,minNetUsd:4.00},{equityUsd:1000,minNetUsd:8.00},{equityUsd:2500,minNetUsd:18.00},\n      {equityUsd:5000,minNetUsd:40.00},{equityUsd:10000,minNetUsd:80.00}")
replace('cloudflare-worker/bybit-auto-config.js',"    baseEntryRiskPct:.70,strongEntryRiskPct:.95,aPlusEntryRiskPct:1.20,absoluteSingleEntryRiskPct:1.25,\n    maxActiveRiskPct:4.2,temporaryAPlusActiveRiskPct:5.0,maxPortfolioMarginPct:60,maxMarginPerPositionPct:55,minFreeReservePct:20,","    baseEntryRiskPct:1.00,strongEntryRiskPct:1.45,aPlusEntryRiskPct:2.00,absoluteSingleEntryRiskPct:2.25,\n    maxActiveRiskPct:7.0,temporaryAPlusActiveRiskPct:8.5,maxPortfolioMarginPct:78,maxMarginPerPositionPct:65,minFreeReservePct:12,")
replace('cloudflare-worker/bybit-auto-config.js',"    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:2,riskRecycleAfterProtection:true,","    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:3,riskRecycleAfterProtection:true,")
replace('cloudflare-worker/bybit-auto-config.js',"    earlyHarvestMinNetUsd:.18,\n    earlyHarvestMinPeakR:.55,","    earlyHarvestMinNetUsd:.30,\n    earlyHarvestMinPeakR:.65,")
replace('cloudflare-worker/bybit-auto-config.js',"    earlyHarvestGivebackR:.25,","    earlyHarvestGivebackR:.30,")

# Dynamic crypto participates more meaningfully, but remains below core risk.
replace('cloudflare-worker/bybit-coin-profiles.js',"authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V7_ALL_CRYPTO_SAME_RISK_BUDGET'","authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V8_CAPITAL_INTELLIGENCE_FAST_SCALE'")
replace('cloudflare-worker/bybit-coin-profiles.js',"marketCapClass:'DYNAMIC',riskMult:.35,targetMult:1.02,stopMult:1.06,signalGain:.94,flowThresholdMult:1.05,qualityThresholdMult:1.12,bookToleranceMult:.92,leverageMult:.70,maxSpreadBps:20.0,minTurnoverUsd:500_000,runnerMaxR:3.8,holdMult:1.00","marketCapClass:'DYNAMIC',riskMult:.55,targetMult:1.10,stopMult:1.06,signalGain:.96,flowThresholdMult:1.04,qualityThresholdMult:1.10,bookToleranceMult:.94,leverageMult:.82,maxSpreadBps:20.0,minTurnoverUsd:500_000,runnerMaxR:4.5,holdMult:1.08")

# Capital high-water from the dedicated reconciler is authoritative over stale per-symbol legacy state.
replace('cloudflare-worker/bybit-symbol-engine.js',"highWaterUsd:Math.max(equity,num(state.highWaterUsd),num(portfolioContext?.highWaterUsd))","highWaterUsd:num(portfolioContext?.highWaterUsd)>0?Math.max(equity,num(portfolioContext.highWaterUsd)):Math.max(equity,num(state.highWaterUsd))")
replace('cloudflare-worker/bybit-symbol-engine.js','BYBIT-MULTI-ASSET-ENGINE-4.5.0-EXPECTANCY-CAPITAL-PRESERVATION','BYBIT-MULTI-ASSET-ENGINE-4.8.0-CAPITAL-INTELLIGENCE-FAST-SCALE',99)
replace('cloudflare-worker/bybit-symbol-engine.js','EXCHANGE_CAPPED_CONTINUOUS_CAPITAL_LEVERAGE','EXCHANGE_CAPPED_RISK_BUDGET_ADAPTIVE_LEVERAGE',99)

# Controller telemetry exposes exactly what capital the risk engine can use.
replace('cloudflare-worker/bybit-multi-asset-controller.js',"continuousCapacityCapitalUsd:capacityCapital,walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),lastCycleAt:iso()","continuousCapacityCapitalUsd:capacityCapital,walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),capitalIntelligence:{authority:balance?.state?.continuousScaleAuthority||null,stateVersion:num(balance?.state?.capitalStateVersion),highWaterUsd:num(balance?.state?.highWaterUsd),protectedEquityUsd:num(balance?.state?.protectedEquityUsd),lastExternalCashFlow:balance?.state?.lastExternalCashFlow||null,recognition:balance?.state?.capitalRecognition||null,transactionLogPages:num(balance?.state?.transactionLogPages),transactionLogRows:num(balance?.state?.transactionLogRows)},lastCycleAt:iso()")
replace('cloudflare-worker/bybit-multi-asset-controller.js',"BYBIT_MULTI_ASSET_CONTROLLER_V5_EXPECTANCY_CAPITAL_PRESERVATION","BYBIT_MULTI_ASSET_CONTROLLER_V6_CAPITAL_INTELLIGENCE_FAST_SCALE")

# Monitor keeps schema backward-compatible and adds risk-capacity visibility.
replace('cloudflare-worker/bybit-android-monitor.js',"realizedPnl72h:p72.realizedPnl,source:'BOT_CONTROLLER_PLUS_VPS_WS_MARK_TO_MARKET'","realizedPnl72h:p72.realizedPnl,riskCapacityCapital:num(controller.continuousCapacityCapitalUsd),capitalLagUsd:Math.max(0,num(controller.walletBalanceUsd)-num(controller.continuousCapacityCapitalUsd)),capitalAuthority:controller.capitalIntelligence?.authority||null,source:'BOT_CONTROLLER_PLUS_VPS_WS_MARK_TO_MARKET'")
replace('cloudflare-worker/bybit-android-monitor.js',"candidateDecisions:controller.candidateDecisions||[]}","candidateDecisions:controller.candidateDecisions||[],capitalIntelligence:controller.capitalIntelligence||null}")

# Transport health is based on connection + fresh books. Trade freshness remains a separate entry-quality metric.
bridge=ROOT/'bybit-live-bridge/bybit_live_bridge.py';s=bridge.read_text();start=s.index('def ws_telemetry(snaps):');end=s.index('\ndef market_telemetry(snaps):',start)
new_ws=r'''def ws_telemetry(snaps):
    now=int(time.time()*1000);book_ages=[];trade_ages=[];dual_ages=[];stale=[];connected=ready=book_fresh=trade_fresh=dual_fresh=0
    for symbol,x in snaps.items():
        if x.get('connected'):connected+=1
        if not x.get('ok'):continue
        ready+=1;d=x.get('data') or {};book=d.get('book') or {};trades=d.get('trades') or {};lb=int(book.get('updateTime') or 0);lt=int(trades.get('lastTradeTime') or trades.get('updateTime') or 0)
        ba=max(0,now-lb) if lb>0 else 999999;ta=max(0,now-lt) if lt>0 else 999999;da=max(ba,ta);book_ages.append(ba);trade_ages.append(ta);dual_ages.append(da)
        if ba<=5000:book_fresh+=1
        if ta<=5000:trade_fresh+=1
        if da<=5000:dual_fresh+=1
        if da>5000:stale.append({'symbol':symbol,'bookAgeMs':ba,'tradeAgeMs':ta,'dataAgeMs':da})
    def pct(xs,q):
        if not xs:return None
        xs=sorted(xs);i=max(0,min(len(xs)-1,int(math.ceil(q*len(xs)))-1));return int(xs[i])
    min_connected=max(1,int(math.ceil(len(snaps)*.80)));min_book=max(1,int(math.ceil(len(snaps)*.70)))
    transport_healthy=connected>=min_connected and book_fresh>=min_book
    return {'healthy':transport_healthy,'transportHealthy':transport_healthy,'connectedCount':connected,'readyCount':ready,'freshCount':dual_fresh,'bookFreshCount':book_fresh,'tradeFreshCount':trade_fresh,'dualFreshCount':dual_fresh,'totalCount':len(snaps),'p50DataAgeMs':pct(book_ages,.50),'p95DataAgeMs':pct(book_ages,.95),'maxDataAgeMs':int(max(book_ages)) if book_ages else None,'tradeP50AgeMs':pct(trade_ages,.50),'tradeP95AgeMs':pct(trade_ages,.95),'dualP95AgeMs':pct(dual_ages,.95),'staleSymbols':sorted(stale,key=lambda x:x['dataAgeMs'],reverse=True)[:20],'freshThresholdMs':5000,'healthAuthority':'TRANSPORT_CONNECTION_PLUS_BOOK_FRESHNESS_TRADE_FRESHNESS_PER_SYMBOL_ENTRY_GATE','timestamp':now}

'''
s=s[:start]+new_ws+s[end+1:];bridge.write_text(s)

# Runtime contract V4.8.
replace('cloudflare-worker/bybit-runtime-contract.js',"BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK","BYBIT_MULTI_ASSET_RUNTIME_V26_CAPITAL_INTELLIGENCE_FAST_SCALE")
replace('cloudflare-worker/bybit-runtime-contract.js',"BYBIT-MULTI-STATEFLOW-4.7.0","BYBIT-MULTI-STATEFLOW-4.8.0")
replace('cloudflare-worker/bybit-runtime-contract.js',"continuousTimeCapitalScale:true,","continuousTimeCapitalScale:true,capitalIntelligenceV4:true,separateCapitalState:true,instantDepositRecognition:true,instantWithdrawalRiskReduction:true,paginatedTransactionReconciliation:true,capitalHighWaterDoubleCountFixed:true,fastScaleControlled:true,adaptiveLeverageExpanded:true,")

print('BYBIT_V480_CAPITAL_FASTSCALE_PATCHED')
