# Skill-Mandatory Fast Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every GitHub Brain request select and apply exactly one validated primary skill while keeping FAST routing local, exact-SHA traceable, and free of GitHub/provider round-trips.

**Architecture:** Canonical V4 YAML/catalog/manifests remain the source of truth. A deterministic Python compiler builds an ephemeral exact-SHA hot snapshot during CI/deploy; Cloudflare converts that snapshot to a bundled JS module and exposes a small `/brain/route` diagnostic/API surface backed by a pure local router. STANDARD/DEEP continue to lazy-load context/tools after routing, while a shared quality gate rejects missing/invalid skill capsules.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, Node.js 22 ESM, Cloudflare Workers/Wrangler 4.124.0, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-12-skill-mandatory-fast-gateway-design.md`

## Global Constraints

- Every handled GitHub Brain request has exactly one primary skill.
- `task_router` is mandatory infrastructure and does not count as the primary skill.
- The selected primary skill must have a validated execution capsule and that capsule must be marked applied before answer emission.
- FAST performs zero GitHub reads and zero external-network calls for routing/skill selection.
- Unknown intents fall back deterministically to `core_reasoning`.
- FAST has zero supporting skills; STANDARD/DEEP retain a global maximum of 2.
- Live/trading, deployment/runtime claims, financial/destructive/credential-sensitive work must not remain FAST.
- Provider/tool output remains evidence/capability, never reasoning authority.
- No credential, private provider payload, live market/account state, user secret, or hidden chain-of-thought may enter the snapshot/capsule/trace.
- Current Trading authority and hard-risk controls are unchanged.
- Generated hot snapshots are build artifacts, not committed source; production `source_sha` comes from the exact checkout SHA used to build/deploy, avoiding self-referential commit hashes.
- The unfinished Bybit public-bridge work remains independent and is not a dependency for this feature.

---

### Task 1: Enforce the skill-mandatory policy in canonical V4 configuration

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/router.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/validate_v4.py`
- Modify: `AI_SKILL_LIBRARY/validate_router.py`
- Create: `AI_SKILL_LIBRARY/tests/test_skill_mandatory_policy.py`

**Interfaces:**
- Produces policy fields consumed by the compiler: `policy.primary_skill_required`, `policy.fallback_primary_skill`, per-profile `primary_skill_count`, `skill_capsule_required`.
- Keeps existing `task_router`, domain routes, profile limits, security and authority semantics intact.

- [ ] **Step 1: Write failing policy tests**

```python
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_every_profile_requires_exactly_one_primary_skill():
    router = load("AI_SKILL_LIBRARY/v4/stable/router.yaml")
    runtime = load("AI_SKILL_LIBRARY/v4/stable/runtime.yaml")
    assert router["policy"]["primary_skill_required"] is True
    assert router["policy"]["fallback_primary_skill"] == "core_reasoning"
    for name in ("FAST", "STANDARD", "DEEP"):
        assert runtime["profiles"][name]["primary_skill_count"] == 1
        assert runtime["profiles"][name]["skill_capsule_required"] is True
    assert runtime["profiles"]["FAST"]["max_supporting_skills"] == 0
```

- [ ] **Step 2: Run the new test and verify RED**

Run:
```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_mandatory_policy -v
```
Expected: FAIL because the new mandatory fields are absent.

- [ ] **Step 3: Add the minimal canonical policy**

Add under `AI_SKILL_LIBRARY/v4/stable/router.yaml` `policy`:
```yaml
primary_skill_required: true
fallback_primary_skill: core_reasoning
skill_execution_capsule_required: true
```

Add to every profile in `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`:
```yaml
primary_skill_count: 1
skill_capsule_required: true
```
Keep FAST `max_supporting_skills: 0`; do not alter its tool/memory/bridge zeroes.

- [ ] **Step 4: Extend validators to reject policy drift**

In `validate_v4.py`, add errors when mandatory fields are missing, fallback is not `core_reasoning`, FAST supporting skills are not zero, or any profile does not require one primary/capsule.

