# Adaptive Free Model Mesh — Multidomain Extension Design

Date: 2026-09-15
Status: Approved design extension, implementation not started
Repository: `hanlinh227-ship-it/trading-api`
Canonical branch: `main`
Extends: `docs/superpowers/specs/2026-09-15-adaptive-free-model-mesh-design.md`
Checkpoint-resolved baseline: Brain V4 / release 4.8.1 at approval time

## 1. Purpose

Extend the approved Adaptive Free Model Mesh from a general free-provider execution pool into a multidisciplinary execution fabric that can assist every routed Brain domain without creating parallel reasoning authority.

The user goal is to make the system faster, smoother, more resilient, and more capable across disciplines by maintaining the broadest practical pool of legitimately free/free-tier models and assigning independent subtasks to complementary models in parallel.

This extension is normative with the base Adaptive Free Model Mesh design. If the two documents appear to conflict, the stricter authority, security, privacy, quota, and verification rule wins.

## 2. Meaning of “all free models”

“All free models” does not mean a permanent hard-coded list and does not mean every model runs on every request.

For this system it means:

> every remotely accessible model/provider candidate that is currently verified to have zero-current-cost usage for the active account or public free tier, is permitted by provider terms, is compatible with the Brain permission/data class, is reachable through the approved cloud runtime, and passes the minimum capability/quality/health gates.

The pool is therefore open-ended and time-sensitive.

A model may automatically enter or leave the eligible pool when its current verified status changes. No model is entitled to permanent membership.

The system must never use IP rotation, account cycling, key farming, proxy hopping, region hopping, or other quota/rate-limit circumvention to preserve free status.

## 3. Authority invariants

This extension preserves the current Brain contracts:

- one canonical `task_router`;
- exactly one primary reasoning skill and validated execution capsule per routed request;
- provider/model workers are execution/evidence resources only;
- provider/model outputs never become project authority or routing authority;
- no majority vote for truth;
- no silent averaging of conflicting claims;
- project authority, current runtime evidence, Stable security, risk policy, and verified sources outrank model opinion;
- FAST keeps zero external routing calls;
- STANDARD/DEEP may use bounded mesh execution only after canonical routing;
- no hidden chain-of-thought persistence;
- no secret/credential/private-key leakage to free external endpoints;
- no automatic widening of repository-write, production-write, wallet, trading execution, credential, destructive, or financial permissions.

The mesh starts after canonical routing and can never bypass it.

## 4. Multidomain coverage

The model mesh must support the current canonical Brain domains as capability workers. The domain router remains authoritative; model specialization is only an execution choice within the routed domain.

### 4.1 Core / research / reasoning

Useful capabilities:

- general reasoning;
- fact-check assistance;
- decomposition/planning;
- comparison;
- long-context synthesis;
- multilingual understanding;
- structured output;
- contradiction detection.

Models are not sources. Current claims still require authoritative external evidence when the task requires it.

### 4.2 Engineering

Useful capabilities:

- code generation and review;
- debugging;
- test generation;
- architecture analysis;
- API/schema reasoning;
- database reasoning;
- security review;
- Android/web/deployment analysis;
- automation;
- skill/eval engineering.

Repository mutation remains controlled by the canonical engineering workflow. Multiple workers may analyze independent areas in parallel, but competing edits to the same resource may not be silently merged.

### 4.3 Trading

Useful capabilities are limited to the existing Trading authority and safety boundary:

- market research;
- technical/quantitative analysis;
- strategy/backtest reasoning;
- code review for trading systems;
- risk analysis;
- cross-market research;
- interpretation of approved live-data evidence.

Free models must never fabricate current prices, account state, fills, balances, positions, or runtime status. They do not gain order execution, wallet, transfer, leverage-change, or other high-risk authority.

### 4.4 Game development

Useful capabilities:

- game design;
- gameplay systems;
- Godot/Unity code;
- AI/NPC logic;
- 2D/3D asset planning;
- level/system design;
- runtime/debug reasoning.

### 4.5 Design 2D / UX / product

Useful capabilities:

- UX/UI critique;
- interaction flows;
- component/state reasoning;
- graphic design analysis;
- branding/typography/layout;
- accessibility checks;
- design-to-code assistance;
- multimodal visual analysis when the selected model supports vision.

Specialized design/generation tools remain tools; language models do not replace Figma/image-generation authority.

### 4.6 Design 3D / Blender

Useful capabilities:

- modeling/topology/UV guidance;
- material/lighting/rigging reasoning;
- animation planning;
- Blender scripting;
- asset validation logic;
- render troubleshooting;
- multimodal inspection when supported.

Free text/vision models may analyze and advise; actual 3D generation/validation still uses approved specialized tools where required.

### 4.7 Adobe / media workflows

Useful capabilities:

