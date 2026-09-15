# AI Legion and OpenCode Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a bounded specialist AI Legion and a cloud OpenCode coding worker so Brain can decompose DEEP/STANDARD work, assign the smallest useful set of specialists/models/tools, execute code work in isolation, and merge verified outputs without parallel authority.

**Architecture:** The canonical Legion catalog and task-graph rules live in `AI_SKILL_LIBRARY/v4/legion/` and are compiled into a runtime snapshot. `crypto-research-gateway` gains an orchestration client that consumes only the validated snapshot and Adaptive Model Mesh; a separate `opencode-worker` service hosts OpenCode for isolated plan/explore/research/patch/test/review jobs. The OpenCode service gets its own Brain runtime policy so its sandboxed process/shell capability does not widen the existing research gateway execution boundary. Patterns from Awesome LLM Apps are absorbed as bounded specialist/MCP/Mixture-of-Agents workflows, not copied as a second framework.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, Node.js 22, TypeScript, Fastify 5.12.4, Zod 4.0.0, `@opencode-ai/sdk@1.18.31`, OpenCode CLI/server, Railway cloud runtime, unittest/node:test.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`

## Global Constraints

- Brain `task_router` remains the only router authority; Legion is post-route execution only.
- FAST uses zero Legion workers and no OpenCode call.
- STANDARD <= 2 concurrent workers; DEEP <= 4; hard graph nodes <= 10.
- One primary Brain skill remains mandatory. Agent roles are execution metadata, never replacement reasoning authorities.
- Same model family on multiple providers is availability redundancy, not reasoning diversity.
- OpenCode explicit Brain `deny` always wins; OpenCode auto mode may not widen permissions.
- OpenCode `plan`, `explore`, `research`, `review` are read-only. `patch` writes only to an isolated workspace/branch and allowed paths. `test` executes only approved command prefixes.
- The existing `crypto-research-gateway` keeps `shell_execution=false` and `local_process_spawn=false`; only the separate OpenCode worker may spawn its managed OpenCode process inside its isolated service boundary.
- No worker may push to `main`, mutate credentials, perform live financial execution, or access secret-bearing files outside explicit runtime authorization.
- External upstream code is untrusted until sandbox/eval gates pass.
- No Mixture-of-Agents vote counting; outputs are normalized into claims/evidence and checked before synthesis.
- Provider/runtime failure degrades to bounded serial execution or last known-good Stable behavior.

---

### Task 1: Define Legion agent contracts and specialist catalog

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- Create: `AI_SKILL_LIBRARY/v4/legion/orchestration.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_agent.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_task_graph.schema.json`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_catalog.py`

**Interfaces:**
- Consumes: canonical domains in `v4/mesh/graph.yaml` and model capability dimensions in `v4/model_mesh/domain_capabilities.yaml`.
- Produces: typed specialist definitions and task graph schema.

- [ ] **Step 1: Write RED tests for every required division**

```python
REQUIRED_DIVISIONS = {
    "engineering", "security", "research", "data_docs", "creative",
    "ux_ui", "design_3d", "automation", "deployment", "trading_research",
    "business", "game", "academic", "checker",
}

def test_catalog_has_required_specialists_and_no_authority():
    catalog = load_catalog()
    assert REQUIRED_DIVISIONS <= set(catalog["agents"])
    for agent in catalog["agents"].values():
        assert agent["routing_authority"] is False
        assert agent["reasoning_authority"] is False
        assert agent["permission_ceiling"]
        assert agent["risk_ceiling"]
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_catalog -v
```

- [ ] **Step 3: Implement typed agent rows**

Every agent row must contain:

```yaml
role: engineering_maker
domain: engineering
accepted_input_schema: legion_task_v1
output_contract: evidence_artifact_v1
tools: [repository_read, isolated_patch, test_runner]
sources: [project_authority, approved_docs, approved_upstreams]
permission_ceiling: reversible_write_isolated
risk_ceiling: reversible_write
model_capabilities: {coding: 0.8, text_reasoning: 0.7, tool_calling: 0.5}
concurrency_budget: 1
retry_budget: 2
provenance_required: true
verification_required: true
routing_authority: false
reasoning_authority: false
```

