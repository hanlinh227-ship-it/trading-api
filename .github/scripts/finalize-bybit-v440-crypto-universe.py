from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]

# Keep dynamic universe naming consistent in UI and production audit.
control=ROOT/'cloudflare-worker/bybit-control-plane.js'
s=control.read_text(encoding='utf-8')
s=s.replace("SYMBOL_NOT_IN_DYNAMIC_LINEAR_UNIVERSE","SYMBOL_NOT_IN_DYNAMIC_CRYPTO_UNIVERSE")
s=s.replace("BYBIT_DYNAMIC_LINEAR_SCALP_UNIVERSE_V1","BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2")
control.write_text(s,encoding='utf-8')

diag=ROOT/'.github/workflows/diagnose-bybit-v43-live.yml'
s=diag.read_text(encoding='utf-8')
s=s.replace("u.authority!=='BYBIT_DYNAMIC_LINEAR_SCALP_UNIVERSE_V1'","u.authority!=='BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2'")
s=s.replace("c.dynamicBybitScalpUniverse!==true||c.positiveAntiSweepLock", "c.dynamicBybitScalpUniverse!==true||c.cryptoOnlyDynamicUniverse!==true||c.positiveAntiSweepLock")
diag.write_text(s,encoding='utf-8')

# VPS collector: discover broad liquid crypto contracts only. Bybit symbolType
# explicitly identifies stock/forex/ETF/commodity linear products.
bridge=ROOT/'bybit-live-bridge/bybit_live_bridge.py'
s=bridge.read_text(encoding='utf-8')
pat=r"def discover_ws_symbols\(\):\n.*?\n    return tuple\(seed\)\nSYMBOLS=discover_ws_symbols\(\)"
new="""def discover_ws_symbols():
    seed=list(dict.fromkeys(list(CORE_SYMBOLS)+list(MANUAL_SYMBOLS)))
    if not AUTO_DISCOVER:return tuple(seed[:MAX_WS_SYMBOLS])
    rows=[]; crypto_symbols=set()
    for base in BYBIT_BASES:
        try:
            cursor=''
            for _ in range(3):
                qs={'category':'linear','limit':'1000'}
                if cursor:qs['cursor']=cursor
                req=urllib.request.Request(base+'/v5/market/instruments-info?'+urllib.parse.urlencode(qs),headers={'user-agent':'Mozilla/5.0','accept':'application/json'})
                with urllib.request.urlopen(req,timeout=10) as r: meta=json.loads(r.read(6_000_000).decode())
                result=meta.get('result') or {}
                for x in result.get('list') or []:
                    s=str(x.get('symbol') or '').upper(); st=str(x.get('symbolType') or '').lower(); status=str(x.get('status') or '').upper(); contract=str(x.get('contractType') or '')
                    if s.endswith('USDT') and st not in {'stock','forex','etf','commodity','xstocks'} and status=='TRADING' and 'PERPETUAL' in contract.upper():crypto_symbols.add(s)
                nxt=str(result.get('nextPageCursor') or '')
                if not nxt or nxt==cursor:break
                cursor=nxt
            if crypto_symbols:break
        except Exception:continue
    for base in BYBIT_BASES:
        try:
            req=urllib.request.Request(base+'/v5/market/tickers?category=linear',headers={'user-agent':'Mozilla/5.0','accept':'application/json'})
            with urllib.request.urlopen(req,timeout=8) as r: data=json.loads(r.read(4_000_000).decode())
            for x in (data.get('result') or {}).get('list') or []:
                s=str(x.get('symbol') or '').upper()
                if not s.endswith('USDT') or s in seed or (crypto_symbols and s not in crypto_symbols):continue
                try:
                    bid=float(x.get('bid1Price') or 0);ask=float(x.get('ask1Price') or 0);turn=float(x.get('turnover24h') or 0);mid=(bid+ask)/2 if bid>0 and ask>0 else 0;spread=(ask-bid)/mid*10000 if mid>0 and ask>=bid else 999
                except Exception:continue
                if turn>=35_000_000 and spread<=7.0:rows.append((turn,-spread,s))
            if rows:break
        except Exception:continue
    rows.sort(reverse=True)
    for _,__,s in rows:
        if len(seed)>=MAX_WS_SYMBOLS:break
        seed.append(s)
    return tuple(seed)
SYMBOLS=discover_ws_symbols()"""
s,n=re.subn(pat,new,s,count=1,flags=re.S)
if n!=1:raise SystemExit('BRIDGE_DISCOVERY_BLOCK_NOT_FOUND')
bridge.write_text(s,encoding='utf-8')
print('BYBIT_V440_CRYPTO_ONLY_FINALIZED')
