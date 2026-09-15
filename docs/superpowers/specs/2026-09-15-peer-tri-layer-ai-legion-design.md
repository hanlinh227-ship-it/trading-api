# Peer Tri-Layer AI Legion — Design Specification

Date: 2026-09-15
Status: Approved in-chat design; written spec awaiting final user review
Repository: `hanlinh227-ship-it/trading-api`
Implementation branch baseline: `github-brain-v4-afmm-implementation2`

## 1. Purpose

Extend GITHUB_BRAIN_V4 into a single-authority, full-autonomous AI Legion that can:

- decompose work into bounded specialist tasks;
- route each task to the best available agent, model, tool, MCP, RAG path, or coding worker;
- run independent work concurrently without authority races;
- learn continuously from experience, curated sources, and open discovery;
- create, improve, merge, benchmark, canary, promote, and retire reusable skills;
- remain active during idle periods through a persistent cloud scheduler;
- preserve one Brain authority, one permission ceiling, and one promotion pipeline.

The design fuses useful patterns from three primary upstream families:

1. `Shubhamsaboo/awesome-llm-apps` (the user-supplied `awesome-llm-apps/awesome-llm-apps` is a fork): multi-agent teams, Mixture-of-Agents, MCP routing, agentic/corrective RAG, memory, multimodal and research-agent patterns.
2. `anomalyco/opencode`: coding execution, Plan/Build separation, primary/subagent patterns, child sessions, permission-scoped tools, MCP connectivity, provider abstraction, and isolated coding workers.
3. `ECNU-ICALK/AutoSkill` + `SkillEvo`: experience-driven skill creation, skill merging/versioning, replay-driven mutation, evaluation, champion selection, and controlled promotion.

These upstreams contribute capabilities and patterns only. None becomes routing authority or reasoning authority over GITHUB_BRAIN_V4.

## 2. Core invariants

The implementation MUST preserve all of the following:

- `GITHUB_BRAIN_V4` remains the only command/routing authority.
- Providers, models, agents, upstream frameworks, and generated skills are execution or evidence resources, never parallel authorities.
- A/B/C learning branches are peers: branch identity itself gives no fixed epistemic priority.
- Truth is never decided by majority vote.
- Evidence quality is claim-specific and is scored by provenance, freshness, reproducibility, benchmark evidence, domain authority, consistency, and verification outcome.
- No learning process may expand its own permission ceiling.
- No generated skill writes directly to stable without evaluation and promotion gates.
- External code is untrusted by default and executes only inside the approved sandbox/runtime boundary.
- Secrets, credentials, private keys, and raw sensitive data never enter learning corpora, generated skills, traces, or public-model prompts unless explicitly authorized by a higher security contract.
- Financial execution, destructive production actions, permission changes, and credential mutations remain explicit high-risk gates.
- Zero-local operation remains supported; persistent autonomy must run in cloud/runtime infrastructure, not rely on the user's PC or a ChatGPT browser session.

## 3. Architecture

```text
USER / EVENTS / IDLE SCHEDULER
            |
            v
     GITHUB BRAIN V4
  COMMANDER + AUTHORITY
            |
  +---------+----------+-------------------+
  |                    |                   |
  v                    v                   v
TASK ROUTER       LEARNING ORCH.      RUNTIME SUPERVISOR
  |                    |                   |
  v                    v                   v
TASK GRAPH       PEER TRI-LAYER       health/quota/queue
BUILDER          INTELLIGENCE         retries/circuit breaker
  |                    |
  |         +----------+----------+
  |         |          |          |
  |         v          v          v
  |         A          B          C
  |      Experience  Curated   Exploration
  |         |          |          |
  |         +----------+----------+
  |                    |
  |             INTELLIGENCE BUS
  |                    |
  |         compare/challenge/synthesize
  |                    |
  |              EVIDENCE ENGINE
  |                    |
  |               SKILL FACTORY
  |                    |
  |                 SKILLEVO
  |                    |
  |          sandbox -> eval -> canary
  |                    |
  +--------------------+-------------------+
                       |
                       v
                  AI LEGION
                       |
          specialist agent divisions
                       |
                       v
              ADAPTIVE MODEL MESH
                       |
              tools / MCP / RAG / code
                       |
                       v
             CHECKER / GRADER / MERGE
                       |
                       v
                    OUTPUT
```

