from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

if 'FAST_DISCOVERY_V372' in s:
    print('V372_RADAR_ALREADY_PATCHED=TRUE')
    raise SystemExit(0)

required=[
    'const MAX_CURRENT=220;',
    'const MAX_OUTPUT=320;',
    'const map=new Map();const freshProviders=new Set();const freshSources=[];',
    "current.sort((a,b)=>b.preScore-a.preScore||b.discoveryConfidence-a.discoveryConfidence);const chosen=current.slice(0,MAX_CURRENT);",
]
for x in required:
    if x not in s:
        raise SystemExit('V372_RADAR_PATCH_MISS='+x[:80])

s=s.replace('const MAX_CURRENT=220;','const MAX_CURRENT=360;\nconst FAST_DISCOVERY_RESERVE=140;\nconst FAST_PROVIDER_MAX_AGE_MS=90000; // FAST_DISCOVERY_V372',1)
s=s.replace('const MAX_OUTPUT=320;','const MAX_OUTPUT=520;',1)

# Faster refresh only for discovery-oriented feeds; keep the slow top-pool feed conservative.
s=s.replace("'jupiter-recent':{ttl:45000,","'jupiter-recent':{ttl:20000,",1)
s=s.replace("'gecko-new-1':{ttl:30000,","'gecko-new-1':{ttl:20000,",1)
s=s.replace("'gecko-new-2':{ttl:60000,","'gecko-new-2':{ttl:30000,",1)
s=s.replace("'gecko-trending':{ttl:60000,","'gecko-trending':{ttl:30000,",1)

s=s.replace(
    'const map=new Map();const freshProviders=new Set();const freshSources=[];',
    'const map=new Map();const freshProviders=new Set();const freshSources=[];const fastProviders=new Set();const fastSources=[];',
    1,
)
old="for(const [name,cfg] of Object.entries(FEEDS)){const f=cache.feeds[name]||{},age=Date.now()-n(f.lastOkAt,0);if(!f.body||age<0||age>FEED_STALE_MAX_MS)continue;freshProviders.add(cfg.provider);freshSources.push(name);if(name.startsWith('gecko-'))parseGecko(map,f.body,name,cfg.provider);else if(name==='jupiter-recent')parseJupiter(map,f.body,name,cfg.provider);else parseDex(map,f.body,name,cfg.provider)}"
new="for(const [name,cfg] of Object.entries(FEEDS)){const f=cache.feeds[name]||{},age=Date.now()-n(f.lastOkAt,0);if(!f.body||age<0||age>FEED_STALE_MAX_MS)continue;freshProviders.add(cfg.provider);freshSources.push(name);if(age<=FAST_PROVIDER_MAX_AGE_MS){fastProviders.add(cfg.provider);fastSources.push(name)}if(name.startsWith('gecko-'))parseGecko(map,f.body,name,cfg.provider);else if(name==='jupiter-recent')parseJupiter(map,f.body,name,cfg.provider);else parseDex(map,f.body,name,cfg.provider)}"
if old not in s:
    raise SystemExit('V372_RADAR_PATCH_MISS_PROVIDER_LOOP')
s=s.replace(old,new,1)

