# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md` — current canonical runtime/auto-trade state.
2. `MASTER_TRADING_STATE.md` — historical/frozen architecture and market-method context.
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**V77.18.2** is the current consolidated runtime. Production entrypoint: `cloudflare-worker/index.js`.
Cloudflare is deployment only; do not maintain a second hand-edited Worker copy.

Latest important deploy fix: commit `8f59191f26ef57cbea52ff794c46bc34f4605130` fixed `hyro-scanner.js` syntax error (`Expected ')' but found ';'`). Cloudflare builds are now GREEN/deployed after this fix.

## NON-NEGOTIABLE RUNTIME SEPARATION
### SIGNAL
- Telegram signal/scanner system only.
- Preserves all working Signal/LIVE ORDERS logic from the legacy V77.16.8/V77.17 stack.
- Does NOT feed PROP execution or PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime using `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js`.
- Does NOT consume SIGNAL Telegram entries/candidates.
- Telegram PROP is ACCOUNT MONITORING/CONTROL only.
- Telegram may show account config, wallet/equity/available, daily equity P/L, realized profit, realized loss, net realized P/L, floating P/L, peak/DD, open positions, open-risk, pending count, connection/auto/pause state.
- Telegram MUST NOT push, announce, mirror or expose Hyro auto-entry candidates/orders.
- Auto entries remain silent; only actual account positions/PnL may be viewed.

### PERSONAL
- Independent reserved runtime. No order/state routing from SIGNAL or PROP.

## HYRO ACCOUNT / CURRENT USER STATE
Hyro dashboard account currently shown by user:
- Active HYRO CHALLENGE.
- One-Step.
- 5K USDT.
- Futures.
- Bybit.
- Trailing / Standard.
- Hyro dashboard currently shows Current Balance = $5,000.00 and challenge ongoing.
- Hyro dashboard currently does NOT show a Reconnect API button. User has been advised NOT to delete/modify the existing Hyro-connected Bybit API before Hyro reconnect is available/approved.
- User prepared an email to Hyro Support asking (a) whether active Challenge API can be replaced/reconnected now, (b) to enable/provide Reconnect API procedure, and (c) written confirmation that their own private Bybit API auto-trading bot is permitted on Challenge and Funded accounts. Await support response.

Cloudflare/Bybit bot connection currently:
- Runtime secrets `HYRO_BYBIT_API_KEY` and `HYRO_BYBIT_API_SECRET` have been added as Cloudflare Secrets.
- Build variable `TRADING_KV_NAMESPACE_ID` exists and root directory/deploy config are correct.
- `HYRO_BYBIT_MODE` currently DEMO/default.
- `HYRO_AUTO_EXECUTION` remains OFF. DO NOT enable yet.
- Telegram PROP connection panel showed Credentials OK and telemetry callable.
- Direct account overview successfully read Bybit Demo telemetry: Equity $4,994.97; Wallet $4,994.97; Available $4,994.97; daily equity P/L $0; realized profit $0; realized loss $0; net realized $0; floating $0; positions 0; pending 0; peak equity $4,994.97; DD $0; target +5% = $250; AUTO OFF.
- Earlier connection panel displayed `Auto engine state: TELEMETRY_ERROR`, while direct account overview telemetry succeeded. Treat this as stale/runtime-state discrepancy to resolve before AUTO ON.
- IMPORTANT discrepancy: Hyro dashboard shows $5,000.00 while bot API telemetry shows $4,994.97. Before auto execution, confirm Cloudflare API credentials point to the exact Bybit Demo account/subaccount attached to this Hyro Challenge, or explain the balance difference. Do not arm auto until resolved.

## HYRO ACCOUNT WIZARD
Stored profile asks: CHALLENGE/FUNDED -> account size -> Standard/Trailing or Swing/Static -> Challenge only One-Step/Two-Step. Runtime state persists in KV.

