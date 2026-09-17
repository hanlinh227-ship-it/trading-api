# Persistent Brain Entry / Always-On Chat Bridge — Design

Date: 2026-09-17
Status: Proposed
Base: `c5ad9112de60223ef9e1175bb5bcc1fcdfdf163f`

## 1. Problem

The Brain already has a production Universal Entry, client authentication, memory/context services, and Image V3 execution. The remaining continuity problem is at the client boundary: a ChatGPT/Claude session can exhaust its context or be replaced, and the next session has no authoritative project handoff unless the user manually re-explains it.

The target is to make chat sessions disposable clients. Project continuity, current phase, blockers, pending job references, and next actions must live in the Brain backend so a newly authenticated client can bootstrap and resume without relying on the previous chat transcript.

This design does **not** make an arbitrary unconnected ChatGPT conversation magically gain a private tool. A ChatGPT/Claude client must have the Brain connector/action available and authenticated. The backend will make that connection persistent and resumable once the client integration is present; any one-time account-level connector authorization remains a user-controlled platform action.

## 2. Goals

- A fresh authenticated ChatGPT/Claude client can discover the current Brain revision, current project, latest handoff, subsystem capabilities, and resumable job references in one bootstrap request.
- Project state is isolated per project and cannot be overwritten by another project.
- Concurrent agents cannot silently overwrite a newer handoff.
- Existing Image V3 endpoints remain the canonical image execution path.
- The bridge must not widen trading authority, provider permissions, paid fallbacks, or privacy policy.
- No session transcript is required as a source of truth.
- No new GitHub workflow is required; existing Universal Brain and exact-main production gates are extended.

## 3. Existing Foundations Reused

The implementation will extend the existing Universal Fabric rather than create a parallel control plane:

- `universal-entry-handler.js`: authenticated Universal Brain entry.
- `universal-auth.js`: per-client bearer auth and scoped permissions.
- `universal-state.js`: namespaced non-authoritative shared state helpers.
- `memory-context-handler.js`: existing explicit context retrieval with fail-closed shared-state behavior.
- `/brain/image/v3/*`: canonical Image Agent job/status/retry/assets routes.
- Existing client secrets: ChatGPT, Claude, Gemini, Evergreen.
- Existing exact-main deploy, Universal Brain canary, and Image production smoke workflows.

The Brain remains the source of truth for routing/capabilities; the new project-continuity store is state, not reasoning authority.

## 4. Alternatives Considered

### A. Extend Universal KV only

Store handoffs in `BRAIN_STATE`/namespaced KV and expose bootstrap APIs.

Pros: smallest patch, reuses current store.  
Cons: KV does not provide the strong compare-and-swap semantics needed to prevent two agents from silently overwriting each other. Not chosen for the canonical mutable project record.

### B. Dedicated `BrainProjectState` Durable Object — **chosen**

One Durable Object identity per normalized `project_id`; it owns the canonical mutable project snapshot and version.

Pros: strong serialization, project isolation, deterministic optimistic concurrency, natural place for bounded handoff history. Fits existing Worker Durable Object pattern already used by Image jobs.  
Cons: one new binding/class/migration and deploy-wiring tests.

### C. Store project continuity in memory records

Represent project state as long-term memories.

Pros: uses existing memory pipeline.  
Cons: project execution state is not semantic memory; promotion/review lifecycle and retrieval ranking are the wrong consistency model. Rejected.

## 5. Architecture

```text
ChatGPT / Claude / Gemini / other authenticated client
                  |
                  v
        Universal Brain Entry/Auth
                  |
           /brain/bootstrap
                  |
       BrainProjectState Durable Object
          |                    |
          | pointers           | latest handoff
          v                    v
 existing subsystem       project snapshot
 canonical APIs
 (Image V3, etc.)
```

The bootstrap layer does not proxy all subsystem execution. It tells the client which canonical subsystem routes and current capabilities are valid. Image rendering continues through `/brain/image/v3/jobs`, `/status`, `/retry`, `/assets`, etc.

## 6. Canonical Project State

Each project snapshot is bounded and versioned:

```json
{
  "project_id": "image-agent",
  "schema_version": 1,
  "version": 12,
  "active_phase": "production-operation",
  "status": "active",
  "latest_handoff": {
    "summary": "...",
    "blockers": [],
    "next_actions": [],
    "refs": []
  },
  "job_refs": [
    {"subsystem":"image-v3","job_id":"...","state":"running"}
  ],
  "runtime_revision": "<sha>",
  "updated_at": "<iso8601>",
  "updated_by": "chatgpt"
}
```

Rules:

- `project_id`, phase, status, summary, blockers, next actions, refs, and job refs are length/count bounded.
- No credentials, raw secret values, private keys, provider tokens, or arbitrary binary assets are stored.
- Job state is **not duplicated**. `job_refs` only point to canonical subsystem state (for example Image Logical Job Durable Objects).
- A short bounded handoff history may be retained for recovery/audit, but `latest_handoff` is the resume source.
- Project IDs are normalized and cannot contain traversal/control characters.

## 7. Concurrency Model

Writes use optimistic concurrency:

- Reader receives `version=N`.
- Writer must supply `expected_version=N`.
- Durable Object serializes requests.
- If current version changed, return HTTP 409 `project_state_conflict` with the current version; never silently overwrite.
- Initial creation requires `expected_version=0`.

