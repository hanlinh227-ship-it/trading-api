# SAFETY_RULES

These rules are mandatory for every crypto-agent workflow in this workspace.

1. **Research-only by default.** Market data, token research, risk checks, news, sentiment, on-chain observation, watchlists, and trading-plan drafting are allowed. Execution is not.
2. **No withdrawal permission.** Never request, enable, store, or route a credential with withdrawal capability for this research layer.
3. **No live order without a separate explicit future confirmation.** Preparing an analysis or trading plan is not authorization to place, amend, cancel, or close an order.
4. **No private key or seed phrase in chat, repository, notes, logs, screenshots, or generated files.** The same applies to API secrets, passphrases, OAuth tokens, session tokens, and signing material.
5. **Prefer public/no-auth data first.** If private account data is genuinely needed later, use a restricted read-only API key or testnet/sub-account profile with minimum permissions.
6. **HIGH RISK stays disabled.** Trading, transfers, withdrawals, swaps, bridges, wallet creation/authentication, transaction signing/broadcasting, payments, DeFi deposit/withdraw/claim, earn purchase/redeem, leverage changes, account-mode changes, and bot creation/control must not be activated by this setup.
7. **Capability does not imply permission.** A skill may document an action that this workspace is not allowed to execute.
8. **No hidden escalation.** A read-only workflow must never automatically fall through to a write-capable module when data is unavailable.
9. **No secret echoing.** Health checks may confirm that a variable exists, but must not print its value. Do not use commands that reveal complete credentials.
10. **Human decision boundary.** AI may collect evidence, compare sources, assess risk, and draft a trading plan. The human user makes the trading decision and separately authorizes any future execution layer.

## Risk classes

- **LOW** — public/read-only information; cannot move funds or change account state.
- **MEDIUM** — authenticated read-only/account-context capability, strategy/signal tooling, or a mixed skill that is safe only when constrained to query functions.
- **HIGH** — can place/cancel/amend orders, transfer/withdraw funds, create/authenticate wallets, sign/broadcast transactions, swap/bridge, pay, stake/invest, change leverage/account state, or otherwise affect real assets.

## Fail-closed rule

If it is unclear whether a command is read-only, treat it as HIGH RISK and do not execute it until its behavior and permissions are verified from current official documentation and the user separately confirms activation.