Trading specialist must use `risk_ceiling: read_only` and `financial_execution: false`.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_catalog -v
git add AI_SKILL_LIBRARY/v4/legion/agents.yaml AI_SKILL_LIBRARY/v4/legion/orchestration.yaml AI_SKILL_LIBRARY/v4/schemas/legion_agent.schema.json AI_SKILL_LIBRARY/v4/schemas/legion_task_graph.schema.json AI_SKILL_LIBRARY/tests/test_ai_legion_catalog.py
git commit -m "feat: define AI Legion specialist contracts"
```

---

### Task 2: Implement bounded task decomposition and agent assignment

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/legion.py`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_task_graph.py`

**Interfaces:**
- Produces:
  - `compile_task_graph(objective: dict, *, profile: str, agent_catalog: dict) -> dict`
  - `select_agent(task: dict, agents: list[dict], *, model_candidates: list[dict]) -> dict | None`
  - `validate_delegation(parent: dict, child: dict) -> bool`
  - `merge_contract(graph: dict) -> dict`

- [ ] **Step 1: Write RED tests for bounded decomposition**

```python
def test_fast_is_serial_and_spawns_no_legion_workers():
    graph = compile_task_graph({"domain": "engineering", "steps": ["inspect"]}, profile="FAST", agent_catalog=CATALOG)
    assert graph["worker_nodes"] == []

def test_deep_never_exceeds_global_limits():
    graph = compile_task_graph(LARGE_OBJECTIVE, profile="DEEP", agent_catalog=CATALOG)
    assert len(graph["nodes"]) <= 10
    assert graph["max_parallel"] <= 4
```

Also test dependency cycles, duplicate artifact ownership, delegation permission widening, and same-task blind fan-out are rejected.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_task_graph -v
```

- [ ] **Step 3: Implement graph compiler**

Graph nodes use exact fields:

```python
{
  "task_id": "t1",
  "role": "researcher",
  "domain": "engineering",
  "depends_on": [],
  "input_hash": "sha256",
  "artifact_owner": "research-evidence",
  "permission_ceiling": "read_only",
  "risk_ceiling": "read_only",
  "verification": ["schema", "provenance"],
}
```

Decomposition must prefer independent subwork and the smallest worker set. No child can exceed parent permission/risk ceilings.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_task_graph -v
git add AI_SKILL_LIBRARY/v4/tools/legion.py AI_SKILL_LIBRARY/tests/test_ai_legion_task_graph.py
git commit -m "feat: add bounded AI Legion task graphs"
```

---

### Task 3: Absorb Awesome LLM Apps specialist/MCP/MoA patterns safely

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/upstreams.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/legion.py`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_upstream_patterns.py`

**Interfaces:**
- Produces:
  - `build_specialist_round(task: dict, *, roles: list[str]) -> dict`
  - `normalize_worker_output(output: dict) -> dict`
  - `needs_checker(outputs: list[dict]) -> bool`

- [ ] **Step 1: Write RED tests**

Tests must prove:
- maintained canonical upstream is `Shubhamsaboo/awesome-llm-apps` with Apache-2.0 evidence;
- user-supplied fork is mirror/reference only;
- absorbed patterns are `multi_agent_specialists`, `mcp_specialist_routing`, `bounded_mixture_of_agents`, `agentic_rag`, `corrective_rag`, `multimodal_team`, `research_planner_executor`;
- no code/app is imported wholesale;
- no worker count determines truth.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_upstream_patterns -v
```

- [ ] **Step 3: Implement bounded perspective rounds**

Use pipeline:

```text
selected diverse specialists -> normalized outputs -> claims/evidence -> conflict detector -> checker when material -> evidence-weighted synthesis
```