This is the core protection against ChatGPT, Claude, and another agent updating the same project simultaneously.

## 8. API Contract

### `GET /brain/bootstrap?project_id=<id>`

Authenticated read endpoint. Returns:

- client identity (non-secret ID only),
- production runtime revision/release,
- requested project snapshot or explicit `project_not_initialized`,
- current Universal Brain capabilities,
- canonical subsystem route descriptors,
- resumable `job_refs`,
- explicit `next_action` derived only from stored handoff/capability state, not invented reasoning.

No secret material is returned.

### `GET /brain/project/state?project_id=<id>`

Returns the canonical project snapshot.

### `PUT /brain/project/state`

Authenticated state update. Requires `project_id`, `expected_version`, and the complete bounded handoff/state update allowed by the schema. Returns the new version.

A separate append-only "chat transcript" endpoint is intentionally not added. The backend stores project continuity, not full conversations.

## 9. Authentication and Scopes

Reuse `universal-auth.js` and generated adapter principals.

Add least-privilege scopes:

- `brain.bootstrap` — read bootstrap snapshot.
- `brain.read_project_state` — read a project state.
- `brain.write_project_state` — update a project handoff/state.

User adapters (ChatGPT/Claude/Gemini) may receive these scopes in the canonical adapter config. Internal principals keep their existing duties. No route accepts a client-selected identity without valid bearer auth.

Image execution remains protected by its existing image token/auth contract; this design does not weaken or merge those credentials into project-state responses.

## 10. Project Isolation

- Durable Object ID is derived only from normalized `project_id`.
- A request can read/write only the project explicitly named in that request.
- No automatic cross-project context merge.
- Bootstrap returns one requested project at a time.
- Project state never changes trading execution authority or runtime switches.

This allows Image Agent, trading, design, and future projects to coexist without contaminating one another.

## 11. New-Session Resume Flow

1. A connected client opens with no prior transcript context.
2. Client calls `/brain/bootstrap?project_id=image-agent`.
3. Brain authenticates the client and returns latest handoff + capability/route descriptors + job refs.
4. Client resumes the requested work from that backend snapshot.
5. If the user asks for an image render, client calls the existing Image V3 canonical route; it does not emulate the renderer inside bootstrap.
6. The client stores only the resulting job reference and updated handoff through the project-state API.
7. Another independent connected session can repeat step 2 and observe the new version/job reference.

## 12. Capability Honesty

Bootstrap must not claim a subsystem is usable merely because code exists. It may expose:

- canonical route names,
- production revision,
- the latest already-verified capability snapshot or an explicit unknown/unavailable state.

It must not turn an unavailable runtime into AVAILABLE, fake visual critic verification, or turn a wait state into success.

Image FREE_ONLY, privacy, reference-safe routing, and paid-fallback rules remain owned by Image V3.

## 13. Failure Behavior

- Missing project state: 404 `project_not_initialized` (bootstrap may still return runtime/capability metadata with project initialized=false).
- Shared project Durable Object unavailable: 503 `project_state_unavailable`.
- Stale write: 409 `project_state_conflict`.
- Invalid/bounds-violating payload: 400.
- Missing scope/auth: existing 401/403 contract.
- No fallback to `TRADING_STATE` for canonical project continuity.
- No paid service fallback and no local-runtime requirement introduced.

## 14. Tests / Acceptance Criteria

TDD acceptance must prove:

1. Fresh ChatGPT-like client A authenticates, initializes/updates `image-agent`, then receives version N.
2. Independent Claude-like client B with no transcript calls bootstrap and receives exactly the latest project handoff/version and job reference.
3. A stale client update with `expected_version=N-1` gets 409 and cannot overwrite N.
4. `image-agent` and another project remain isolated.
5. Secrets/authorization headers never appear in bootstrap/project responses or persisted records.
6. Existing Universal routing tests, memory tests, Image tests, and trading authority tests remain green.
7. Image execution remains `/brain/image/v3/*`; project continuity only stores pointers.
8. Exact-main deployment and existing production Universal Brain canary pass after the change.
9. A production bootstrap smoke demonstrates persistence across two separately authenticated requests/sessions.

## 15. Deployment Strategy

- Add `BrainProjectState` Durable Object class and binding/migration through the existing Wrangler generation path.
- Add bootstrap/project handlers before generic Skill Gateway routing in `index.js`.
- Extend the existing Universal Fabric test suite and existing deploy/canary workflow; do not add a new workflow unless technically unavoidable.
- Deploy through existing exact-main gate with rollback protection.

## 16. Platform Boundary / Definition of Done

Backend DONE means:

- project continuity is production-persistent,
- fresh authenticated clients can bootstrap/resume without prior transcript context,
- concurrent agent writes are conflict-safe,
- canonical subsystem execution remains callable and referenced,
- production canary proves the above.

Full "any new ChatGPT chat can call Brain" additionally requires the user's ChatGPT account/client to have the Brain app/action/connector available and authorized. Repository code cannot force-install an account integration. If that integration is not already present, the final setup step is a one-time user-controlled connection/authorization; after that, session context exhaustion no longer loses backend project state.

## 17. Non-Goals

- No automatic trading actions or trading authority expansion.
- No storage of complete chat transcripts.
- No secret storage in project snapshots.
- No replacement of Memory lifecycle with project state.
- No duplicate image-render engine.
- No claim that an unconnected third-party chat client can access the private Brain without authentication/integration.