## 4. Peer Tri-Layer Intelligence

### 4.1 Layer A — Experience

Sources include:

- successful and failed task trajectories;
- user corrections and accepted revisions;
- sanitized telemetry;
- regression failures;
- benchmark outcomes;
- model/provider reliability history;
- skill performance history.

### 4.2 Layer B — Curated Knowledge

Sources include:

- approved GitHub repositories;
- official documentation;
- current canonical Brain skills and policies;
- verified project authority files;
- trusted papers or datasets already admitted to the registry;
- approved plugin/tool metadata.

### 4.3 Layer C — Open Exploration

Sources include:

- public GitHub repositories not yet approved;
- public web sources;
- new papers and benchmarks;
- emerging agent frameworks;
- new free-model/provider opportunities;
- newly discovered tools and protocols.

### 4.4 Peer semantics

A, B, and C MUST have equal rights to:

- generate hypotheses;
- challenge another branch;
- request an experiment;
- create a skill candidate;
- propose a mutation;
- propose a new upstream source;
- produce evidence for or against an existing rule.

No fixed score such as `A > B > C` or `B > C` is allowed.

Operational safety constraints are not epistemic priority. For example, executable code from any branch, including A or B, still passes sandbox and security validation. Similarly, an official specification may carry stronger claim-specific authority for an API contract than an anecdotal trajectory, but that is evidence weighting for the particular claim, not permanent priority for Layer B.

### 4.5 Naming boundary: learning layers vs risk classes

`Layer A / Layer B / Layer C` in this document identify the three peer learning-source planes only. They MUST NOT be confused with the existing Brain autonomy/promotion `Class A / Class B / Class C / Class D` risk taxonomy.

The mapping is intentionally many-to-many: a candidate originating from any learning Layer A, B, or C is independently classified into the existing risk class according to what the candidate would change or execute. Source layer MUST NOT lower or raise the candidate's risk class by itself. For example, a Layer A internal-experience proposal can still be high-risk, while a Layer C open-discovery idea can still be low-risk if it is non-executable, well-verified, and does not widen permissions.

## 5. Intelligence Bus and conflict resolution

Every material claim entering synthesis SHOULD carry:

- `claim_id`;
- source branch A/B/C;
- source identifier and revision;
- authority type;
- observed/fetched time;
- freshness requirement;
- reproducibility status;
- benchmark or test evidence when applicable;
- domain;
- confidence;
- contradiction links;
- verification state.

Conflict resolution pipeline:

```text
claim set
  -> normalize
  -> provenance check
  -> freshness check
  -> authority/contract check
  -> reproducibility/experiment when possible
  -> benchmark/regression evidence
  -> contradiction analysis
  -> checker/grader
  -> accepted / unresolved / rejected
```

`2 votes vs 1` MUST NOT determine truth. A single well-supported C-branch result may overturn A and B if it survives verification; conversely, a novel C hypothesis may be rejected if it cannot reproduce.

Unresolved material conflicts remain unresolved and block stable promotion where the conflict affects correctness or safety.

## 6. AI Legion

The Legion is a pool of specialist roles rather than many competing commanders.

Initial divisions:

- Engineering / coding / debugging / architecture;
- Security / code review / threat modeling;
- Research / web / papers / evidence synthesis;
- Data / analytics / RAG / document intelligence;
- Creative / prompt / image / video / animation;
- UX/UI / design systems / multimodal design review;
- 2D / 3D / Blender / asset validation;
- Automation / browser / MCP / workflow integration;
- Deployment / runtime / observability;
- Trading and quantitative research (analysis/backtest only by default; no autonomous live financial execution);
- Business / market / operations;
- Game design / game engineering;
- Academic / writing / citation support;
- General checker / critic / grader.

Each agent MUST expose a typed contract containing at minimum:

- role/domain;
- accepted input schema;
- output contract;
- declared tools;
- allowed sources;
- permission ceiling;
- risk ceiling;
- model capability requirements;
- concurrency/retry budget;
- provenance requirements;
- verification requirements.

Agents may delegate only through the Brain task graph; no specialist can create an unbounded authority subtree.

## 7. Task decomposition and bounded concurrency