In `validate_router.py`, load the stable V4 router/runtime in addition to legacy compatibility inputs and reject a fallback skill not present in `skills/catalog.yaml`.

- [ ] **Step 5: Run policy + canonical regressions**

Run:
```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_mandatory_policy -v
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
```
Expected: all PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add AI_SKILL_LIBRARY/v4/stable/router.yaml AI_SKILL_LIBRARY/v4/stable/runtime.yaml AI_SKILL_LIBRARY/validate_v4.py AI_SKILL_LIBRARY/validate_router.py AI_SKILL_LIBRARY/tests/test_skill_mandatory_policy.py
git commit -m "feat: require a primary skill for every V4 request"
```

---

### Task 2: Build deterministic multilingual skill capsules and the exact-SHA snapshot

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py`
- Create: `AI_SKILL_LIBRARY/tests/test_skill_gateway_compiler.py`
- Generate at build time only: `AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json`
- Modify: `.gitignore` to ignore the generated snapshot directory if it is not already ignored.

**Interfaces:**
- `compile_snapshot(root: Path, source_sha: str, generated_at: str | None = None) -> dict`
- `write_snapshot(root: Path, source_sha: str, output: Path) -> Path`
- Snapshot contains `profiles`, `domains`, `skills`, `capsules`, `fallback_primary_skill`, source hashes and `source_sha`.
- `capsules[skill_id]` is the runtime execution contract for that skill.

- [ ] **Step 1: Write RED compiler tests**

Tests must cover:
```python
def test_snapshot_is_deterministic_except_generated_at(): ...
def test_snapshot_contains_core_reasoning_capsule(): ...
def test_vietnamese_aliases_route_to_canonical_skill_ids_only(): ...
def test_snapshot_rejects_unknown_alias_skill(): ...
def test_snapshot_contains_no_secret_shaped_fields(): ...
```
Use representative aliases such as:
```yaml
aliases:
  debugging: ["sửa lỗi", "lỗi code", "debug"]
  advertising_copy: ["viết quảng cáo", "kịch bản quảng cáo"]
  video_prompt: ["prompt video", "viết prompt video"]
  academic_research: ["nghiên cứu học thuật", "bài nghiên cứu"]
  ux_ui: ["thiết kế ux ui", "giao diện"]
  trading_router: ["quét market", "tìm entry", "giao dịch live"]
```

- [ ] **Step 2: Run compiler tests and verify RED**

Run:
```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_gateway_compiler -v
```
Expected: FAIL because compiler/schema/aliases do not exist.

- [ ] **Step 3: Implement the compiler with canonical normalization**

Compiler rules:
```python
normalized = unicodedata.normalize("NFKC", text).casefold()
normalized = " ".join(normalized.split())
```
Use SHA-256 over exact source bytes for checkpoint/router/runtime/catalog/registry/security/authority/domain manifests/aliases. Build capsules only from validated catalog + matching domain manifest fields. Reject aliases to unknown skills and manifests whose listed skills disagree with catalog domain membership.

Production mode requires `source_sha` matching `^[0-9a-f]{40}$`; tests may supply a fixed 40-char SHA.

- [ ] **Step 4: Implement snapshot schema and validator**

Schema requires at minimum:
```json
{
  "schema_version": 1,
  "source_sha": "40-hex",
  "fallback_primary_skill": "core_reasoning",
  "profiles": {},
  "domains": {},
  "skills": {},
  "capsules": {},
  "hashes": {}
}
```
Validator additionally asserts exactly one fallback capsule, no unknown skills, no capsule without a catalog skill, and no sensitive keys matching `secret|token|password|private_key|api_key|credential` (case-insensitive).

- [ ] **Step 5: Generate and validate an exact-head snapshot locally/CI**

Run:
```bash
python AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py --source-sha "$(git rev-parse HEAD)" --output AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json
python AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json
```
Expected: PASS; generated file remains uncommitted/ignored.

- [ ] **Step 6: Run full Brain tests and commit Task 2**

