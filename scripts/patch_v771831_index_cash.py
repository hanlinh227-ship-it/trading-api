from pathlib import Path
import re


def replace_once(s, old, new, label):
    if old not in s:
        raise SystemExit(f"MISSING:{label}")
    return s.replace(old, new, 1)

# --- Signal engine: remove Futures/Massive branch and install Index Cash on Twelve Data ---
p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
s=s.replace('import FUTURES_KNOWLEDGE from "../data/futures_knowledge.json" with { type: "json" };\n','')
s=replace_once(s,'version: "V77.16.11",\n  service: "Trading V77.16.11 Forex Opportunity Routing R3",','version: "V77.16.12",\n  service: "Trading V77.16.12 Metal + Index Cash Routing R1",','engine version')
s=s.replace('  futureQuoteAgeSec: 12,\n','').replace('  futureAnalysisMaxAgeSec: 900,\n','').replace('    futureContract: "v7714:future_contract",\n','')
s=replace_once(s,'const METALS = ["XAUUSD","XAGUSD"];\nconst FUTURE_SYMBOLS = ["NQ","MNQ","ES","MES"];\nconst FUTURE_SCAN = ["NQ","ES"];\nconst GROUPS = { forex: FOREX, crypto: CRYPTO, metal: METALS, future: FUTURE_SYMBOLS };',
'''const METALS = ["XAUUSD","XAGUSD"];
const INDEX_CASH = ["NAS100","US30","US500","DEX","JP225"];
const INDEX_PROVIDER = {NAS100:"NDX",US30:"DJI",US500:"SPX",DEX:"DAX",JP225:"N225"};
const INDEX_PRIORS = {
  NAS100:{profile:"INDEX_GROWTH_MOMENTUM",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.72,newsProfile:{profileDrivers:["Fed/FOMC","US CPI/PCE/NFP","US yields","US mega-cap technology"]}},
  US30:{profile:"INDEX_BLUECHIP_ROTATION",families:["TREND","MEANREV"],allowedModes:["TREND","MEAN_REVERSION"],riskATR:.68,newsProfile:{profileDrivers:["Fed/FOMC","US macro","industrial/financial rotation"]}},
  US500:{profile:"INDEX_BROAD_RISK",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.66,newsProfile:{profileDrivers:["Fed/FOMC","US CPI/PCE/NFP","US yields","broad risk sentiment"]}},
  DEX:{profile:"INDEX_EUROPE_SESSION",families:["TREND","MEANREV"],allowedModes:["TREND","MEAN_REVERSION"],riskATR:.72,newsProfile:{profileDrivers:["ECB","Eurozone CPI/PMI","Germany macro"]}},
  JP225:{profile:"INDEX_ASIA_SESSION",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.74,newsProfile:{profileDrivers:["BoJ","Japan CPI/wages","JPY","Asia risk sentiment"]}}
};
const GROUPS = { forex: FOREX, crypto: CRYPTO, metal: METALS, index: INDEX_CASH };''','universe')
s=replace_once(s,'function marketType(symbol){const s=norm(symbol);if(FOREX.includes(s))return "forex";if(CRYPTO.includes(s))return "crypto";if(METALS.includes(s))return "metal";if(FUTURE_SYMBOLS.includes(s))return "future";return "unknown";}\nfunction tdSymbol(symbol){const s=norm(symbol),t=marketType(s);if(t==="forex"||t==="metal")return `${s.slice(0,3)}/${s.slice(3)}`;return s;}',
'''function marketType(symbol){const s=norm(symbol);if(FOREX.includes(s))return "forex";if(CRYPTO.includes(s))return "crypto";if(METALS.includes(s))return "metal";if(INDEX_CASH.includes(s))return "index";return "unknown";}
function tdSymbol(symbol){const s=norm(symbol),t=marketType(s);if(t==="forex"||t==="metal")return `${s.slice(0,3)}/${s.slice(3)}`;if(t==="index")return INDEX_PROVIDER[s]||s;return s;}''','market type')
s=s.replace('function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:0;}','function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:group==="index"?25:0;}')
# Remove entire Massive/Futures implementation; Index Cash uses canonical Twelve Data index feed.
s, n = re.subn(r'\nasync function massiveFetch\(pathname,params,env\)\{.*?\nasync function bybit\(path,params=\{\}\)\{', '\nasync function bybit(path,params={}){', s, count=1, flags=re.S)
if n != 1: raise SystemExit('MISSING:future implementation block')
# Knowledge and RR.
s=s.replace('function symbolKnowledge(symbol){const s=canonicalUserSymbol(symbol),k=s.endsWith("USDT")?s.slice(0,-4):s;return FUTURES_KNOWLEDGE?.symbols?.[s]||SYMBOL_KNOWLEDGE?.symbols?.[s]||SYMBOL_KNOWLEDGE?.symbols?.[k]||null;}',
'''function symbolKnowledge(symbol){const s=canonicalUserSymbol(symbol),k=s.endsWith("USDT")?s.slice(0,-4):s;return INDEX_PRIORS[s]||SYMBOL_KNOWLEDGE?.symbols?.[s]||SYMBOL_KNOWLEDGE?.symbols?.[k]||null;}''')
s=s.replace('if(type==="future")x=Math.max(x,1.45);','if(type==="index")x=Math.max(x,mode==="MEAN_REVERSION"?1.20:1.35);')
# Futures-only sizing gates have no meaning for cash-index signal plans.
s=re.sub(r'if\(type==="future"&&\["MNQ","MES"\]\.includes\(norm\(symbol\)\)&&planned\)\{.*?\}const status=', 'const status=', s, count=1, flags=re.S)
s=re.sub(r'if\(a\?\.market==="future"&&\["MNQ","MES"\]\.includes\(norm\(a\?\.symbol\)\)\)\{.*?\}if\(a\?\.contextOnly\)', 'if(a?.contextOnly)', s, count=1, flags=re.S)
# Add Metal and Index Cash session/context models near FX context helpers.
needle='function forexSessionBias(symbol){'
pos=s.find(needle)
if pos<0: raise SystemExit('MISSING:forexSessionBias')
# insert helpers before forexSessionBias
helpers='''function metalSessionBias(){const h=new Date().getUTCHours();if(h>=12&&h<17)return {score:1.15,label:"LONDON_NY_OVERLAP"};if(h>=7&&h<16)return {score:.95,label:"LONDON_ACTIVE"};if(h>=13&&h<21)return {score:.95,label:"NEW_YORK_ACTIVE"};return {score:.45,label:"OFF_PEAK"};}\nfunction indexSessionBias(symbol){const s=norm(symbol),h=new Date().getUTCHours();if(s==="JP225")return h>=0&&h<7?{score:1.10,label:"TOKYO_ACTIVE"}:{score:.35,label:"TOKYO_OFF"};if(s==="DEX")return h>=7&&h<16?{score:1.10,label:"EUROPE_ACTIVE"}:{score:.35,label:"EUROPE_OFF"};return h>=13&&h<21?{score:1.10,label:"US_CASH_WINDOW"}:{score:.40,label:"US_OFF"};}\nfunction weightedIndexMove(c){if(!Array.isArray(c)||c.length<7)return changeFromCandles(c);const last=Number(c.at(-1)?.close||0);if(!(last>0))return 0;const mv=n=>{const a=Number(c.at(-(n+1))?.close||0);return a>0?(last-a)/a*100:0;};return mv(1)*.45+mv(3)*.35+mv(6)*.20;}\nfunction indexBenchmark(symbol){const s=norm(symbol);return s==="NAS100"?"US500":s==="US30"?"US500":s==="US500"?"NAS100":null;}\n'''
s=s[:pos]+helpers+s[pos:]
# Broad context: split metal/index explicitly instead of treating every non-FX group as metal.
s=s.replace('let metalMoves={};if(group==="metal")for(const sym of symbols)metalMoves[sym]=changeFromCandles(h1Map.get(sym)||[]);if(group==="forex")await saveMarketContext("forex",{strength:fx},env);else if(group==="metal")await saveMarketContext("metal",{moves:metalMoves},env);',
'''let metalMoves={},indexMoves={};if(group==="metal")for(const sym of symbols)metalMoves[sym]=changeFromCandles(h1Map.get(sym)||[]);if(group==="index")for(const sym of symbols)indexMoves[sym]=weightedIndexMove(h1Map.get(sym)||[]);if(group==="forex")await saveMarketContext("forex",{strength:fx},env);else if(group==="metal")await saveMarketContext("metal",{moves:metalMoves},env);else if(group==="index")await saveMarketContext("index",{moves:indexMoves},env);''')
s=s.replace('}else{const other=sym==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(metalMoves[sym]||0)-(metalMoves[other]||0);context={relativeStrength:rel,benchmark:other,score:Math.min(10,5+Math.abs(rel)*3)};}const raw=',
'''}else if(group==="metal"){const other=sym==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(metalMoves[sym]||0)-(metalMoves[other]||0),sess=metalSessionBias();context={relativeStrength:rel,benchmark:other,session:sess.label,sessionScore:sess.score,score:Math.min(10,4.8+Math.abs(rel)*3.2+sess.score*.75)};}else if(group==="index"){const bench=indexBenchmark(sym),rel=bench?Number(indexMoves[sym]||0)-Number(indexMoves[bench]||0):0,sess=indexSessionBias(sym);context={relativeStrength:rel,benchmark:bench,session:sess.label,sessionScore:sess.score,indexMove:Number(indexMoves[sym]||0),score:Math.min(10,4.8+Math.abs(rel)*3+Math.abs(Number(indexMoves[sym]||0))*1.2+sess.score*.8)};}const raw=''')
s=s.replace('sessionBoost=group==="forex"?Number(context.sessionScore||.35):sessionFit(prior),directionBoost=group==="forex"?Math.min(1.4,Math.abs(Number(context.strengthDiff||0))*3.2):0,',
'''sessionBoost=(group==="forex"||group==="metal"||group==="index")?Number(context.sessionScore||.35):sessionFit(prior),directionBoost=group==="forex"?Math.min(1.4,Math.abs(Number(context.strengthDiff||0))*3.2):group==="index"?Math.min(1.2,Math.abs(Number(context.relativeStrength||0))*2.5):group==="metal"?Math.min(1.0,Math.abs(Number(context.relativeStrength||0))*2):0,''')
# MARKET_SIGNAL eligibility for Forex + Metal + Index Cash, still signal-only and never broker-filled.
s=s.replace('const forexAdvisory=type==="forex"&&!pendingRetest&&mg?.pass&&Number(intel.methodFit||0)>=50&&Number(context.score||0)>=5.4&&Number.isFinite(Number(M15.close))&&quality.pass;\n    if(forexAdvisory)return {ok:true,status:"MARKET_SIGNAL",',
'''const advisoryFit=type==="forex"?50:type==="metal"?52:type==="index"?52:999,advisoryContext=type==="forex"?5.4:type==="metal"?5.5:5.4;
    const marketAdvisory=["forex","metal","index"].includes(type)&&!pendingRetest&&mg?.pass&&Number(intel.methodFit||0)>=advisoryFit&&Number(context.score||0)>=advisoryContext&&Number.isFinite(Number(M15.close))&&quality.pass;
    if(marketAdvisory)return {ok:true,status:"MARKET_SIGNAL",''')