`needs_checker()` returns true on material contradiction, high-impact DEEP work, schema failure, or verification disagreement; it must not trigger merely because there are multiple outputs.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_upstream_patterns -v
git add AI_SKILL_LIBRARY/v4/legion/upstreams.yaml AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml AI_SKILL_LIBRARY/v4/tools/legion.py AI_SKILL_LIBRARY/tests/test_ai_legion_upstream_patterns.py
git commit -m "feat: absorb bounded multi agent patterns"
```

---

### Task 4: Build a validated Legion runtime snapshot

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_runtime_snapshot.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_legion_snapshot.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_legion_snapshot.py`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_snapshot.py`

**Interfaces:**
- `compile_legion_snapshot(root: Path, *, source_sha: str, output: Path) -> dict`
- `validate_legion_snapshot(root: Path, snapshot_path: Path, *, expected_source_sha: str) -> list[str]`

- [ ] **Step 1: Write RED tests**

Require deterministic output, exact source SHA, no secrets, max concurrency copied from Stable budgets, all agent contracts schema-valid, `routing_authority=false`, `reasoning_authority=false`, and FAST worker limit zero.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_snapshot -v
```

- [ ] **Step 3: Implement whitelist-only compiler and validator**

Snapshot must include `source_sha`, `agents`, `profiles`, `allowed_modes`, `model_mesh_contract`, `permission_ceiling`, `opencode_runtime_policy_hash`, `upstream_pattern_refs`, and schema hashes; do not copy arbitrary YAML keys.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_snapshot -v
git add AI_SKILL_LIBRARY/v4/schemas/legion_runtime_snapshot.schema.json AI_SKILL_LIBRARY/v4/tools/compile_legion_snapshot.py AI_SKILL_LIBRARY/v4/tools/validate_legion_snapshot.py AI_SKILL_LIBRARY/tests/test_ai_legion_snapshot.py
git commit -m "feat: compile AI Legion runtime snapshot"
```

---

### Task 5: Add an isolated cloud OpenCode worker with a separate Brain runtime policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/opencode_runtime.yaml`
- Create: `opencode-worker/package.json`
- Create: `opencode-worker/tsconfig.json`
- Create: `opencode-worker/src/contracts.ts`
- Create: `opencode-worker/src/policy.ts`
- Create: `opencode-worker/src/opencode.ts`
- Create: `opencode-worker/src/server.ts`
- Create: `opencode-worker/test/policy.test.ts`
- Create: `opencode-worker/test/server.test.ts`
- Create: `opencode-worker/railway.toml`
- Test: `AI_SKILL_LIBRARY/tests/test_opencode_runtime_policy.py`

**Interfaces:**
- HTTP `GET /health`
- HTTP `GET /capabilities`
- HTTP `POST /v1/jobs`
- Job modes: `plan | explore | research | patch | test | review`
- Request type:

```ts
export type OpenCodeJob = {
  jobId: string;
  mode: 'plan' | 'explore' | 'research' | 'patch' | 'test' | 'review';
  repoUrl: string;
  baseSha: string;
  prompt: string;
  allowedPaths: string[];
  allowedCommands: string[];
  permissionCeiling: 'read_only' | 'reversible_write_isolated';
  timeoutMs: number;
};
```

- [ ] **Step 1: Write RED Brain runtime-policy tests**

Require `reasoning_authority=false`, `routing_authority=false`, `service_isolation_required=true`, `stable_secret_access=false`, `financial_execution=false`, `main_push=false`, `workspace=temporary_exact_sha`, and process/shell execution allowed only inside the OpenCode service sandbox.

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_opencode_runtime_policy -v
```

Expected: FAIL because the policy file does not exist.

- [ ] **Step 2: Implement `opencode_runtime.yaml` and create package with pinned dependencies**

Minimum policy:

```yaml
version: 1
routing_authority: false
reasoning_authority: false
service_isolation_required: true
stable_secret_access: false
financial_execution: false
destructive_production_action: false
credential_mutation: false
main_push: false
workspace: temporary_exact_sha
shell_execution: sandbox_only
process_spawn: managed_opencode_process_only
allowed_modes: [plan, explore, research, patch, test, review]
```

`package.json` must pin:

```json
{
  "type": "module",
  "dependencies": {
    "@opencode-ai/sdk": "1.18.31",
    "fastify": "5.12.4",
    "zod": "4.0.0"
  }
}
```

Keep a lockfile generated by the package manager used by CI; do not use floating dependency ranges.

- [ ] **Step 3: Write RED worker permission tests**

```ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPermissionConfig } from '../src/policy.js';

