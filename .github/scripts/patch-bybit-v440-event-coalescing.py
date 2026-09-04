from pathlib import Path
p=Path('bybit-live-bridge/bybit_live_bridge.py')
s=p.read_text(encoding='utf-8')
old="""SYMBOLS=discover_ws_symbols()
_extra=[s for s in SYMBOLS if s not in CORE_SYMBOLS]
_default_events=list(CORE_SYMBOLS[:10])+_extra[:8]
EVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS',','.join(_default_events)).split(',') if x.strip() and x.strip().upper() in SYMBOLS)
BYBIT_ALLOWED_PREFIXES=('/v5/account/','/v5/position/','/v5/order/','/v5/market/')
"""
new="""SYMBOLS=discover_ws_symbols()
_extra=[s for s in SYMBOLS if s not in CORE_SYMBOLS]
EVENT_SYMBOL_LIMIT=max(4,min(12,int(os.environ.get('BYBIT_EVENT_SYMBOL_LIMIT','8'))))
_default_events=list(CORE_SYMBOLS[:6])+_extra[:2]
_event_candidates=[x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS',','.join(_default_events)).split(',') if x.strip() and x.strip().upper() in SYMBOLS]
EVENT_SYMBOLS=set(list(dict.fromkeys(_event_candidates))[:EVENT_SYMBOL_LIMIT])
BYBIT_ALLOWED_PREFIXES=('/v5/account/','/v5/position/','/v5/order/','/v5/market/')
"""
if old not in s: raise SystemExit('event symbol block not found')
s=s.replace(old,new,1)
s=s.replace("'eventSymbols':sorted(EVENT_SYMBOLS),'dynamicWsDiscovery':AUTO_DISCOVER,'maxWsSymbols':MAX_WS_SYMBOLS","'eventSymbols':sorted(EVENT_SYMBOLS),'eventSymbolLimit':EVENT_SYMBOL_LIMIT,'eventWakeAuthority':'BOUNDED_DRIVER_SET_GLOBAL_SERIAL_COALESCING','dynamicWsDiscovery':AUTO_DISCOVER,'maxWsSymbols':MAX_WS_SYMBOLS",1)
p.write_text(s,encoding='utf-8')
print('BYBIT_V440_EVENT_COALESCING_PATCHED')