```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -v
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
git add .gitignore AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py AI_SKILL_LIBRARY/tests/test_skill_gateway_compiler.py
git commit -m "feat: compile exact-SHA skill gateway snapshots"
```

---

### Task 3: Add a pure no-network Cloudflare router and quality gate

**Files:**
- Create: `cloudflare-worker/skill-gateway.js`
- Create: `cloudflare-worker/generated/.gitkeep`
- Create at build time only: `cloudflare-worker/generated/skill-gateway-snapshot.js`
- Create: `cloudflare-worker/test-skill-gateway.mjs`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- `routeSkillRequest({text, trustedHints?}, snapshot) -> RouteDecision`
- `assertResponseQuality({route, execution}) -> {ok:true}` or throws a bounded contract error.
- `RouteDecision` fields: `profile`, `domain`, `primarySkill`, `capsuleId`, `capsuleHash`, `supportingSkills`, `requiresFreshState`, `requiresAuthority`, `toolRequirement`, `sourceSha`, `routeLatencyMs`.
- No `fetch`, GitHub API, provider registry, KV, Durable Object or VPC call is permitted inside `routeSkillRequest`.

- [ ] **Step 1: Write RED Node tests**

Representative assertions:
```js
assert.equal(routeSkillRequest({text:'giải thích bác sĩ nội trú'}, SNAPSHOT).primarySkill,'core_reasoning');
assert.equal(routeSkillRequest({text:'sửa lỗi API này'}, SNAPSHOT).primarySkill,'debugging');
assert.equal(routeSkillRequest({text:'viết kịch bản quảng cáo giày'}, SNAPSHOT).primarySkill,'advertising_copy');
assert.equal(routeSkillRequest({text:'quét market BTC live'}, SNAPSHOT).profile,'DEEP');
assert.equal(routeSkillRequest({text:'quét market BTC live'}, SNAPSHOT).primarySkill,'trading_router');
assert.throws(()=>assertResponseQuality({route:{primarySkill:null},execution:{answer:'x'}}));
```
Patch `globalThis.fetch` to throw and prove FAST routing still passes.

- [ ] **Step 2: Run and verify RED**

```bash
cd cloudflare-worker
node test-skill-gateway.mjs
```
Expected: FAIL because router/generated module do not exist.

- [ ] **Step 3: Implement deterministic local selection**

Selection order must implement the spec exactly: normalize -> trusted hints -> exclusions -> trigger/alias eligibility -> deterministic rank -> `core_reasoning` fallback -> independent profile escalation.

Hard escalation terms are snapshot/policy data, not provider results. At minimum cover architecture/protocol, deployment/runtime, live/trading, financial action, destructive action, credential-sensitive action and fresh external state.

- [ ] **Step 4: Add build-time JSON-to-ESM generation**

Extend `prepare-wrangler.mjs` so it reads the already validated snapshot and writes:
```js
export const SKILL_GATEWAY_SNAPSHOT = Object.freeze(<canonical JSON object>);
```
It must abort when snapshot `source_sha !== RUNTIME_REVISION/GITHUB_SHA` in CI/deploy mode.

Do not add network discovery for the snapshot. Existing KV/VPC discovery behavior remains unchanged.

- [ ] **Step 5: Run Node tests + real Wrangler dry-run**

```bash
cd cloudflare-worker
node test-skill-gateway.mjs
npm run check
npm run prepare:wrangler
npx wrangler deploy --dry-run --outdir .wrangler-skill-gateway
```
Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add cloudflare-worker/skill-gateway.js cloudflare-worker/generated/.gitkeep cloudflare-worker/test-skill-gateway.mjs cloudflare-worker/prepare-wrangler.mjs cloudflare-worker/package.json
git commit -m "feat: add no-network Cloudflare skill router"
```

---

### Task 4: Expose bounded Brain routing diagnostics without touching trading execution routes

**Files:**
- Create: `cloudflare-worker/skill-gateway-handler.js`
- Create: `cloudflare-worker/test-skill-gateway-handler.mjs`
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/research-gateway.js` only to include Brain snapshot metadata in `/health` if doing so does not couple market-provider health to Brain routing.