The Task Graph Builder converts a request or autonomous objective into independent or dependency-aware subgraphs.

Rules:

- split only when subwork is meaningfully independent or pipeline-parallel;
- avoid sending the same task to every model;
- prefer the smallest worker set that meets quality requirements;
- deduplicate identical model families across providers;
- same-family alternate providers count as availability redundancy, not reasoning diversity;
- immutable task input snapshots prevent silent cross-worker mutation;
- shared artifacts use explicit ownership/merge contracts;
- existing bounded concurrency ceilings remain the starting point: STANDARD <= 2 concurrent workers, DEEP <= 4, unless later benchmark evidence justifies an increase.

Typical deep task:

```text
Planner
  -> Researcher --------+
  -> Implementer A -----+--> Integrator -> Checker -> Grader
  -> Implementer B -----+
```

## 8. OpenCode fusion

OpenCode is integrated as a bounded cloud execution worker, not a commander.

Absorbed patterns:

- Plan vs Build separation;
- primary/subagent distinction;
- read-only Explore/Scout behavior;
- child-session/task isolation;
- per-agent permissions;
- granular `allow / ask / deny` tool policy;
- MCP client/server interoperability patterns;
- provider abstraction;
- coding session lifecycle;
- managed isolation/sandbox patterns where compatible.

Brain-native modes:

- `plan`: read/reason only, no writes;
- `explore`: repository exploration, read-only;
- `research`: external dependency/docs investigation, read-only;
- `patch`: bounded edits to an isolated branch/worktree/container;
- `test`: execute approved tests/validators;
- `review`: independent read-only critique.

OpenCode auto mode MUST NOT override Brain permission ceilings. Explicit Brain deny always wins.

## 9. Awesome LLM Apps fusion

The canonical reference SHOULD be the maintained parent `Shubhamsaboo/awesome-llm-apps`; the user-supplied fork may be used only as a mirror/reference when needed.

Absorb patterns selectively rather than importing entire applications:

- multi-agent specialist teams;
- Mixture-of-Agents parallel perspective generation;
- MCP specialist routing;
- agentic RAG;
- corrective RAG;
- knowledge-graph/citation-aware RAG where useful;
- memory patterns;
- multimodal coding/design teams;
- deep research planner/executor patterns;
- browser/research specialist separation.

Mixture-of-Agents is adapted to:

```text
bounded diverse workers
 -> normalized outputs
 -> claim/evidence extraction
 -> conflict detector
 -> checker/critic
 -> evidence-weighted synthesis
```

The raw pattern of collecting many answers and asking one aggregator to summarize is insufficient for stable Brain use unless evidence and conflict checks are present.

## 10. AutoSkill + SkillEvo fusion

AutoSkill becomes a Brain-native Skill Factory and SkillEvo becomes the controlled Evolution Engine.

### 10.1 Skill mining

Candidate reusable experience can be extracted from:

- A/B/C learning output;
- accepted task trajectories;
- repeated failure/fix clusters;
- new upstream documentation;
- benchmark discoveries;
- recurring user corrections.

Triage actions:

- `discard`;
- `improve`;
- `merge`;
- `create`.

### 10.2 Skill lifecycle

```text
candidate
 -> incubating
 -> eval_ready
 -> benchmarked
 -> canary
 -> champion_candidate
 -> promoted
 -> superseded / retired
```

Every skill keeps lineage and provenance.

### 10.3 Evolution loop

```text
frozen replay set
 -> compile eval rules
 -> generate bounded mutations
 -> evaluate mutation-dev
 -> promotion-test
 -> compare against champion
 -> regression suite
 -> canary
 -> promotion gate
```

A mutation MUST NOT replace the current champion merely because an LLM judge prefers it. Promotion requires measurable evidence and protected regression checks.

AutoSkill/SkillEvo MUST NOT write directly to the stable Skill Registry.

## 11. Full-autonomous idle operation

Persistent cloud runtime may generate its own low-risk background objectives when no user task is active.

Allowed autonomous background work:

- analyze failure backlog;
- detect capability gaps;
- discover new public sources;
- discover and benchmark free models/providers;
- refresh source freshness and maintenance state;
- mine candidate skills;
- generate bounded skill mutations;
- run replay/regression/evals;
- update quarantine indexes;
- deduplicate knowledge and skills;
- perform retrieval-quality evaluation;
- perform agent/model routing benchmarks;
- prepare sandbox patches or proposals;
- canary previously approved low-risk candidates.

