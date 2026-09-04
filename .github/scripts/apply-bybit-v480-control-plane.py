from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'cloudflare-worker/bybit-control-plane.js';s=p.read_text()
old="import {bybitV5} from './bybit-v5-client.js';"
new=old+"\nimport {reconcileBtcAccountBalance} from './bybit-btc-balance-reconciler.js';"
if "reconcileBtcAccountBalance" not in s:s=s.replace(old,new,1)
needle="if(u.pathname==='/bybit/runtime/preflight'&&req.method==='GET')"
route="if(u.pathname==='/bybit/capital/sync'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);try{const b=await reconcileBtcAccountBalance(env),st=b.state||{},snap=b.snapshot||{};return json({ok:b.ok!==false,readOnlyExecution:true,tradingExecuted:false,reason:b.reason||null,netExternalCashFlowUsd:Number(b.netExternalCashFlowUsd||0),account:{equityUsd:Number(snap.equityUsd||0),walletBalanceUsd:Number(snap.walletBalanceUsd||0),availableUsd:Number(snap.availableUsd||0)},capital:{stateVersion:Number(st.capitalStateVersion||0),continuousCapitalUsd:Number(st.continuousCapitalUsd||0),highWaterUsd:Number(st.highWaterUsd||0),protectedEquityUsd:Number(st.protectedEquityUsd||0),authority:st.continuousScaleAuthority||null,recognition:st.capitalRecognition||null,lastExternalCashFlow:st.lastExternalCashFlow||null,transactionLogPages:Number(st.transactionLogPages||0),transactionLogRows:Number(st.transactionLogRows||0)},checkedAt:new Date().toISOString()})}catch(e){return json({ok:false,readOnlyExecution:true,tradingExecuted:false,reason:'CAPITAL_SYNC_FAILED',error:String(e?.message||e)},502)}}"
if route not in s:
    if needle not in s:raise SystemExit('CONTROL_PLANE_INSERT_PATTERN_MISSING')
    s=s.replace(needle,route+needle,1)
p.write_text(s)

# Migrate every exact source-level assertion that legitimately changes in V4.8.
v=ROOT/'cloudflare-worker/validate-btc-hyperscale.mjs';x=v.read_text()
repls={
"'BYBIT-MULTI-STATEFLOW-4.7.0'":"'BYBIT-MULTI-STATEFLOW-4.8.0'",
"'BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK'":"'BYBIT_MULTI_ASSET_RUNTIME_V26_CAPITAL_INTELLIGENCE_FAST_SCALE'",
"'BYBIT-MULTI-ASSET-ENGINE-4.5.0-EXPECTANCY-CAPITAL-PRESERVATION'":"'BYBIT-MULTI-ASSET-ENGINE-4.8.0-CAPITAL-INTELLIGENCE-FAST-SCALE'",
"'BYBIT_MULTI_ASSET_CONTROLLER_V5_EXPECTANCY_CAPITAL_PRESERVATION'":"'BYBIT_MULTI_ASSET_CONTROLLER_V6_CAPITAL_INTELLIGENCE_FAST_SCALE'",
"'const baseMax=maxConcurrentForEquity(equity)'":"'const baseMax=maxConcurrentForEquity(capacityCapital)'",
"balance.includes('TIME_DECAYED_EQUITY_BALANCE_INSTANT_DOWNSIDE')":"balance.includes('CAPITAL_INTELLIGENCE_V4_INSTANT_EXTERNAL_UPSIDE_INSTANT_DOWNSIDE_90S_ORGANIC_SMOOTH')"
}
for a,b in repls.items():x=x.replace(a,b)
marker="console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');"
extra="""assert.equal(BYBIT_RUNTIME_CONTRACT.capitalIntelligenceV4,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.separateCapitalState,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.instantDepositRecognition,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.instantWithdrawalRiskReduction,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.paginatedTransactionReconciliation,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.capitalHighWaterDoubleCountFixed,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.fastScaleControlled,true);\nassert.equal(BYBIT_RUNTIME_CONTRACT.adaptiveLeverageExpanded,true);\nassert.equal(BYBIT_AUTO_CONFIG.risk.martingale,false);\nassert.equal(BYBIT_AUTO_CONFIG.risk.addToLoser,false);\nassert.ok(BYBIT_AUTO_CONFIG.risk.baseEntryRiskPct>=1.0);\nassert.ok(BYBIT_AUTO_CONFIG.risk.strongEntryRiskPct>=1.45);\nassert.ok(BYBIT_AUTO_CONFIG.risk.aPlusEntryRiskPct>=2.0);\nassert.ok(BYBIT_AUTO_CONFIG.risk.absoluteSingleEntryRiskPct<=2.25);\nassert.ok(BYBIT_AUTO_CONFIG.risk.maxActiveRiskPct<=7.0);\nassert.ok(BYBIT_AUTO_CONFIG.leverage.max<=125);\nassert.ok(balance.includes('bybit:capital:intelligence:v1'));\nassert.ok(balance.includes('transactionPages'));\nassert.ok(balance.includes('capitalRecognition'));\n"""
if 'assert.equal(BYBIT_RUNTIME_CONTRACT.capitalIntelligenceV4,true)' not in x:
    x=x.replace(marker,extra+marker,1) if marker in x else x+'\n'+extra
v.write_text(x)
print('BYBIT_V480_CONTROL_PLANE_AND_VALIDATOR_PATCHED')
