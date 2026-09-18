// Personal AI Control Tower - renderer.
//
// This file renders. It does not decide. Two rules hold everywhere below:
//
//  1. Provenance is READ, never computed here. The server stamps it from the
//     origin it recorded when the value was obtained. If a value arrives with
//     no provenance, it renders NOT_OBSERVED - the client must not upgrade an
//     unlabelled value into a labelled one by guessing.
//  2. Nothing is invented. No placeholder model runs, no simulated activity, no
//     "probably healthy". A thing we do not know renders as a thing we do not
//     know.

const PROVENANCE_HELP = {
  REAL_LIVE: 'Quan sát trong cửa sổ tươi mới',
  HISTORICAL_EVIDENCE: 'Đã quan sát, nhưng không phải bây giờ',
  CONFIGURED: 'Có cấu hình, chưa có runtime state',
  NOT_OBSERVED: 'Chưa từng hỏi / không có câu trả lời',
  UNVERIFIED: 'Có câu trả lời nhưng không xác định được',
};
const PROVENANCE_ORDER = Object.keys(PROVENANCE_HELP);

const SYSTEM_LABELS = { vps: 'VPS / VPC Bridge', github: 'GitHub', cloudflare: 'Cloudflare Edge', telegram: 'Telegram Hub' };
const AI_LABELS = { deepseek: 'DeepSeek', codex: 'Codex', claude: 'Claude', qwen: 'Qwen', openrouter: 'OpenRouter' };
const PIPELINE_ORDER = ['intake', 'implementation', 'validation', 'codex_review', 'claude_review',
  'qwen_review', 'openrouter_review', 'consensus', 'merge', 'deploy'];
const HEALTHY_STATES = ['ONLINE', 'WAITING', 'RUNNING', 'REVIEWING', 'ACCEPT', 'PASS'];

const VIEWS = [
  { id: 'overview', label: 'Tổng quan', title: 'Tổng quan', sub: 'Trạng thái đã được chứng minh, không phải trạng thái mong muốn.' },
  { id: 'ai', label: 'Mạng AI', title: 'Mạng AI', sub: 'Mỗi provider kèm nguồn gốc bằng chứng của riêng nó.' },
  { id: 'fleet', label: 'Đội hình mô hình', title: 'Đội hình mô hình', sub: 'Chỉ liệt kê model do telemetry báo cáo. Không suy đoán.' },
  { id: 'runtime', label: 'Runtime Fabric', title: 'Runtime Fabric', sub: 'Đọc từ acceptance.py. Control Tower không tự suy ra ma trận này.' },
  { id: 'pipeline', label: 'Pipeline', title: 'Pipeline', sub: 'Stage không có timestamp riêng sẽ là UNKNOWN.' },
  { id: 'evidence', label: 'Evidence', title: 'Evidence', sub: 'Sự kiện thô và các bề mặt chưa có nguồn telemetry.' },
];

const state = { status: null, fabric: null, error: null, filter: '', view: 'overview' };

/* ---------- helpers ---------- */
const $ = (id) => document.getElementById(id);
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}
function stateClass(s) {
  const v = String(s || 'UNKNOWN').toLowerCase();
  if (['online', 'accept', 'pass', 'true'].includes(v)) return 'ok';
  if (['running', 'reviewing', 'waiting', 'pending'].includes(v)) return 'busy';
  if (['degraded'].includes(v)) return 'warn';
  if (['offline', 'reject', 'fail', 'blocked', 'false'].includes(v)) return 'bad';
  return 'unknown';
}
function age(ms) {
  if (ms == null) return 'unknown';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h`;
}
// Unlabelled input falls closed to NOT_OBSERVED rather than being guessed.
function provOf(x) {
  const p = x && x._provenance;
  return PROVENANCE_ORDER.includes(p) ? p : 'NOT_OBSERVED';
}
function provChip(p, title) {
  const label = PROVENANCE_ORDER.includes(p) ? p : 'NOT_OBSERVED';
  return `<span class="prov ${label}" title="${esc(title || PROVENANCE_HELP[label])}">${label}</span>`;
}
function badge(text, cls) { return `<span class="badge ${cls}">${esc(String(text).toUpperCase())}</span>`; }
function panel(title, note, body) {
  return `<section class="panel"><div class="panelHead"><h2>${esc(title)}</h2>${note ? `<span class="note">${esc(note)}</span>` : ''}</div><div class="panelBody">${body}</div></section>`;
}
function empty(msg) { return `<div class="empty">${esc(msg)}</div>`; }
function matches(haystack) {
  const q = state.filter.trim().toLowerCase();
  return !q || String(haystack).toLowerCase().includes(q);
}

/* ---------- cards ---------- */
function statusCard(label, d = {}) {
  const st = String(d.state || d.status || 'UNKNOWN').toUpperCase();
  const ctx = [d.task || d.task_id, d.pr && `PR #${d.pr}`, d.sha && String(d.sha).slice(0, 10)].filter(Boolean).join(' · ');
  return `<article class="card inPanel">
    <div class="cardTop"><strong>${esc(label)}</strong>${badge(st, stateClass(st))}</div>
    <div>${provChip(provOf(d))}</div>
    ${ctx ? `<div class="ctx">${esc(ctx)}</div>` : ''}
    <div class="meta">Last seen: ${esc(d.last_seen || d.last_updated || d.timestamp || 'unknown')} · age ${esc(age(d.age_ms))}</div>
    ${d.message ? `<p>${esc(d.message)}</p>` : ''}
  </article>`;
}
function kpi(label, value, prov, cls) {
  return `<div class="kpi"><span class="kLabel">${esc(label)}</span>
    <span class="kValue ${cls ? '' : ''}">${cls ? badge(value, cls) : esc(value)}</span>
    ${provChip(prov)}</div>`;
}

