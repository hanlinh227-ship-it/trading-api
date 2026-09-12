# SETUP_ERRORS

Report date: 2026-09-12

## E001 — Local runtime cannot be directly inspected from this hosted session

**Status:** OPEN — requires local verification, not a crypto-skill failure.

**Command run:**

No shell command was run on the user's actual Mac/Windows/Linux machine because this hosted ChatGPT session does not have direct shell access to that device. Running the same commands in a hosted sandbox would not prove the user's local environment and would create a false health claim.

**Observed result:**

- GitHub repository access is working.
- Official upstream repositories/README/SKILL references for Binance, OKX, Bybit, Gate, KuCoin and Coinbase were accessible during this work cycle.
- The repository workspace has been prepared on the isolated branch `crypto-agent-research-setup-20260912`.
- Local OS, Node.js, npm/npx, Git, Python and installed agent clients are still unverified.

**Likely cause:**

Environment boundary: the current assistant can operate on the connected GitHub repository but cannot directly inspect the user's local terminal/runtime.

**Proposed fix:**

Run the following **read-only environment checks** from the actual machine that will host the agent.

### macOS / Linux

```bash
uname -a
sw_vers 2>/dev/null || true
node --version
npm --version
npx --version
git --version
python3 --version
command -v claude || true
command -v codex || true
command -v cursor || true
command -v openclaw || true
```

### Windows PowerShell

```powershell
$PSVersionTable.OS
node --version
npm --version
npx --version
git --version
py --version
Get-Command claude,codex,cursor,openclaw -ErrorAction SilentlyContinue
```

These commands do not authenticate to an exchange, reveal credentials, or perform financial actions.

**Does the user need to confirm before this fix?**

Yes if the assistant is expected to execute them through a future local-computer/CLI session. The user may run them manually at any time because they are inspection-only.

---

## E002 — Binance local install cannot be verified yet

**Status:** OPEN / PREPARED.

**Command run:**

Not run on the user's machine.

**Current official install command:**

```bash
npx skills add https://github.com/binance/binance-skills-hub
```

**Potential blocker:**

Current Binance Skills Hub documentation requires Node.js 22+.

**Proposed fix:**

First run `node --version`. Only if Node.js is 22 or newer should the Skills CLI installation be considered. Even then, activate only the research subset defined by `config/research-allowlist.yaml`; do not route wallet/trading/payment capabilities.

**Does the user need to confirm before this fix?**

Yes before package installation or local agent configuration.

---

## E003 — OKX authenticated research capabilities are intentionally not activated

**Status:** EXPECTED SAFETY HOLD.

**Command run:**

No auth/config command was run.

**Reason:**

`okx-sentiment-tracker`, smart-money/account-context functions and OnchainOS APIs may require authentication. A real API key/passphrase has not been supplied and must not be created or written automatically.

**Proposed fix:**

If private read-only data is later required, create a separately restricted read/query-only credential with no withdrawal permission and review the exact scope before configuring it.

**Does the user need to confirm before this fix?**

Yes.

---

## E004 — Bybit full skill is mixed read/write and therefore not activated

**Status:** EXPECTED SAFETY HOLD.

**Command run:**

No credential or trading command was run.

**Reason:**

The current Bybit skill contains public Market research plus spot, derivatives, account, earn, strategy, bot, copy-trading, DEX/Alpha, payment and fiat capabilities. Activating the entire skill without a proven module boundary would violate research-only mode.

**Proposed fix:**

Keep Bybit at Market-module documentation/routing level until the local client can guarantee that only public market functions are available. Do not configure mainnet credentials during this phase.

**Does the user need to confirm before this fix?**

Yes for any future credentialed or write-capable activation.

---

## E005 — Coinbase wallet/AgentKit capability intentionally quarantined

**Status:** EXPECTED SAFETY HOLD.

**Command run:**

No wallet creation, wallet login, funding, send, trade, x402 payment, or on-chain action was run.

**Reason:**

The official projects include actions that can move real assets. This exceeds the research-only permission boundary.

**Proposed fix:**

Keep documentation only. A future testnet-specific project may be designed separately with explicit human approval and hard action allowlists.

**Does the user need to confirm before this fix?**

Yes.

---

## Safe health-check boundary

Allowed during this phase:
- version checks;
- executable discovery (`command -v` / `Get-Command`);
- reading official READMEs/SKILL files;
- fetching public market/info/news/docs data;
- validating configuration files;
- checking that no secret files are committed.

Not allowed during this phase:
- API-key creation or login flows;
- wallet creation/login;
- order placement/amend/cancel/close;
- transfers or withdrawals;
- token swaps or bridges;
- transaction signing/broadcasting;
- sending USDC or other assets;
- payment/x402 execution;
- DeFi/earn investment actions.