- Photoshop/Illustrator/Premiere/After Effects workflow reasoning;
- edit planning;
- compositing logic;
- export settings analysis;
- asset/prompt preparation.

External media-generation/editing tools remain capability tools, not replaced by the model mesh.

### 4.8 Prompt / image / video / animation

Useful capabilities:

- prompt engineering;
- image/video prompt generation;
- negative constraints;
- prompt debugging;
- character consistency;
- scene continuity;
- camera direction;
- storyboard reasoning;
- animation action consistency;
- vision-based inspection when available.

For stochastic generators, model consensus must never be represented as a guarantee that a render cannot fail.

### 4.9 Writing

Useful capabilities:

- scriptwriting;
- screenwriting;
- voice-over;
- advertising copy;
- hooks/retention;
- storytelling;
- multilingual adaptation.

### 4.10 Academic

Useful capabilities:

- literature-review assistance;
- methodology reasoning;
- qualitative/quantitative analysis;
- interdisciplinary synthesis;
- citation review.

Models are not citation authority. Claims requiring academic evidence must remain grounded in approved research sources/tools.

### 4.11 Data / documents

Useful capabilities:

- data analysis;
- spreadsheet reasoning;
- chart/report logic;
- document summarization;
- DOCX/PDF/slide planning;
- structured extraction and transformation.

Format-specific artifact tools remain authoritative for final file generation/validation.

### 4.12 Business / marketing

Useful capabilities:

- market/business analysis;
- positioning;
- product/marketing reasoning;
- campaign ideation;
- decision comparison;
- structured planning.

Fresh market/company claims still require current sources.

## 5. Capability taxonomy

Every discovered model must be benchmarked and tagged by measured capabilities rather than provider marketing alone.

Initial capability dimensions:

```yaml
text_reasoning
coding
math_quant
long_context
multilingual
vision
structured_output
tool_calling
planning
creative_writing
prompt_media
research_synthesis
data_analysis
low_latency
```

Optional future dimensions may be added through the existing harmonization process.

Each capability receives:

```yaml
supported: true | false | unknown
score: 0.0..1.0
evidence: benchmark references
verified_at: timestamp
```

Unknown capability never receives a positive routing preference until tested.

## 6. Domain-to-model matching

After `task_router` chooses the primary domain and primary skill, the mesh maps the routed subtask to capability requirements.

Example:

```text
video_prompt task
  -> prompt_media high
  -> multilingual high
  -> vision optional/required when an image is supplied
  -> coding irrelevant

MQL5 debugging
  -> coding high
  -> reasoning high
  -> structured_output useful
  -> math_quant useful

academic literature review
  -> long_context high
  -> research_synthesis high
  -> multilingual useful
  -> external evidence tool required
```

The worker selector filters incompatible models before scoring. A generally strong model must not automatically outrank a specialist that performs better on the routed task class.

## 7. Complementary worker roles

The mesh supports complementary roles instead of duplicated voting.

Possible roles:

- `maker`: produces the candidate solution;
- `researcher`: gathers/structures evidence supplied by approved sources;
- `specialist`: handles one domain-specific subproblem;
- `critic`: finds concrete defects or contradictions;
- `checker`: validates against task contract;
- `grader`: scores candidate against explicit criteria in DEEP/high-impact work;
- `summarizer`: compresses independent outputs for final synthesis.

A single request does not automatically instantiate all roles.

Role assignment must stay inside existing STANDARD/DEEP budgets.

## 8. Cross-domain task graphs

When one request spans multiple domains, the canonical router still selects one primary domain/skill according to existing policy. The mesh may create bounded secondary subtask labels for execution only.

Example:

```text
"build a trading dashboard and explain the strategy"

primary authority: engineering or project-resolved authority

subtask graph:
  A: backend/API analysis          -> engineering worker
  B: UX/dashboard state design    -> design worker
  C: trading terminology/risk     -> trading research worker
  D: verification                 -> checker
```

Secondary model workers never become secondary routers and never gain independent project authority.

## 9. Parallelism without conflict

The system should maximize useful concurrency, not raw model count.

Initial rule remains:

- FAST: zero mesh workers;
- STANDARD: one worker normally, up to two independent workers when budget permits;
- DEEP: up to four concurrent independent worker slots under the current Brain hard limit.

Tasks are parallel only when:

- inputs can be snapshotted;
- outputs have separate ownership or typed merge boundaries;
- no worker depends on the unfinished result of another worker;
- simultaneous writes cannot corrupt shared state.

If two workers would edit the same file/section/state, mutation ownership is serialized or isolated before merge.

## 10. Collective refinement pattern

“All models working together” is implemented as selective collective refinement, not all-model fan-out.

For a suitable DEEP task:

