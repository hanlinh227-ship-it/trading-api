from pathlib import Path

worker = Path('signalhub-worker/gateway-v3.js')
android = Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
gradle = Path('signalhub-android/app/build.gradle')

w = worker.read_text()
a = android.read_text()
g = gradle.read_text()

# 1) Repair the production blocker: scanCrypto() calls analyzeCryptoBatch(),
# but the V3.22.1 patch chain did not emit that helper.  A missing runtime symbol
# caused /v3/scan to throw and left the active portfolio empty.
if 'async function analyzeCryptoBatch(' not in w:
    marker = 'async function scanCrypto(env,style){'
    assert marker in w, 'scanCrypto marker missing'
    helper = r'''async function analyzeCryptoBatch(rows,style,concurrency=6){
  const source=Array.isArray(rows)?rows.filter(Boolean):[];
  if(!source.length)return[];
  const out=new Array(source.length).fill(null);let cursor=0;
  const workers=Math.max(1,Math.min(Number(concurrency)||6,source.length,8));
  async function run(){
    while(true){
      const i=cursor++;if(i>=source.length)return;
      try{out[i]=await analyzeCryptoCandidate(source[i],style);}catch(e){out[i]=null;}
    }
  }
  await Promise.all(Array.from({length:workers},()=>run()));
  return out.filter(Boolean);
}

'''
    w = w.replace(marker, helper + marker, 1)

# 2) Make scan failures observable instead of silently producing an empty UI.
old = "async function scanRoute(url,env,ctx){\n  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);\n  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';return json(await scanCrypto(env,style));\n}"
new = "async function scanRoute(url,env,ctx){\n  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);\n  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';\n  try{const body=await scanCrypto(env,style);return json(body,body?.ok===false?503:200);}\n  catch(e){return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,error:'SCAN_RUNTIME_ERROR',detail:String(e?.message||e),portfolio:await realtimePortfolioSnapshot(env).catch(()=>null)},503);}\n}"
assert old in w, 'scanRoute contract changed unexpectedly'
w = w.replace(old, new, 1)

# 3) Version bump so the Android client and production identity can be audited.
w = w.replace("SIGNALHUB-V3-GATEWAY-3.22.1", "SIGNALHUB-V3-GATEWAY-3.22.2")
w = w.replace("versionName: '3.22.1'", "versionName: '3.22.2'")
w = w.replace("title: 'SignalHub 3.22.1 Universe Watch + Resilient Read'", "title: 'SignalHub 3.22.2 Scan Refill Recovery'")
w = w.replace("artifactName: 'SignalHub-Android-v3.22.1-Universe-Watch-Resilient-Read'", "artifactName: 'SignalHub-Android-v3.22.2-Scan-Refill-Recovery'")

# Add a release note only once.
needle = "  notes: [\n"
if "V3.22.2 repairs the missing analyzeCryptoBatch runtime helper" not in w:
    w = w.replace(needle, needle + "    'V3.22.2 repairs the missing analyzeCryptoBatch runtime helper that caused /v3/scan HTTP 500 and empty active books; batch analysis is now bounded-concurrency and isolates per-symbol failures.',\n    'V3.22.2 production audit fails unless both SCALP and SWING scans return ok and the live portfolio contains at least one active signal in each style after refill attempts.',\n", 1)

# Android identity only; signal rendering/data model stays unchanged.
a = a.replace('APP_VERSION="3.22.1"', 'APP_VERSION="3.22.2"')
a = a.replace('SignalHub 3.22.1', 'SignalHub 3.22.2')

g = g.replace('versionCode 30', 'versionCode 31')
g = g.replace("versionName '3.22.1'", "versionName '3.22.2'")

worker.write_text(w)
android.write_text(a)
gradle.write_text(g)

assert 'async function analyzeCryptoBatch(' in w
assert "error:'SCAN_RUNTIME_ERROR'" in w
assert 'SIGNALHUB-V3-GATEWAY-3.22.2' in w
assert 'APP_VERSION="3.22.2"' in a
assert 'versionCode 31' in g and "versionName '3.22.2'" in g
print('patched SignalHub V3.22.2 scan/refill recovery')
