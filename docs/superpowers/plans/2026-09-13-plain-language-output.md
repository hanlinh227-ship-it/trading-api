# Plain Language Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the Brain's technical processing unchanged while adding simple Vietnamese display names and a user-facing plain-language policy after verification.

**Architecture:** Add one stable presentation policy plus one complete display-name map. The Skill Gateway compiler embeds presentation metadata into the exact-SHA snapshot, routing keeps internal IDs unchanged, and the route response adds a separate easy display name. The response-quality layer gains an optional plain-language check for ordinary user-facing text without rewriting exact code, commands, numbers, dates, or machine tokens.

**Tech Stack:** YAML, Python 3.12, JSON Schema, JavaScript/Node 22, Cloudflare Worker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-plain-language-output-design.md`

## Global Constraints

- Internal canonical skill IDs, routing IDs, file names, API fields, execution capsules, and project authority stay unchanged.
- Normal user-facing display names contain no underscore characters.
- Default user-facing language is simple Vietnamese suitable for a nontechnical reader.
- Exact numbers, dates, prices, limits, warnings, uncertainty, code, commands, API fields, and machine tokens must remain exact when required.
- The presentation layer has no routing, tool, trading, security, or permission authority.
- Trading permissions and project authority must remain unchanged.
- FAST external routing calls must remain zero.
- No local installation becomes required.

---

### Task 1: Add RED contracts for presentation metadata

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_plain_language_presentation.py`
- Modify: `cloudflare-worker/test-skill-gateway.mjs`
- Modify: `cloudflare-worker/test-skill-gateway-handler.mjs`

**Interfaces:**
- Consumes: existing compiled snapshot and `routeSkillRequest()`.
- Produces: failing requirements for `presentation`, `display_name`, route `primarySkillName`, no-underscore labels, preserved internal `primarySkill`, and optional answer-text quality checks.

- [ ] **Step 1: Write failing Python tests**

Test that the compiled snapshot contains `presentation`, every canonical skill has a non-empty Vietnamese-facing `display_name`, and no display name contains `_`. Assert the four newly added skills resolve to `Tạo kỹ năng`, `Kiểm tra kỹ năng`, `Kiểm tra chiến lược`, and `Kiểm tra mô hình 3D`.

- [ ] **Step 2: Write failing Worker tests**

Extend the fixture with presentation metadata, then assert routing still returns the exact internal ID and additionally returns an easy `primarySkillName`. Add response-quality tests showing ordinary answer text containing a mapped internal ID fails, while exact technical mode permits it.

- [ ] **Step 3: Run PR CI to confirm RED**

Expected: new presentation tests fail because the stable presentation files/compiler/runtime fields do not exist yet; existing unrelated validators should remain green.

- [ ] **Step 4: Commit RED tests**

Commit message: `test(brain): add plain-language presentation contracts`.

---

### Task 2: Add stable plain-language policy and complete display names

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/presentation.yaml`
- Create: `AI_SKILL_LIBRARY/v4/stable/display_names.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

**Interfaces:**
- Consumes: canonical skill IDs from the V4 router/catalog.
- Produces: `presentation.yaml` policy and `display_names.yaml` mapping keyed by internal skill ID.

- [ ] **Step 1: Add the policy file**

Define locale `vi`, default mode `plain`, direct-answer-first behavior, familiar-word preference, technical-term explanation, internal-ID hiding by default, exact-token exceptions, warning/uncertainty preservation, and `no_underscore_display_names: true`.

- [ ] **Step 2: Add the display-name map**

Provide a simple Vietnamese display name for every canonical primary skill plus selected infrastructure names. Examples include `skill_engineering: Tạo kỹ năng`, `eval_engineering: Kiểm tra kỹ năng`, `quant_validation: Kiểm tra chiến lược`, `asset_validation_3d: Kiểm tra mô hình 3D`, `risk_management: Quản lý rủi ro`, `live_data_validation: Kiểm tra dữ liệu trực tiếp`, and `task_router: Bộ chọn cách xử lý`.

- [ ] **Step 3: Expose paths from checkpoint**

Add checkpoint fields for the stable presentation policy and display-name map without changing routing authority.

- [ ] **Step 4: Run static tests**

Expected: mapping completeness/no-underscore tests move toward GREEN; compiler-related tests remain RED until Task 3.

- [ ] **Step 5: Commit stable presentation configuration**

Commit message: `feat(brain): add plain-language presentation policy`.

---