# Provider/source language and any residual group strings.
s=s.replace('type==="future"?"Massive Futures analysis":"Twelve Data analysis"','type==="index"?"Twelve Data Index":"Twelve Data analysis"')
s=s.replace('source:"Twelve Data analysis",price:Number(M15.close)','source:type==="index"?"Twelve Data Index":"Twelve Data analysis",price:Number(M15.close)')
s=s.replace('source:"Twelve Data analysis",canonical:', 'source:type==="index"?"Twelve Data Index":"Twelve Data analysis",canonical:')
# Generic route/group conversions after future implementation has been removed.
s=s.replace('"future"','"index"').replace("'future'","'index'")
s=s.replace('📈 FUTURES','📊 INDEX CASH').replace('FUTURES','INDEX CASH')
s=s.replace('futureMinRR','indexMinRR')
# Remove leftover function calls/identifiers that should not survive cash-index migration.
for bad in ['runFutureGroup','runFutureSymbol','recentFutureScanAnalysis','futureSizing','FUTURE_SYMBOLS','FUTURE_SCAN','FUTURES_KNOWLEDGE','MASSIVE_API_KEY','Massive Futures']:
    if bad in s:
        print('LEFTOVER_ENGINE',bad)
p.write_text(s)

# --- Hub: replace Futures branch/buttons with Index Cash ---
p=Path('cloudflare-worker/hub-v77171.js'); h=p.read_text()
h=h.replace('const VERSION="V77.18.29",UI_REV="HUB-R4-LIVE-PNL",SERVICE="Trading V77.18.29 • Unified Live PnL UX";','const VERSION="V77.18.31",UI_REV="HUB-R5-INDEX-CASH",SERVICE="Trading V77.18.31 • Metal + Index Cash UX";')
h=h.replace('{text:"📈 Futures",callback_data:"signal:scan:future"}','{text:"📊 Index Cash",callback_data:"signal:scan:index"}')
h=h.replace('{text:"📈 Futures",callback_data:"symmarket:future"}','{text:"📊 Index Cash",callback_data:"symmarket:index"}')
h=h.replace('g==="metal"?"🥇 METAL":"📈 FUTURES"','g==="metal"?"🥇 METAL":"📊 INDEX CASH"')
h=h.replace('["crypto","forex","metal","future"]','["crypto","forex","metal","index"]')
h=h.replace('"future"','"index"').replace("'future'","'index'")
h=h.replace('Futures','Index Cash').replace('FUTURES','INDEX CASH')
p.write_text(h)

