from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()
repls={
"minActivePerMarket:7":"minActivePerMarket:0",
"minActivePerStyle:2":"minActivePerStyle:0",
"maxActivePerRiskCluster:7":"maxActivePerRiskCluster:3",
"coverageMode:'CRYPTO_EXACT_5_SCALP_2_SWING_MARKET_ONLY'":"coverageMode:'CRYPTO_TARGET_5_SCALP_2_SWING_MARKET_ONLY_NEVER_FORCE_WEAK'",
"replacementMode:'HEALTH_CUT_THEN_ASYNC_MARKET_RESCAN'":"replacementMode:'QUALITY_FIRST_RESCAN_NO_WEAK_QUOTA_FILL'",
"deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE'":"deepScanRotation:'FULL_QUALITY_SCAN_WHEN_UNDERFILLED'",
"continuousRefill:'TARGET_5_SCALP_2_SWING_MARKET_ONLY'":"continuousRefill:'TARGET_5_SCALP_2_SWING_ONLY_IF_QUALIFIED'",
}
for old,new in repls.items():
    w=w.replace(old,new)
p.write_text(w)
assert "continuousRefill:'TARGET_5_SCALP_2_SWING_ONLY_IF_QUALIFIED'" in w
assert "coverageMode:'CRYPTO_TARGET_5_SCALP_2_SWING_MARKET_ONLY_NEVER_FORCE_WEAK'" in w
assert "replacementMode:'QUALITY_FIRST_RESCAN_NO_WEAK_QUOTA_FILL'" in w
print('V3.22.8 decision policy synchronized')
