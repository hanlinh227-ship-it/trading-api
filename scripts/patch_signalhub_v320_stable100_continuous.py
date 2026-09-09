from pathlib import Path
import re

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text(); a=A.read_text(); g=G.read_text()

def rep(text,old,new,label):
    if old not in text:
        raise SystemExit('missing '+label)
    return text.replace(old,new)

def sub1(text,pattern,repl,label,flags=0):
    out,n=re.subn(pattern,repl,text,count=1,flags=flags)
    if n!=1:
        raise SystemExit(f'missing {label} matches={n}')
    return out

# Version bump after V3.19 + V3.19.1 patches.
w=rep(w,"SIGNALHUB-V3-GATEWAY-3.19.1","SIGNALHUB-V3-GATEWAY-3.20.0",'worker version')
a=rep(a,'private static final String APP_VERSION="3.19.1";','private static final String APP_VERSION="3.20.0";','app version')
g=rep(g,'versionCode 25','versionCode 26','version code')
g=rep(g,"versionName '3.19.1'","versionName '3.20.0'",'version name')
w=w.replace("versionCode: 25,\n  versionName: '3.19.1',","versionCode: 26,\n  versionName: '3.20.0',")
w=w.replace("title: 'SignalHub 3.19.1 Stable Reference Coverage'","title: 'SignalHub 3.20 Stable100 Continuous Universe'")
w=w.replace("artifactName: 'SignalHub-Android-v3.19.1-10Scalp-5Swing-StableUniverse'","artifactName: 'SignalHub-Android-v3.20.0-Stable100-Continuous'")
a=a.replace('CRYPTO • 10 SCALP + 5 SWING','CRYPTO • TOP 100 • 10 SCALP + 5 SWING')

# Portfolio policy: active book remains 10 SCALP + 5 SWING, but a larger reserve pool is maintained.
policy_old="standbyPerStyle:12,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'FULL_LIVE_PROVIDER_SNAPSHOT_EVERY_CRON_AND_REFILL'"
policy_new="standbyPerStyle:20,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STABLE_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES'"
w=rep(w,policy_old,policy_new,'portfolio stable100 metadata')

# Dynamic top-100 stable/liquid market universe. This is a broad universe guard; stricter per-style
# SCALP/SWING filters still apply before a signal can occupy an active slot.
needle='function signalLiquidityFacts(s){'
if needle not in w: raise SystemExit('signalLiquidityFacts needle missing')
helper=r'''const STABLE100_SIZE=100;
const STABLE100_CACHE_KEY='v320:crypto:stable100';
function stable100Eligible(t){
  if(!t||!(Number(t.lastPrice)>0))return false;
  const symbol=canonical(t.symbol),base=symbol.replace(/USDT$/,''),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Math.abs(Number(t.change24hPct||0)),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  if(!symbol.endsWith('USDT')||STABLE_BASE_EXCLUDE.has(base))return false;
  if(turn<20_000_000||spread<0||spread>15||move>35)return false;
  if(oi!=null&&Number.isFinite(oi)&&oi>0&&oi<1_000_000)return false;
  if(fund!=null&&Number.isFinite(fund)&&fund>.008)return false;
  return true;
}
function stable100Compare(a,b){
  const at=Number(a.turnover24h||0),bt=Number(b.turnover24h||0);if(at!==bt)return bt-at;
  const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;
  const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;
  const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;
  return String(a.symbol||'').localeCompare(String(b.symbol||''));
}
function buildStable100Universe(rows){return (rows||[]).filter(stable100Eligible).sort(stable100Compare).slice(0,STABLE100_SIZE);}
async function persistStable100(env,snap,rows){
  const universe=buildStable100Universe(rows),payload={version:V3_VERSION,provider:snap?.provider||null,receivedAt:snap?.receivedAt||nowIso(),refreshedAt:nowIso(),target:STABLE100_SIZE,count:universe.length,symbols:universe.map(x=>x.symbol),rows:universe};
  if(env?.SIGNALS_KV)await env.SIGNALS_KV.put(STABLE100_CACHE_KEY,JSON.stringify(payload),{expirationTtl:180});
  return universe;
}
async function readStable100(env){
  if(!env?.SIGNALS_KV)return null;const raw=await env.SIGNALS_KV.get(STABLE100_CACHE_KEY);if(!raw)return null;try{return JSON.parse(raw)}catch{return null;}
}
function rotatingStableCandidates(rows,style,limit){
  const sorted=[...(rows||[])].sort(stableUniverseCompare),n=sorted.length;if(n<=limit)return sorted;
  const coreCount=Math.min(style==='SWING'?14:18,Math.max(8,Math.floor(limit*.35))),core=sorted.slice(0,coreCount),rest=sorted.slice(coreCount);
  const wanted=Math.max(0,limit-core.length),epoch=Math.floor(Date.now()/60000),offset=rest.length?((epoch*(style==='SWING'?17:23))%rest.length):0,rot=[];
  for(let i=0;i<Math.min(wanted,rest.length);i++)rot.push(rest[(offset+i)%rest.length]);
  return [...core,...rot];
}
'''
w=w.replace(needle,helper+needle,1)

