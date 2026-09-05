from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()

def repl(old,new,count=1):
    global s
    n=s.count(old)
    if n<count: raise SystemExit(f'PATCH_MISS {n} {old[:160]!r}')
    s=s.replace(old,new,count)

repl('const DISCOVERY_MIN_SOURCES = 2;','const DISCOVERY_MIN_SOURCES = 2;\nconst DISCOVERY_RADAR_MIN_MATCHES = 3;')
repl('const JUPITER_MIN_INTERVAL_MS = 2200;','const JUPITER_MIN_INTERVAL_MS = 3200;')
repl('const maxAttempts = 2;','const maxAttempts = 1;')
# Avoid hammering all four Jupiter token feeds. Stop after we have at least one useful
# live source beyond the first attempt; fresh Dex radar will provide provider redundancy.
old='''    if (\n      i <\n      ENDPOINTS.length - 1\n    ) {\n      await sleep(750);\n    }\n  }\n\n  // NEW_LISTING_RADAR_V312_MERGE'''
new='''    if (\n      i <\n      ENDPOINTS.length - 1\n    ) {\n      await sleep(750);\n    }\n    if (i >= 1 && successfulSources >= 1 && map.size >= DISCOVERY_MIN_UNIQUE) {\n      break;\n    }\n  }\n\n  // NEW_LISTING_RADAR_V312_MERGE'''
repl(old,new)
old2='''  const liveHealthy =\n    successfulSources >=\n      DISCOVERY_MIN_SOURCES &&\n    liveRows.length >=\n      DISCOVERY_MIN_UNIQUE;'''
new2='''  const providerRedundancy =\n    successfulSources >= DISCOVERY_MIN_SOURCES ||\n    (successfulSources >= 1 && radarHealthy && radarMatches >= DISCOVERY_RADAR_MIN_MATCHES);\n\n  const liveHealthy =\n    providerRedundancy &&\n    liveRows.length >= DISCOVERY_MIN_UNIQUE;'''
repl(old2,new2)
# expose redundancy evidence in health records
repl('''      successfulSources,\n      failedSources,\n\n      discoveredUnique:''','''      successfulSources,\n      failedSources,\n      radarHealthy,\n      radarMatches,\n      providerRedundancy,\n\n      discoveredUnique:''',1)
# second occurrence for degraded branch
idx=s.find('''    successfulSources,\n    failedSources,\n\n    discoveredUnique:''')
if idx<0: raise SystemExit('DEGRADED_HEALTH_PATCH_MISS')
s=s[:idx]+s[idx:].replace('''    successfulSources,\n    failedSources,\n\n    discoveredUnique:''','''    successfulSources,\n    failedSources,\n    radarHealthy,\n    radarMatches,\n    providerRedundancy,\n\n    discoveredUnique:''',1)
# Add a deterministic source-health self-test mode before scanner main execution if possible.
# We don't alter scanner business logic beyond discovery source-health topology.
p.write_text(s)
print('V365_SCANNER_SOURCE_RESILIENCE_PATCH=PASS')
