#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v092-lite-$STAMP
SERVICE=meme-alpha-paper.service

rollback() {
  rc=$?
  echo "ROLLBACK rc=$rc"
  if [ -f "$BACKUP/scanner.js" ]; then
    cp -f "$BACKUP/scanner.js" "$APP/src/scanner.js"
    chown meme-alpha:meme-alpha "$APP/src/scanner.js" || true
  fi
  systemctl start "$SERVICE" || true
  exit "$rc"
}
trap rollback ERR

cd "$APP"

echo "=== V092 LITE START ==="
mkdir -p "$BACKUP"
cp -a src/scanner.js "$BACKUP/scanner.js"

echo "MODE CHECK"
node - <<'NODE'
const fs=require('fs');
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

systemctl stop "$SERVICE"

python3 - <<'PY'
from pathlib import Path
import re
p=Path('/opt/meme-alpha/app/src/scanner.js')
s=p.read_text()

if 'DISCOVERY_CACHE_MAX_AGE_MS' in s:
    print('ALREADY_PATCHED')
    raise SystemExit(0)

pattern=r'''async function getJSON\(url\) \{.*?\n\}\n\nasync function discovery\(\) \{.*?\n\}\n\nfunction n\(v, fallback = 0\) \{'''
replacement=r'''const DISCOVERY_CACHE =
  "/var/lib/meme-alpha/data/paper/discovery-last-good.json";
const DISCOVERY_HEALTH =
  "/var/lib/meme-alpha/data/paper/scanner-source-health.json";
const DISCOVERY_MIN_UNIQUE = 20;
const DISCOVERY_MIN_SOURCES = 2;
const DISCOVERY_CACHE_MAX_AGE_MS = 5 * 60 * 1000;

let discoveryHealth = {
  status: "INIT",
  checkedAt: null,
  successfulSources: 0,
  failedSources: 0,
  discoveredUnique: 0,
  usingCache: false,
  cacheAgeMs: null,
  allowNewEntries: false,
  failures: []
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function atomicJSON(path, value) {
  const tmp = `${path}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2));
  fs.renameSync(tmp, path);
}

async function getJSON(url) {
  let lastError = null;
  for (let attempt = 1; attempt <= 2; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const r = await fetch(url, {
        headers: { accept: "application/json" },
        signal: controller.signal
      });
      if (r.ok) return await r.json();
      const err = new Error(`HTTP ${r.status}: ${url}`);
      err.httpStatus = r.status;
      lastError = err;
      if ((r.status === 429 || r.status >= 500) && attempt < 2) {
        await sleep(1500);
        continue;
      }
      throw err;
    } catch (err) {
      lastError = err;
      if (attempt < 2 && (err?.name === "AbortError" || err?.httpStatus === 429 || err?.httpStatus >= 500)) {
        await sleep(1500);
        continue;
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError || new Error(`FETCH_FAILED: ${url}`);
}

async function discovery() {
  const map = new Map();
  let successfulSources = 0;
  let failedSources = 0;
  const failures = [];

  for (let i = 0; i < ENDPOINTS.length; i++) {
    const [source, endpoint] = ENDPOINTS[i];
    try {
      const rows = await getJSON(`${cfg.jupiter}/tokens/v2/${endpoint}`);
      if (!Array.isArray(rows)) throw new Error(`INVALID_RESPONSE_${source}`);
      successfulSources++;
      for (const token of rows) {
        if (!token?.id) continue;
        if (!map.has(token.id)) map.set(token.id, { ...token, sources: [] });
        const existing = map.get(token.id);
        existing.sources.push(source);
        for (const [k, v] of Object.entries(token)) {
          if (v !== null && v !== undefined) existing[k] = v;
        }
      }
    } catch (err) {
      failedSources++;
      failures.push({ source, error: String(err?.message || err).slice(0, 180) });
      console.error(`DISCOVERY_FAIL ${source}:`, err.message);
    }
    if (i < ENDPOINTS.length - 1) await sleep(500);
  }

  const liveRows = [...map.values()];
  const liveHealthy = successfulSources >= DISCOVERY_MIN_SOURCES && liveRows.length >= DISCOVERY_MIN_UNIQUE;

  if (liveHealthy) {
    atomicJSON(DISCOVERY_CACHE, { savedAt: new Date().toISOString(), tokens: liveRows });
    discoveryHealth = {
      status: "HEALTHY",
      checkedAt: new Date().toISOString(),
      successfulSources,
      failedSources,
      discoveredUnique: liveRows.length,
      usingCache: false,
      cacheAgeMs: 0,
      allowNewEntries: true,
      failures
    };
    atomicJSON(DISCOVERY_HEALTH, discoveryHealth);
    return liveRows;
  }

  let cachedRows = [];
  let cacheAgeMs = null;
  try {
    const cached = JSON.parse(fs.readFileSync(DISCOVERY_CACHE, 'utf8'));
    const saved = Date.parse(cached.savedAt);
    cacheAgeMs = Number.isFinite(saved) ? Date.now() - saved : Infinity;
    if (Array.isArray(cached.tokens) && cacheAgeMs >= 0 && cacheAgeMs <= DISCOVERY_CACHE_MAX_AGE_MS) {
      cachedRows = cached.tokens;
    }
  } catch {}

  discoveryHealth = {
    status: cachedRows.length ? "DEGRADED_CACHE" : "DEGRADED_NO_CACHE",
    checkedAt: new Date().toISOString(),
    successfulSources,
    failedSources,
    discoveredUnique: liveRows.length,
    usingCache: cachedRows.length > 0,
    cacheAgeMs,
    allowNewEntries: false,
    failures
  };
  atomicJSON(DISCOVERY_HEALTH, discoveryHealth);
  console.error('DISCOVERY_DEGRADED', JSON.stringify(discoveryHealth));
  return cachedRows.length ? cachedRows : liveRows;
}

function n(v, fallback = 0) {'''
ns,count=re.subn(pattern,replacement,s,count=1,flags=re.S)
if count != 1:
    raise SystemExit('PATCH_TARGET_NOT_FOUND')

