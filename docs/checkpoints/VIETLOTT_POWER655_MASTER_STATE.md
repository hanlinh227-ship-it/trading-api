# VIETLOTT POWER 6/55 — MASTER STATE

Updated: 2026-08-28 (Asia/Ho_Chi_Minh)
Status: ACTIVE DATA/RESEARCH CHECKPOINT

## Mục tiêu

Checkpoint này là điểm khởi động chuẩn cho dự án nghiên cứu toán học/thống kê Vietlott Power 6/55. Khi mở chat mới và muốn tiếp tục, phải đọc file này trước, sau đó đọc `data/vietlott/power655/metadata.json` và dataset hiện hành.

Mục tiêu nghiên cứu là kiểm tra khách quan xem lịch sử quay có chứa tín hiệu thống kê có khả năng tổng quát hóa hay không. Không được giả định trước rằng tồn tại công thức dự đoán chắc chắn và không được làm đẹp kết quả backtest.

## Nguồn dữ liệu và phạm vi

- Sản phẩm: Vietlott Power 6/55.
- Kỳ đầu tiên: #00001, ngày 2017-08-01.
- Kết quả kỳ #00001: 05 10 14 23 24 38 | Power 35.
- Tại thời điểm lập checkpoint, kỳ mới nhất đã xác minh trên web là #01390, ngày 2026-08-27.
- Kết quả #01390: 01 03 11 21 26 44 | Power 10.
- Như vậy phạm vi mục tiêu hiện tại là 1,390 kỳ liên tục từ #00001 đến #01390.
- Nguồn upstream dùng để đồng bộ snapshot: `vietvudanh/vietlott-data`, file `data/power655.jsonl`.
- Nguồn đối chiếu ưu tiên: trang kết quả chính thức Vietlott; nguồn công khai thứ cấp chỉ dùng để kiểm tra chéo khi cần.

## Dataset trong repository

Workflow `.github/workflows/vietlott-power655-sync.yml` tự tải và chuẩn hóa toàn bộ lịch sử thành:

- `data/vietlott/power655/power655_all_draws.csv`
- `data/vietlott/power655/power655_all_draws.jsonl`
- `data/vietlott/power655/metadata.json`

Schema CSV:

`date, draw_id, n1, n2, n3, n4, n5, n6, power_number`

Quy ước: `n1..n6` là sáu số chính; `power_number` là số Power dùng cho Jackpot 2.

## Data integrity hard rules

1. Không phân tích nếu dataset không bắt đầu ở #00001.
2. `draw_id` phải liên tục, không trùng và không thiếu kỳ.
3. Mỗi kỳ phải có đúng 6 số chính + 1 Power number.
4. Tất cả số phải thuộc 1..55; sáu số chính không được trùng nhau.
5. Khi có kỳ mới, cập nhật dataset trước rồi mới chạy phân tích/backtest.
6. Nếu upstream và Vietlott chính thức bất đồng, Vietlott chính thức là authority; đánh dấu kỳ đó để audit, không âm thầm sửa.
7. Không sử dụng dữ liệu tương lai trong feature của kỳ quá khứ (no look-ahead leakage).

## Research protocol

Các hướng kiểm tra tối thiểu:

- frequency / expected frequency của 01..55;
- gap/overdue distribution;
- pair/triple co-occurrence;
- odd/even, low/high, sums, ranges, spacing, consecutive numbers, terminal digits;
- rolling-window frequency/momentum/reversion;
- autocorrelation và dependency giữa kỳ t và t+1;
- conditional patterns theo thứ/ngày/tháng chỉ khi có kiểm định out-of-sample;
- entropy/randomness tests;
- Monte Carlo baseline;
- walk-forward train/validation/test;
- multiple-hypothesis correction để hạn chế data-mining false positives.

Một công thức chỉ được giữ nếu cải thiện trên dữ liệu OUT-OF-SAMPLE / WALK-FORWARD so với baseline ngẫu nhiên. Kết quả in-sample đẹp nhưng thất bại out-of-sample phải bị loại.

## Baseline toán học

Power 6/55 có `C(55,6) = 28,989,675` tổ hợp sáu số. Nếu cơ chế quay là ngẫu nhiên công bằng, mỗi tổ hợp sáu số có cùng xác suất Jackpot 1 là `1 / 28,989,675` cho một dòng vé.

Mục tiêu của dự án không phải tuyên bố phá được tính ngẫu nhiên, mà là tìm và kiểm định bất kỳ sai lệch/tín hiệu nào bằng dữ liệu thực, với chống overfit nghiêm ngặt.

## Continuation prompt

Trong chat mới có thể nói:

`Tiếp tục dự án Vietlott Power 6/55. Fresh-read GitHub main, đọc docs/checkpoints/VIETLOTT_POWER655_MASTER_STATE.md và data/vietlott/power655/metadata.json trước, xác nhận dataset mới nhất rồi tiếp tục nghiên cứu/backtest. Không làm đẹp số và không dùng look-ahead.`

## Next research step

Sau khi dataset sync hoàn tất: tạo baseline statistical audit toàn bộ lịch sử, khóa train/test theo thời gian, rồi bắt đầu thử từng hypothesis. Mọi hypothesis phải có log, version, metrics và kết quả rejected/accepted để tránh thử lại các công thức đã thất bại.
