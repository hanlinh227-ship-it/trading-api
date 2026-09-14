# Brain V4 Selective Open-Source Fusion — Design

Date: 2026-09-14
Status: Approved direction; implementation gated on written-spec review
Base repository: `hanlinh227-ship-it/trading-api`
Base branch: `main`
Base commit: `b594ea5e20f329322e7f8a6b3f5a914ec82e1fa8`
Current release pointer at design time: `4.6.0`

## 1. Objective

Strengthen the existing GitHub Brain comprehensively with high-value open-source patterns while preserving the current architecture and authority model.

The upgrade MUST:

- keep the current canonical routed skill count unchanged at 109 unless a later independent design proves a genuinely distinct skill is required;
- strengthen existing canonical skills before considering any new skill;
- keep one routing authority and one primary skill per request;
- preserve the validated execution-capsule requirement;
- keep upstream repositories as evidence/reference inputs, never reasoning authority;
- preserve FAST routing with zero external routing calls and no source preload;
- preserve zero-local normal operation;
- preserve current Trading/G9 project authority and all financial execution boundaries;
- add no wallet, credential, destructive, production-write, or order-execution permission;
- copy no upstream source code by default;
- promote only through existing provenance, license, conflict, security, authority, eval, regression, context-cost, canary, release and verification gates.

This is a selective fusion, not a framework migration and not a second Brain.

## 2. Current authority and invariants

Implementation resolves paths from `AI_SKILL_LIBRARY/checkpoint.json` at execution time rather than hard-coding future versions.

The design is subordinate to:

1. current runtime/source state when verified;
2. current project authority;
3. Stable evidence/security/harmonization policy;
4. current immutable release bundle;
5. imported open-source guidance.

Protected invariants:

- `task_router` remains mandatory infrastructure;
- exactly one canonical primary skill is selected;
- aliases never become primary;
- imported sources cannot own triggers;
- providers/tools remain capabilities, not reasoning authority;
- hidden chain-of-thought is never persisted;
- secrets and credentials never enter repository state or telemetry;
- unresolved source/license/permission conflicts fail closed;
- current live-price and Trading execution authority are untouched.

## 3. Candidate intake decisions

All source metadata below was re-verified from the public GitHub repositories on 2026-09-14. `RAG_ONLY` means eligible as a bounded source after domain/skill selection; it does not mean package installation or runtime execution. `REFERENCE_ONLY` means patterns may be absorbed into native Brain contracts but the source is not a runtime reasoning dependency.

| Repository | Verified license | Maintenance at design time | Decision | Primary value |
| --- | --- | --- | --- | --- |
| `modelcontextprotocol/python-sdk` | MIT | active, not archived | RAG_ONLY | MCP client/server contracts, capability negotiation, typed tool/resource/prompt interoperability |
| `docling-project/docling` | MIT | active, not archived | RAG_ONLY | structure-aware document parsing, tables/layout, PDF/DOCX/PPTX/XLSX conversion patterns |
| `microsoft/graphrag` | MIT | active, not archived | REFERENCE_ONLY initially | entity/relationship extraction and bounded local/global graph retrieval patterns |
| `UKGovernmentBEIS/inspect_ai` | MIT | active, not archived | RAG_ONLY | task/dataset/scorer separation, reproducible model/agent evaluation patterns |
| `ossf/scorecard` | Apache-2.0 | active, not archived | RAG_ONLY | open-source security-health and maintenance posture signals for candidate intake |
| `aquasecurity/trivy` | Apache-2.0 | active, not archived | RAG_ONLY | vulnerability, secret, misconfiguration, SBOM and dependency-risk scan semantics |
| `Arize-ai/openinference` | Apache-2.0 | active, not archived | RAG_ONLY | OpenTelemetry-aligned AI span/operation semantics for sanitized observability |
| `microsoft/playwright` | Apache-2.0 | active, not archived | RAG_ONLY | browser/E2E runtime verification across Chromium, Firefox and WebKit |

### 3.1 Deliberately not promoted in this cycle

- `microsoft/agent-framework`: verified active/MIT, but overlaps heavily with existing LangGraph, OpenAI Agents and Google ADK references. Keep as a future comparison candidate, with zero routing authority and no registry promotion now.
- `nautechsystems/nautilus_trader`: already represented in Stable capability fusion as design-reference-only because LGPL-3.0 is outside the active registry allowlist. Do not duplicate it.
- Graphiti/Mem0-like memory additions: defer because scoped memory is already covered and a second memory authority would increase overlap.
- PyRIT-like red-team additions: defer because Garak/Promptfoo already cover adversarial-eval patterns; add only if a measured eval gap appears.
- Syft-like SBOM additions: defer because Trivy already supplies SBOM semantics for this cycle; add only if the intake eval shows a material missing capability.
- Storybook/Lighthouse additions: defer because current UX/design-system references plus Playwright runtime verification cover the intended delta without growing the source set further.

