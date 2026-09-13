# Plain Language Output Design

Status: approved design, implementation not started
Date: 2026-09-13
Target: GITHUB_BRAIN_V4

## Goal

Keep all Brain reasoning, routing, validation, authority, security, tools, project rules, and technical processing fully intact, while making the final answer easy to understand for a person with no technical background.

The Brain may continue using precise machine identifiers internally. Those identifiers are implementation details and must not be exposed by default in normal user-facing answers.

## Core principle

The system has two language layers:

1. Internal language: precise technical names, machine identifiers, contracts, routing metadata, validators, and implementation details.
2. User language: simple Vietnamese, short explanations, familiar words, and easy display names.

The user-facing layer must never weaken, skip, or simplify the underlying reasoning itself. It only changes how the verified result is explained.

## User-facing naming rules

For normal answers to the user:

- Do not show underscore characters in names.
- Prefer short Vietnamese names that describe what something does.
- Prefer everyday words over software or AI jargon.
- Do not expose internal skill identifiers unless the user explicitly asks for technical details.
- If an exact machine identifier is genuinely required for debugging or editing a system file, label it clearly as an internal system code and keep it outside ordinary explanatory prose.
- New user-facing names must be understandable without prior technical knowledge.

Examples:

- Internal skill for building skills -> display as `Tạo kỹ năng`
- Internal skill for evaluating skills -> display as `Kiểm tra kỹ năng`
- Internal quantitative audit skill -> display as `Kiểm tra chiến lược`
- Internal 3D asset validation skill -> display as `Kiểm tra mô hình 3D`
- Internal risk skill -> display as `Quản lý rủi ro`
- Internal live-data validation skill -> display as `Kiểm tra dữ liệu trực tiếp`
- Internal router -> display as `Bộ chọn cách xử lý`

These display names are presentation aliases only. They must not replace canonical internal routing identifiers.

## Plain-language answer rules

The final answer should normally:

- Start with the direct answer.
- Explain the result before explaining the system behind it.
- Use short sentences and familiar words.
- Explain one idea at a time.
- Avoid unexplained abbreviations.
- Replace technical jargon with a plain-language equivalent when possible.
- When a technical term is necessary, explain it immediately in simple words.
- Prefer practical consequences: what it means, what happens next, what the user should do.
- Avoid exposing implementation details that do not help the user decide or act.

The answer may still be detailed when the task requires detail, but the wording must remain accessible.

## Accuracy guardrails

Plain-language conversion must not:

- Change numerical values, dates, prices, limits, risk values, file names, command text, legal language, or other exact facts.
- Remove important warnings, uncertainty, limitations, or safety conditions.
- Turn an estimate into a certainty.
- Hide a failed verification or degraded runtime state.
- Rewrite code, commands, API fields, configuration keys, or exact machine tokens when the user explicitly needs those exact values.
- Change the meaning of a technical conclusion merely to make it sound simpler.

When exact technical material must be shown, explain it in plain language around the exact block instead of altering the exact block.

## Response pipeline

The intended request path remains:

request
-> task router
-> runtime profile
-> project authority when required
-> primary skill
-> execution capsule
-> bounded context and tools
-> execute
-> verify
-> response quality gate
-> plain-language presentation
-> answer

The new presentation step is downstream of reasoning and verification. It has no routing authority, tool authority, trading authority, security authority, or permission-expansion capability.

## Scope

This change applies to normal user-facing Brain answers across all domains, including:

- general questions
- coding
- trading explanations
- design
- 2D and 3D work
- Adobe workflows
- prompts and scripts
- academic work
- documents and data
- business

It does not require renaming existing internal skill IDs, file names, API fields, or runtime contracts.

## Internal compatibility

Existing internal identifiers must remain unchanged unless a separate migration is explicitly designed and tested. This avoids breaking:

- routing
- manifests
- tests
- release hashes
- retrieval index references
- execution capsules
- Cloudflare runtime contracts
- historical checkpoints

The system should instead maintain a presentation mapping from internal identifiers to easy display names.

## Suggested implementation shape

Use a small stable presentation policy rather than changing every skill independently.

Proposed components:

1. A stable plain-language policy file containing user-facing wording rules.
2. A display-name mapping for canonical skills and selected system components.
3. A response-quality check that rejects ordinary user-facing output containing internal underscore-style identifiers when a plain display name exists.
4. Tests covering simple-language conversion, exact-value preservation, safety-warning preservation, and technical-token exceptions.
5. Skill Gateway integration that applies the presentation policy after reasoning and verification, not before.

## Default behavior

For this user, plain-language mode is the default for normal answers.

Default output level:

- Assume no prior technical knowledge.
- Do not make the answer childish or patronizing.
- Keep important detail, but explain it plainly.
- Use technical depth internally even when the final wording is simple.

## Example

Internal result:

`quant validation found likely lookahead bias and insufficient out-of-sample evidence`

User-facing result:

`Cách kiểm tra này có dấu hiệu dùng thông tin mà lúc giao dịch thật chưa thể biết trước. Vì vậy kết quả đang đẹp hơn thực tế. Chưa nên tin tỷ lệ thắng hiện tại cho đến khi kiểm tra lại bằng dữ liệu chưa từng dùng để tối ưu.`

The technical conclusion stays the same; only the explanation becomes easier to understand.

## Verification requirements

Implementation must follow the repository engineering contract:

RED -> minimum GREEN -> regression suite -> validators -> CI -> merge -> post-merge production verification.

Required tests include:

- A normal answer does not expose mapped internal underscore-style names.
- A user-facing name contains no underscore.
- A simple-language answer preserves exact numbers and dates.
- Safety and uncertainty language survives simplification.
- Code blocks and exact machine fields remain unchanged when explicitly required.
- Trading permissions and project authority remain unchanged.
- Existing routing results remain unchanged.
- Skill Gateway still compiles all skills and capsules.
- FAST external routing calls remain zero.

## Non-goals

This change does not:

- reduce reasoning depth;
- remove verification;
- replace canonical skill identifiers;
- change trading execution authority;
- add a second router;
- add a parallel reasoning system;
- make external services mandatory;
- require local installation.

## Success criteria

The change is successful when:

- Brain reasoning and routing stay technically identical for equivalent requests;
- normal answers are understandable to a nontechnical user;
- user-visible feature and skill names avoid underscores;
- easy names describe function rather than implementation;
- exact facts and warnings are preserved;
- tests, validators, release checks, Skill Gateway CI, zero-local runtime checks, and production route checks all pass.