/* ---------- views ---------- */
function viewOverview() {
  const s = state.status, f = state.fabric;
  const rows = Object.fromEntries((f?.rows || []).map((r) => [r.key, r]));
  const row = (k) => rows[k];
  const fabricKpi = (k, label) => {
    const r = row(k);
    if (!r) return kpi(label, 'NOT_OBSERVED', 'NOT_OBSERVED');
    return kpi(label, String(r.value), r.provenance, stateClass(r.value));
  };

  const systems = Object.entries(SYSTEM_LABELS)
    .filter(([k, l]) => matches(`${k} ${l}`))
    .map(([k, l]) => statusCard(l, s?.systems?.[k])).join('');

  const counts = PROVENANCE_ORDER.map((p) => {
    const all = [...Object.values(s?.systems || {}), ...Object.values(s?.ai || {})];
    return [p, all.filter((x) => provOf(x) === p).length];
  });

  return [
    panel('Cổng vận hành', f?.status === 'OK' ? 'đọc từ acceptance.py' : 'fabric không đọc được',
      `<div class="kpis">
        ${fabricKpi('FULL_ACTIVE', 'Full active')}
        ${fabricKpi('PRIMARY_RUNTIME', 'Primary runtime')}
        ${fabricKpi('FAILOVER_PROOF', 'Failover proof')}
        ${fabricKpi('ZERO_COST_GUARD', 'Zero-cost guard')}
        ${fabricKpi('PAID_FALLBACK', 'Paid fallback')}
      </div>
      ${(f?.blockers || []).length
        ? `<div class="blockers">${f.blockers.map((b) => `<span class="blocker">${esc(b)}</span>`).join('')}</div>`
        : empty(f?.status === 'OK' ? 'Không có blocker nào trong ma trận acceptance.' : 'Blocker không đọc được vì fabric chưa đọc được.')}`),
    panel('Hệ thống', 'evidence vận hành', systems ? `<div class="grid">${systems}</div>` : empty('Không có hệ thống nào khớp bộ lọc.')),
    panel('Phân bố nguồn gốc bằng chứng', 'đếm trên system + AI cards',
      `<div class="kpis">${counts.map(([p, n]) => kpi(p, String(n), p)).join('')}</div>`),
  ].join('');
}

function viewAi() {
  const s = state.status;
  const cards = Object.entries(AI_LABELS).filter(([k, l]) => matches(`${k} ${l}`))
    .map(([k, l]) => statusCard(l, s?.ai?.[k])).join('');
  return panel('AI workers', 'mỗi card mang nguồn gốc riêng',
    cards ? `<div class="grid">${cards}</div>` : empty('Không có provider nào khớp bộ lọc.'));
}