### Task 3: Compile presentation metadata into the Skill Gateway snapshot

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py`
- Modify: `AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json`
- Modify: `AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py` if current validator needs an explicit presentation check.

**Interfaces:**
- Consumes: `presentation.yaml`, `display_names.yaml`, canonical skill catalog and router.
- Produces snapshot fields `presentation` and skill metadata field `display_name`; adds presentation source hashes without changing capsule hashes or internal routing IDs.

- [ ] **Step 1: Load and validate presentation files**

Compiler must reject missing mappings, empty names, underscore-containing display names, non-string names, or mappings for unknown canonical IDs.

- [ ] **Step 2: Embed display names**

Add `display_name` to each compiled skill row and add a compact `presentation` object with locale/mode/rules needed by the runtime.

- [ ] **Step 3: Extend schema and snapshot validator**

Require presentation metadata while keeping schema version compatible if the existing additional-properties contract allows it; otherwise bump only the snapshot schema in a backward-compatible coordinated change.

- [ ] **Step 4: Run compiler tests**

Expected: all Python plain-language tests pass and existing skill/capsule counts remain unchanged.

- [ ] **Step 5: Commit compiler changes**

Commit message: `feat(brain): compile easy display names into gateway snapshot`.

---

### Task 4: Add user-facing names and plain-language quality checks to runtime

**Files:**
- Modify: `cloudflare-worker/skill-gateway.js`
- Modify: `cloudflare-worker/skill-gateway-handler.js`
- Modify: `cloudflare-worker/test-skill-gateway.mjs`
- Modify: `cloudflare-worker/test-skill-gateway-handler.mjs`
- Modify: `cloudflare-worker/test-skill-gateway-snapshot.mjs`

**Interfaces:**
- Consumes: snapshot skill `display_name` and presentation policy.
- Produces: route field `primarySkillName` while retaining internal `primarySkill`; `assertResponseQuality()` optionally validates `execution.answerText` when `execution.technicalOutput !== true`.

- [ ] **Step 1: Add display name to route result**

Set `primarySkillName` from compiled metadata. Do not rename or remove `primarySkill`, `capsuleId`, or any machine field.

- [ ] **Step 2: Add optional plain-language quality check**

When normal `answerText` is supplied, reject mapped internal identifiers exposed as ordinary prose. When `technicalOutput === true`, permit exact internal machine identifiers. The check must never alter the answer text itself.

- [ ] **Step 3: Add health metadata**

Expose a simple boolean such as `plainLanguagePresentation: true` and locale `vi` on `/brain/health`, without changing existing health fields.

- [ ] **Step 4: Run Worker tests and benchmark**

Expected: routing skills/profiles remain identical, all handler tests pass, FAST external calls remain `0`, and routing latency remains within the existing benchmark envelope.

- [ ] **Step 5: Commit runtime changes**

Commit message: `feat(brain): expose easy names at the answer boundary`.

---

### Task 5: Protect authority, trading, and exact-data behavior

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_plain_language_presentation.py`
- Test existing: `AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml`
- Test existing: `AI_SKILL_LIBRARY/v4/stable/router.yaml`

**Interfaces:**
- Consumes: final presentation configuration and compiled snapshot.
- Produces regression evidence that presentation cannot alter authority/routing.

- [ ] **Step 1: Add authority regression assertions**

Assert the trading domain remains read-only where currently configured, project authority remains required, and the new presentation files contain no permission/tool/routing fields.

- [ ] **Step 2: Add exact-data preservation tests**

Use representative text with `150 USD`, `13/09/2026`, warnings, uncertainty wording, code/command blocks, and internal tokens. The checker must validate presentation without modifying exact material.

- [ ] **Step 3: Run the focused regression suite**

Expected: all presentation, router, authority, trading, and Worker tests pass.

- [ ] **Step 4: Commit guardrails**

Commit message: `test(brain): protect accuracy and authority in plain-language mode`.

---

### Task 6: Build release, run full CI, and verify production

**Files:**
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/4.5.0/**`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- Generated snapshot as required by existing CI/deploy workflow.

**Interfaces:**
- Consumes: completed branch implementation.
- Produces: immutable release `4.5.0`, fresh retrieval index, exact-SHA production deployment.

- [ ] **Step 1: Generate release/index using repository tools only**

Use the canonical release and index builders through the existing cloud CI/release path; do not hand-edit generated hashes/history/index files.

- [ ] **Step 2: Run the single validation entrypoint and full CI**

Require all Brain tests, repository tests, router/authority/runtime/V4/registry/gateway validators, release check, retrieval freshness, Worker tests, zero-local checks, and Cloudflare dry-run to pass.

- [ ] **Step 3: Review final PR diff**

Confirm no temporary workflow remains, no internal skill ID was renamed, no trading authority widened, all display names are simple/no-underscore, and generated files are tool-produced.

- [ ] **Step 4: Merge with expected head SHA**

Use squash merge only after final exact-tree CI is green.

- [ ] **Step 5: Verify production after merge**

Require the automatic exact-main Cloudflare deployment to succeed. Verify `/runtime/contract` and `/brain/health` report the merged SHA, route smoke still selects the same internal primary skills/profiles, `plainLanguagePresentation=true`, FAST external routing calls remain zero, and runtime trading switches were not changed.
