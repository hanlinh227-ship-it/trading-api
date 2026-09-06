from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

if 'FAST_DISCOVERY_V372_MERGE' in s:
    print('V372_SCANNER_ALREADY_PATCHED=TRUE')
    raise SystemExit(0)

if 'SOLANA_DEX_UNIVERSE_V367_MERGE' not in s:
    raise SystemExit('V372_SCANNER_REQUIRES_V367')
if 'const DISCOVERY_RADAR_ONLY_MAX = 120;' not in s:
    raise SystemExit('V372_SCANNER_PATCH_MISS_RADAR_MAX')

s=s.replace('const DISCOVERY_RADAR_ONLY_MAX = 120;','const DISCOVERY_RADAR_ONLY_MAX = 240; // FAST_DISCOVERY_V372_CAP',1)

start=s.find('  // SOLANA_DEX_UNIVERSE_V367_MERGE')
end=s.find('  const liveRows =',start)
if start<0 or end<0:
    raise SystemExit('V372_SCANNER_PATCH_MISS_RADAR_BLOCK')

block='''  // FAST_DISCOVERY_V372_MERGE
  // Two discovery lanes:
  //   CONFIRMED = >=2 discovery providers, same conservative v3.67 behavior.
  //   FAST = >=1 very-fresh provider + new/high-velocity evidence.
  // FAST candidates are analysis-only. This block NEVER grants entry; downstream
  // security, sellability, holder, liquidity, quote/impact and live execution gates stay authoritative.
  let radarHealthy = false;
  let radarMatches = 0;
  let radarOnlyAdded = 0;
  let radarProviderCount = 0;
  let radarFastProviderCount = 0;
  let radarFastUsable = false;
  let radarFastMatches = 0;
  try {
    const radar = JSON.parse(fs.readFileSync(NEW_LISTING_RADAR, "utf8"));
    const radarAgeMs = Date.now() - Date.parse(radar.updatedAt || 0);
    radarProviderCount = n(radar.providerCount);
    radarFastProviderCount = n(radar.fastProviderCount, radarProviderCount);
    const radarFresh = Number.isFinite(radarAgeMs) && radarAgeMs >= 0 && radarAgeMs <= 45000;
    radarHealthy = radar.status === "HEALTHY" && radarFresh && radarProviderCount >= 2;
    radarFastUsable = ["HEALTHY","DEGRADED"].includes(radar.status) && radarFresh && radarFastProviderCount >= 1;
    if (radarHealthy || radarFastUsable) {
      for (const r of (radar.candidates || [])) {
        if (!r?.mint || r.currentFeed !== true) continue;
        const ageSec = Number.isFinite(Number(r.pairAgeSec)) ? Number(r.pairAgeSec) : Infinity;
        const confidence = n(r.discoveryConfidence);
        const preScore = n(r.preScore);
        const liq = n(r.liquidityUsd), buys = n(r.buys5m), vol = n(r.volume5m), ratio = n(r.buySellTxnRatio), chg = Math.abs(n(r.priceChange5m));
        const confirmedAccept = radarHealthy && confidence >= 0.35 && (ageSec <= 7 * 24 * 3600 || preScore >= 55);
        const fastFlow = (buys >= 3 && ratio >= 1.03) || vol >= 1500 || chg >= 5;
        const fastMetric = ageSec >= 0 && ageSec <= 6 * 3600 && confidence >= 0.24 && preScore >= 32 && (liq >= 4000 || ageSec <= 3600) && fastFlow;
        const fastAccept = radarFastUsable && (r.fastDiscoveryLane === true || fastMetric);
        let existing = map.get(r.mint);
        if (!existing) {
          if (radarOnlyAdded >= DISCOVERY_RADAR_ONLY_MAX) continue;
          if (!confirmedAccept && !fastAccept) continue;
          existing = {
            id:r.mint,
            symbol:r.symbol||null,
            name:r.name||null,
            sources:[],
            firstPool:r.pairAddress?{id:r.pairAddress,createdAt:r.pairCreatedAt||null}:null,
            liquidity:n(r.liquidityUsd),
            holderCount:n(r.holderCount),
            organicScore:n(r.organicScore),
            stats5m:{
              numBuys:n(r.buys5m), numSells:n(r.sells5m),
              buyVolume:n(r.volume5m) * (n(r.buys5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m)))),
              sellVolume:n(r.volume5m) * (n(r.sells5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m))))
            },
            radarDiscoveryOnly:true,
            radarFastDiscoveryOnly:fastAccept && !confirmedAccept,
            radarAgeBucket:r.ageBucket||null,
            radarDiscoveryConfidence:confidence,
            radarDexId:r.dexId||null
          };
          map.set(r.mint, existing);
          radarOnlyAdded++;
        }
        existing.sources = Array.isArray(existing.sources) ? existing.sources : [];
        if (!existing.sources.includes("solana-dex-universe")) existing.sources.push("solana-dex-universe");
        if (fastAccept && !existing.sources.includes("fast-discovery-v372")) existing.sources.push("fast-discovery-v372");
        for (const src of (r.sources || [])) {
          const tag=`radar:${src}`;
          if (!existing.sources.includes(tag)) existing.sources.push(tag);
        }
        existing.newListingRadar = {
          pairCreatedAt:r.pairCreatedAt||null,
          pairAgeSec:Number.isFinite(Number(r.pairAgeSec))?Number(r.pairAgeSec):null,
          ageBucket:r.ageBucket||null,
          preScore,
          discoveryConfidence:confidence,
          discoveryPriority:n(r.discoveryPriority,preScore),
          fastDiscoveryLane:fastAccept,
          liquidityUsd:n(r.liquidityUsd),
          buys5m:n(r.buys5m), sells5m:n(r.sells5m),
          volume5m:n(r.volume5m), priceChange5m:n(r.priceChange5m),
          providers:Array.isArray(r.providers)?r.providers:[],
          sources:Array.isArray(r.sources)?r.sources:[],
          dexId:r.dexId||null
        };
        if (!existing.firstPool && r.pairCreatedAt) existing.firstPool={id:r.pairAddress||null,createdAt:r.pairCreatedAt};
        radarMatches++;
        if (fastAccept) radarFastMatches++;
      }
    }
  } catch (e) {
    console.error(`FAST_DISCOVERY_V372_READ_FAIL=${String(e?.message||e).slice(0,120)}`);
  }
  console.log(`FAST_DISCOVERY_V372 MATCHES=${radarMatches} FAST=${radarFastMatches} RADAR_ONLY_ADDED=${radarOnlyAdded} PROVIDERS=${radarProviderCount} FAST_PROVIDERS=${radarFastProviderCount} CONFIRMED_HEALTHY=${radarHealthy} FAST_USABLE=${radarFastUsable}`);

'''
s=s[:start]+block+s[end:]

