# AI Skill Library

Kho nguồn mở dùng làm corpus cho AI cá nhân, tách biệt khỏi code production của `trading-api`.

## Mục tiêu

- Game development
- UX/UI & design systems
- Prompt engineering
- Script/screenwriting/story structure
- Coding & software agents
- Trading: Forex, Crypto, Futures, Index/Equities
- Software architecture & application development

## Cách tích hợp

Không vendor/copy toàn bộ upstream vào GitHub này. `sources.yaml` là registry nguồn chuẩn; `ingest_sources.py` shallow-clone vào thư mục cache cục bộ rồi xuất corpus JSONL có metadata nguồn, commit và license.

Pipeline đề xuất:

`GitHub sources -> license gate -> shallow clone -> file filter -> chunk -> JSONL -> RAG/vector DB hoặc fine-tune pipeline`

## Nguyên tắc license

1. Chỉ auto-ingest các repo có license được whitelist trong `LICENSE_POLICY.md`.
2. Không coi "public repo" là tự động được phép huấn luyện/redistribute.
3. Repo có mixed assets, model weights, datasets hoặc third-party content chỉ ingest phần code/docs thuộc license đã xác minh.
4. Nguồn public-domain theo từng tác phẩm (ví dụ GITenberg) cần kiểm tra từng item trước khi bật.
5. Giữ metadata `source_url`, `commit`, `license`, `path` trong mọi chunk để truy vết/attribution.

## Chạy

```bash
cd AI_SKILL_LIBRARY
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python ingest_sources.py --category trading --output ./corpus/trading.jsonl
python ingest_sources.py --category ux_ui --output ./corpus/ux_ui.jsonl
python ingest_sources.py --all --output ./corpus/all.jsonl
```

Mặc định script chỉ tải source vào `.cache/repos/`, không cài dependency, không chạy build script và không execute code từ upstream.

## Dùng cho AI

- **RAG**: ưu tiên trước; ít rủi ro license hơn và cập nhật upstream dễ.
- **Fine-tune/SFT**: chỉ dùng entries có `training: true`, giữ provenance và tuân thủ attribution/copyright tương ứng.
- **Trading**: corpus là nguồn kỹ thuật/nghiên cứu, không phải tín hiệu giao dịch hay cam kết lợi nhuận.

## Trạng thái

Đây là whitelist v1 chất lượng cao, không phải tuyên bố bao phủ "toàn bộ GitHub". GitHub có hàng trăm triệu repo và license thay đổi; registry được thiết kế để mở rộng có kiểm soát thay vì ingest mù.