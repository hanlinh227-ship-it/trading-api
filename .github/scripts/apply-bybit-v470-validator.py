from pathlib import Path
p=Path(__file__).resolve().parents[2]/'cloudflare-worker/validate-btc-hyperscale.mjs'
s=p.read_text()
s=s.replace("assert.equal(BYBIT_AUTO_VERSION,'BYBIT-MULTI-STATEFLOW-4.6.0')","assert.equal(BYBIT_AUTO_VERSION,'BYBIT-MULTI-STATEFLOW-4.7.0')")
s=s.replace("assert.equal(BYBIT_RUNTIME_CONTRACT.version,'BYBIT_MULTI_ASSET_RUNTIME_V24_BROAD_SCALP_OPPORTUNITY_NETWORK')","assert.equal(BYBIT_RUNTIME_CONTRACT.version,'BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK')")
s=s.replace("assert.equal(BYBIT_RUNTIME_CONTRACT.newListingsWatchBeforeTrade,true)","assert.equal(BYBIT_RUNTIME_CONTRACT.newListingsWatchBeforeTrade,false);assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,true);assert.equal(BYBIT_RUNTIME_CONTRACT.executionUnsafeNoNewRisk,true)")
s=s.replace("assert.ok(BYBIT_PORTFOLIO_POLICY.promotionScanCount>=12)","assert.equal(BYBIT_PORTFOLIO_POLICY.promotionScanCount,0)")
s=s.replace("['TRADE_CORE','TRADE_STABLE','TRADE_SCALP_FAST','TRADE_PROMOTED','WATCH_NEW','WATCH_THIN','DO_NOT_TRADE','BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION'","['TRADE_CORE','TRADE_ALL_CRYPTO','WATCH_EXECUTION_UNSAFE','DO_NOT_TRADE','BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V5_ALL_ACTIVE_CRYPTO'")
s=s.replace("['BYBIT_MULTI_ASSET_RUNTIME_V24_BROAD_SCALP_OPPORTUNITY_NETWORK'","['BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK'")
s=s.replace("newListingsWatch:true","newListingsWatch:false,allActiveCryptoEligible:true")
p.write_text(s)
print('BYBIT_V470_VALIDATOR_PATCHED')