# A secondary venue that is neutral must not discard a stable pending LIMIT/STOP reference.
# Only a directly opposing secondary context rejects that pending idea. This does not relax MARKET confirmation.
w=w.replace("setup.technicalAtIssue.crossMomentum=sec.momentum;setup.crossProviderConfirmation=confirmed;",
            "setup.technicalAtIssue.crossMomentum=sec.momentum;setup.technicalAtIssue.crossOpposing=opposing;setup.crossProviderConfirmation=confirmed;")
w=rep(w,"if(setup.referenceFallback&&checked&&!setup.crossProviderConfirmation)return null;",
      "if(setup.referenceFallback&&checked&&setup.technicalAtIssue?.crossOpposing===true)return null;",'neutral secondary pending rule')

# Replace the V3.19.1 selection block robustly. All live tickers are reviewed into stable100 each scan;
# deeper candles use a liquidity core plus rotating coverage to avoid exchange API bursts.
scan_pattern=r"const all=snap\.rows,portfolio=await realtimePortfolioSnapshot\(env\),styleUnderfilled=Number\(portfolio\.styles\?\.\[style\]\|\|0\)<styleTarget\(style\);\s*const liquid=all\.filter\(x=>stableUniverseEligible\(x,style\)\);\s*const rankedLimit=style==='SCALP'\?\(styleUnderfilled\?Math\.min\(64,liquid\.length\):32\):\(styleUnderfilled\?Math\.min\(44,liquid\.length\):24\);\s*const ranked=liquid\.sort\(stableUniverseCompare\)\.slice\(0,rankedLimit\);"
scan_new="""const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);
  const liquid=stable100.filter(x=>stableUniverseEligible(x,style));
  const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(72,liquid.length):Math.min(52,liquid.length)):(styleUnderfilled?Math.min(58,liquid.length):Math.min(42,liquid.length));
  const ranked=rotatingStableCandidates(liquid,style,rankedLimit);"""
w=sub1(w,scan_pattern,scan_new,'scan stable100 selection')

# Expose universe telemetry on scan response.
resp_pattern=r"scanned:all\.length,liquidUniverse:liquid\.length,deepAnalyzed:ranked\.length,"
w=sub1(w,resp_pattern,"scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,stable100Symbols:stable100.map(x=>x.symbol),liquidUniverse:liquid.length,deepAnalyzed:ranked.length,",'scan telemetry')

# Maintenance runs every existing one-minute server cron. It refreshes both style pools and promotes a hot spare
# immediately when the realtime portfolio is below the style target.
maint_pattern=r"async function cryptoOnlyMaintenance\(env\)\{.*?\n\}\n\nasync function exnessQuoteMap"
maint_new="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'REFILL_TO_TARGET':'STABLE100_ROTATION_REFRESH'}`);
    await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<target){await promoteCryptoStandby(env,style,'CONTINUOUS_STABLE100_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'STABLE100_CONTINUOUS',stableUniverse:await readStable100(env),attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}

async function exnessQuoteMap"""
w=sub1(w,maint_pattern,maint_new,'maintenance loop',re.S)

# Read-only endpoint for app/diagnostics; it never consumes an active trading slot.
route_needle="if(path==='/v3/crypto/tickers')return cryptoTickers(url,env);"
if route_needle not in w: raise SystemExit('crypto ticker route missing')
w=w.replace(route_needle,route_needle+"\n    if(path==='/v3/crypto/stable100'){const cached=await readStable100(env);if(cached)return json({ok:true,...cached});const snap=await loadCryptoSnapshot(env),rows=await persistStable100(env,snap,snap.rows);return json({ok:true,version:V3_VERSION,provider:snap.provider,receivedAt:snap.receivedAt,refreshedAt:nowIso(),target:STABLE100_SIZE,count:rows.length,symbols:rows.map(x=>x.symbol),rows});}",1)

# Release notes, if the marker exists in the generated base.
marker="'V3.19 targets exactly 10 SCALP + 5 SWING active reference signals, counting both OPEN market entries and PENDING LIMIT/STOP entries.',"
if marker in w:
    w=w.replace(marker,"'V3.20 continuously maintains a dynamic top-100 stable USDT perpetual universe. All 100 are refreshed at ticker/liquidity level each server maintenance cycle and on-demand scan; deep candle analysis rotates through the universe while preserving a high-liquidity core.',\n    'V3.20 keeps 20 hot-spare candidates per style and continuously refills toward 10 SCALP + 5 SWING without forcing weak-liquidity or MARKET fallback entries.',\n    "+marker,1)

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.20 stable100 continuous universe')
