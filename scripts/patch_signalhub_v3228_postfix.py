from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
w=p.read_text()
if 'const STYLE_EXECUTION_POLICY = Object.freeze({' not in w:
    marker='function validSignalStructure(signal){'
    i=w.find(marker); assert i>=0
    policy="""const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE_MARKET_ONLY',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'fresh MARKET only; structure/liquidity event + aligned context + anti-FOMO + liquidity/spread hard safety',stopFocus:'micro invalidation + ATR/spread buffer',targetFocus:'liquidity/structure geometry',holdModel:'realtime health monitor; persistent deterioration only'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE_MARKET_ONLY',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'fresh MARKET only; H4/D1 aligned context + H1 execution + anti-extension + liquidity/spread hard safety',stopFocus:'H1/H4 invalidation + wider ATR buffer',targetFocus:'H4/D1 liquidity/structure geometry',holdModel:'realtime health monitor; persistent deterioration only'})
});

"""
    w=w[:i]+policy+w[i:]
p.write_text(w)
assert 'const STYLE_EXECUTION_POLICY = Object.freeze({' in w
print('V3.22.8 style policy present')