test('review mode denies edits and shell writes', () => {
  const p = buildPermissionConfig({ mode: 'review', allowedPaths: [], allowedCommands: [] });
  assert.equal(p.edit, 'deny');
  assert.equal(p.external_directory, 'deny');
});
```

Also assert `patch` may edit only allowed paths, `test` allows only approved command prefixes, `.env*` reads are denied, `git push`/credential commands are denied in all modes, and no mode can widen the Brain ceiling.

- [ ] **Step 4: Run RED worker tests**

```bash
cd opencode-worker && npm test
```

Expected: FAIL until policy/server modules exist.

- [ ] **Step 5: Implement OpenCode lifecycle**

Use `@opencode-ai/sdk` to launch/connect to an OpenCode server inside the isolated worker environment. Generate OpenCode config from the Brain job contract; explicit denies override every permissive default. Create one temporary workspace per job keyed by `jobId`, check out exact `baseSha`, and delete the workspace after artifact extraction.

Return only:

```ts
{
  jobId, mode, sourceSha, status,
  patch, artifacts, commandResults,
  provenance, modelId, providerId,
  durationMs, verification
}
```

Never return hidden reasoning or secret-bearing environment values.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_opencode_runtime_policy -v
cd opencode-worker && npm test && npm run typecheck
cd ..
git add AI_SKILL_LIBRARY/v4/legion/opencode_runtime.yaml AI_SKILL_LIBRARY/tests/test_opencode_runtime_policy.py opencode-worker
git commit -m "feat: add isolated OpenCode cloud worker"
```

---

### Task 6: Connect the Gateway to Legion and OpenCode without changing live-price authority

**Files:**
- Create: `crypto-research-gateway/src/legion/contracts.ts`
- Create: `crypto-research-gateway/src/legion/orchestrator.ts`
- Create: `crypto-research-gateway/src/legion/opencode-client.ts`
- Modify: `crypto-research-gateway/src/server.ts`
- Test: `crypto-research-gateway/test/legion-orchestrator.test.ts`
- Test: `crypto-research-gateway/test/opencode-client.test.ts`

**Interfaces:**
- `planLegionTask(input: LegionRequest, snapshot: LegionSnapshot): LegionPlan`
- `executeLegionPlan(plan: LegionPlan, deps: ExecutionDeps): Promise<LegionResult>`
- `mergeLegionResults(results: WorkerResult[]): LegionResult`
- New HTTP route: `POST /brain/legion/execute`

- [ ] **Step 1: Write RED runtime tests**

Test FAST rejection/no-op, STANDARD<=2, DEEP<=4, timeout/retry limits, immutable input hashes, checker on material conflict, no live-price route mutation, and OpenCode failure degrading to serial/non-coding path rather than disabling `/research/market`.

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- --test-name-pattern="legion|opencode"
```

- [ ] **Step 3: Implement orchestrator**

Runtime plan consumes validated Legion + Model Mesh snapshots only. It must not infer new routing authority. Require `DEPLOYMENT_SOURCE_SHA` match for active execution claims. The gateway calls OpenCode over its bounded internal client; it does not itself spawn OpenCode or enable shell/process execution.

- [ ] **Step 4: Expose capabilities safely**

`GET /capabilities` may advertise Legion modes but must retain current research-safe tool list and must not claim high-risk execution capability. `/research/market` behavior and Bybit/Binance execution-quote semantics stay unchanged.

- [ ] **Step 5: Run full gateway regression and commit**

```bash
cd crypto-research-gateway && npm test && npm run typecheck
cd ..
git add crypto-research-gateway/src/legion crypto-research-gateway/src/server.ts crypto-research-gateway/test
git commit -m "feat: orchestrate bounded AI Legion workers"
```
