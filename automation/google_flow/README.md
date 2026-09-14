# Google Flow Persistent Autopilot v0.3

Chrome extension local + GitHub command bus để tự động hóa render Google Flow theo lệnh từ các chat sau, không dùng TinyFish/Runway và không lưu thông tin đăng nhập Google.

## Command bus canonical

- Repository: `hanlinh227-ship-it/trading-api`
- Branch: `automation/google-flow-command-bus`
- Queue path: `automation/google_flow/queue.json`
- Raw URL: `https://raw.githubusercontent.com/hanlinh227-ship-it/trading-api/automation/google-flow-command-bus/automation/google_flow/queue.json`

Routine render commands chỉ cập nhật branch command-bus, không cập nhật `main`.

## Cài extension

1. Tải ZIP v0.3 và giải nén.
2. Mở `chrome://extensions/`.
3. Bật **Developer mode**.
4. Chọn **Load unpacked / Tải tiện ích đã giải nén**.
5. Chọn thư mục extension có `manifest.json` ở ngay cấp đầu.
6. Mở Google Flow bằng Chrome profile/Gmail muốn dùng.
7. Mở popup extension.

## Calibration bắt buộc

Remote mode fail-closed: phải lưu selector CSS cho đúng **một** ô prompt và đúng **một** nút Generate đang hiển thị.

Trong popup:

- `Prompt selector`: CSS selector của ô nhập prompt.
- `Generate selector`: CSS selector của nút gửi/generate.
- `Download selector`: tùy chọn, chưa bắt buộc cho acceptance test.
- Bấm **Run preflight trên tab Flow hiện tại**.

Chỉ khi preflight PASS mới nên bật Autopilot.

## Bật Persistent Autopilot

- `Autopilot = ON` được lưu trong `chrome.storage.local`.
- `chrome.alarms` tiếp tục poll queue sau khi service worker sleep hoặc Chrome restart.
- Khi tab Flow đang mở, content script yêu cầu poll nhanh hơn khoảng 15 giây/lần.
- Dedupe theo `command_id`, vì vậy restart không tự submit lại command đã ở trạng thái final.

## Command contract

Chỉ action `render` được chấp nhận.

```json
{
  "command_id": "flow-20260914-scene24-001",
  "created_at": "2026-09-14T05:20:00Z",
  "not_before": null,
  "expires_at": "2026-09-15T05:20:00Z",
  "action": "render",
  "project_url": "https://labs.google/fx/tools/flow/...",
  "scene": 24,
  "prompt": "...",
  "duration_seconds": 8,
  "aspect_ratio": "16:9",
  "start_image": { "mode": "current" },
  "end_image": { "mode": "none" },
  "output_filename": "Scene_24.mp4",
  "retry": { "max_attempts": 1 }
}
```

### Asset support v0.3

Execution enabled:

- `current`
- `none`

Schema nhận diện nhưng executor hiện **fail-closed** cho:

- `local_file`
- `remote_url`

Hai mode này không được tự degrade sang mode khác.

## Security boundary

Extension không:

- đọc/xuất password Google;
- đọc/xuất cookie/session;
- nhập 2FA;
- bypass CAPTCHA/anti-bot;
- chạy arbitrary JavaScript từ queue;
- click arbitrary selector từ command payload;
- điều khiển website ngoài Google Flow allowlist.

Nếu gặp login, CAPTCHA, hết credit/quota, selector mất/ambiguous, mode asset chưa hỗ trợ, hoặc navigation ngoài Flow, execution dừng ở trạng thái `blocked`.

## Future-chat workflow

Sau khi cài v0.3 + calibration + bật Autopilot:

1. User nói: `render Scene 24 trên Flow`.
2. ChatGPT refresh GitHub context.
3. Đọc `automation/google_flow/CURRENT_HANDOFF.md`.
4. Đọc queue branch `automation/google-flow-command-bus`.
5. Append command mới với `command_id` duy nhất, không secret.
6. Extension poll queue và submit khi Chrome/Flow khả dụng.
7. ChatGPT không được tuyên bố render thành công nếu chưa có browser evidence.

## Scene 24 acceptance test

Acceptance đầu tiên dùng ảnh Scene 24 đã được đặt sẵn làm Start trong Flow:

- start mode: `current`
- end mode: `none`
- 8 giây
- 16:9
- retry: 1

Success evidence: Flow hiển thị trạng thái generation/render hoặc video/download result.
