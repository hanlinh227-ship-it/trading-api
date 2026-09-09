from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
android=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
gradle=Path('signalhub-android/app/build.gradle')
w=worker.read_text();a=android.read_text();g=gradle.read_text()

# Underfilled books must still be able to generate a structure-derived pending setup.
# V3.22.1 already contains buildStableReferenceSetup(), but analyzeCryptoCandidate()
# returned null before ever using it. This made every quiet/mixed market disappear
# from the active refill path even when a safe pending LIMIT/STOP plan was available.
old="const setup=buildCryptoSetup(t,style,stats);if(!setup)return null;"
new="let setup=buildCryptoSetup(t,style,stats);if(!setup)setup=buildStableReferenceSetup(t,style,stats);if(!setup)return null;"
assert old in w, 'analyzeCryptoCandidate setup marker missing'
w=w.replace(old,new,1)

# Ensure conditional/reference setups can be inspected in scan diagnostics without
# weakening hard liquidity, spread, invalidation, target-path or reachability checks.
old2="const rawAnalyses=await analyzeCryptoBatch(ranked,style,6),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);"
new2="const rawAnalyses=await analyzeCryptoBatch(ranked,style,6),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority),assessmentFailures=assessed.filter(x=>x.entryAssessment.verdict!=='PASS').slice(0,12).map(x=>({symbol:x.symbol,coverageFallback:Boolean(x.coverageFallback),orderType:x.orderType,failed:x.entryAssessment.failed||[]}));"
assert old2 in w, 'scan assessment marker missing'
w=w.replace(old2,new2,1)
old3="rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length"
new3="rejectedByAssessment:rawAnalyses.length-analyses.length,assessmentFailures,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length"
assert old3 in w, 'scan response marker missing'
w=w.replace(old3,new3,1)

# Version identity after V3.22.2 patch has been applied by CI.
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.2','SIGNALHUB-V3-GATEWAY-3.22.3')
w=w.replace("versionName: '3.22.2'","versionName: '3.22.3'")
w=w.replace("title: 'SignalHub 3.22.2 Scan Refill Recovery'","title: 'SignalHub 3.22.3 Active Refill Recovery'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.2-Scan-Refill-Recovery'","artifactName: 'SignalHub-Android-v3.22.3-Active-Refill-Recovery'")
needle='  notes: [\n'
if 'V3.22.3 reconnects the existing stable-liquid reference pending builder' not in w:
    w=w.replace(needle,needle+"    'V3.22.3 reconnects the existing stable-liquid reference pending builder to the real scan/refill path. When strict immediate structure is absent, the engine may emit only a hard-safety-passing structure-derived LIMIT/STOP wait setup; it does not force a MARKET trade.',\n    'V3.22.3 keeps liquidity, spread, invalidation, target path and pending reachability hard checks and adds scan rejection diagnostics for production audit.',\n",1)

a=a.replace('APP_VERSION="3.22.2"','APP_VERSION="3.22.3"').replace('SignalHub 3.22.2','SignalHub 3.22.3')
g=g.replace('versionCode 31','versionCode 32').replace("versionName '3.22.2'","versionName '3.22.3'")

worker.write_text(w);android.write_text(a);gradle.write_text(g)
assert 'buildStableReferenceSetup(t,style,stats)' in w
assert 'assessmentFailures' in w
assert 'SIGNALHUB-V3-GATEWAY-3.22.3' in w
assert 'APP_VERSION="3.22.3"' in a
assert 'versionCode 32' in g and "versionName '3.22.3'" in g
print('patched SignalHub V3.22.3 active refill recovery')
