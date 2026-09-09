from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text();a=A.read_text();g=G.read_text()

def rep(text,old,new,label):
    if old not in text:
        raise SystemExit('missing '+label)
    return text.replace(old,new)

# V3.20.1 identifies the liquidity-normalized build.
w=rep(w,'SIGNALHUB-V3-GATEWAY-3.20.0','SIGNALHUB-V3-GATEWAY-3.20.1','worker version')
a=rep(a,'private static final String APP_VERSION="3.20.0";','private static final String APP_VERSION="3.20.1";','app version')
g=rep(g,'versionCode 26','versionCode 27','version code')
g=rep(g,"versionName '3.20.0'","versionName '3.20.1'",'version name')
w=w.replace("versionCode: 26,\n  versionName: '3.20.0',","versionCode: 27,\n  versionName: '3.20.1',")
w=w.replace("title: 'SignalHub 3.20 Stable100 Continuous Universe'","title: 'SignalHub 3.20.1 Stable100 Liquidity Normalized'")
w=w.replace("artifactName: 'SignalHub-Android-v3.20.0-Stable100-Continuous'","artifactName: 'SignalHub-Android-v3.20.1-Stable100-LiquidityFix'")

# OKX SWAP `volCcy24h` is base-currency volume, not quote-USDT turnover.
# Convert base quantity to approximate quote turnover using last price before ranking/filtering.
bad="turnover24h:isFinitePositive(quoteVol)?quoteVol:(isFinitePositive(baseVol)&&isFinitePositive(last)?baseVol*last:null),volume24h:baseVol,openInterestValue:null,fundingRate:null"
good="turnover24h:isFinitePositive(quoteVol)&&isFinitePositive(last)?quoteVol*last:null,volume24h:quoteVol,contractVolume24h:baseVol,turnoverModel:'OKX_BASE_CCY_VOL_X_LAST',openInterestValue:null,fundingRate:null"
w=rep(w,bad,good,'OKX SWAP turnover normalization')

# Stamp the stable100 snapshot with the ranking model for observability.
old="const universe=buildStable100Universe(rows),payload={version:V3_VERSION,provider:snap?.provider||null,receivedAt:snap?.receivedAt||nowIso(),refreshedAt:nowIso(),target:STABLE100_SIZE,count:universe.length,symbols:universe.map(x=>x.symbol),rows:universe};"
new="const universe=buildStable100Universe(rows),payload={version:V3_VERSION,provider:snap?.provider||null,receivedAt:snap?.receivedAt||nowIso(),refreshedAt:nowIso(),target:STABLE100_SIZE,count:universe.length,ranking:'QUOTE_TURNOVER_THEN_OI_THEN_SPREAD_THEN_MOVE',turnoverNormalization:'OKX_SWAP_VOLCCY24H_X_LAST',symbols:universe.map(x=>x.symbol),rows:universe};"
w=rep(w,old,new,'stable100 observability')

# Release-note marker when present.
marker="'V3.20 continuously maintains a dynamic top-100 stable USDT perpetual universe. All 100 are refreshed at ticker/liquidity level each server maintenance cycle and on-demand scan; deep candle analysis rotates through the universe while preserving a high-liquidity core.',"
if marker in w:
    w=w.replace(marker,"'V3.20.1 normalizes OKX swap base-currency 24h volume into quote-USDT turnover before liquidity ranking, preventing tiny-price high-token-count markets from being falsely ranked as the deepest markets.',\n    "+marker,1)

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.20.1 OKX liquidity normalization')