**Interfaces:**
- `POST /brain/route` accepts `{text:string}` with a strict body limit and returns route metadata + execution capsule/output contract; it performs no provider/tool call.
- `GET /brain/health` returns active snapshot `sourceSha`, schema version and `freshGitContext`/last-known-good status.
- It must not return hidden chain-of-thought, user memory, secrets, provider payloads or private project content.

- [ ] **Step 1: Write handler RED tests**

Tests require:
- method/body validation;
- `POST /brain/route` returns exactly one `primarySkill` and a capsule;
- unknown text returns `core_reasoning`;
- live/trading text returns DEEP without calling providers;
- `/brain/health` source SHA matches bundled snapshot;
- no existing `/runtime/contract`, `/health`, `/research/market`, `/bybit/*` route behavior is shadowed.

- [ ] **Step 2: Run tests and verify RED**

```bash
cd cloudflare-worker
node test-skill-gateway-handler.mjs
```
Expected: FAIL because handler is absent.

- [ ] **Step 3: Implement the handler and add one delegation in `index.js`**

Place Brain delegation before the final 404 but ensure it only claims `/brain/route` and `/brain/health`. Do not modify trading/private route implementations or LIVE/PAPER switches.

- [ ] **Step 4: Add quality-gate fields to diagnostics**

Route response includes bounded fields such as:
```json
{
  "ok": true,
  "profile": "FAST",
  "domain": "writing",
  "primarySkill": "advertising_copy",
  "capsuleId": "advertising_copy",
  "capsuleHash": "...",
  "sourceSha": "...",
  "externalRoutingCalls": 0
}
```
Do not expose internal reasoning text.

- [ ] **Step 5: Run Worker regression/dry-run and commit Task 4**

```bash
cd cloudflare-worker
node test-skill-gateway.mjs
node test-skill-gateway-handler.mjs
npm run check
npm run prepare:wrangler
npx wrangler deploy --dry-run --outdir .wrangler-skill-gateway
```
Commit after all PASS.

---

### Task 5: Add exact-SHA CI compilation, no-network regression and latency benchmark

**Files:**
- Modify: `.github/workflows/ai-skill-library-ci.yml`
- Create: `.github/workflows/skill-mandatory-fast-gateway-ci.yml`
- Create: `cloudflare-worker/benchmark-skill-gateway.mjs`
- Modify: `.github/workflows/deploy-cloudflare-worker.yml` only after the Bybit-bridge PR no longer conflicts, or place Brain snapshot compilation in a separate deploy step that cannot mutate trading switches.

**Interfaces:**
- CI compiles snapshot from `${{ github.sha }}` before Worker preparation.
- Benchmark prints machine-readable `FAST_ROUTE_P50_MS`, `FAST_ROUTE_P95_MS`, `FAST_EXTERNAL_CALLS`.
- Required gate: external calls exactly 0; p95 target <=25ms is reported and should fail only if project policy explicitly chooses hard enforcement after baseline evidence.

- [ ] **Step 1: Add RED CI/static checks**

CI must fail if:
- snapshot compiler is not run;
- snapshot validator fails;
- generated snapshot SHA differs from checkout SHA;
- Node no-network test fails;
- Wrangler bundle cannot consume generated snapshot.

- [ ] **Step 2: Add benchmark**

Benchmark at least 10,000 warm local route selections across representative Vietnamese/English FAST inputs; use `performance.now()` and calculate sorted p50/p95. Patch `fetch` to increment/fail on calls and assert zero calls.

- [ ] **Step 3: Integrate compilation before `prepare:wrangler`**

GitHub Actions sequence:
```bash
python AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py --source-sha "$GITHUB_SHA" --output AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json
python AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json
cd cloudflare-worker
npm install --no-audit --no-fund
npm run prepare:wrangler
node test-skill-gateway.mjs
node test-skill-gateway-handler.mjs
node benchmark-skill-gateway.mjs
npx wrangler deploy --dry-run --outdir .wrangler-skill-gateway
```

