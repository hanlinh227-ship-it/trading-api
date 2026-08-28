# BYBIT GPT MARKET ENTRY REASONING CHECKPOINT — 2026-08-28

## Mục đích
Checkpoint này dùng để giữ nguyên cùng một tư duy giữa bot Bybit runtime và các cuộc chat GPT khác khi người dùng yêu cầu tìm lệnh MARKET ngay tại GPT.

## Provenance Claude + GPT
Reasoning hiện tại là bản hợp nhất giữa:
- Claude ở vai trò co-architect: ưu tiên tail-risk, execution safety, reconciliation, sizing theo context, tránh over-filter và yêu cầu mọi thay đổi phải chứng minh tăng edge hoặc giảm tail-risk.
- GPT ở vai trò primary engineer: verify source trước khi sửa, bảo toàn tần suất lệnh, loại double-count/filter ngầm, chuyển soft correlation từ reject sang size-only, candidate fallback cùng cycle, post-AI quote revalidation và hard-lock bằng validator.

Runtime marker bắt buộc: `CLAUDE_COARCHITECT_GPT_PRIMARY_ENGINEER_FUSION`.
Nguyên tắc quyết định: nếu một thay đổi chỉ tăng complexity mà không tăng real edge, giảm tail-risk hoặc tăng execution robustness thì REJECT.

## Authority chain
1. Fresh-read GitHub `main` trước mọi phân tích.
2. Source hiện tại thắng mọi checkpoint cũ nếu có xung đột.
3. Đọc tối thiểu:
   - `cloudflare-worker/bybit-runtime-contract.js`
   - `cloudflare-worker/bybit-market-entry-reasoning.js`
   - `cloudflare-worker/bybit-auto-config.js`
   - `cloudflare-worker/bybit-scalp-engine.js`
   - `cloudflare-worker/bybit-adaptive-edge.js`
   - `cloudflare-worker/bybit-risk-guard.js`
   - `cloudflare-worker/bybit-ai-scalp-gate.js`
   - `cloudflare-worker/bybit-position-manager.js`
4. Không dùng số liệu/backtest không có evidence thật.

## Reasoning contract
- Signal authority: closed candle 5m.
- Context authority: closed candle 15m.
- M1 không được dùng làm decision authority cho entry hoặc Smart CUT.
- Quote MARKET phải fresh/live; phải ghi source + timestamp/quote age nếu khả dụng.
- Không dùng stale/cached quote để phát entry.
- Không thêm confirmation/filter mới ngoài source hiện tại.
- Không hạ minScore/minRR để ép ra lệnh.
- Không tăng điểm cứng cho BTC/ETH/SOL hay bất kỳ symbol nào.
- Spread: giữ hard safety cap/liquidity quality; không double-penalize lại vào threshold chỉ vì spread đã được tính ở layer khác.
- Correlation: vùng soft 0.84–0.94 là size-only; không biến thành hard reject. >=0.94 vẫn hard reject theo source hiện tại.
- Contextual size multiplier không được trở thành hidden entry filter; utilization floor phải scale tương ứng. Chỉ reject vì exchange min qty/notional hoặc hard safety thực sự.
- Same-direction cap phải được check trước execution để candidate queue có thể fallback sang candidate khác trong cùng cycle.
- Không nới hard risk caps từ `bybit-auto-config.js`.
- Không làm SL/TP gần hơn; không làm BE/trailing/Smart CUT sớm hơn.
- Learning chỉ bounded; `autoPromote=false`.
- Nếu thiếu dữ liệu thật thì nói thiếu; không bịa giá, fill, PnL, win rate, backtest hay AI consensus.

## Cách GPT tìm MARKET entry trực tiếp
Khi user yêu cầu `tìm 1 entry crypto MARKET`, `quét market`, `bắt buộc tìm entry`, hoặc tương đương:

