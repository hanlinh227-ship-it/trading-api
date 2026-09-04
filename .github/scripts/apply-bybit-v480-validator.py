from pathlib import Path
p=Path(__file__).resolve().parents[2]/'cloudflare-worker/validate-btc-hyperscale.mjs'
s=p.read_text()
s=s.replace("'BYBIT-MULTI-STATEFLOW-4.7.0'","'BYBIT-MULTI-STATEFLOW-4.8.0'")
s=s.replace("'BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK'","'BYBIT_MULTI_ASSET_RUNTIME_V26_CAPITAL_INTELLIGENCE_FAST_SCALE'")
# V4.8 keeps all V4.7 safety assertions and adds capital/risk invariants.
append="""
assert.equal(BYBIT_RUNTIME_CONTRACT.capitalIntelligenceV4,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.separateCapitalState,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.instantDepositRecognition,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.instantWithdrawalRiskReduction,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.capitalHighWaterDoubleCountFixed,true);
assert.equal(BYBIT_AUTO_CONFIG.risk.martingale,false);
assert.equal(BYBIT_AUTO_CONFIG.risk.addToLoser,false);
assert.ok(BYBIT_AUTO_CONFIG.risk.baseEntryRiskPct>=1.0);
assert.ok(BYBIT_AUTO_CONFIG.risk.absoluteSingleEntryRiskPct<=2.25);
assert.ok(BYBIT_AUTO_CONFIG.risk.maxActiveRiskPct<=7.0);
assert.ok(BYBIT_AUTO_CONFIG.leverage.max<=125);
"""
if 'capitalHighWaterDoubleCountFixed' not in s:
    # Insert before the final PASS print when present; otherwise append.
    marker="console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');"
    if marker in s:s=s.replace(marker,append+"\n"+marker,1)
    else:s += "\n"+append
p.write_text(s)
print('BYBIT_V480_VALIDATOR_PATCHED')
