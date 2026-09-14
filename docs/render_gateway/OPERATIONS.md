# Curious Beyond Render Gateway V2 — Operations

## Purpose

Render Gateway V2 lets ChatGPT act as the render desk from any device while Google Drive carries binary assets/artifacts and GitHub carries signed job state.

## Default policy

```text
QUALITY_DEFAULT = FLOW_GRADE
LOCAL_DRAFT_ALLOWED = TRUE
AUTO_PURCHASE = FALSE
PAID_RENDER_REQUIRES_APPROVAL = TRUE
USE_EXISTING_ENTITLEMENTS = TRUE
SILENT_QUALITY_DOWNGRADE = FALSE
```

The current GTX 1650 + SD1.5 path is `DRAFT_LOCAL` only. It must never satisfy `FLOW_GRADE` by itself.

## Binary plane

Google Drive root created for this project:

```text
CuriousBeyond_RenderGateway/
  projects/
    max-bus/
      masters/
        characters/
        objects/
        vehicles/
        backgrounds/
        style/
      jobs/
```

Large images, videos and ZIPs stay in Drive. GitHub stores only compact JSON metadata, SHA256 hashes and state.

## Control plane

Each immutable attempt uses:

```text
render_gateway/jobs/<project>/<job>/<attempt>/request.json
render_gateway/jobs/<project>/<job>/<attempt>/signed.json
render_gateway/jobs/<project>/<job>/<attempt>/result.json
```

Any change to a signed payload requires a new `attempt_id`.

## Provider routing

1. Validate requested quality tier.
2. Reject unauthorized/unavailable providers.
3. Reject providers below requested quality.
4. Enforce cost policy.
5. Prefer strongest qualifying automated provider.
6. Never silently fall back from `FLOW_GRADE` to `DRAFT_LOCAL`.

Google Flow adapters remain fail-closed until a supported authenticated connector/API path is actually bound. Unknown entitlement/quota remains `UNKNOWN`.

## Image quality pipeline

Master Lock -> Exact Scene Contract -> Composition Blueprint -> isolated regional reference conditioning -> render -> deterministic QA -> identity/semantic/finish QA -> repair/reroute -> packaging -> Drive return.

`FLOW_GRADE` cannot become `VERIFIED` if any mandatory semantic assertion lacks evidence.

## Video quality pipeline

Approved keyframe -> start/end frame anchors -> Motion Contract -> render -> deterministic frame sampling -> continuity QA -> packaging -> Drive return.

Without a semantic continuity verifier, video terminal QA is `HUMAN_REVIEW`, never `VERIFIED`.

## Second-device acceptance procedure

1. From a phone, laptop or ChatGPT session that is not the render PC, provide prompt + reference assets.
2. Stage binaries into the project Drive folders and record exact SHA256 in the render job.
3. Create a new immutable attempt in GitHub and sign it with the existing worker HMAC flow.
4. Router must select a provider that qualifies for the requested quality tier.
5. Execute render on an authorized provider/worker.
6. Run QA. A deliberately bad composition must be rejected.
7. Upload accepted artifacts to Drive and verify returned metadata/hash.
8. Return the Drive artifact card/file to the ChatGPT session.
9. Resume the same project from another device/session using Drive + GitHub state only.

## Current production gate

The architecture and fail-closed provider shells can be deployed without pretending Google Flow is automated. Real `FLOW_GRADE` rendering remains blocked until a supported authenticated quality provider is connected and preflight reports available.
