# License & Provenance Policy

## Auto-allow

Các license sau được phép qua cổng ingest mặc định, nhưng vẫn phải giữ attribution/notice theo điều khoản của từng license:

- MIT
- Apache-2.0
- BSD-2-Clause
- BSD-3-Clause
- CC0-1.0
- CC-BY-4.0 (attribution bắt buộc)
- Zlib

## Không auto-ingest

- Repo không có license rõ ràng.
- Source-available/proprietary/EULA-only.
- GPL/AGPL/LGPL được để ngoài whitelist mặc định để tránh vô tình tạo corpus/derivative có nghĩa vụ copyleft chưa được đánh giá.
- Datasets/model weights có license riêng không kế thừa license của repo chứa code.
- Ảnh, icon, font, sample media, game assets, screenshots và third-party bundles nếu không có license tương thích riêng.
- Nội dung người dùng, issues/discussions, secrets, credentials, `.env`, dumps hoặc dữ liệu cá nhân.

## Quy tắc provenance

Mỗi record JSONL phải giữ tối thiểu:

- `category`
- `repo`
- `source_url`
- `commit`
- `license`
- `path`
- `content`

Không xóa metadata nguồn trước khi index RAG hay tạo dataset SFT.

## Public domain / GITenberg

Không ingest cả organization một cách tự động. Chỉ bật từng tác phẩm khi chính repository/tác phẩm xác nhận public domain hoặc quyền sử dụng phù hợp với khu vực pháp lý áp dụng. Project Gutenberg cũng lưu ý trạng thái bản quyền có thể khác ngoài Hoa Kỳ.

## Trading

Chỉ dùng code/docs/research làm kiến thức kỹ thuật. Không coi chiến lược mẫu, backtest, README hay model nghiên cứu là bằng chứng về lợi nhuận thực tế.