# --- Entrypoint: schedule Index Cash instead of Futures and version bump ---
p=Path('cloudflare-worker/index.js'); x=p.read_text()
x=x.replace('const VERSION="V77.18.30",SERVICE="Trading V77.18.30 Forex Opportunity Routing R3";\nconst RELEASE_NAME="Forex Opportunity Routing R3";','const VERSION="V77.18.31",SERVICE="Trading V77.18.31 Metal + Index Cash Migration";\nconst RELEASE_NAME="Metal + Index Cash Migration";')
x=x.replace('"future"','"index"').replace("'future'","'index'")
x=x.replace('Futures','Index Cash').replace('FUTURES','INDEX CASH')
x=x.replace('ensureDualAiIntervention(env,{version:"V77.18.30"','ensureDualAiIntervention(env,{version:"V77.18.31"')
p.write_text(x)

# --- Adaptive tuning: remove futures key, create index cash key ---
p=Path('cloudflare-worker/adaptive-tuning.js'); a=p.read_text()
a=a.replace('futureMinRR:1.43','indexMinRR:1.35').replace('futureMinRR:[1.40,1.50]','indexMinRR:[1.30,1.42]')
p.write_text(a)

# --- Claude: review Metal + Index Cash and stop proposing futures tuning ---
p=Path('cloudflare-worker/dual-ai-intervention.js'); d=p.read_text()
d=d.replace('const REVIEW_REV="FOREX_ENTRY_R3";','const REVIEW_REV="METAL_INDEX_CASH_R1";')
d=d.replace('FOREX ENTRY QUALITY IS THE FIRST PRIORITY FOR THIS REVIEW.', 'METAL + INDEX CASH QUALITY IS THE FIRST PRIORITY FOR THIS REVIEW. Futures have been intentionally removed from Signal. Index Cash universe is NAS100, US30, US500, DEX (mapped to DAX), and JP225 (mapped to N225). Audit provider-symbol mapping, index cash session routing, relative-strength context, Metal XAUUSD/XAGUSD session/context, HTF/location/trigger/RR gates, and duplicated gates. Preserve hard news/freshness/structural-SL safeguards. FOREX ENTRY QUALITY REMAINS IMPORTANT.')
d=d.replace('futureMinRR','indexMinRR')
d=d.replace('Perform FOREX_ENTRY_R3 first, then a compact Hub UX sanity review.','Perform METAL_INDEX_CASH_R1 first, then Forex and compact Hub UX sanity review.')
d=d.replace('lastAction:"FOREX_ENTRY_R3_AND_SYSTEM"','lastAction:"METAL_INDEX_CASH_R1_AND_SYSTEM"')
d=d.replace('🧠 CLAUDE • HUB UX R2','🧠 CLAUDE • METAL + INDEX CASH')
p.write_text(d)