This rejection/defer list is intentional evidence of deduplication, not unfinished work.

## 4. Native capability fusion

No upstream framework becomes a runtime dependency. Patterns are normalized and absorbed into existing Brain contracts.

### 4.1 MCP interoperability

Absorb MCP patterns into existing `api`, `skill_engineering`, `automation`, and tool-capability contracts.

Required native behavior when MCP is relevant:

- declare protocol/version compatibility explicitly;
- declare tool/resource/prompt input and output schema boundaries;
- distinguish discovery from invocation;
- declare read/write permission ceiling before invocation;
- treat authentication material as external restricted runtime state, never repository knowledge;
- validate provider output before use;
- fail closed on unknown capability, incompatible schema, or permission widening;
- never equate MCP capability with reasoning authority.

No local MCP server becomes mandatory.

### 4.2 Document intelligence

Absorb Docling patterns into existing `pdf`, `docx`, `slides`, `spreadsheet`, `data_analysis`, `report`, and `research` behavior.

Native behavior:

- prefer structured/native extraction before OCR;
- preserve document hierarchy, page/section provenance, table structure and reading order when material;
- distinguish extracted text from inferred interpretation;
- validate table/cell structure and layout-sensitive claims;
- use OCR only as a degraded fallback when native extraction is unavailable or insufficient;
- verify generated/modified artifacts using format-specific validators where available.

Docling itself is not installed or required for normal execution.

### 4.3 Graph retrieval

Absorb GraphRAG patterns into existing retrieval/research behavior only when entity relationships or corpus-wide synthesis materially improve the answer.

Rules:

- exact/lexical/semantic retrieval remains the default path;
- graph retrieval is optional and STANDARD/DEEP only;
- graph nodes/edges are evidence indexes, not authority;
- every synthesized graph claim must remain traceable to source evidence;
- current project authority and freshness filters apply before graph expansion;
- graph expansion is bounded by existing context and retrieval budgets;
- no graph database becomes a mandatory runtime dependency.

### 4.4 Eval engineering

Absorb Inspect AI patterns into existing `eval_engineering` and verification contracts.

Native eval units distinguish:

- task definition;
- dataset/case set;
- solver/agent under test;
- scorer/assertion;
- sandbox/tool boundary;
- baseline and candidate result;
- protected-regression result.

Representative, adversarial and negative cases remain required when material. Evaluation output is evidence, never self-promotion authority.

### 4.5 Open-source intake firewall

Absorb OpenSSF Scorecard and Trivy patterns into Evergreen/harmonization source intake without making either executable tool mandatory.

Candidate metadata gains bounded security-posture evidence when available:

- archived/disabled status;
- recent maintenance signal;
- verified SPDX/license evidence;
- dependency/vulnerability posture;
- secret-scanning posture;
- SBOM availability or equivalent dependency inventory;
- release/signing/provenance signals when available.

Security posture is advisory evidence inside the existing authority chain. A high score never auto-promotes a source. A critical unresolved issue may block promotion.

### 4.6 Sanitized AI observability semantics

Absorb OpenInference conventions into existing observability metadata without persisting prompts, private payloads or hidden reasoning.

Normalize optional fields such as operation class, tool/retriever/evaluator role, model/provider identifier when non-sensitive, duration, status and verification outcome. Existing redaction and trace-size limits remain authoritative.

### 4.7 Browser/runtime verification

Absorb Playwright patterns into `web_app`, `debugging`, `verification`, `ux_ui`, and `product_design` verification guidance.

For browser-facing behavior changes, verification should prefer a runnable flow over static-code confidence when a browser test environment exists. Checks may include navigation, state transition, visible outcome, accessibility-relevant state, network failure handling and cross-browser behavior when material.

Playwright is an optional CI/runtime validation mechanism, not a required user-local dependency.

## 5. Repository changes in implementation

Implementation should make the smallest coherent changes needed to express the above contracts.

Expected change set:

1. `AI_SKILL_LIBRARY/sources.yaml`
   - add only the approved source rows;
   - preserve provenance, license, maintenance, usage tier and permission ceiling;
   - keep total/category caps valid;
   - avoid duplicate upstreams already represented elsewhere.