1. Fresh-read `main` + checkpoint này.
2. Lấy quote live/fresh trước khi đưa entry. Nếu có pipeline/connected runtime Bybit thì dùng pipeline đó; nếu không có, dùng nguồn live đáng tin nhất đang khả dụng và ghi rõ nguồn. Không giả vờ đã gọi runtime nếu không gọi được.
3. Quét candidate theo logic source hiện tại: 5m signal + 15m context, closed candles, liquidity, regime, setup score, RR, current hard safety.
4. Với ALL/universe: scan rộng, xếp hạng candidate, thử candidate fallback thay vì dừng ở candidate đầu bị cap mềm/side cap.
5. Nếu candidate nằm correlation soft 0.84–0.94: giữ candidate và giảm size theo source; không reject chỉ vì soft correlation.
6. Sau khi có candidate, freshen/revalidate MARKET quote. Nếu giá đã drift làm RR/geometry hỏng thì bỏ candidate và thử candidate tiếp theo.
7. Nếu không có candidate hợp lệ sau scan/fallback: trả `NO_MARKET_ENTRY` và lý do chính xác. Câu “bắt buộc tìm” không cho phép bịa lệnh.
8. Trong chat GPT mặc định chỉ đưa signal/review. Không thực hiện trade thật trừ khi user yêu cầu và tool execution hợp lệ thực sự khả dụng.

## Output chuẩn
Trả ngắn gọn theo format:

`MARKET LONG` / `MARKET SHORT` / `NO_MARKET_ENTRY`

- Symbol:
- Live quote:
- Source:
- Quote age / timestamp:
- Entry MARKET:
- SL:
- TP:
- RR:
- Score / threshold:
- Regime:
- Correlation state / size multiplier nếu có:
- Lý do chọn:
- Blocking reason nếu NO_MARKET_ENTRY:

Không ghi giá entry giả định nếu quote không fresh.

## Prompt dùng ở chat GPT khác
Copy nguyên prompt dưới đây:

> Tiếp tục dự án Trading từ GitHub `hanlinh227-ship-it/trading-api`. Fresh-read `main` trước. Đọc `docs/checkpoints/BYBIT_GPT_MARKET_ENTRY_REASONING_20260828.md` và các source authority nó chỉ định. Sau đó tìm 1 entry crypto MARKET tốt nhất hiện tại theo đúng Bybit reasoning contract hiện tại. Bắt buộc lấy quote live/fresh trước khi phát entry và ghi source + timestamp/quote age. Chỉ dùng closed candle 5m cho signal và 15m cho context; M1 không có authority. Không thêm filter mới, không hạ minScore/minRR, không double-penalize spread, correlation 0.84–0.94 là size-only và >=0.94 mới hard reject. Candidate bị side cap/soft condition thì thử candidate tiếp theo trong cùng scan. Trả `MARKET LONG`, `MARKET SHORT` hoặc `NO_MARKET_ENTRY` với symbol, live quote, entry, SL, TP, RR, score/threshold, regime và lý do. Nếu không có dữ liệu live thật hoặc không có candidate hợp lệ thì nói đúng lý do, tuyệt đối không bịa giá/lệnh.

## Prompt siêu ngắn sau khi checkpoint đã được biết
> Dùng `BYBIT_GPT_MARKET_ENTRY_REASONING_20260828`, fresh-read main rồi tìm MARKET entry crypto tốt nhất hiện tại. Quote phải live/fresh, 5m/15m only, không bịa, trả đúng MARKET LONG/SHORT/NO_MARKET_ENTRY.

## Trạng thái wave reasoning
Các thay đổi frequency-preserving đã merge trước checkpoint này:
- bỏ spread double-punishment trong adaptive threshold;
- soft correlation chuyển từ binary reject sang size-only scaling;
- utilization floor scale theo contextual multiplier để không thành hidden gate;
- same-direction cap được đưa lên candidate risk preflight để fallback trong cùng cycle;
- runtime expose full reasoning object để `/runtime/contract` có thể audit;
- validator riêng hard-lock reasoning invariants và provenance Claude+GPT.

## Deployment verification rule
Bybit runtime verification phải độc lập với Forex health. Forex/MT5 stale heartbeat phải được báo riêng, không được làm một Bybit deploy đã PASS bị đánh FAIL giả. Checkpoint này vẫn không phải bằng chứng production LIVE; chỉ được tuyên bố môi trường nào đã verified đúng môi trường đó.