function viewFleet() {
  // A model is listed only when a provider's telemetry actually named one.
  // There is no static model table here on purpose: a hard-coded fleet would be
  // the Tower asserting a model-selection fact it has no authority over.
  const s = state.status;
  const rows = Object.entries(AI_LABELS).map(([k, label]) => {
    const d = s?.ai?.[k] || {};
    return { key: k, label, model: d.model, role: d.role, prov: provOf(d) };
  }).filter((r) => matches(`${r.key} ${r.label} ${r.model || ''} ${r.role || ''}`));

  const named = rows.filter((r) => r.model);
  const body = `<table class="rows"><thead><tr><th>Provider</th><th>Model</th><th>Role</th><th>Nguồn gốc</th></tr></thead><tbody>
    ${rows.map((r) => `<tr>
      <td class="k">${esc(r.label)}</td>
      <td class="v">${r.model ? esc(r.model) : '<span class="prov NOT_OBSERVED">NOT_OBSERVED</span>'}</td>
      <td class="k">${r.role ? esc(r.role) : '—'}</td>
      <td>${provChip(r.model ? r.prov : 'NOT_OBSERVED')}</td>
    </tr>`).join('')}
  </tbody></table>`;

  return [
    panel('Đội hình mô hình', `${named.length}/${rows.length} provider báo cáo model`,
      rows.length ? body : empty('Không có provider nào khớp bộ lọc.')),
    panel('Thẩm quyền chọn model', 'ranh giới, không phải tính năng thiếu',
      empty('Model Mesh là thẩm quyền duy nhất chọn model/provider. Control Tower chỉ hiển thị model mà telemetry đã báo cáo; nó không xếp hạng, không chọn và không đề xuất model.')),
  ].join('');
}

function viewRuntime() {
  const f = state.fabric;
  if (!f || f.status !== 'OK') {
    return panel('Runtime Fabric', 'không đọc được',
      empty(`Không đọc được ma trận acceptance nên không hiển thị giá trị nào. Lý do: ${f?.reason || 'chưa đọc'}. Control Tower không tự suy ra ma trận thay thế.`));
  }
  const rows = (f.rows || []).filter((r) => matches(`${r.key} ${r.value} ${r.provenance}`));
  const life = f.lifecycles || { stable: [], development_lab: [], by_runtime: {} };
  const lifeRow = (n) => `<div class="lifeRow"><span>${esc(n)}</span><span>${esc(life.by_runtime?.[n] || 'UNVERIFIED')}</span></div>`;

  return [
    panel('Ma trận acceptance', `nguồn: ${f.source}`,
      rows.length
        ? `<table class="rows"><thead><tr><th>Row</th><th>Giá trị</th><th>Nguồn gốc</th></tr></thead><tbody>
            ${rows.map((r) => `<tr><td class="k">${esc(r.key)}</td><td class="v">${badge(String(r.value), stateClass(r.value))}</td><td>${provChip(r.provenance)}</td></tr>`).join('')}
          </tbody></table>`
        : empty('Không có row nào khớp bộ lọc.')),
    panel('Stable vs Development Lab', 'chỉ STABLE được nhận traffic ổn định',
      `<div class="split">
        <div><h3 class="kLabel">Stable</h3><div class="lifeList">${life.stable.length ? life.stable.map(lifeRow).join('') : empty('Không có runtime STABLE.')}</div></div>
        <div><h3 class="kLabel">Development Lab</h3><div class="lifeList">${life.development_lab.length ? life.development_lab.map(lifeRow).join('') : empty('Lab trống.')}</div></div>
      </div>
      <div>${provChip(life.provenance)}</div>`),
    panel('Blockers', 'từ ma trận, không phải từ giao diện',
      (f.blockers || []).length ? `<div class="blockers">${f.blockers.map((b) => `<span class="blocker">${esc(b)}</span>`).join('')}</div>` : empty('Không có blocker.')),
  ].join('');
}

function viewPipeline() {
  const p = state.status?.pipeline || {};
  const steps = PIPELINE_ORDER.filter((k) => matches(k)).map((k) => {
    const raw = p[k];
    const st = String((raw && typeof raw === 'object' ? (raw.state || raw.status) : raw) || 'PENDING').toUpperCase();
    const observed = raw !== undefined;
    const ageMs = raw && typeof raw === 'object' ? raw.age_ms : null;
    return `<div class="step">
      <span class="dot ${stateClass(st)}"></span>
      <span class="name">${esc(k.replaceAll('_', ' '))}</span>
      <span class="meta">${esc(ageMs != null ? `age ${age(ageMs)}` : '')}</span>
      ${observed ? badge(st, stateClass(st)) : provChip('NOT_OBSERVED')}
    </div>`;
  }).join('');
  return panel('Pipeline', 'stage thiếu timestamp riêng sẽ là UNKNOWN',
    steps ? `<div class="timeline">${steps}</div>` : empty('Không có stage nào khớp bộ lọc.'));
}