```text
canonical route
   |
planner/task graph
   |
+-- specialist A
+-- specialist B
+-- researcher C
   |
normalized result bus
   |
conflict detector
   |
checker/critic when material
   |
canonical synthesis
```

The available pool may contain dozens of models, while only the smallest useful complementary subset is active for the request.

This preserves quota, reduces latency, and decreases correlated errors.

## 11. Model-family and provider diversity

The registry must separate:

- `model_family`: underlying model identity;
- `provider_id`: serving path;
- `model_variant`: provider-specific quantization/context/tooling variant when material.

Different providers serving the same underlying model improve availability but do not count as independent reasoning diversity.

When complementary reasoning diversity is useful, the scheduler should prefer different validated model families after capability and policy gates are satisfied.

Diversity is a tie-break/quality feature, never a truth vote.

## 12. Dynamic discovery scope

Discovery should scan as broadly as practical using first-party model/provider catalogs and approved aggregator catalogs.

Initial discovery surfaces include, subject to current verified entitlement and terms:

- OpenCode Zen;
- OpenCode-supported provider catalog;
- Groq;
- Google Gemini Developer API;
- Cloudflare Workers AI;
- OpenRouter free catalog/router;
- Mistral free mode;
- Cohere trial/evaluation capacity;
- Hugging Face Inference Providers free allowance;
- NVIDIA hosted NIM developer access;
- Cerebras free/trial capacity where current entitlement is verified;
- SambaNova where current free entitlement is verified;
- Alibaba Model Studio free quotas where region/account terms permit;
- future providers discovered by Evergreen that satisfy the same gates.

The discovery system must not infer that a provider is free merely because OpenCode supports it.

## 13. Candidate lifecycle

Every newly discovered provider/model begins outside Stable execution:

```text
discovered
 -> quarantine
 -> provenance/terms/privacy check
 -> free-entitlement verification
 -> capability probe
 -> task-class benchmark
 -> model-family dedupe
 -> canary
 -> active free pool
```

Removal/demotion triggers include:

- payment required;
- free allocation removed;
- free-status evidence stale beyond policy;
- provider/model deprecated;
- privacy/terms become incompatible;
- persistent health failure;
- capability regression;
- security concern;
- account entitlement unavailable.

## 14. Free-only safety

The initial mode remains `FREE_ONLY`.

Rules:

- only verified zero-current-cost candidates can execute;
- unknown billing state is excluded;
- no silent fallback to a paid endpoint;
- no auto-purchase/credit top-up;
- no quota circumvention;
- when free capacity is exhausted, use another legitimately free eligible worker or return degraded capacity status;
- a future paid fallback requires separate explicit authorization.

## 15. Quota-aware continuous operation

The scheduler records provider/model headroom and reset/recovery metadata.

Preferred evidence order:

1. runtime/API quota and reset metadata;
2. response headers;
3. current account entitlement metadata;
4. current first-party documentation;
5. last verified snapshot within freshness TTL.

When quota is exhausted:

```text
ACTIVE
 -> COOLDOWN_QUOTA
 -> another eligible provider/model receives new work
 -> reset/recovery time reached
 -> bounded probe
 -> AVAILABLE when verified
```

A provider in cooldown is not repeatedly hammered.

## 16. Performance policy

The objective is lower wall-clock latency and higher useful throughput, not maximum request count.

The scheduler should optimize for:

- capability fit;
- measured quality;
- provider health;
- latency;
- reliability;
- quota headroom;
- context fit;
- privacy compatibility;
- provider/model-family diversity when useful.

The system should avoid using a high-cost-in-quota model for trivial subtasks when a fast small model meets the quality floor.

## 17. Model tiers by work type

The implementation may maintain dynamic tiers based on benchmark evidence:

### Fast workers

Small/fast models for:

- classification after canonical routing;
- extraction;
- formatting;
- simple transformations;
- lightweight checks;
- short summaries.

### Specialist workers

Models that benchmark strongly on a specific domain/capability.

### Deep workers

Stronger models reserved for complex reasoning, difficult debugging, cross-domain synthesis, or checker/grader roles.

Tier assignment is empirical and may change as models/providers change.

## 18. Benchmark suite

A model cannot be considered multidisciplinary merely because it answers generic prompts.

The mesh needs representative benchmark cases for each active Brain domain, including at minimum:

- core reasoning/fact-check structure;
- software coding/debugging;
- API/schema reasoning;
- trading research/quant reasoning without live-data fabrication;
- game design/code;
- UX/UI critique;
- 3D/Blender reasoning;
- image/video prompt constraints and continuity;
- script/copy writing;
- academic synthesis with evidence boundaries;
- data/document structured output;
- business analysis.

Benchmarks must include adversarial/conflict cases and protected regression checks.

## 19. Quality floor and reputation

Per model family/provider path, track task-class metrics such as:

```text
success_rate
schema_valid_rate
verifier_accept_rate
hallucination_or_unsupported_claim_rate
latency_p50
latency_p95
quota_failure_rate
privacy_or_policy_incident_count
```

A provider/model that is free but repeatedly fails quality floors must not remain preferred merely to maximize free capacity.

Reputation influences ranking only among candidates that already pass authority/security/privacy/capability gates.

## 20. Result normalization and merge

Every worker result must carry enough metadata to preserve traceability without hidden reasoning:

```text
task_id
subtask_id
input_hash
authority_revision
primary_skill_id
capsule_hash
domain_label
worker_role
provider_id
model_id
model_family
capability_scores_used
started_at
completed_at
latency_ms
quota_state
source_refs
verification_status
```

Merge rules:

- schema-invalid output is rejected;
- factual disagreements are resolved by authority/evidence, not vote;
- permission conflicts fail closed;
- code/artifact mutation conflicts use explicit ownership/isolation;
- unresolved material conflicts are escalated to verifier or disclosed.

## 21. Privacy routing

The base design data classes remain mandatory.

Broad free-model fan-out is permitted only for `PUBLIC` content.

`INTERNAL` and `CONFIDENTIAL` content require provider-specific verified retention/training compatibility.

`SECRET` content is never sent to external free endpoints.

The mesh must minimize prompt payloads and send each worker only the context required for its subtask.

## 22. Stable / Evergreen separation

Stable execution uses a last-known-good model snapshot and never waits for discovery.

Evergreen may continuously:

- discover new free candidates;
- revalidate free status;
- revalidate model lists;
- refresh quota semantics;
- benchmark new models;
- detect model/provider deprecation;
- prepare promotion/demotion candidates.

Evergreen failure must not stop Stable request handling.

No discovery event can mutate an in-flight Stable request.

## 23. Rollout extension

The base rollout phases remain, with multidisciplinary expansion added:

### Phase A — registry/discovery

Build dynamic provider/model inventory, free-status, privacy, family dedupe, and capability schema.

### Phase B — benchmark and shadow routing

Benchmark candidates by Brain domain and shadow-score actual routed task metadata without external task-content execution.

### Phase C — engineering/research canary

Enable low-risk `PUBLIC` engineering/core tasks first.

### Phase D — multidisciplinary canary

Add writing, prompt/media, design, game, academic, data/docs, and business subtasks after task-class quality/privacy gates pass.

### Phase E — trading research canary

Enable only allowed read-only Trading analysis/research subtasks with existing authority, freshness, and live-data restrictions intact.

### Phase F — performance tuning

Benchmark worker counts 1/2/3/4 and routing weights. Do not exceed the existing Brain concurrency hard limit without a separately approved architecture change.

## 24. Acceptance criteria added by this extension

In addition to the base design acceptance criteria:

1. Every current canonical Brain domain has a defined model-capability mapping.
2. Discovery can add new free models without hard-coding them into the request router.
3. A provider/model is not active solely because it appears in an OpenCode/provider catalog.
4. Multidisciplinary routing uses measured task-class capability scores.
5. Cross-domain requests can create bounded independent subtask labels without creating secondary routing authorities.
6. Same-family models on multiple providers are deduplicated for reasoning diversity.
7. The scheduler can select complementary workers from different validated model families when useful.
8. The system can run with one healthy free worker and can exploit up to the current bounded concurrency when independent subtasks exist.
9. Quality floors can demote a free model that is unreliable or weak.
10. No paid usage can occur in `FREE_ONLY`.
11. Free quota exhaustion results in legitimate cooldown/fallback, never evasion.
12. Secrets remain blocked from free external providers.
13. Domain benchmark regressions in correctness, authority, security, verification, or project isolation block promotion.
14. Existing FAST zero-external-call behavior remains unchanged.
15. Stable remains functional if the entire Free Model Mesh is unavailable.

## 25. Implementation boundary

This document approves architecture only. Implementation must follow the current repository engineering contract:

`RED -> minimum GREEN -> regression suite -> canonical validators -> CI -> exact-SHA release/deployment verification where runtime behavior changes`

Generated release manifests, hashes, snapshots, and retrieval indices must be produced by existing canonical tools and must not be hand-edited.

Any credential onboarding required by a provider is a separate explicit authorization step. Credentials must never be committed to GitHub.

## 26. Final design decision

The approved architecture is:

**Adaptive Free Model Mesh + Multidomain Capability Routing + Dynamic Free Discovery + Quota-Aware Scheduling + Bounded Parallel Task Graphs + Brain-Owned Conflict Resolution.**

The design deliberately maximizes the size and diversity of the *available* free model pool while minimizing the number of models activated per task. This is the mechanism that improves speed, smoothness, uptime, and multidisciplinary quality without turning the system into an unbounded, conflicting multi-agent swarm.
