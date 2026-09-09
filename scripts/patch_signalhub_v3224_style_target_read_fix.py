from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
android=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
gradle=Path('signalhub-android/app/build.gradle')
w=worker.read_text();a=android.read_text();g=gradle.read_text()

# V3.22.3 production proved scan/refill could create an active book, but the app-facing
# /v3/signals read path still used the old generic targetActivePerStyle=10. SWING is
# intentionally capped at 5, so every SWING read saw 5 < 10 and synchronously launched
# repeated deep scans. The production audit then timed out at 30s even though the book
# itself was healthy. Use the canonical per-style target everywhere on the read path.
old="""  if(status==='active'&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle){
    for(let attempt=0;attempt<3&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle;attempt++){
      await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL').catch(()=>{});await scanCrypto(env,style).catch(()=>{});await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL_AFTER_SCAN').catch(()=>{});
      let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
    }
  }
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,targetActive:PORTFOLIO_POLICY.targetActivePerStyle,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
"""
new="""  const targetActive=styleTarget(style);
  if(status==='active'&&rows.length<targetActive){
    // One bounded refill attempt is enough for an interactive read. Continuous/server
    // maintenance owns deeper refill work; the app request must stay responsive.
    await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL').catch(()=>{});
    let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
    if(rows.length<targetActive&&ctx?.waitUntil){
      ctx.waitUntil(Promise.resolve(scanCrypto(env,style)).then(()=>promoteCryptoStandby(env,style,'ACTIVE_READ_BACKGROUND_REFILL')).catch(()=>{}));
    }
  }
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,targetActive,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
"""
assert old in w, 'V3.22.3 unifiedSignals target/refill block not found'
w=w.replace(old,new,1)

# Version identity after the V3.22.2 + V3.22.3 patches are applied by CI.
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.3','SIGNALHUB-V3-GATEWAY-3.22.4')
w=w.replace("versionName: '3.22.3'","versionName: '3.22.4'")
w=w.replace("title: 'SignalHub 3.22.3 Active Refill Recovery'","title: 'SignalHub 3.22.4 Responsive Style Target Read'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.3-Active-Refill-Recovery'","artifactName: 'SignalHub-Android-v3.22.4-Responsive-Style-Target-Read'")
needle='  notes: [\n'
if 'V3.22.4 fixes the app-facing SWING target mismatch' not in w:
    w=w.replace(needle,needle+"    'V3.22.4 fixes the app-facing SWING target mismatch: active reads now use the canonical 10 SCALP / 5 SWING targets instead of forcing both styles toward 10.',\n    'V3.22.4 keeps deep refill asynchronous from interactive signal reads, preventing the 30-second app/API timeout while continuous maintenance still restores missing slots.',\n",1)

a=a.replace('APP_VERSION=\"3.22.3\"','APP_VERSION=\"3.22.4\"').replace('SignalHub 3.22.3','SignalHub 3.22.4')
g=g.replace('versionCode 32','versionCode 33').replace("versionName '3.22.3'","versionName '3.22.4'")

worker.write_text(w);android.write_text(a);gradle.write_text(g)

assert 'const targetActive=styleTarget(style);' in w
assert "rows.length<targetActive" in w
assert "ACTIVE_READ_BACKGROUND_REFILL" in w
assert 'SIGNALHUB-V3-GATEWAY-3.22.4' in w
assert 'APP_VERSION=\"3.22.4\"' in a
assert 'versionCode 33' in g and "versionName '3.22.4'" in g
print('patched SignalHub V3.22.4 responsive style target read')