2. `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
   - add normalized upstream pattern mappings for the approved candidates;
   - record deferred/rejected overlap decisions where useful for future audits;
   - keep routing authority false, mandatory runtime dependency false and code reuse false by default.

3. `AI_SKILL_LIBRARY/skills/catalog.yaml`
   - strengthen existing output contracts only;
   - do not add a new primary skill or competing trigger owner;
   - do not increase the canonical routed skill target;
   - recompile execution capsules through the canonical compiler rather than editing generated capsule output by hand.

4. `AI_SKILL_LIBRARY/evals.yaml`
   - add benchmark/failure coverage for MCP contract integrity, document fidelity, graph-retrieval contamination, source-intake security posture, observability sanitization and browser runtime verification;
   - preserve the existing pass score and zero protected-regression tolerance.

5. Evergreen/harmonization declarative policy only if required by tests
   - add bounded intake metadata fields rather than a second source-quality authority;
   - do not make external scanners mandatory on FAST or normal Stable requests.

6. Existing validators/tests
   - extend the current test/validator layout discovered in the implementation plan;
   - do not create a parallel validation framework.

7. Generated artifacts
   - rebuild retrieval index, compiled Skill Gateway snapshot and release manifest only through checkpoint-declared tools;
   - never hand-edit generated hashes/indexes.

## 6. Tests and acceptance criteria

Implementation is acceptable only if all of the following are demonstrated from the implementation branch and again after merge where production verification applies.

### 6.1 Structural invariants

- canonical routed skills remain 109;
- execution capsules remain one-to-one with routed canonical skills;
- no new primary trigger owner conflict;
- aliases remain non-routable;
- no external framework gains routing/reasoning authority;
- no mandatory local installation is introduced;
- source registry remains within configured limits;
- every promoted source has verified provenance, allowed license and current maintenance status.

### 6.2 FAST invariants

- FAST performs zero source preload;
- FAST performs zero external routing calls;
- no synchronous upstream refresh is added;
- warm FAST latency does not materially regress relative to the current baseline.

### 6.3 Functional evals

At minimum, add cases proving:

- MCP: incompatible schema or permission widening fails closed; read-only discovery does not grant write permission;
- documents: hierarchy/table/page provenance survives structured extraction semantics and unsupported structure is disclosed rather than invented;
- graph retrieval: irrelevant graph expansion cannot override exact authoritative evidence and cross-domain contamination is rejected;
- eval engineering: baseline/candidate/scorer boundaries are explicit and protected regressions block promotion;
- OSS intake: archived, license-unresolved, secret-bearing or materially unsafe candidates do not promote;
- observability: sensitive payload and hidden reasoning remain absent from traces;
- browser verification: static success claims are rejected when the required runnable-flow verification fails.

### 6.4 Protected regression

No regression is allowed in correctness, security, authority, verification or project isolation. Existing Trading, G9, live-price, deployment and creative/domain suites must remain green.

## 7. Release and deployment path

Implementation occurs on the isolated branch created from the exact base SHA.

Sequence after written-spec approval:

1. create a detailed implementation plan using the repository's Superpowers workflow;
2. apply TDD/RED where behavior is testable;
3. make the minimum native-contract changes;
4. run focused tests and existing validators;
5. run checkpoint-declared `ci_validate` on the exact source SHA;
6. rebuild generated retrieval/snapshot artifacts using canonical tools;
7. build the next feature release resolved from the current release pointer; at design time `4.6.0` makes the expected next feature release `4.7.0`, but implementation must resolve this dynamically if `main` moves;
8. create a PR with source/license/overlap/eval evidence;
9. merge only with green CI and no protected regression;
10. verify the production Skill Gateway exact deployed SHA, health contract, primary skill/capsule contract and route smoke matrix;
11. do not modify Railway live-price authority unless a separate approved design explicitly does so.

## 8. Rollback

The previous verified release remains the rollback target until the new release is fully verified in production.

Rollback triggers include:

- source/license/provenance mismatch;
- duplicate capability or trigger ownership conflict;
- permission-ceiling widening;
- protected eval regression;
- FAST external call or latency regression;
- invalid capsule/snapshot/index;
- failed CI or release verification;
- post-deploy exact-SHA or route-smoke mismatch.

Rollback does not require root-cause completion before restoring the last known-good release.

## 9. Explicit non-goals

This upgrade does NOT:

- replace GitHub Brain with Microsoft Agent Framework, LangGraph, MCP, GraphRAG, Docling, Inspect, Trivy, Playwright or any other framework;
- create a second router, memory system, authority chain or skill catalog;
- install external packages on the user's computer;
- run third-party repository code as trusted code by default;
- change Trading execution rules, G9 authority, live-price source semantics or wallet/order permissions;
- train/fine-tune automatically from the new sources;
- persist hidden reasoning;
- bulk-import upstream repositories.

## 10. Definition of done

The work is complete only when the approved selective-fusion changes exist in the canonical repository, generated artifacts are rebuilt through canonical tools, all required tests/validators/evals pass, the immutable release is promoted, and production reports the exact intended source SHA with the existing routing/capsule and zero-external-FAST-call guarantees intact.

Until then, the current verified Stable release remains authoritative.