# GITHUB BRAIN V4.6 — Open Source Fusion Upgrade

Date: 2026-09-13
Status: proposed design, awaiting user review
Target architecture: GITHUB_BRAIN_V4
Baseline release: 4.5.0
Canonical repository: hanlinh227-ship-it/trading-api

## 1. Goal

Upgrade the Brain's practical capability by absorbing verified open-source methods into the existing canonical skill system without creating parallel reasoning authorities, unnecessary duplicate skills, local-install dependencies, or new financial execution permissions.

The primary success condition is higher capability quality, not a larger skill count. The default target is to keep the current 109 canonical routed skills and strengthen them. A new canonical skill may be added only when a genuinely distinct capability is proven missing after overlap analysis and evaluation.

## 2. Non-goals

This release will not:

- create a second Brain, agent swarm authority, or voting-based truth system;
- bulk-import external repositories or make them runtime dependencies by default;
- grant upstream code or providers routing authority;
- widen trading, wallet, credential, destructive, or production-write permissions;
- require the user to install Node, Python, Blender, MCP servers, provider CLIs, or other local software for normal Brain operation;
- weaken FAST latency or add external routing calls to FAST;
- replace current project authority, stable security policy, live-data freshness rules, or release verification contracts;
- claim that upstream repositories are trusted merely because they are popular.

## 3. Design choice

Use selective capability fusion rather than repository ingestion.

Every upstream source remains reference evidence. The Brain extracts reusable patterns, validation rules, eval methods, and typed capability contracts, then expresses them in native V4 policy/skill/eval structures. External code is not copied unless its license, provenance, security, maintenance status, and necessity justify doing so. Native declarative contracts are preferred.

The canonical path remains:

request -> task router -> one runtime profile -> exactly one primary skill -> validated execution capsule -> bounded context/tools -> response quality gate -> answer

No upstream framework is inserted into this authority chain.

## 4. Candidate source groups

The first 4.6 candidate set is intentionally bounded.

### 4.1 Agent engineering and evaluation

Reference candidates:

- google/adk-python
- openai/openai-agents-python
- langfuse/langfuse
- NVIDIA/garak

Intended absorption:

- agent/task handoff patterns;
- bounded orchestration and explicit state transitions;
- typed tool contracts;
- tracing and evaluation metadata;
- simulation/evaluation cases;
- adversarial prompt and capability testing;
- quality, safety, and regression measurement.

Primary skills to strengthen:

- planning
- automation
- skill engineering
- eval engineering
- verification
- security
- troubleshooting

No new agent authority is created.

### 4.2 Software engineering

Reference candidates:

- langchain-ai/open-swe
- SWE-agent/SWE-agent and/or mini-swe-agent patterns where licensing and maintenance checks pass
- plandex-ai/plandex as design reference where appropriate

Intended absorption:

- issue/task -> repository inspection -> plan -> isolated change -> test -> review -> PR workflow;
- reproducible repository-level debugging;
- verification checkpoints;
- bounded context handling for large repositories;
- feedback/review incorporation.

Primary skills to strengthen:

- coding
- debugging
- tdd
- github
- software architecture
- deployment

The repository's existing Superpowers/TDD workflow remains authoritative for implementation behavior.

### 4.3 Quantitative trading research

Reference candidate:

- nautechsystems/nautilus_trader

Potential supporting references may be used only after license review.

Intended absorption:

- event-driven backtest architecture concepts;
- research/live semantic consistency checks;
- order/execution modeling concepts;
- slippage, fees, latency, fill assumptions;
- market/instrument semantic separation;
- deterministic simulation and reproducibility;
- regime-aware validation inputs.

Primary skills to strengthen:

- quant backtesting
- quant validation
- market microstructure
- risk management
- trading bot

Trading remains analysis/research constrained by current project authority. No order placement, leverage mutation, wallet signing, account mutation, or permission expansion is introduced by this upgrade.

### 4.4 UX and design-to-code

Reference candidates:

