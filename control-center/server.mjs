import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, 'public');
const PORT = Number(process.env.PORT || 8788);
const REFRESH_MS = Math.max(2000, Number(process.env.CONTROL_CENTER_REFRESH_MS || 5000));
const STALE_MS = Math.max(15000, Number(process.env.CONTROL_CENTER_STALE_MS || 120000));

const SOURCES = {
  vps: process.env.CC_VPS_STATUS_URL || '',
  github: process.env.CC_GITHUB_STATUS_URL || '',
  cloudflare: process.env.CC_CLOUDFLARE_STATUS_URL || '',
  telegram: process.env.CC_TELEGRAM_STATUS_URL || '',
  deepseek: process.env.CC_DEEPSEEK_STATUS_URL || '',
  codex: process.env.CC_CODEX_STATUS_URL || '',
  claude: process.env.CC_CLAUDE_STATUS_URL || '',
};

const SAFE_KEYS = new Set([
  'state','status','message','last_updated','last_seen','timestamp','task','task_id',
  'issue','pr','sha','run_id','workflow','validation','verdict','consensus','deploy',
  'version','provider','events','details','stage','url','label','age_ms','pipeline',
  'intake','implementation','codex_review','claude_review','merge'
]);

const STALE_SUCCESS_STATES = new Set(['ONLINE','RUNNING','REVIEWING','ACCEPT','PASS']);

function nowIso() { return new Date().toISOString(); }
function normalizeState(v) {
  const s = String(v || 'UNKNOWN').toUpperCase();
  const allowed = new Set(['ONLINE','DEGRADED','OFFLINE','UNKNOWN','WAITING','RUNNING','REVIEWING','ACCEPT','REJECT','BLOCKED','PASS','FAIL','PENDING']);
  return allowed.has(s) ? s : 'UNKNOWN';
}
function sanitize(value, depth = 0) {
  if (depth > 4) return null;
  if (Array.isArray(value)) return value.slice(0, 100).map(v => sanitize(v, depth + 1));
  if (!value || typeof value !== 'object') return typeof value === 'string' ? value.slice(0, 2000) : value;
  const out = {};
  for (const [k, v] of Object.entries(value)) {
    if (!SAFE_KEYS.has(k)) continue;
    out[k] = sanitize(v, depth + 1);
  }
  return out;
}
function parseTime(obj) {
  for (const key of ['last_updated','last_seen','timestamp']) {
    const t = Date.parse(obj?.[key]);
    if (Number.isFinite(t)) return t;
  }
  return NaN;
}
function freshness(obj) {
  const t = parseTime(obj);
  if (!Number.isFinite(t)) return { stale: true, age_ms: null };
  const age = Math.max(0, Date.now() - t);
  return { stale: age > STALE_MS, age_ms: age };
}
async function fetchJson(url) {
  if (!url) return { state: 'UNKNOWN', message: 'source not configured', last_updated: null };
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 5000);
  try {
    const res = await fetch(url, { headers: { accept: 'application/json' }, signal: ctl.signal });
    if (!res.ok) return { state: 'DEGRADED', message: `HTTP ${res.status}`, last_updated: nowIso() };
    const raw = sanitize(await res.json());
    const fresh = freshness(raw);
    const base = { ...raw, state: normalizeState(raw?.state || raw?.status), age_ms: fresh.age_ms };
    if (fresh.stale && STALE_SUCCESS_STATES.has(base.state)) {
      base.state = 'DEGRADED';
      base.message = base.message || 'stale or missing evidence timestamp';
    }
    return base;
  } catch (err) {
    return { state: 'OFFLINE', message: String(err?.message || err).slice(0, 500), last_updated: nowIso() };
  } finally {
    clearTimeout(timer);
  }
}

let cache = { last_updated: nowIso(), refresh_ms: REFRESH_MS, systems: {}, ai: {}, pipeline: {}, events: [] };
let refreshing = false;
async function refresh() {
  if (refreshing) return cache;
  refreshing = true;
  try {
    const entries = await Promise.all(Object.entries(SOURCES).map(async ([name, url]) => [name, await fetchJson(url)]));
    const map = Object.fromEntries(entries);
    const events = [];
    for (const [name, item] of entries) {
      if (Array.isArray(item.events)) {
        for (const e of item.events.slice(-25)) events.push({ source: name, ...sanitize(e) });
      }
    }
    events.sort((a, b) => Date.parse(b.timestamp || b.last_updated || 0) - Date.parse(a.timestamp || a.last_updated || 0));
    cache = {
      last_updated: nowIso(),
      refresh_ms: REFRESH_MS,
      systems: { vps: map.vps, github: map.github, cloudflare: map.cloudflare, telegram: map.telegram },
      ai: { deepseek: map.deepseek, codex: map.codex, claude: map.claude },
      pipeline: map.github?.details?.pipeline || map.github?.pipeline || {},
      events: events.slice(0, 100),
    };
    return cache;
  } finally { refreshing = false; }
}
setInterval(() => refresh().catch(() => {}), REFRESH_MS).unref();
await refresh();

const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8' };
async function serveFile(req, res) {
  const urlPath = new URL(req.url, 'http://localhost').pathname;
  const rel = urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '');
  const file = path.resolve(PUBLIC_DIR, rel);
  const relative = path.relative(PUBLIC_DIR, file);
  if (relative.startsWith('..') || path.isAbsolute(relative)) { res.writeHead(403); res.end('Forbidden'); return; }
  try {
    const data = await fs.readFile(file);
    res.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
    res.end(data);
  } catch { res.writeHead(404); res.end('Not found'); }
}

http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://localhost');
  if (u.pathname === '/healthz') {
    res.writeHead(200, { 'content-type':'application/json', 'cache-control':'no-store' });
    res.end(JSON.stringify({ ok:true, service:'trading-multi-ai-control-center', time:nowIso() }));
    return;
  }
  if (u.pathname === '/api/status') {
    const data = await refresh();
    res.writeHead(200, { 'content-type':'application/json', 'cache-control':'no-store' });
    res.end(JSON.stringify(data));
    return;
  }
  await serveFile(req, res);
}).listen(PORT, '0.0.0.0', () => {
  console.log(`Control Center listening on :${PORT}`);
});