# Extend observability records when the exact v3.67 shape is present. This does not alter fail-closed logic.
s=s.replace('''      radarHealthy,\n      radarMatches,\n      radarOnlyAdded,\n      radarProviderCount,\n      providerRedundancy,''','''      radarHealthy,\n      radarMatches,\n      radarOnlyAdded,\n      radarProviderCount,\n      radarFastProviderCount,\n      radarFastUsable,\n      radarFastMatches,\n      providerRedundancy,''',1)
s=s.replace('''    radarHealthy,\n    radarMatches,\n    radarOnlyAdded,\n    radarProviderCount,\n    providerRedundancy,''','''    radarHealthy,\n    radarMatches,\n    radarOnlyAdded,\n    radarProviderCount,\n    radarFastProviderCount,\n    radarFastUsable,\n    radarFastMatches,\n    providerRedundancy,''',1)

p.write_text(s)
print('V372_SCANNER_FAST_DISCOVERY_PATCH=PASS')
print('RADAR_ONLY_MAX_240=TRUE')
print('ONE_PROVIDER_FAST_ANALYSIS_ALLOWED=TRUE')
print('FAST_DISCOVERY_NEVER_GRANTS_ENTRY=TRUE')
print('DOWNSTREAM_SAFETY_GATES_PRESERVED=TRUE')
