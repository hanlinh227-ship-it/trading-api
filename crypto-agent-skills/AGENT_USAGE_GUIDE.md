# AGENT_USAGE_GUIDE

Mục tiêu của workspace này là hỗ trợ **research và lập kế hoạch**, không tự giao dịch. AI có thể tổng hợp dữ liệu, kiểm tra rủi ro, so sánh nguồn, tạo watchlist và xây dựng trading plan; **quyết định giao dịch cuối cùng luôn do con người đưa ra**.

## 1. Morning Brief thị trường

### Mục tiêu
Tạo bản tóm tắt đầu ngày về trạng thái crypto market: BTC/ETH, market breadth, nhóm coin nổi bật, funding, open interest, biến động, smart-money signal, tin tức và các rủi ro vĩ mô đáng chú ý.

### Nguồn ưu tiên
- Gate public Market / Info / News / Docs.
- OKX public market module.
- Binance market-rank/token-info.
- KuCoin public spot/futures GET endpoints.

### Prompt mẫu

```text
Tạo Morning Brief crypto cho hôm nay ở chế độ research-only. Hãy kiểm tra BTC, ETH và các nhóm coin đang có volume/momentum đáng chú ý; tổng hợp funding rate, open interest, market breadth, biến động 24h, smart-money hoặc inflow signal nếu nguồn read-only có sẵn, và các tin tức/macro event có thể tác động trong ngày. Ghi rõ nguồn và độ mới của dữ liệu khi có thể. Không đề xuất đặt lệnh tự động, không gọi wallet/trading action. Kết thúc bằng 3 nhóm: Market Regime, Watchlist ưu tiên, Risk cần tránh.
```

---

## 2. Watchlist Scanner

### Mục tiêu
Lọc một danh sách coin từ nhiều nguồn theo thanh khoản, volume, động lượng, funding/OI, token risk và tín hiệu dòng tiền để tìm các ứng viên cần theo dõi sâu hơn.

### Nguồn ưu tiên
- Binance `crypto-market-rank`, `query-token-info`, `query-token-audit`.
- Gate coin analysis/risk check/market analysis.
- OKX market module và read-only DEX market research.
- KuCoin spot/futures market GET.

### Prompt mẫu

```text
Quét watchlist crypto theo chế độ research-only. Hãy tìm tối đa 10 coin có thanh khoản tốt và chuyển động đáng chú ý dựa trên volume, biến động, xu hướng đa khung, funding, open interest và dòng tiền/smart-money nếu có. Loại hoặc hạ hạng token có risk flag, holder concentration bất thường, thanh khoản kém hoặc dấu hiệu honeypot/rug. Với mỗi coin, ghi: lý do lọt watchlist, catalyst/risk, vùng cần theo dõi và dữ liệu nào cần xác nhận thêm. Không đặt lệnh và không kích hoạt trading/wallet skill.
```

---

## 3. Setup Deep Dive

### Mục tiêu
Phân tích sâu một coin/setup cụ thể trước khi con người quyết định có giao dịch hay không.

### Kiểm tra tối thiểu
- Market structure và multi-timeframe context.
- Liquidity/order-book context nếu có.
- Funding, OI và derivatives positioning.
- Token/security risk nếu là altcoin/on-chain token.
- News/catalyst và invalidation evidence.
- Điều kiện khiến setup không còn hợp lệ.

### Prompt mẫu

```text
Phân tích sâu setup [SYMBOL] ở chế độ research-only. Dùng dữ liệu thị trường mới nhất từ các nguồn read-only hiện có để kiểm tra cấu trúc H4/H1/M15, momentum, support/resistance hoặc liquidity zone, funding, open interest, order book nếu có, news/catalyst, token risk và smart-money context. Hãy tách rõ FACT / INFERENCE / ASSUMPTION. Cho tôi kịch bản bullish, bearish và no-trade; nêu invalidation rõ ràng. Chỉ xây dựng phân tích và trading plan nháp, không đặt lệnh.
```

---

## 4. Smart Money / Dòng tiền

### Mục tiêu
Theo dõi public wallet activity, inflow/outflow, top traders, whale/KOL signal hoặc token flow mà không dùng quyền wallet action.

### Nguồn ưu tiên
- Binance market-rank / query-address-info.
- OKX read-only DEX market/smart-money analytics.
- Gate address tracker/token-onchain/market research.

### Prompt mẫu

```text
Phân tích Smart Money / dòng tiền cho [TOKEN hoặc danh sách token] ở chế độ research-only. Tổng hợp inflow/outflow, whale/public-wallet activity, holder concentration, top trader hoặc smart-money signal nếu nguồn read-only hỗ trợ. Phân biệt tín hiệu mới với dữ liệu đã cũ, kiểm tra xem dòng tiền có đi kèm volume/liquidity thật hay chỉ là chuyển ví. Trả về: Direction of Flow, Quality of Flow, Confirmation, Risk Flags và các token đáng theo dõi tiếp. Không ký giao dịch, không swap, không dùng wallet action.
```

---

## 5. Trading Plan Builder

### Mục tiêu
Biến phân tích thành một kế hoạch giao dịch có điều kiện để con người xem xét. Workflow này **không phải execution workflow**.

### Output nên có
- Bias và điều kiện để bias đúng.
- Entry zone hoặc trigger condition.
- Invalidation/SL logic.
- TP logic và RR dự kiến.
- Position-sizing input cần con người cung cấp.
- Trường hợp bắt buộc NO TRADE.
- Dữ liệu cần refresh trước khi ra quyết định.

### Prompt mẫu

```text
Từ toàn bộ dữ liệu research hiện có cho [SYMBOL], hãy xây dựng một Trading Plan nhưng tuyệt đối không đặt lệnh. Tách rõ FACT / INFERENCE / ASSUMPTION. Cho tôi bias chính, điều kiện entry, vùng entry hoặc trigger, invalidation/SL logic, TP1/TP2/TP3, RR dự kiến, catalyst/risk, và điều kiện NO TRADE. Nếu dữ liệu giá/funding/OI/news đã stale thì yêu cầu refresh trước khi kết luận. Không gọi bất kỳ API order, wallet, transfer, swap, bridge hay broadcast nào. Tôi sẽ là người quyết định có giao dịch hay không.
```

## Nguyên tắc vận hành chung

- AI hỗ trợ phân tích; **con người ra quyết định**.
- Không biến một tín hiệu thành lệnh chỉ vì confidence cao.
- Nếu dữ liệu live/staleness không xác minh được, phải nói rõ thay vì suy đoán.
- Nếu các nguồn mâu thuẫn, ưu tiên nguồn mới hơn/có authority cao hơn và nêu xung đột.
- Bất kỳ bước nào cần quyền ghi, giao dịch, wallet hoặc chuyển tiền đều phải dừng tại research boundary và yêu cầu một quy trình HIGH-RISK riêng trong tương lai.