- penpot/penpot-ai-kit or the current canonical Penpot AI skill source if repository naming changes
- figma/code-connect

Intended absorption:

- accessibility validation;
- design token consistency;
- component mapping;
- design-system constraints;
- design-to-code validation;
- UI consistency checks.

Primary skills to strengthen:

- ux ui
- product design
- layout
- typography
- graphic design where relevant

### 4.5 3D asset validation

Reference candidates:

- KhronosGroup/glTF-Validator
- mikedh/trimesh
- isl-org/Open3D

Intended absorption:

- glTF schema/export validation concepts;
- geometry integrity checks;
- transform/scale/normal checks;
- manifold/topology checks where relevant;
- material/UV/animation/export-reimport verification;
- multi-view validation discipline.

Primary skills to strengthen:

- asset validation 3D
- design 3D
- modeling
- topology
- uv
- materials
- blender

No mandatory local Blender runtime is introduced.

### 4.6 Prompt and generative media optimization

Reference candidate:

- stanfordnlp/dspy

Intended absorption:

- measured prompt optimization;
- test-case driven prompt revision;
- objective/constraint scoring;
- prompt regression testing;
- separate generation from validation.

Primary skills to strengthen:

- prompt engineering
- prompt debugging
- image prompt
- video prompt
- negative constraints
- character consistency
- scene continuity

The Brain must not turn stochastic generation results into false guarantees.

### 4.7 Game validation patterns

Reference candidates are allowed only if license and openness are clear. Summer-like screenshot/debugger/input validation patterns may be used as reference concepts, but proprietary or closed engine components must not become dependencies.

Primary skills to strengthen:

- game development
- game design
- game ai
- game 2D
- game 3D
- godot
- unity

## 5. Fusion pipeline

Every candidate passes the following stages before any stable effect:

1. provenance and repository identity check;
2. license/usage-status check;
3. maintenance/current-status check;
4. security and permission-surface review;
5. semantic normalization into domain, intent, inputs, outputs, tools, sources, freshness, units, and risk class;
6. overlap scan against the 109 current canonical skills;
7. conflict scan against current project authority, stable security, evidence precedence, provider policy, and permission ceilings;
8. classification as one of:
   - strengthen existing skill;
   - approved reference only;
   - alias/adapter candidate;
   - genuinely new capability candidate;
   - reject/quarantine;
9. candidate eval generation;
10. baseline comparison;
11. bounded canary;
12. immutable release promotion only if all protected dimensions have zero material regression.

Default state is quarantine with zero routing authority.

## 6. Skill-count policy

The default release target remains 109 canonical routed skills.

A new skill requires all of the following:

- distinct task intent not adequately represented by any existing canonical skill;
- measurable improvement from a separate contract rather than a strengthened existing skill;
- unique input/output contract;
- no trigger ownership conflict;
- validated execution capsule;
- eval evidence;
- authority and security approval;
- acceptable context/latency cost.

If any condition fails, strengthen an existing skill or use a reference/adapter instead.

## 7. Evaluation upgrade

Release 4.6 will extend the current evaluation layer without replacing it.

Required evaluation areas:

- routing correctness;
- overlap/duplicate detection;
- authority preservation;
- source/provenance correctness;
- license-status enforcement;
- security and prompt-injection resistance;
- permission-ceiling preservation;
- repository-task workflow quality;
- quantitative backtest realism;
- 3D validation coverage;
- UX/design-system validation;
- prompt regression quality;
- answer quality;
- latency/context cost.

Protected dimensions remain correctness, verification, safety, and authority with zero allowed material regression.

For DEEP high-impact or complex requests, independent grading may use stronger adversarial/eval patterns. The grader remains non-authoritative and cannot expand permissions.

## 8. Security and conflict rules

The following rules are invariant:

