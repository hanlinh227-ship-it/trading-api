# Curated AI coding repository fusion — design

Date: 2026-10-02  
Status: Approved by Han Linh for implementation  
Targets: `appvn553-byte/linhai-system-core`, `hanlinh227-ship-it/trading-api`

## Goal and boundaries

Curate the ten repositories shown by the user into LinhAI's existing skill and upstream-fusion architecture. Record source provenance and immutable commit pins; fold useful ideas into existing engineering and UX/UI workflows. Do not add a second router, skill authority, memory store, or model/runtime dependency.

- `task_router` remains the sole routing authority; `linhai-executor` remains the sole executor.
- The upstream registry loads after domain selection, with at most three candidates and zero routing/reasoning authority.
- Keep ZERO_BILLING. No paid API, trial, extra model calls, or cloud build is required.
- Change no strategy, Forex execution status, order path, credential, or trading permission.
- Brain graph runtime is disabled; do not enable a graph database or always-on indexer.
- The local Brain/Control source is not admitted as a reproducible Git checkout. Do not install a moving branch or claim deployment without a verified immutable release.

## Source disposition

Each repository was checked at the pinned full commit on 2026-10-02. MIT and Apache-2.0 were read from upstream LICENSE files. Awesome Claude Skills has no standard LICENSE file; its README badge is not treated as permission to copy its listed third-party content.

| Source | Decision | Capability folded into LinhAI |
|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | Engineering reference | Scope/design first for complex work, incremental tests, review and verified completion. |
| [Addy Osmani Agent Skills](https://github.com/addyosmani/agent-skills) | Engineering reference | Lifecycle checklists and measured performance checks. |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | Engineering reference | Minimal correct changes and concise output when appropriate. |
| [Caveman](https://github.com/JuliusBrussee/caveman) | Engineering reference | Token efficiency while preserving safety checks. |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Upgrade existing core UX/UI skill | Visual direction, platform fit, responsive behavior and interface checks. |
| [Impeccable](https://github.com/pbakaus/impeccable) | Upgrade existing core UX/UI skill | Design review and deterministic-check ideas; no upstream hooks, CLI, detectors or browser extension. |
| [Graphify](https://github.com/Graphify-Labs/graphify) | Sole optional codebase-graph reference | On-demand code map and source-traceable navigation; runtime remains disabled. |
| [Understand Anything](https://github.com/Egonex-AI/Understand-Anything) | Deferred duplicate | Overlaps Graphify and graph runtime remains off. |
| [Awesome Claude Skills](https://github.com/ComposioHQ/awesome-claude-skills) | Discovery index only | No catalog or third-party skill copied without per-item license review. |
| [Archify](https://github.com/tt-a1i/archify) | Diagram reference | Optional interactive HTML diagrams; no generator or dependency installed. |

## Implementation

1. Upgrade the original `ux-ui-design` skill in the core repo; add all ten pinned references and license outcomes to its provenance file. No upstream prose, code, assets, hooks or templates are copied.
2. Add ten records to the Brain's existing WARM `upstream_knowledge_fusion` registry. Extend its validator and add a focused regression test for exact SHAs, provenance and no authority/dependencies.
3. Store this design and plan in the canonical trading repository. Leave router, stable release pointer, strategies, market execution, runtime and machine policy files unchanged.
4. Retry read-only local computer access after GitHub changes. The bridge returned MCP `-32603 Internal error` for initial read-only filesystem operations. Use only the authorized LinhAI executor for any install; do not bypass it with DCR, shell, or remote branch execution.

## Verification and release

- Parse changed JSON/YAML; confirm all ten source pins and license dispositions.
- Run the focused fusion validator and regression test from a repository checkout.
- Confirm no routing, execution, strategy or permission files changed.
- Review both PR diffs and run available repository gates before merge.
- Do not report local installation until an immutable release is installed by the executor and post-install health/context checks pass; preserve rollback to the prior known-good state.
