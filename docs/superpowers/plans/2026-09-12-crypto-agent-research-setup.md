# Crypto Agent Research-Only Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a research-only crypto agent skills workspace with explicit allow/block policies, official-source inventory, safe usage workflows, and post-setup health reporting without enabling live trading credentials or fund-moving actions.

**Architecture:** The workspace is isolated under `crypto-agent-skills/`. Public/read-only capabilities are allowlisted, authenticated read-only capabilities are documented but not credentialed, and any trade/wallet/transfer/swap/bridge/broadcast/payment capability is blocked by policy and marked HIGH RISK. Current GitHub Brain security authority remains the permission boundary.

**Tech Stack:** Markdown, YAML, GitHub repository contents, upstream official Agent Skills/MCP documentation.

**Spec:** User-approved research-only setup requirements in the 2026-09-12 conversation, governed by `AI_SKILL_LIBRARY/checkpoint.json`, `AGENTS.md`, and `AI_SKILL_LIBRARY/v4/stable/security.yaml`.

## Global Constraints

- Research-only / read-only by default.
- No withdrawal permission.
- No live order or fund-moving action without explicit future authorization.
- No private key, seed phrase, API secret, or credential logging.
- Prefer public endpoints first; testnet/restricted read-only credentials only if a later task requires authentication.
- HIGH RISK capabilities remain unactivated.
- Do not claim local CLI installation or local environment health unless it is actually verified on the user's machine.

---

### Task 1: Create workspace safety baseline

**Files:**
- Create: `crypto-agent-skills/README_SETUP.md`
- Create: `crypto-agent-skills/SAFETY_RULES.md`
- Create: `crypto-agent-skills/.gitignore`
- Create: `crypto-agent-skills/config/research-allowlist.yaml`
- Create: `crypto-agent-skills/config/high-risk-blocklist.yaml`
- Create: `crypto-agent-skills/docs/OFFICIAL_SOURCES.md`
- Create: `crypto-agent-skills/notes/README.md`

**Interfaces:**
- Consumes: current Brain security policy and verified upstream official repositories.
- Produces: explicit permission boundary and source registry used by all later tasks.

- [ ] Create the directory tree implicitly by writing the files above.
- [ ] Record public/read-only sources and authenticated read-only sources separately.
- [ ] Block trading, transfer, withdrawal, swap, bridge, broadcast, wallet creation, payment and DeFi investment actions.
- [ ] Add secret-file patterns to the local `.gitignore`.
- [ ] Verify all listed source URLs are official upstream sources already checked in this work cycle.

### Task 2: Create installed/prepared skills report

**Files:**
- Create: `crypto-agent-skills/INSTALLED_SKILLS_REPORT.md`

**Interfaces:**
- Consumes: official-source registry and safety baseline.
- Produces: provider-by-provider status matrix with installation/preparation state and risk classification.

- [ ] Record Binance research skills as prepared unless a local Skills CLI install is actually verified.
- [ ] Record OKX CEX market/read-only capabilities as prepared; block trade/portfolio write functions.
- [ ] Record Bybit Market module as prepared documentation only; keep write modules disabled.
- [ ] Record Gate public Market/Info/News/Docs MCP endpoints as prepared and no-auth.
- [ ] Record KuCoin GET-only skills as prepared.
- [ ] Record Coinbase Agentic Wallet/AgentKit as HIGH RISK and not activated.
- [ ] Explicitly state API-key requirements and whether each capability can affect real funds.

### Task 3: Create Vietnamese usage guide

**Files:**
- Create: `crypto-agent-skills/AGENT_USAGE_GUIDE.md`

**Interfaces:**
- Consumes: allowlisted research capability classes.
- Produces: five safe operator workflows with Vietnamese prompts.

- [ ] Write Morning Brief workflow and prompt.
- [ ] Write Watchlist Scanner workflow and prompt.
- [ ] Write Setup Deep Dive workflow and prompt.
- [ ] Write Smart Money / Dòng tiền workflow and prompt.
- [ ] Write Trading Plan Builder workflow and prompt that produces a plan only, never order execution.
- [ ] Reinforce that the AI supports analysis and the human makes the trading decision.

### Task 4: Perform safe health check and record limitations

**Files:**
- Create: `crypto-agent-skills/SETUP_ERRORS.md`

**Interfaces:**
- Consumes: GitHub accessibility checks and upstream documentation checks from this work cycle.
- Produces: explicit health status without fabricating local runtime state.

- [ ] Confirm all required repository files exist on the setup branch after creation.
- [ ] Treat successful official GitHub file fetches as source-availability checks only, not local installation checks.
- [ ] Record that the user's local OS/Node/npm/npx/Git/Python/Claude/Codex/Cursor/OpenClaw environment cannot be directly inspected from this hosted ChatGPT session.
- [ ] List the exact read-only commands the user or a local agent should run later to close the local-runtime verification gap.
- [ ] Do not run or recommend any command that creates a wallet, logs into a wallet, places an order, transfers assets, swaps, bridges, broadcasts a transaction, or pays a service during this phase.

### Task 5: Fix stale Claude bootstrap pointer

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `AGENTS.md` and `AI_SKILL_LIBRARY/checkpoint.json`.
- Produces: a version-agnostic Claude bootstrap that follows the current canonical checkpoint instead of hard-coding an obsolete Brain version.

- [ ] Replace hard-coded Brain version instructions with dynamic checkpoint resolution.
- [ ] Preserve no-global-Trading-preload and current-authority rules.
- [ ] Verify no specific future Brain version is hard-coded.

### Task 6: Final repository verification

**Files:**
- Verify: all files created/modified above.

**Interfaces:**
- Consumes: completed branch state.
- Produces: evidence that requested artifacts exist and HIGH RISK actions remain disabled.

- [ ] Fetch every required file from the setup branch.
- [ ] Compare setup branch against `main` and review changed-file scope.
- [ ] Confirm no credential values or live-trading activation were introduced.
- [ ] Report research-ready, read-only-auth-required, and HIGH-RISK-disabled categories to the user.
