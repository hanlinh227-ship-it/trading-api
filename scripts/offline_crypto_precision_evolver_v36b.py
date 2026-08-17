#!/usr/bin/env python3
import statistics
import scripts.offline_crypto_precision_evolver_v36 as v


def fixed_regime_at(mp,t):
    eligible={}
    for s in v.SYMBOLS:
        q=mp[s].get(t)
        if not q:
            continue
        r=q[1]
        required=(r.get('ret24'),r.get('ret72'),r.get('adx'),r.get('rsi'),r.get('ema20'),r.get('ema50'),r.get('atr'),r.get('mom24atr'),r.get('dev'))
        if all(x is not None for x in required):
            eligible[s]=q
    if len(eligible)<20:
        return None
    rets=[q[1]['ret24'] for q in eligible.values()]
    breadth=sum(x>0 for x in rets)/len(rets)
    med=statistics.median(rets)
    disp=statistics.pstdev(rets) or 1e-9
    btc=eligible.get('BTC')
    btc24=btc[1]['ret24'] if btc else med
    btc72=btc[1]['ret72'] if btc else 0
    return eligible,{
        'breadth':breadth,
        'median24':med,
        'dispersion24':disp,
        'btc24':btc24,
        'btc72':btc72,
        'eligible':len(eligible),
    }

v.regime_at=fixed_regime_at
v.OUT='data/offline_crypto_precision_v36b.json'

if __name__=='__main__':
    v.main()
