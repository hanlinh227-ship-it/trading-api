from pathlib import Path
p=Path('.github/workflows/validate-cloudflare-v77.yml')
s=p.read_text()
s=s.replace("'V77.16.12'","'V77.16.13'")
s=s.replace("if(/MASSIVE_API_KEY|Massive Futures/.test(health))throw new Error('System Health still depends on removed Futures provider');","if(/Massive Futures/.test(health))throw new Error('System Health still depends on removed Futures provider');")
s=s.replace("if(/FUTURE_SYMBOLS|FUTURE_SCAN|MASSIVE_API_KEY|Massive Futures|signal:scan:future|symmarket:future|futureMinRR|runFutureGroup|runFutureSymbol|futureSizing/.test(legacy))throw new Error('Legacy Futures conflict remains');","if(/FUTURE_SYMBOLS|FUTURE_SCAN|Massive Futures|signal:scan:future|symmarket:future|futureMinRR|runFutureGroup|runFutureSymbol|futureSizing/.test(legacy))throw new Error('Legacy Futures conflict remains');")
s=s.replace("console.log('V77.18.31 Metal + Index Cash validation PASS');","for(const x of ['MASSIVE_INDEX_PROVIDER','I:NDX','I:DJI','I:SPX','I:DAX','I:N225','Massive Indices'])if(!engine.includes(x))throw new Error('Massive Index lock missing: '+x);\n          console.log('V77.18.32 Index Provider R2 validation PASS');")
p.write_text(s)
print('VALIDATOR_V771832_OK')