Autonomous work MUST be governed by budgets for:

- API quota;
- token use;
- compute time;
- concurrency;
- retry count;
- storage growth;
- network calls;
- per-source crawl/fetch frequency.

The idle loop MUST yield to active user work.

## 12. Safety and autonomy classes

Full Autonomous Mode means the system may independently research, plan, test, generate skills, patch isolated branches, run validators, perform sandbox deployment, benchmark, retry, fail over, and canary low-risk changes.

It does NOT mean unrestricted authority.

The existing Class A/B/C/D risk taxonomy remains separate from Peer Learning Layers A/B/C. Risk classification is performed after candidate generation and is based on action/change risk, not source-layer identity.

Always gated unless separately and explicitly authorized:

- live financial execution;
- transfer of funds or assets;
- credential/key rotation or secret mutation;
- destructive production data operations;
- production permission widening;
- disabling security controls;
- modifying the Brain's own authority hierarchy;
- self-approving a high-risk promotion;
- bypassing provider quotas, access controls, or terms.

Learning can propose policy changes but cannot approve its own permission expansion.

## 13. Data, memory, and context control

The system can accumulate a large knowledge base without loading everything into each prompt.

Data states:

```text
RAW -> QUARANTINED -> VERIFIED -> PROMOTED
```

Retrieval path:

```text
request/objective
 -> domain + project authority
 -> primary skill
 -> relevant memory/evidence
 -> bounded supporting skills
 -> selected workers
```

Context budgets and progressive disclosure remain mandatory. Large skill banks or source registries MUST NOT be preloaded into FAST requests.

Persisted learning state may include:

- task outcomes;
- sanitized observations;
- accepted constraints;
- source/provenance references;
- skill/eval scores;
- model/provider health;
- regression outcomes;
- artifact references.

It MUST exclude hidden chain-of-thought, secrets, private keys, and unauthorized sensitive data.

## 14. Runtime and persistence

Autonomous operation requires a persistent external runtime. Chat sessions are not daemons.

Required runtime capabilities:

- durable job queue;
- scheduler;
- persistent state store;
- stateless or replaceable workers;
- provider/model mesh;
- health probes and heartbeats;
- watchdog/restart behavior;
- circuit breakers;
- bounded retry with backoff;
- exact-source deployment provenance;
- logs/metrics/traces with secret redaction;
- per-task idempotency keys;
- replayable low-risk jobs.

The design remains cloud-first and zero-local-capable.

## 15. Model Mesh integration

The existing Adaptive Free Model Mesh remains the model/provider execution layer.

The Legion asks for capabilities, not hard-coded providers.

Selection signals include:

- domain capability fit;
- measured quality;
- health;
- latency;
- quota/reset state;
- reliability;
- context requirements;
- privacy compatibility;
- cost/free eligibility when relevant;
- model-family diversity.

Provider fallback MUST preserve schema, permissions, privacy class, and risk ceiling.

## 16. Evaluation strategy

Protected eval suites MUST cover at least:

- routing accuracy;
- task decomposition quality;
- agent contract compatibility;
- conflict resolution without majority voting;
- A/B/C peer-right invariants;
- learning-layer vs risk-class separation;
- source provenance preservation;
- prompt-injection resistance in open discovery;
- permission-ceiling enforcement;
- secret redaction;
- generated-skill regression;
- mutation promotion correctness;
- replay determinism where applicable;
- provider/model disappearance;
- quota exhaustion and reset;
- same-family provider dedupe;
- MCP/tool schema mismatch;
- worker crash/retry/idempotency;
- isolated patch/test lifecycle;
- trading research vs execution boundary;
- production high-risk gate enforcement.

High-impact or complex DEEP changes require maker-checker plus an independent grader consistent with existing Brain policy.

## 17. Promotion policy

Promotion is evidence-based and branch-neutral.

A candidate may promote only when:

- provenance is complete;
- license/security requirements pass;
- permission ceiling is unchanged or explicitly approved;
- protected evals pass;
- no unresolved critical contradiction remains;
- candidate beats or matches protected baseline requirements;
- regression suite passes;
- canary outcome is acceptable where required;
- exact source revision is recorded.