## HYRO RISK/POLICY
- Daily strategy objective fixed at +5% of configured account size.
- Risk firewall always overrides profit objective; target must never force bad trades or a prop-rule breach.
- Internal daily hard stop remains below 3% of account size.
- Native structural SL required; never widen stop.
- TP follows structure/liquidity; planned RR >= 1.5.
- Maximum 2 active Hyro symbols across filled positions + pending orders.
- No duplicate active symbol.
- Manual PAUSE blocks new Hyro entries/cancels pending but must NOT stop Signal scanner or monitoring of existing positions/account.
- Reaching daily +5% or daily hard stop blocks new entries and cancels remaining pending orders.
- HYRO_AUTO_EXECUTION defaults OFF; HYRO_BYBIT_MODE defaults DEMO.
- Dynamic Hyro universe uses Bybit USDT linear perpetual markets; existing symbol-specific knowledge is preserved for known symbols, generic dynamic fallback is stricter for newly discovered symbols.

## STATE CONTINUITY — NEVER DELETE/RESET
- KV binding remains `TRADING_STATE`; preserve the existing namespace ID.
- Existing Signal/LIVE ORDERS keys remain untouched, including legacy books/order archives.
- Hyro profile: `v7717:hyro:profile`
- Hyro wizard draft: `v77171:hyro:draft`
- Hyro manual control: `v77173:hyro:control`
- Hyro runtime/execution/day/idempotency keys: `v7718:hyro:*`
- New versions must read/preserve these states before adding replacements. Migration must be non-destructive.

## REPOSITORY/CLOUDFLARE CLEANUP CONTRACT
- Legacy `.github/workflows/apply-v*.yml` auto-promotion workflows removed from main.
- Legacy `scripts/apply_v*.js` migration scripts removed from main.
- Do not restore them.
- Deploy only `cloudflare-worker/index.js` as canonical entrypoint.
- Keep same `TRADING_STATE` KV namespace and `keep_vars`; never recreate/clear state during deploy.
- Audit/validation/research assets may remain only if they cannot rewrite canonical production code.

## IMMEDIATE NEXT STEPS BEFORE AUTO ON
1. Wait for/read Hyro Support answer about API reconnect and custom private auto-trading permission.
2. Confirm the Cloudflare Bybit API belongs to the exact Hyro Challenge account/subaccount; resolve $5,000 Hyro vs $4,994.97 API telemetry discrepancy.
3. Fix/refresh stale `TELEMETRY_ERROR` auto-engine state so connection/runtime and direct telemetry agree.
4. Test `VỊ THẾ ĐANG CHẠY` and `RISK/DD` while flat; verify no errors.
5. Test reconciliation/idempotency/pending cancellation/native SL-TP in DEMO before real Challenge execution.
6. Only after all gates pass should `HYRO_AUTO_EXECUTION=true` be considered. Keep Telegram auto orders silent; PROP only monitors account/positions/PnL.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- Existing market-specific Signal knowledge, market-data integrity, fresh-price requirements and durable LIVE ORDERS behavior remain active unless explicitly superseded here.
- Do not restore deleted legacy score-only authority or old migration chains.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó docs/checkpoints/V77180_AUTO_READY_CONSOLIDATED.md và MASTER_TRADING_STATE.md; không quay lại phương pháp/workflow đã loại và phải bảo toàn toàn bộ KV/LIVE ORDERS/state đang hoạt động. Canonical hiện là V77.18.2, Cloudflare build đã xanh sau commit 8f59191 sửa hyro-scanner. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập; PROP Telegram chỉ theo dõi/control tài khoản, tuyệt đối không phát candidate/lệnh auto. Hyro hiện là Challenge One-Step 5K Futures Bybit Standard/Trailing; Cloudflare đã có HYRO_BYBIT_API_KEY/SECRET và đọc được Bybit DEMO telemetry $4,994.97 nhưng Hyro dashboard đang hiện $5,000, AUTO vẫn OFF và từng có stale TELEMETRY_ERROR ở connection panel. Tôi đang chờ Hyro Support trả lời về reconnect API và quyền dùng custom auto bot. Việc tiếp theo là xác nhận API Cloudflare đúng chính account/subaccount Hyro, xử lý chênh balance + TELEMETRY_ERROR, test Positions/Risk-DD/reconciliation/native SL-TP trong DEMO, rồi chỉ khi mọi gate pass mới bật HYRO_AUTO_EXECUTION=true. Hãy tiếp tục đúng trạng thái này và tự đọc GitHub để biết toàn bộ chi tiết trước khi sửa.`
