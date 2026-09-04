from pathlib import Path

src_path=Path('.github/scripts/apply-bybit-v500-scalp-quality.py')
src=src_path.read_text()
bad="s = rep(s, \"BYBIT-MULTI-STATEFLOW-4.9.0\", \"BYBIT-MULTI-STATEFLOW-5.0.0\", 'config version')\n"
if bad not in src:
    raise SystemExit('V500_BASE_PATCH_UNEXPECTED')
src=src.replace(bad,'',1)
exec(compile(src,str(src_path),'exec'),{'__name__':'__main__'})

# Keep the repository's source validator aligned with the new runtime contract.
p=Path('cloudflare-worker/validate-btc-hyperscale.mjs')
s=p.read_text()
repls=[
    ("assert.equal(BYBIT_AUTO_VERSION,'BYBIT-MULTI-STATEFLOW-4.9.0');","assert.equal(BYBIT_AUTO_VERSION,'BYBIT-MULTI-STATEFLOW-5.0.0');"),
    ("assert.equal(BYBIT_RUNTIME_CONTRACT.version,'BYBIT_MULTI_ASSET_RUNTIME_V27_SCALP_FIRST_MULTI_ENTRY');","assert.equal(BYBIT_RUNTIME_CONTRACT.version,'BYBIT_MULTI_ASSET_RUNTIME_V28_SCALP_QUALITY_POSITIVE_EDGE');"),
    ("for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V27_SCALP_FIRST_MULTI_ENTRY','capitalIntelligenceV4:true','instantDepositRecognition:true','capitalHighWaterDoubleCountFixed:true','fastScaleControlled:true'])","for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V28_SCALP_QUALITY_POSITIVE_EDGE','entryQualityPositiveNetEdge:true','shortHorizonPriceConfirmation:true','probeNewRiskDisabled:true','transitionNewRiskDisabled:true','positiveExpectancyGovernorV2:true','capitalIntelligenceV4:true','instantDepositRecognition:true','capitalHighWaterDoubleCountFixed:true','fastScaleControlled:true'])"),
    ("for(const x of ['GLOBAL_NEGATIVE_EXPECTANCY_GUARD','SYMBOL_NEGATIVE_EXPECTANCY_QUARANTINE'])","for(const x of ['GLOBAL_POSITIVE_EDGE_REQUALIFICATION','GLOBAL_72H_POSITIVE_EDGE_REQUALIFICATION','SYMBOL_POSITIVE_EDGE_QUARANTINE'])")
]
for old,new in repls:
    if old not in s:
        raise SystemExit(f'VALIDATOR_EXPECTATION_MISSING:{old[:60]}')
    s=s.replace(old,new,1)
p.write_text(s)
print('BYBIT_V500_VALIDATOR_UPDATED')