needle='''  const reasons = [];
  const hardReject = [];

  // -------- HARD GATES --------
'''
repl='''  const reasons = [];
  const hardReject = [];

  if (discoveryHealth.allowNewEntries !== true) {
    hardReject.push("DATA_SOURCE_DEGRADED");
    reasons.push(discoveryHealth.status || "DATA_DEGRADED");
  }

  // -------- HARD GATES --------
'''
if needle not in ns:
    raise SystemExit('ANALYZE_TARGET_NOT_FOUND')
ns=ns.replace(needle,repl,1)

old='console.log("SCANNER_STATUS=PASS");'
new='''console.log(discoveryHealth.allowNewEntries === true ? "SCANNER_STATUS=PASS" : `SCANNER_STATUS=${discoveryHealth.status}`);
console.log(`DISCOVERY_SOURCES_OK=${discoveryHealth.successfulSources}`);
console.log(`DISCOVERY_SOURCES_FAILED=${discoveryHealth.failedSources}`);
console.log(`DISCOVERY_CACHE_USED=${discoveryHealth.usingCache}`);
console.log(`DISCOVERY_ENTRY_ALLOWED=${discoveryHealth.allowNewEntries}`);'''
if old not in ns:
    raise SystemExit('STATUS_TARGET_NOT_FOUND')
ns=ns.replace(old,new,1)

p.write_text(ns)
print('PATCH_APPLIED')
PY

chown meme-alpha:meme-alpha src/scanner.js
node --check src/scanner.js

echo "SYNTAX_PASS"
systemctl start "$SERVICE"

# Do not run an extra full cycle. The service owns the loop.
sleep 70

echo "=== SERVICE ==="
systemctl --no-pager is-active "$SERVICE"
systemctl --no-pager is-enabled "$SERVICE"

echo "=== SOURCE HEALTH ==="
if [ -f "$DATA/scanner-source-health.json" ]; then
  cat "$DATA/scanner-source-health.json"
else
  echo "SOURCE_HEALTH_NOT_YET_CREATED"
fi

echo "=== RECENT LOG ==="
tail -60 /var/log/meme-alpha/paper.log || true

echo "=== RECENT ERROR ==="
tail -30 /var/log/meme-alpha/paper-error.log || true

echo "=== SAFETY ASSERT ==="
node - <<'NODE'
const fs=require('fs');
const sf='/var/lib/meme-alpha/data/paper/scanner-latest.json';
const hf='/var/lib/meme-alpha/data/paper/scanner-source-health.json';
if(!fs.existsSync(sf)) throw new Error('SCANNER_STATE_MISSING');
if(!fs.existsSync(hf)) throw new Error('SOURCE_HEALTH_MISSING');
const s=JSON.parse(fs.readFileSync(sf,'utf8'));
const h=JSON.parse(fs.readFileSync(hf,'utf8'));
const bad=(s.candidates||[]).filter(c=>h.allowNewEntries!==true && c.decision==='PROBE_CANDIDATE');
console.log('SOURCE_STATUS='+h.status);
console.log('ENTRY_ALLOWED='+h.allowNewEntries);
console.log('BAD_DEGRADED_PROBES='+bad.length);
if(bad.length) throw new Error('DEGRADED_SOURCE_ALLOWED_PROBE');
console.log('V092_LITE_INVARIANT_PASS');
NODE

echo "=== RESOURCES ==="
uptime
free -h

echo "V092_LITE_COMPLETE"
echo "BACKUP=$BACKUP"
trap - ERR
