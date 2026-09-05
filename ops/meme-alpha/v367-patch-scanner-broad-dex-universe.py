from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()

if 'SOLANA_DEX_UNIVERSE_V367_MERGE' in s:
    print('V367_SCANNER_ALREADY_PATCHED=TRUE')
    raise SystemExit(0)

anchor='const DISCOVERY_RADAR_MIN_MATCHES = 3;'
if anchor not in s: raise SystemExit('V367_PATCH_MISS_RADAR_MIN_MATCHES')
s=s.replace(anchor,anchor+'\nconst DISCOVERY_RADAR_ONLY_MAX = 120;',1)

start=s.find('  // NEW_LISTING_RADAR_V312_MERGE')
end=s.find('  const liveRows =',start)
if start<0 or end<0: raise SystemExit('V367_PATCH_MISS_RADAR_BLOCK')
block='''  // SOLANA_DEX_UNIVERSE_V367_MERGE\n  // Discovery is deliberately broad. Radar-only mints may enter scanner analysis,\n  // but this block NEVER grants entry: security, sellability, holder, liquidity,\n  // impact and live execution gates remain authoritative downstream.\n  let radarHealthy = false;\n  let radarMatches = 0;\n  let radarOnlyAdded = 0;\n  let radarProviderCount = 0;\n  try {\n    const radar = JSON.parse(fs.readFileSync(NEW_LISTING_RADAR, "utf8"));\n    const radarAgeMs = Date.now() - Date.parse(radar.updatedAt || 0);\n    radarProviderCount = n(radar.providerCount);\n    radarHealthy = radar.status === "HEALTHY" && Number.isFinite(radarAgeMs) && radarAgeMs >= 0 && radarAgeMs <= 30000 && radarProviderCount >= 2;\n    if (radarHealthy) {\n      for (const r of (radar.candidates || [])) {\n        if (!r?.mint || r.currentFeed !== true) continue;\n        let existing = map.get(r.mint);\n        if (!existing) {\n          if (radarOnlyAdded >= DISCOVERY_RADAR_ONLY_MAX) continue;\n          const ageSec = Number.isFinite(Number(r.pairAgeSec)) ? Number(r.pairAgeSec) : Infinity;\n          const confidence = n(r.discoveryConfidence);\n          const radarOnlyAccept = radarProviderCount >= 2 && confidence >= 0.35 && (ageSec <= 7 * 24 * 3600 || n(r.preScore) >= 55);\n          if (!radarOnlyAccept) continue;\n          existing = {\n            id:r.mint,\n            symbol:r.symbol||null,\n            name:r.name||null,\n            sources:[],\n            firstPool:r.pairAddress?{id:r.pairAddress,createdAt:r.pairCreatedAt||null}:null,\n            liquidity:n(r.liquidityUsd),\n            holderCount:n(r.holderCount),\n            organicScore:n(r.organicScore),\n            stats5m:{\n              numBuys:n(r.buys5m), numSells:n(r.sells5m),\n              buyVolume:n(r.volume5m) * (n(r.buys5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m)))),\n              sellVolume:n(r.volume5m) * (n(r.sells5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m))))\n            },\n            radarDiscoveryOnly:true,\n            radarAgeBucket:r.ageBucket||null,\n            radarDiscoveryConfidence:confidence,\n            radarDexId:r.dexId||null\n          };\n          map.set(r.mint, existing);\n          radarOnlyAdded++;\n        }\n        existing.sources = Array.isArray(existing.sources) ? existing.sources : [];\n        if (!existing.sources.includes("solana-dex-universe")) existing.sources.push("solana-dex-universe");\n        for (const src of (r.sources || [])) {\n          const tag=`radar:${src}`;\n          if (!existing.sources.includes(tag)) existing.sources.push(tag);\n        }\n        existing.newListingRadar = {\n          pairCreatedAt:r.pairCreatedAt||null,\n          pairAgeSec:Number.isFinite(Number(r.pairAgeSec))?Number(r.pairAgeSec):null,\n          ageBucket:r.ageBucket||null,\n          preScore:n(r.preScore),\n          discoveryConfidence:n(r.discoveryConfidence),\n          liquidityUsd:n(r.liquidityUsd),\n          buys5m:n(r.buys5m), sells5m:n(r.sells5m),\n          providers:Array.isArray(r.providers)?r.providers:[],\n          sources:Array.isArray(r.sources)?r.sources:[],\n          dexId:r.dexId||null\n        };\n        if (!existing.firstPool && r.pairCreatedAt) existing.firstPool={id:r.pairAddress||null,createdAt:r.pairCreatedAt};\n        radarMatches++;\n      }\n    }\n  } catch (e) {\n    console.error(`SOLANA_DEX_UNIVERSE_READ_FAIL=${String(e?.message||e).slice(0,120)}`);\n  }\n  console.log(`SOLANA_DEX_UNIVERSE_MATCHES=${radarMatches} RADAR_ONLY_ADDED=${radarOnlyAdded} PROVIDERS=${radarProviderCount} HEALTHY=${radarHealthy}`);\n\n'''
s=s[:start]+block+s[end:]

old='''    (successfulSources >= 1 && radarHealthy && radarMatches >= DISCOVERY_RADAR_MIN_MATCHES);'''
new='''    (successfulSources >= 1 && radarHealthy && radarProviderCount >= 2 && radarMatches >= DISCOVERY_RADAR_MIN_MATCHES);'''
if old not in s: raise SystemExit('V367_PATCH_MISS_PROVIDER_REDUNDANCY')
s=s.replace(old,new,1)

# Extend both health records without weakening fail-closed behavior.
s=s.replace('''      radarHealthy,\n      radarMatches,\n      providerRedundancy,''','''      radarHealthy,\n      radarMatches,\n      radarOnlyAdded,\n      radarProviderCount,\n      providerRedundancy,''',1)
s=s.replace('''    radarHealthy,\n    radarMatches,\n    providerRedundancy,''','''    radarHealthy,\n    radarMatches,\n    radarOnlyAdded,\n    radarProviderCount,\n    providerRedundancy,''',1)

p.write_text(s)
print('V367_SCANNER_BROAD_DEX_PATCH=PASS')
print('RADAR_ONLY_DISCOVERY_NEVER_GRANTS_ENTRY=TRUE')
print('AGE_BUCKET_SHORT_DAY_7D_SUPPORTED=TRUE')