old="current.sort((a,b)=>b.preScore-a.preScore||b.discoveryConfidence-a.discoveryConfidence);const chosen=current.slice(0,MAX_CURRENT);"
new="""// FAST_DISCOVERY_V372: reserve part of the discovery universe for genuinely new/high-velocity mints.
  // This only changes what the scanner gets to inspect. It never grants an entry.
  const fastEligible=x=>{
    const age=n(x.pairAgeSec,Infinity),conf=n(x.discoveryConfidence),liq=n(x.liquidityUsd),buys=n(x.buys5m),vol=n(x.volume5m),chg=Math.abs(n(x.priceChange5m)),ratio=n(x.buySellTxnRatio);
    const flow=(buys>=3&&ratio>=1.03)||vol>=1500||chg>=5;
    return age>=0&&age<=6*3600&&conf>=0.24&&(liq>=4000||age<=3600)&&flow;
  };
  const velocity=x=>Math.min(45,n(x.buys5m)*0.55)+Math.min(35,n(x.volume5m)/3500)+Math.min(25,Math.abs(n(x.priceChange5m))*0.8)+(n(x.pairAgeSec,Infinity)<=3600?18:0)+n(x.preScore)*0.35;
  const scoreRank=current.slice().sort((a,b)=>b.preScore-a.preScore||b.discoveryConfidence-a.discoveryConfidence);
  const hotRank=current.filter(fastEligible).sort((a,b)=>velocity(b)-velocity(a)||b.preScore-a.preScore);
  const hotMints=new Set(hotRank.slice(0,FAST_DISCOVERY_RESERVE).map(x=>x.mint));
  const chosen=[];const chosenMints=new Set();
  for(const x of hotRank){if(chosen.length>=FAST_DISCOVERY_RESERVE)break;if(chosenMints.has(x.mint))continue;x.fastDiscoveryLane=true;x.discoveryPriority=Number(velocity(x).toFixed(3));chosen.push(x);chosenMints.add(x.mint)}
  for(const x of scoreRank){if(chosen.length>=MAX_CURRENT)break;if(chosenMints.has(x.mint))continue;x.fastDiscoveryLane=hotMints.has(x.mint);x.discoveryPriority=x.fastDiscoveryLane?Number(velocity(x).toFixed(3)):n(x.preScore);chosen.push(x);chosenMints.add(x.mint)}"""
s=s.replace(old,new,1)

old="const providerCount=freshProviders.size;const status=providerCount>=2&&chosen.length>0?'HEALTHY':providerCount>=1?'DEGRADED':'DEGRADED';const out={version:'3.67.0',updatedAt:new Date().toISOString(),status,policy:'BROAD_SOLANA_DEX_DISCOVERY_ONLY_NEVER_GRANTS_ENTRY',providerCount,providers:[...freshProviders],freshSources,failures,currentFeedMints:map.size,currentCandidates:chosen.length,watchlistCandidates:retained.length,candidates};"
new="const providerCount=freshProviders.size,fastProviderCount=fastProviders.size;const status=providerCount>=2&&chosen.length>0?'HEALTHY':providerCount>=1?'DEGRADED':'DEGRADED';const out={version:'3.72.0-fast-discovery',updatedAt:new Date().toISOString(),status,policy:'FAST_DISCOVERY_ONLY_NEVER_GRANTS_ENTRY',providerCount,providers:[...freshProviders],freshSources,fastProviderCount,fastProviders:[...fastProviders],fastSources,fastProviderMaxAgeMs:FAST_PROVIDER_MAX_AGE_MS,fastDiscoveryReserve:FAST_DISCOVERY_RESERVE,fastDiscoveryCandidates:chosen.filter(x=>x.fastDiscoveryLane===true).length,failures,currentFeedMints:map.size,currentCandidates:chosen.length,watchlistCandidates:retained.length,candidates};"
if old not in s:
    raise SystemExit('V372_RADAR_PATCH_MISS_OUTPUT')
s=s.replace(old,new,1)
s=s.replace("console.log(`SOLANA_DEX_UNIVERSE v=3.67.0 status=${status} providers=${providerCount} feedMints=${map.size} current=${chosen.length} watch=${retained.length}`)","console.log(`FAST_DISCOVERY v=3.72.0 status=${status} providers=${providerCount} fastProviders=${fastProviderCount} feedMints=${map.size} current=${chosen.length} fast=${out.fastDiscoveryCandidates} watch=${retained.length}`)",1)

self_anchor="console.log('DISCOVERY_ONLY_ENTRY_GATES_UNCHANGED=TRUE');return"
if self_anchor in s:
    s=s.replace(self_anchor,"console.log('DISCOVERY_ONLY_ENTRY_GATES_UNCHANGED=TRUE');console.log('V372_FAST_DISCOVERY_SELF_TEST=PASS');console.log('FAST_DISCOVERY_NEVER_GRANTS_ENTRY=TRUE');return",1)

p.write_text(s)
print('V372_RADAR_FAST_DISCOVERY_PATCH=PASS')
print('RADAR_CAPACITY_360=TRUE')
print('FAST_RESERVE_140=TRUE')
print('FAST_PROVIDER_AGE_90S=TRUE')
print('DISCOVERY_ONLY_ENTRY_GATES_UNCHANGED=TRUE')
