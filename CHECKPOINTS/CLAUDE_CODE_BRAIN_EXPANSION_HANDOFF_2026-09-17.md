# Claude Code Brain Expansion Handoff — 2026-09-17

Copy the prompt below into Claude Code from the root of `hanlinh227-ship-it/trading-api`.

```text
Bạn đang làm việc trực tiếp trên repository `hanlinh227-ship-it/trading-api`.

MỤC TIÊU
Triển khai end-to-end kiến trúc Brain Expansion đã được đăng ký trong repo, tích hợp có kiểm soát 5 runtime-adapter candidates và 3 reference-only candidates, nhưng tuyệt đối không tạo một brain/router/memory/control-plane thứ hai.

BẮT BUỘC ĐỌC TRƯỚC KHI SỬA BẤT KỲ FILE NÀO
1. `AI_SKILL_LIBRARY/checkpoint.json`
2. Tất cả canonical pointers mà checkpoint hiện hành chỉ ra cho router, runtime, security, evidence, memory, observability, reliability, retrieval, integrations, source registry, evals, validators và release policy.
3. `AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml`
4. `docs/superpowers/specs/2026-09-17-brain-expansion-integrations-design.md`
5. `docs/superpowers/plans/2026-09-17-brain-expansion-integrations.md`

ROUTING / AUTHORITY
- Mọi công việc phải đi qua `task_router` hiện hành.
- `task_router` tiếp tục là routing authority duy nhất.
- Legion tiếp tục là multi-agent execution authority.
- Model Mesh tiếp tục là model/provider selection authority.
- Memory Continuity tiếp tục là memory authority.
- Current project authority/checkpoint luôn thắng external framework, memory và reference source.
- External repo không được có reasoning authority.
- Không preload toàn bộ skill library; dùng context tối thiểu đúng protocol.

CÁC UPSTREAM CẦN XỬ LÝ
Runtime-adapter candidates:
- `langfuse/langfuse` — sanitized observability adapter.
- `vibrantlabsai/ragas` — RAG/retrieval evaluation adapter.
- `confident-ai/deepeval` — LLM/agent behavior evaluation adapter.
- `browser-use/browser-use` — sandbox browser execution adapter.
- `BoundaryML/baml` — optional typed-output contract adapter.

Reference-only candidates:
- `microsoft/agent-framework` — orchestration/session/MCP/A2A/telemetry patterns only.
- `letta-ai/letta` — memory architecture patterns only; NO memory authority/writeback.
- `agno-agi/agno` — agent-team/runtime patterns only; NO router/Legion/runtime replacement.

NGUYÊN TẮC INTAKE TRƯỚC DEPENDENCY
Trước khi thêm bất kỳ executable dependency nào, tự xác minh và ghi lại:
- canonical repository identity;
- current default branch;
- pinned commit/tag/ref dùng cho intake/activation;
- verified license và dependency-license concerns;
- archived/maintenance status;
- security/supply-chain risk;
- network/runtime behavior;
- overlap với capability hiện có;
- performance/cost impact;
- permission ceiling;
- rollback path.
Nếu license hoặc security material còn mơ hồ: KHÔNG activate dependency đó; giữ ở reference/quarantine và tiếp tục các phần khác.

TDD / VALIDATION BẮT BUỘC
Đối với mọi thay đổi behavior:
1. Tìm test pattern hiện hành trong repo.
2. Viết test thất bại trước khi implement khi khả thi.
3. Chạy test và xác nhận RED vì đúng lý do.
4. Implement tối thiểu.
5. Chạy lại xác nhận GREEN.
6. Chạy validator/eval liên quan.
7. Commit theo task nhỏ, có ý nghĩa.
Không được tuyên bố hoàn tất chỉ dựa trên đọc code.

LANGFUSE CONTRACT
- Dùng existing sanitized observability contract và OpenTelemetry-compatible metadata khi phù hợp.
- Cấm raw prompts, raw private chat, raw private tool payloads, secrets, credentials, auth tokens, private keys, account data và hidden chain-of-thought.
- Trace chỉ diagnostic, không authority.
- Exporter/telemetry failure không được làm hỏng stable request path.
- Feature flag/adapter phải tắt độc lập được.

RAGAS CONTRACT
- Offline/CI by default.
- Không trở thành production hard dependency.
- Map metrics vào failure taxonomy/eval dimensions hiện hữu.
- Không được dùng một external score để auto-promote candidate.
- Native deterministic validators/evals vẫn có quyền quyết định promotion theo policy.

DEEPEVAL CONTRACT
- Offline/CI by default.
- Dùng cho behavioral regression, instruction/task success, groundedness/hallucination khi phù hợp.
- Map failure về taxonomy hiện hành.
- Không production hard dependency.
- Không majority-vote truth.
- Không auto-promotion.

BROWSER USE CONTRACT
- Sandbox trước khi bất kỳ activation nào.
- Router chọn capability/objective; Browser Use chỉ thi hành bounded task.
- Read-only mặc định.
- Reversible write chỉ khi explicit user request + current project/security policy cho phép.
- Destructive action vẫn theo existing explicit-approval rules.
- Financial execution qua generic browser adapter: FORBIDDEN.
- Credential persistence: FORBIDDEN.
- Domain/tool scope phải bounded.
- Runtime success claim phải có runtime verification khi material.
- Adapter failure phải report failure thật, không giả success.
- Adapter phải disable độc lập được.

BAML CONTRACT
- Optional schema/typed-contract layer only.
- Không thay business logic hoặc reasoning authority.
- Phải tương thích với canonical Pydantic/JSON Schema paths hiện hữu.
- Tắt/gỡ BAML không được đổi business semantics.
- Không provider lock-in.
- Không migrate hàng loạt schema nếu không có measured need.

REFERENCE-ONLY CONTRACT
Microsoft Agent Framework, Letta, Agno:
- Không executable dependency theo task này trừ khi architecture/policy hiện hành đã có separate explicit promotion authorization cụ thể.
- Không parallel router.
- Không parallel memory authority.
- Không parallel model selector.
- Không parallel Legion/control plane.
- Chỉ đăng ký provenance/license/pinned ref/focus theo source registry policy và trích pattern phù hợp.

SECURITY
- Capability does not imply permission.
- Secrets/credentials/private keys không bao giờ commit vào repo hoặc durable memory/trace.
- Dùng env/secret store/runtime credential mechanism hiện hữu nếu adapter cần secret.
- Không nới quyền vì framework hỗ trợ tính năng đó.
- Không bypass security gate, project policy hoặc financial/destructive controls.

FAILURE ISOLATION
Stable brain phải tiếp tục hoạt động khi TẤT CẢ adapter mới đều OFF.
Mỗi adapter runtime phải independently disableable.
Upstream unavailable, stale, misconfigured, quota/rate-limit hoặc exporter failure không được phá stable path trừ khi current canonical policy yêu cầu fail-closed cho action cụ thể.

THỨ TỰ TRIỂN KHAI
Thực hiện đúng implementation plan trong:
`docs/superpowers/plans/2026-09-17-brain-expansion-integrations.md`

Tóm tắt thứ tự:
1. Refresh checkpoint + baseline validators/CI.
2. Audit/pin/license/security tất cả upstream.
3. Shared adapter contracts/feature flags.
4. Langfuse.
5. Ragas + DeepEval.
6. Browser Use sandbox adapter.
7. BAML optional contract adapter.
8. Microsoft Agent Framework + Letta + Agno reference-only registration.
9. Targeted tests/evals.
10. Full brain validators + CI.
11. Disable/rollback smoke test từng adapter.
12. Update canonical pointers/release/checkpoint CHỈ khi current repo policy và toàn bộ required gates cho phép.

KHÔNG LÀM
- Không thay task_router.
- Không thay Legion.
- Không thay Model Mesh.
- Không thay Memory Continuity bằng Letta/Agno/Microsoft Agent Framework.
- Không fork architecture sang subsystem cạnh tranh.
- Không bật dependency chỉ vì repo phổ biến.
- Không dùng floating branch làm bằng chứng activation nếu policy yêu cầu pinned provenance.
- Không gọi code/adapter LIVE nếu chưa verify actual runtime.
- Không sửa unrelated project đang vận hành.
- Không đưa secrets/API keys vào GitHub.

ĐIỀU KIỆN HOÀN TẤT
Chỉ báo COMPLETE khi có bằng chứng:
- architecture/authority preservation tests pass;
- targeted unit/integration tests pass;
- relevant evals pass;
- security/privacy tests pass;
- current brain validators pass;
- CI pass theo repo policy;
- no protected regression in correctness/verification/safety/authority;
- stable path hoạt động với mọi adapter mới OFF;
- rollback/disable của từng adapter được test;
- runtime activation state của từng candidate được xác minh và phân biệt rõ: architecture_registered / reference_only / sandbox_ready / enabled / production_verified.

OUTPUT CUỐI CÙNG
Trả về một handoff ngắn nhưng đầy đủ gồm:
- branch/commit SHAs;
- files changed;
- mỗi upstream: canonical repo + pinned ref + verified license + status;
- dependencies added/không added;
- feature flags;
- tests/evals/validators/CI đã chạy + exact result;
- lỗi gặp và cách sửa;
- unresolved blockers;
- activation state từng adapter;
- rollback instructions;
- xác nhận rõ `fresh_git_context=true/false` và runtime verification thực tế.

Bắt đầu ngay. Không hỏi lại những gì repo/checkpoint/spec/plan đã trả lời. Nếu gặp blocker của một candidate, cô lập candidate đó, ghi blocker chính xác và tiếp tục các candidate độc lập còn lại. Không hạ security/authority/test gates để ép hoàn tất.
```