No candidate gains stable status because it originated from Learning Layer A, B, or C, OpenCode, AutoSkill, Awesome LLM Apps, or any named model/provider. Every candidate is separately assigned the existing action/change risk class before promotion.

## 18. Upstream intake policy

The three upstream families are references/capability donors. Bulk repository import is not the default.

For each absorbed component, record:

- upstream repository;
- revision/commit when material;
- license;
- capability being absorbed;
- whether code is copied or pattern-only;
- security posture;
- maintenance status;
- expected context/runtime cost;
- conflicts/overlaps with existing Brain capability.

Strengthen an existing canonical Brain skill before creating a duplicate skill.

## 19. Migration sequence

The implementation SHOULD proceed in bounded phases:

1. register upstreams and capability map;
2. define Legion agent contracts and permission classes;
3. add Peer Tri-Layer claim/evidence contract;
4. add Intelligence Bus and conflict engine;
5. integrate OpenCode worker adapter;
6. absorb Awesome LLM Apps orchestration/RAG patterns into native contracts;
7. add AutoSkill-style skill mining and lineage registry;
8. add SkillEvo replay/mutation/eval engine;
9. add idle autonomous scheduler and budgets;
10. connect to Adaptive Free Model Mesh;
11. run multidomain evals and adversarial tests;
12. canary on isolated runtime;
13. build versioned release and verify exact SHA;
14. only then consider stable promotion/merge.

Existing AFMM implementation work MUST remain valid; this design extends it rather than replacing its FREE_ONLY, quota, dedupe, snapshot, and provider-safety contracts.

## 20. Non-goals

This design does NOT:

- train or fine-tune foundation-model weights automatically;
- grant unrestricted Internet/code execution;
- create multiple competing Brain authorities;
- permit autonomous live trading;
- bypass provider quotas or access controls;
- load all agents/skills/models into every request;
- treat model consensus as truth;
- allow self-generated skills to bypass tests.

## 21. Acceptance criteria

The design is considered implemented only when all of the following are demonstrated:

1. A/B/C Learning Layers have equal candidate/challenge rights with no hard-coded branch priority.
2. Learning-layer identity cannot change the existing autonomy risk class by itself.
3. Claim-specific evidence can override a majority of weaker agents.
4. A user task can be decomposed into bounded specialist work and merged deterministically.
5. Agent permissions cannot exceed the Brain-issued ceiling.
6. OpenCode can operate in bounded plan/explore/patch/test/review modes without gaining authority.
7. Awesome LLM Apps patterns are represented as native Brain capabilities rather than a second orchestration stack.
8. AutoSkill-style mining can create candidate skills with lineage/provenance.
9. SkillEvo-style mutation cannot promote unless protected evals/regressions pass.
10. Idle scheduler can create and complete low-risk learning jobs while yielding to active user tasks.
11. Adaptive Model Mesh can select/fail over providers without counting identical model families as independent reasoning votes.
12. Secrets and unauthorized sensitive data are absent from learning artifacts and model-mesh snapshots.
13. Trading agents remain research/backtest-only unless a separately approved execution authority exists.
14. High-risk production actions remain gated.
15. CI/evals pass on the release candidate.
16. Production activation, if requested later, is tied to an exact verified source SHA and health/smoke verification.

## 22. Design decision summary

Chosen architecture: **Peer Tri-Layer AI Legion**.

- One Brain authority.
- Many specialist agents.
- Many model/provider execution resources.
- Three peer learning branches: Experience, Curated, Exploration.
- No fixed A/B/C epistemic ranking.
- Learning Layers A/B/C are distinct from existing autonomy Risk Classes A/B/C/D.
- Evidence-based conflict resolution.
- OpenCode as bounded coding/execution worker.
- Awesome LLM Apps as orchestration/RAG/multimodal pattern source.
- AutoSkill + SkillEvo as Brain-native skill mining/evolution patterns.
- Persistent cloud idle learning with budgets.
- Self-generated skills require sandbox, eval, regression, canary, and promotion gates.
- Full autonomy for low-risk learning/execution; explicit gates for high-risk authority, financial, credential, destructive, or production changes.
