from pathlib import Path

p=Path(__file__).resolve().parents[2]/'cloudflare-worker/validate-btc-hyperscale.mjs'
s=p.read_text()
repls={
"BYBIT-MULTI-STATEFLOW-4.4.0":"BYBIT-MULTI-STATEFLOW-4.4.1",
"BYBIT_MULTI_ASSET_RUNTIME_V20_DYNAMIC_SCALP_ANTI_SWEEP":"BYBIT_MULTI_ASSET_RUNTIME_V21_DIRECTION_COHERENCE_LONG_RUN_FREEZE",
"BYBIT_SYMBOL_COGNITION_V4_MOMENTUM_FOOTPRINT_DYNAMIC_SCALP":"BYBIT_SYMBOL_COGNITION_V5_DIRECTION_COHERENCE_LONG_RUN_FREEZE",
}
for old,new in repls.items():
    if old not in s:
        raise SystemExit(f'MISSING_VALIDATOR_MARKER:{old}')
    s=s.replace(old,new)
needle="assert.equal(BYBIT_RUNTIME_CONTRACT.newListingsWatchBeforeTrade,true);"
extra="assert.equal(BYBIT_RUNTIME_CONTRACT.perSymbolRegimeSideCoherence,true);assert.equal(BYBIT_RUNTIME_CONTRACT.crossMarketDirectionBreadthGuard,true);assert.equal(BYBIT_RUNTIME_CONTRACT.strictContrarianException,true);assert.equal(BYBIT_RUNTIME_CONTRACT.longRunCoreFreeze,true);"
if extra not in s:
    if needle not in s: raise SystemExit('MISSING_VALIDATOR_INSERT_POINT')
    s=s.replace(needle,needle+extra,1)
needle2="for(const x of ['buildBybitDynamicUniverse','DYNAMIC_UNIVERSE_WATCH_ONLY','continuousCapacityCapitalUsd','pendingEntrySlot=1','BYBIT_MULTI_ASSET_CONTROLLER_V4_DYNAMIC_UNIVERSE_CONTINUOUS_SLOTS'])"
replacement2="for(const x of ['buildBybitDynamicUniverse','DYNAMIC_UNIVERSE_WATCH_ONLY','continuousCapacityCapitalUsd','pendingEntrySlot=1','BYBIT_MULTI_ASSET_CONTROLLER_V4_DYNAMIC_UNIVERSE_CONTINUOUS_SLOTS','CROSS_MARKET_DIRECTION_CONFLICT','PER_SYMBOL_REGIME_PLUS_CROSS_MARKET_BREADTH'])"
if needle2 in s: s=s.replace(needle2,replacement2,1)
needle3="for(const x of ['momentumFootprint','FOOTPRINT_SPIKE_WITHOUT_FOLLOW_THROUGH','BYBIT_SYMBOL_COGNITION_V5_DIRECTION_COHERENCE_LONG_RUN_FREEZE','PROFILE_MICROSTRUCTURE_STALE_OR_FALLBACK_ONLY'])"
replacement3="for(const x of ['momentumFootprint','FOOTPRINT_SPIKE_WITHOUT_FOLLOW_THROUGH','BYBIT_SYMBOL_COGNITION_V5_DIRECTION_COHERENCE_LONG_RUN_FREEZE','PROFILE_MICROSTRUCTURE_STALE_OR_FALLBACK_ONLY','PROFILE_COUNTERTREND_UNCONFIRMED','marketContrarianQualified'])"
if needle3 in s: s=s.replace(needle3,replacement3,1)
p.write_text(s)
print('BYBIT_V441_VALIDATOR_SYNCED')