- current runtime facts outrank cached or upstream claims;
- current project authority outranks imported guidance;
- stable security/risk policy cannot be weakened;
- provider/upstream output is evidence, not a vote;
- no majority vote for truth;
- no silent averaging of conflicting conclusions;
- unresolved material conflict blocks dependent high-consequence conclusions;
- permission disagreement fails closed;
- unknown write capability is high risk;
- external code is untrusted by default;
- secrets, credentials, private keys, and sensitive provider payloads never enter learned artifacts;
- trading/live claims require current approved runtime evidence where the existing policy requires it.

## 9. Runtime and performance

FAST must remain lightweight:

- exactly one primary skill and capsule;
- zero supporting skills;
- zero external routing calls;
- no upstream refresh during request handling;
- no new maker/checker loop;
- no new mandatory semantic retrieval stage.

STANDARD may use bounded supporting context and one revision when material.

DEEP may use bounded maker/checker and independent grading for complex/high-impact work within existing budgets.

Open-source research and promotion happen in the Evergreen plane, never synchronously inside a normal Stable request.

## 10. Zero-local requirement

Normal operation remains cloud-first and must not require user-local installation.

Upstream projects that require local runtimes may still be used as design references, but their local runtime must not become a stable dependency unless a separate approved cloud adapter is designed and verified.

## 11. Expected stable changes

Implementation should prefer a small number of native changes, likely including:

- extension of capability fusion reference map;
- extension of harmonization candidate checks where gaps are found;
- extension of eval taxonomy and test cases;
- targeted strengthening of existing skill contracts/triggers/output requirements;
- source registry additions for approved references;
- release/retrieval metadata regenerated by canonical tools;
- tests proving skill count/authority/routing/permissions remain stable unless a separately justified new skill is introduced.

Generated release/index files must never be hand-edited.

## 12. Test-first requirements

Implementation must follow RED -> minimum GREEN -> full regression.

New tests must prove at least:

- candidate references cannot become primary reasoning authorities;
- duplicate capability candidates strengthen/attach to existing skills instead of creating duplicate primary skills;
- skill count stays 109 by default;
- every routable skill still has a valid execution capsule;
- FAST still has zero external routing calls;
- financial/trading permission ceilings do not widen;
- external-code license/provenance status is represented and enforced;
- rejected/quarantined sources have zero routing authority;
- new eval cases cover adversarial, repository workflow, quant realism, 3D validation, UX, and prompt regression;
- stable presentation/plain-language behavior from 4.5.0 remains intact;
- current release pointer, retrieval index, and immutable manifest are generated and valid.

All existing tests must remain green.

## 13. Release and rollout

If implementation passes all gates, build immutable release 4.6.0 using the canonical release tool.

Required completion evidence:

- full Brain validators pass;
- AI_SKILL_LIBRARY tests pass;
- repository tests pass;
- Skill Gateway compile/snapshot validation pass;
- release check and retrieval index freshness pass;
- FAST benchmark records p50/p95 and confirms zero external routing calls;
- Cloudflare dry-run passes without runtime-switch mutation;
- merge to main by reviewed PR;
- exact-main production deploy succeeds;
- /runtime/contract and /brain/health expose the exact merged SHA;
- production route matrix passes;
- current trading execution/live-research authority remains unchanged unless separately approved.

Rollback remains pointer-based to the previous known-good immutable release 4.5.0.

## 14. Acceptance criteria

The upgrade is complete only when:

1. useful patterns from the approved candidate groups are represented in native Brain contracts/evals/reference metadata;
2. no parallel reasoning authority is created;
3. no material duplicate skill is introduced;
4. default canonical routed skill count remains 109 unless a separately documented distinct-capability exception passes all gates;
5. all protected regressions are zero;
6. FAST performance contract remains intact;
7. zero-local and permission ceilings remain intact;
8. production exact-SHA verification succeeds;
9. the user-facing plain-language layer remains active;
10. 4.5.0 remains a known-good rollback target.

## 15. Decision summary

Recommended implementation strategy: selective fusion into existing skills, stronger evaluation, stronger harmonization, no bulk repository import, no parallel agent authority, no trading permission expansion, and no default increase in skill count.