# --- Canonical validator: lock new universe and explicitly reject old futures path ---
p=Path('.github/workflows/validate-cloudflare-v77.yml'); v=p.read_text()
v=v.replace("'V77.16.11','MARKET_SIGNAL','weightedFxMove','forexSessionBias','SIGNAL_ONLY'","'V77.16.12','MARKET_SIGNAL','weightedFxMove','forexSessionBias','metalSessionBias','indexSessionBias','INDEX_CASH','INDEX_PROVIDER','SIGNAL_ONLY'")
v=v.replace("['V77.18.30','Forex Opportunity Routing R3'","['V77.18.31','Metal + Index Cash Migration'")
v=v.replace("'HUB-R4-LIVE-PNL'","'HUB-R5-INDEX-CASH'")
v=v.replace("['FOREX_ENTRY_R3','hub_tuning'","['METAL_INDEX_CASH_R1','hub_tuning'")
v=v.replace("'FOREX ENTRY QUALITY IS THE FIRST PRIORITY'","'METAL + INDEX CASH QUALITY IS THE FIRST PRIORITY'")
v=v.replace("console.log('V77.18.30 Forex Opportunity Routing R3 validation PASS');","if(/FUTURE_SYMBOLS|FUTURE_SCAN|MASSIVE_API_KEY|Massive Futures|signal:scan:future|symmarket:future|futureMinRR/.test(engine+hub+index+adaptive+dual))throw new Error('Legacy Futures conflict remains');\n          for(const x of ['NAS100','US30','US500','DEX','JP225','NDX','DJI','SPX','DAX','N225'])if(!engine.includes(x))throw new Error('Index Cash mapping missing: '+x);\n          console.log('V77.18.31 Metal + Index Cash validation PASS');")
p.write_text(v)

print('PATCH_V771831_OK')