- [ ] **Step 4: Run full canonical validators**

```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -v
python AI_SKILL_LIBRARY/validate_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_authority.py
python AI_SKILL_LIBRARY/validate_runtime.py
python AI_SKILL_LIBRARY/validate_v3.py
python AI_SKILL_LIBRARY/validate_v4.py
```
Expected: all PASS.

- [ ] **Step 5: Commit Task 5**

Commit CI/benchmark changes only after local/Actions evidence is green.

---

### Task 6: Production rollout, exact-main proof and rollback contract

**Files:**
- Modify: `AGENTS.md` to state every GitHub Brain request requires one primary skill/capsule and FAST uses hot snapshot rather than per-request GitHub refresh.
- Modify: `AI_SKILL_LIBRARY/checkpoint.json` to add paths for the snapshot compiler/schema/aliases and runtime gateway contract after production proof.
- Modify: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` only after exact-main production verification.
- Modify: PR/CI deployment workflow as needed to promote the exact-main snapshot without changing trading runtime switches.

**Interfaces:**
- Production `/brain/health` must show merged main `sourceSha`.
- Production `/brain/route` smoke cases must show exactly one primary skill + capsule.
- Last-known-good snapshot remains the rollback target.

- [ ] **Step 1: Open implementation PR and require all prior gates**

PR description records spec/plan paths and confirms no trading strategy/authority change.

- [ ] **Step 2: Merge only with green Brain + Cloudflare checks**

Required evidence: policy tests, compiler tests, all V4 validators, Node router/handler tests, no-network test, benchmark report, Wrangler real dry-run.

- [ ] **Step 3: Build/promote exact-main snapshot**

Use merged `${GITHUB_SHA}` as `source_sha`; reject deploy if snapshot and runtime revisions differ.

- [ ] **Step 4: Run production smoke matrix**

Minimum cases:
```text
"giải thích khái niệm này" -> FAST/core_reasoning
"sửa lỗi API" -> STANDARD or DEEP/debugging depending mutation/tool context
"viết quảng cáo giày" -> FAST or STANDARD/advertising_copy
"viết prompt video giữ nhân vật" -> STANDARD/video_prompt with bounded support if needed
"nghiên cứu học thuật có nguồn" -> STANDARD/academic_research
"quét BTC live" -> DEEP/trading_router
unknown nonsense -> FAST/core_reasoning
```
Every response must include a valid capsule and `externalRoutingCalls=0` for the routing stage.

- [ ] **Step 5: Measure production routing metadata and compare with baseline**

Record warm p50/p95 from the gateway runtime where available; otherwise record CI benchmark plus production request timing separately. Do not claim model-generation latency improved unless measured.

- [ ] **Step 6: Update AGENTS/checkpoint/global checkpoint only after proof**

Document exact merged SHA, snapshot schema/version, fallback behavior and last-known-good rollback. Preserve all existing Trading authority paths and high-risk prohibitions.

- [ ] **Step 7: Final verification before declaring complete**

Run/confirm:
```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -v
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_authority.py
python AI_SKILL_LIBRARY/validate_v4.py
```
Plus production `/brain/health` and routing smoke matrix. Completion claim requires exact-main SHA match and green evidence.

---

## Plan Self-Review

- Spec coverage: primary-skill requirement, execution capsules, deterministic multilingual selection, exact-SHA snapshot, FAST zero-network path, STANDARD/DEEP escalation, quality gate, observability, benchmark, security and rollback are each assigned to a task.
- Placeholder scan: no TBD/TODO/“implement later” steps remain.
- Type/interface consistency: compiler produces one canonical snapshot consumed by Cloudflare generation; router produces `RouteDecision`; quality gate consumes that decision plus execution metadata; diagnostics expose only bounded route fields.
- Scope isolation: Bybit public-bridge repair remains outside this plan; no trading execution behavior is modified.
