# Render Gateway V2 — Acceptance Checklist

A checkbox may be marked complete only with real evidence. Do not infer provider quota, entitlement, quality, or artifact existence.

- [ ] Second-device/session supplied prompt + references.
- [ ] Input assets stored in Google Drive.
- [ ] Every input has byte size + SHA256 recorded.
- [ ] GitHub request/signed/result paths use immutable attempt ID.
- [ ] HMAC signature verified by Worker.
- [ ] Worker/provider preflight reports actual availability.
- [ ] Selected provider qualifies for requested quality tier.
- [ ] Rejected alternate providers and reasons are recorded.
- [ ] `FLOW_GRADE` did not fall back to `DRAFT_LOCAL`.
- [ ] Multi-character scene uses isolated entity/reference bindings.
- [ ] Composition anchor is present for multi-entity scene.
- [ ] Deliberately bad composition is rejected by QA.
- [ ] Deliberately good composition passes all available evidence-backed gates.
- [ ] Missing semantic verifier produces `HUMAN_REVIEW`, not fabricated `VERIFIED`.
- [ ] Final artifact uploaded to Drive.
- [ ] Drive artifact metadata includes file ID, MIME, size and SHA256.
- [ ] ChatGPT receives an attachment/card or Drive fallback reference.
- [ ] Same project resumes from another session/device.
- [ ] Provider entitlement source is recorded truthfully.
- [ ] Provider quota is recorded truthfully or `UNKNOWN`.
- [ ] `AUTO_PURCHASE = FALSE` confirmed.
- [ ] No new paid credit purchase occurred without explicit user authorization.

## Hardware acceptance

Local Windows Worker evidence must include runner build, runtime build, GPU/engine capabilities and current branch. Local SD1.5/ComfyUI is accepted only for `DRAFT_LOCAL` unless a future tested local provider explicitly advertises a higher tier.

## FLOW_GRADE release gate

Production `FLOW_GRADE` is enabled only when at least one provider satisfies all of the following in a real preflight:

1. authenticated supported execution path;
2. capability matrix covers the job requirements;
3. entitlement/quota status is known enough to obey cost policy;
4. a real render completes;
5. QA provides sufficient evidence for acceptance;
6. artifact is returned through Drive/ChatGPT with verified integrity.
