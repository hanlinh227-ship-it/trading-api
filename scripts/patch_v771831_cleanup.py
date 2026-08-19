from pathlib import Path
import re

p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
# Index Cash must use the generic Twelve Data non-crypto path, never old Futures runners.
s=s.replace('  if(group==="index")return runFutureGroup(env);\n','')
s=re.sub(r'  if\(type==="index"\)\{const recent=await recentFutureScanAnalysis\(s,env\);if\(recent\)return recent;try\{return await runFutureSymbol\(s,env\);\}catch\(e\)\{return \{ok:false,status:"DATA_BLOCK",symbol:s,market:"index",reason:"MASSIVE_RATE_OR_DATA_UNAVAILABLE",error:e\?\.message\|\|String\(e\),engine:CONFIG\.version\};\}\}\n','',s,count=1)
# UI/symbol lists.
s=s.replace('{text:"📈 Futures",callback_data:"symmarket:future"}','{text:"📊 Index Cash",callback_data:"symmarket:index"}')
s=s.replace('{text:"📈 Futures",callback_data:"symmarket:index"}','{text:"📊 Index Cash",callback_data:"symmarket:index"}')
s=s.replace('function symbolListFor(group){return group==="index"?FUTURE_SYMBOLS:(GROUPS[group]||[]);}','function symbolListFor(group){return GROUPS[group]||[];}')
# Live P/L for index plans uses fresh Twelve Data quote.
s=s.replace('if(g==="index"){const a=await recentFutureScanAnalysis(p.symbol,env),q=a?.quote||a?.analysisQuote,price=Number(a?.currentPrice??q?.price);return price>0?{price,source:q?.source||a?.source||"Massive recent"}:null;}','if(g==="index")return await tdQuote(p.symbol,env);')
s=s.replace('for(const g of ["crypto","forex","metal","future"])','for(const g of ["crypto","forex","metal","index"])')
# Remove micro-futures sizing UI/function completely.
s=re.sub(r'function futureSizing\(symbol,plan\)\{.*?\}\nfunction planMetricText', 'function planMetricText', s, count=1, flags=re.S)
s=s.replace('(marketType(symbol)==="index"?" pts":"")','')
s=re.sub(r';const fs=futureSizing\(w\.symbol,w\.planned\);if\(fs\)\{if\(fs\.tradable\)x\+=`\\n   ↳ Micro sizing:.*?`;\}\}', '', s, count=1, flags=re.S)
s=re.sub(r';const fs=futureSizing\(a\.symbol,a\.planned\);if\(fs\)\{if\(fs\.tradable\)L\.push\(`Micro sizing:.*?\);\}', '', s, count=1, flags=re.S)
# Labels/reasons/status providers.
s=s.replace('g==="index"?"📈 INDEX CASH":"🥇 METAL"','g==="index"?"📊 INDEX CASH":"🥇 METAL"')
s=s.replace('g==="future"?"📈 FUTURES":"🥇 METAL"','g==="index"?"📊 INDEX CASH":"🥇 METAL"')
s=s.replace(',FUTURE_RISK_LIMIT_REQUIRED:"SL cấu trúc vượt giới hạn risk micro",MASSIVE_RATE_OR_DATA_UNAVAILABLE:"Massive đang giới hạn hoặc thiếu dữ liệu"','')
s=s.replace('Massive Futures: ${env.MASSIVE_API_KEY?"CONFIGURED":"MISSING"}\\n','')
s=s.replace('Futures: NQ/MNQ/ES/MES\\n','Index Cash: NAS100/US30/US500/DEX/JP225\\n')
s=s.replace('massive:!!env.MASSIVE_API_KEY,','')
s=s.replace('future:"Massive Futures NQ/ES analysis; delayed/basic data remains analysis-only"','index:"Twelve Data Index analysis; signal-only until broker execution authority exists"')
s=s.replace('future:"Massive Futures NQ/ES analysis; delayed/basic data remains analysis-only"','index:"Twelve Data Index analysis; signal-only until broker execution authority exists"')
# Any callback/group labels left after the first migration.
s=s.replace('signal:scan:future','signal:scan:index').replace('symmarket:future','symmarket:index')
s=s.replace('"future"','"index"').replace("'future'","'index'")
s=s.replace('📈 Futures','📊 Index Cash').replace('📈 FUTURES','📊 INDEX CASH')
# Strictly reject old runner names from final engine.
for bad in ['runFutureGroup','runFutureSymbol','recentFutureScanAnalysis','futureSizing','FUTURE_SYMBOLS','FUTURE_SCAN','FUTURES_KNOWLEDGE','MASSIVE_API_KEY','Massive Futures','MNQ','MES']:
    if bad in s:
        print('STILL_ENGINE',bad)
p.write_text(s)

# System Health: Massive Futures is no longer part of Signal dependencies.
p=Path('cloudflare-worker/system-health.js'); h=p.read_text()
h=re.sub(r'\s*if\(!env\.MASSIVE_API_KEY\)add\(issues,"WARN","MASSIVE_MISSING","Massive Futures key missing"\);','',h)
h=h.replace('MASSIVE_API_KEY','TWELVE_DATA_API_KEY') if 'Massive Futures' in h else h
p.write_text(h)

print('PATCH_V771831_CLEANUP_OK')