function viewEvidence() {
  const events = (state.status?.events || []).filter((e) => matches(`${e.source} ${e.message || ''} ${e.label || ''} ${e.state || ''}`));
  return [
    panel('Live events', `${events.length} sự kiện`,
      events.length
        ? `<div class="events">${events.map((e) => `<div class="event">
            <time>${esc(e.timestamp || e.last_updated || 'unknown')}</time>
            <b>${esc(e.source || 'system')}</b>
            <span>${esc(e.message || e.label || e.state || 'event')}</span>
          </div>`).join('')}</div>`
        : empty('Chưa có event evidence.')),
    panel('Learning Fabric', 'chưa có nguồn telemetry',
      empty('Chưa có nguồn telemetry nào cho Learning Fabric trong repository này, nên không có số liệu nào được hiển thị. Đây là NOT_OBSERVED thật, không phải bảng trống chờ dữ liệu giả.')),
    panel('Ranh giới thẩm quyền', 'bất biến, không phải chú thích',
      empty('UI → Brain ingress → task_router → canonical policy → authorized executor. Control Tower không bao giờ gọi thẳng provider/runtime, và transport chỉ trả lời GET/HEAD.')),
  ].join('');
}

const RENDERERS = { overview: viewOverview, ai: viewAi, fleet: viewFleet, runtime: viewRuntime, pipeline: viewPipeline, evidence: viewEvidence };

/* ---------- shell ---------- */
function renderNav() {
  $('nav').innerHTML = VIEWS.map((v) => `<a href="#${v.id}" ${v.id === state.view ? 'aria-current="page"' : ''}>${esc(v.label)}</a>`).join('');
  $('legend').innerHTML = PROVENANCE_ORDER.map((p) => provChip(p, PROVENANCE_HELP[p])).join('');
}

function renderLive() {
  const s = state.status;
  const badgeEl = $('liveBadge');
  if (state.error) { badgeEl.textContent = 'OFFLINE'; badgeEl.className = 'badge bad'; return; }
  const all = [...Object.values(s?.systems || {}), ...Object.values(s?.ai || {})];
  // LIVE requires that everything shown is BOTH healthy AND actually observed
  // live. Health inferred from stale or unobserved values is not liveness, and
  // this badge is the one place that temptation is strongest.
  const live = all.length
    && all.every((x) => HEALTHY_STATES.includes(String(x?.state || '').toUpperCase()))
    && all.every((x) => provOf(x) === 'REAL_LIVE');
  badgeEl.textContent = live ? 'LIVE' : 'OBSERVING';
  badgeEl.className = `badge ${live ? 'ok' : 'warn'}`;
}

function render() {
  const view = VIEWS.find((v) => v.id === state.view) || VIEWS[0];
  $('viewTitle').textContent = view.title;
  $('viewSub').textContent = state.error ? `Control Tower API error: ${state.error}` : view.sub;
  renderNav();
  $('view').innerHTML = state.error
    ? empty(`Không đọc được /api/status: ${state.error}. Không hiển thị giá trị nào từ bộ nhớ đệm giao diện.`)
    : RENDERERS[view.id]();
  const s = state.status;
  $('footMeta').textContent = s
    ? `Last updated: ${s.last_updated} · refresh ${Math.round((s.refresh_ms || 5000) / 1000)}s · fabric ${state.fabric?.status || 'UNAVAILABLE'}`
    : '';
  renderLive();
}

async function getJson(path) {
  const r = await fetch(path, { cache: 'no-store' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function tick() {
  try {
    const [status, fabric] = await Promise.all([
      getJson('/api/status'),
      // A fabric read that fails must not blank the whole Tower, but it must
      // also never be filled in with a guess.
      getJson('/api/fabric').catch((e) => ({ status: 'UNAVAILABLE', reason: String(e.message || e), rows: [], blockers: [] })),
    ]);
    state.status = status;
    state.fabric = fabric;
    state.error = null;
  } catch (e) {
    state.error = String(e.message || e);
  }
  render();
}

function route() {
  const id = location.hash.replace(/^#/, '');
  state.view = VIEWS.some((v) => v.id === id) ? id : 'overview';
  render();
}

window.addEventListener('hashchange', route);
$('filter').addEventListener('input', (e) => { state.filter = e.target.value; render(); });
route();
tick();
setInterval(tick, 5000);
