from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text(); a=A.read_text(); g=G.read_text()

def rep(text,old,new,label):
    if old not in text:
        raise SystemExit('missing '+label)
    return text.replace(old,new)

# Version bump after V3.19 + V3.19.1 patches.
w=rep(w,"SIGNALHUB-V3-GATEWAY-3.19.1","SIGNALHUB-V3-GATEWAY-3.20.0",'worker version')
a=rep(a,'private static final String APP_VERSION="3.19.1";','private static final String APP_VERSION="3.20.0";','app version')
g=rep(g,'versionCode 25','versionCode 26','version code')
g=rep(g,"versionName '3.19.1'","versionName '3.20.0'",'version name')
w=w.replace("versionCode: 25,\n  versionName: '3.19.1',","versionCode: 26,\n  versionName: '3.20.0',")
w=w.replace("title: 'SignalHub 3.19.1 Stable Reference Coverage'","title: 'SignalHub 3.20 Stable100 Continuous Universe'")
w=w.replace("artifactName: 'SignalHub-Android-v3.19.1-10Scalp-5Swing-StableUniverse'","artifactName: 'SignalHub-Android-v3.20.0-Stable100-Continuous'")
a=a.replace('CRYPTO • 10 SCALP + 5 SWING','CRYPTO • TOP 100 • 10 SCALP + 5 SWING')

# Portfolio policy: active book remains 10 SCALP + 5 SWING, with a deeper hot-spare pool.
policy_old="standbyPerStyle:12,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'FULL_LIVE_PROVIDER_SNAPSHOT_EVERY_CRON_AND_REFILL'"
policy_new="standbyPerStyle:20,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STABLE_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES'"
w=rep(w,policy_old,policy_new,'portfolio stable100 metadata')

# Dynamic top-100 stable/liquid market universe. This broad universe is refreshed from every live ticker snapshot.
# The existing stricter per-style liquidity filter still decides which coin may occupy a SCALP/SWING signal slot.
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

# A neutral secondary venue may keep a conditional LIMIT/STOP candidate. Only a directly opposing
# secondary context rejects that pending reference. MARKET confirmation rules are not relaxed.
w=w.replace("setup.technicalAtIssue.crossMomentum=sec.momentum;setup.crossProviderConfirmation=confirmed;",
            "setup.technicalAtIssue.crossMomentum=sec.momentum;setup.technicalAtIssue.crossOpposing=opposing;setup.crossProviderConfirmation=confirmed;")
w=rep(w,"if(setup.referenceFallback&&checked&&!setup.crossProviderConfirmation)return null;",
      "if(setup.referenceFallback&&checked&&setup.technicalAtIssue?.crossOpposing===true)return null;",'neutral secondary pending rule')

# Anchor-based replacement so the V3.20 patch is resilient to compact formatting in generated V3.19.1 source.
scan_fn=w.index('async function scanCrypto')
sel_start=w.index('const all=snap.rows',scan_fn)
raw_start=w.index('const rawAnalyses=',sel_start)
indent=w[w.rfind('\n',0,sel_start)+1:sel_start]
scan_new=(
    "const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);\n"
    +indent+"const liquid=stable100.filter(x=>stableUniverseEligible(x,style));\n"
    +indent+"const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(72,liquid.length):Math.min(52,liquid.length)):(styleUnderfilled?Math.min(58,liquid.length):Math.min(42,liquid.length));\n"
    +indent+"const ranked=rotatingStableCandidates(liquid,style,rankedLimit);\n"
    +indent
)
w=w[:sel_start]+scan_new+w[raw_start:]

# Expose universe telemetry in scan response if the compact response marker is present.
tele_old='scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,'
tele_new='scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,stable100Symbols:stable100.map(x=>x.symbol),liquidUniverse:liquid.length,deepAnalyzed:ranked.length,'
if tele_old in w[scan_fn:]:
    before=w[:scan_fn]; after=w[scan_fn:].replace(tele_old,tele_new,1); w=before+after

# Existing one-minute cron calls this maintenance function. Refresh both style pools every cycle,
# and promote a hot spare immediately whenever a style falls below its 10/5 target.
maint_start=w.index('async function cryptoOnlyMaintenance')
maint_end=w.index('async function exnessQuoteMap',maint_start)
maint_new="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'REFILL_TO_TARGET':'STABLE100_ROTATION_REFRESH'}`);
    await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<target){await promoteCryptoStandby(env,style,'CONTINUOUS_STABLE100_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'STABLE100_CONTINUOUS',stableUniverse:await readStable100(env),attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}

"""
w=w[:maint_start]+maint_new+w[maint_end:]

# Read-only universe endpoint for diagnostics/app display; it does not consume an active signal slot.
route_needle="if(path==='/v3/crypto/tickers')return cryptoTickers(url,env);"
if route_needle not in w: raise SystemExit('crypto ticker route missing')
w=w.replace(route_needle,route_needle+"\n    if(path==='/v3/crypto/stable100'){const cached=await readStable100(env);if(cached)return json({ok:true,...cached});const snap=await loadCryptoSnapshot(env),rows=await persistStable100(env,snap,snap.rows);return json({ok:true,version:V3_VERSION,provider:snap.provider,receivedAt:snap.receivedAt,refreshedAt:nowIso(),target:STABLE100_SIZE,count:rows.length,symbols:rows.map(x=>x.symbol),rows});}",1)

marker="'V3.19 targets exactly 10 SCALP + 5 SWING active reference signals, counting both OPEN market entries and PENDING LIMIT/STOP entries.',"
if marker in w:
    w=w.replace(marker,"'V3.20 continuously maintains a dynamic top-100 stable USDT perpetual universe. All 100 are refreshed at ticker/liquidity level each server maintenance cycle and on-demand scan; deep candle analysis rotates through the universe while preserving a high-liquidity core.',\n    'V3.20 keeps 20 hot-spare candidates per style and continuously refills toward 10 SCALP + 5 SWING without forcing weak-liquidity or MARKET fallback entries.',\n    "+marker,1)

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.20 stable100 continuous universe')
