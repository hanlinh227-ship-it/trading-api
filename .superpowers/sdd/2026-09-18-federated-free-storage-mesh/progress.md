# SDD ledger — plan: docs/superpowers/plans/2026-09-18-federated-free-storage-mesh.md

Spec (binding): docs/superpowers/specs/2026-09-18-federated-free-storage-mesh-design.md
Controller: session_01K2S3Pd (sole controller; implementers may not spawn subagents)
Branch: claude/magical-euler-uu98r8 — PR #442 — NO MERGE, NO FORCE PUSH

BASE SHA at start: 86157cad (PR #442 head, CI green after the 4.17.0 digest refresh)

## Ruling 001 — no isolated worktree
Decision: work in the existing checkout, not a separate worktree.
Reason: the directive fixes the branch as claude/magical-euler-uu98r8, and git will not
check the same branch out in two worktrees. An isolated worktree would therefore need a
different branch, which contradicts the branch instruction and the no-merge rule.
Cost if wrong: less isolation from the concurrent session on this branch. Mitigated by
fetching and reconciling before each task, as the directive requires, and never force
pushing.

## Ruling 002 — pinned files get a digest refresh, not a release cut
AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml (Task 1) is sha256-pinned by release
manifest 4.17.0. Established earlier this session on policy.yaml: recomputing a content
digest so the manifest stops asserting a false hash is bookkeeping, and the precedent is
1fea0c0b. The promotion judgement (promotion.validated, known_good) is the operator's and
is never touched. Refresh before each push so the branch does not sit red.

## Ruling 003 — Supabase and live providers are not provisioned
No Supabase project or table is created; no provider account is activated; no paid service
is enabled. Adapters, contracts and tests only. External provisioning is a human action.

## Task log

| task | status | base sha | implementer | tests | review | fix rounds | notes |
|------|--------|----------|-------------|-------|--------|-----------|-------|
| 1 | done | 22275f17 | subagent | 149 green | independent review: 2 findings | 1 (1f97bbd7) | schemas + policy + mesh_validator. Review found the manifest never consulted the registry it validated against, and a policy/validator disagreement on PUBLIC. Both fixed; policy.yaml now states the rule the validator applies (`admitted_verified_only`), not "anywhere external". |
| 2 | committed, review pending | 1f97bbd7 | subagent | 49 focused / 198 module-wide green | pending | - | `AI_SKILL_LIBRARY/v4/storage/manifest.py` + tests. Content-addressed `obj_<sha256>`; unknown fields rejected by a `**unknown` catch-all rather than a denylist of six; `ENCRYPTION_IMPLEMENTED_HERE = False`. Verified by hand: the six named credential fields and an unlisted seventh all rejected, path-shaped and `obj_`-shaped names rejected. |

## Ruling 004 — the workflow budget is not mine to raise
Task-adjacent, recorded here because it gated this commit.

`.github/workflows/deepseek-lane-preflight.yml` (06af8f17) took the repository's active
workflow count from 119 to 120, failing `assertLess(len(active), 120)` in both
`test_retired_workflow_archive_image_v2.py` and `test_v4_consolidation.py`.

Three ways out, and only one is honest:
- Raise the cap to 121. Refused. Fitting my own addition by moving the gate that measures
  it is the failure mode the gate exists to catch, and the concurrent session already set
  this precedent on this branch.
- Retire an existing workflow. Attempted and abandoned. `legion-task1-green.yml` looked
  spent, but `git ls-remote` shows its target branch `github-brain-v4-afmm-implementation2`
  still exists, so it can still fire; retiring a workflow that can still be triggered is a
  behaviour change disguised as cleanup. `ai-brain-v4-release.yml` was rejected as a host:
  it holds `contents: write` and runs on every PR, which is the wrong blast radius for a
  preflight probe.
- Stand the file down. Taken. `git mv` to
  `docs/ai-coengineer/pending/deepseek-lane-preflight.yml.proposed`. Active count back to
  119, CI budget green, and the file is one `git mv` from live once a slot exists.

The slot decision belongs to the repository owner: either free a workflow, or approve the
`.proposed` file into `.github/workflows/`. `DEEPSEEK_CODING_LANE_READY` stays pending
dispatch until then. `.github/scripts/deepseek_preflight_report.py` remains in place — it
is an allowlist reporter with no trigger of its own and costs no budget.

## Task 2 review outcome — the same hole, in a new place

The independent review returned 4 findings, 1 BLOCKER. I reproduced findings 1 and 2
myself before dispatching the fix, and both are real.

**The finding that matters:** `encryption.nonce`, `encryption.tag` and
`encryption.key_rotation_generation` are admitted into the manifest and never validated —
no type, no length, no pattern. `_closed_mapping` whitelists the key *names*;
`_check_encryption` validates `algorithm`, `scheme_version` and `key_ref` and stops. The
schema bounds all three. So the module emits documents the checked-in schema rejects,
which falsifies its own central claim, and it does so in three unbounded string slots
sitting directly beside `key_ref` — the field in the mesh most likely to be handed key
material is the one least able to refuse it.

Reproduced and accepted today: a 2048-char nonce; `nonce="API_KEY=sk-live-..."` (the
credential scan's `sk-` pattern wants 32 unbroken alphanumerics and `sk-live-` breaks on
the hyphen); `tag` holding a 44-char wrapped DEK; `key_rotation_generation` as a string
where the schema demands an integer. Separately, `_EVIDENCE_REF_RE`'s second alternative
is unbounded against a schema `maxLength: 200`, and carries 2KB of opaque material into a
manifest on both `source_provenance` and `verification`.

**This is the second time this class of hole has got past me on this branch.** In the
Learning Fabric it was an allowed-but-unbounded field; here it is an allowed-but-unchecked
one. Both times I verified the named private fields and the unknown-field rejection,
declared privacy structural, and did not check what an *allowed* field could carry. The
unknown-field catch-all is the part I was proud of and it is genuinely sound — the review
could not find a key-name route in. It simply is not the question. The rule I should have
been applying: **a closed vocabulary bounds which fields exist, not what fits inside
them**, and the module must never be looser than the schema it claims to mirror.

The fix round therefore also adds a test that walks `$defs.encryption_metadata` from the
schema file and asserts every property has a model-level check, so the next field added
cannot slip through the same way. `test_every_shape_the_model_can_emit_validates`
enumerated eight hand-picked shapes and never populated these three — which is precisely
why 49/49 was green and wrong.

Findings 3 and 4 (shallow freeze leaving nested containers aliased; direct dataclass
construction bypassing content addressing; `$` anchors admitting a trailing newline) are
in the same fix round.

## Task 2 fix round — and a test written to fit the fix

All four findings fixed; 49 -> 72 tests green, plus 135 Task 1 contract tests unaffected.
The structural remedy is the part that matters: `_ENCRYPTION_FIELD_CHECKS` now dispatches
over *every* admitted key instead of checking three by hand, a test walks
`$defs.encryption_metadata` and fails if any property lacks a model-level check, and
another asserts the emitted corpus actually populates every property the schema defines —
because a shape nobody emits is a field nobody checks, which is exactly why 49/49 was green
and wrong. Every anchored pattern moved from `$` to `\Z` (all seven used `$`, admitting a
trailing newline into a 69-character object_id), with a test that walks `vars(manifest)`
so a future one cannot regress.

**I verified by re-running the reviewer's inputs myself rather than trusting the report,
and one was still accepted.** The implementer's test used
`wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY1` — the reviewer's AWS-secret example with the
hyphens *stripped* — which is one 39-character run that trips the new 31-character bound.
The reviewer's actual input was `wJalrXUtnFEMI-K7MDENG-bPxRfiCYEXAMPLEKEY`, and `-` is a
separator, so it splits into three short runs and walked straight through. That is a test
written to fit the fix rather than the report: the same failure mode as the eight
hand-picked shapes, one level up.

Fixed by me directly (the token-efficiency order discourages a further delegated round for
something this small). A length bound cannot see a secret split on `-` or `/`; the
alphabet can. Every legitimate evidence reference in this repository is built from words —
`CHECKPOINTS`, `evidence`, `r2_probe`, `WAVE0_CAPABILITY_SMOLLM2_360M` — and a word
segment is upper case or lower case, not both at once. Base64 key material mixes them
freely. So a segment of 16+ characters containing both cases is refused. Digits are
deliberately not required: `bPxRfiCYEXAMPLEKEY` has none, and requiring them let it
through on the first attempt.

Measured before accepting it: across all 30 real `evidence_ref` values in the repository,
the new rule causes **zero** refusals, and both hyphen- and slash-separated forms of the
reviewer's input are now refused. The test carries the reviewer's real strings.

### Residual, stated rather than closed
A determined author can still split a secret into word-like chunks shorter than 16
characters, or of a single case, and no shape rule will catch that. `evidence_ref` is a
human-authored pointer bounded at 200 characters; the shape rules raise the cost, they do
not make it impossible. The other three residuals the implementer reported honestly:
encryption bounds are mirrored from the schema rather than loaded (a test asserts equality,
so drift fails the suite); Finding 3's aliasing half is guarded rather than reproduced,
because with non-scalars rejected there is nothing left to alias; and Finding 4a is a
thread-local construction guard, not re-hashing — which means `dataclasses.replace` on a
StorageObject now raises, and Task 3 needs an explicit method if it wants a re-placed copy.

| 2 | done | 1f97bbd7 | subagent | 72 focused / 207 with contracts | review: 4 findings, 1 BLOCKER | 1 (98048541) + 1 by controller | See "Task 2 fix round" above. |
| 3 | committed, review pending | 98048541 | subagent | 161 focused / 368 with Tasks 1-2 | pending | - | capacity.py + placement.py. Gates, not weights. |

## Ruling 005 — the plan's illustrative row is wrong, and I am endorsing the contradiction
The plan's Task 3 sample asserts
`provider_state({"quota_used":79,"quota_total":100,"health":"HEALTHY","write_enabled":True}) == "HEALTHY"`.
The implementer returns `QUARANTINED` for that row and said so plainly rather than quietly
matching the plan. I verified it and I am keeping the contradiction.

That row declares no externality, no free status, no spillover answer and no probe. Calling
it HEALTHY is precisely the optimistic pass `UNKNOWN_COST_STATE=QUARANTINE` exists to
forbid: an incomplete row would be admitted as writable because nothing in it said "no".
The snippet was illustrating the 80% threshold, not specifying admission, and the threshold
is asserted separately on complete rows. A plan is not more authoritative than the spec it
implements, and the spec is binding here.

Same reasoning for the plan's Step-3 ranking prose ("criticality fit, headroom, tier
preference, health, then latency"), which puts headroom above health and tier preference
above health. The checked-in `policy.yaml placement_order` — privacy, integrity, free-only,
**provider_health**, **quota_headroom**, object_size, **access_frequency**, retention,
latency, backend — says otherwise, and the spec agrees with the policy. Implementation
follows the policy; two tests pin that order.

## Controller verification of Task 3 (not taken on the implementer's word)
My first three probe attempts returned "nothing is eligible" — because my hand-built
fixtures were incomplete, and later because I wrote `quota_total_bytes` where the schema
says `quota_total`. Both times the module was refusing undeclared or missing fields, which
is the fail-closed rule working correctly; my probes proved nothing until I used the real
field names. Worth recording because "everything returned None" looked at first like a
broken module and was in fact the module being right about my input.

With correct fixtures: a 100-byte provider at 70% full that admits INTERNAL beats a
10^9-byte provider with `health: FREE` that does not, **in both input orders**, and despite
losing the lexicographic tie-break — capacity does not override privacy. LOCAL_ONLY is
placed nowhere against an external row named `local_r2`, an `external: None` row and an
`external: "false"` row, and lands on owned storage only. Candidate order is identical
across rotation and reversal; inputs are not mutated. A 400-character AWS-key-shaped needle
fed through `provider_id` and `retention_policy_class` does not appear anywhere in the
report. `AUTHORITY` is False in both modules; the shipped registry still admits nothing
external (0 of 9 rows), which is consistent with the finding already recorded: the mesh has
no external writable home today.

### Carried forward, not closed
- Latency (placement order position 9) is unimplemented: no latency evidence exists in the
  provider contract. Named `LATENCY_EVIDENCE_AVAILABLE = False` rather than faked.
- Retention (position 8) is string equality only; no provider declares one today.
- No probe-staleness rule: a `last_probe_at` from 2019 is accepted. The spec sets no TTL
  and the implementer did not invent one. Absent/null/malformed timestamps *are* rejected.
- The emergency reserve's meaning (5% of what?) is an interpretation: the last 5% below the
  hard limit is visible only to CRITICAL objects, never a door past the hard limit.
- `AUTHORITY_FLAGS` is a tuple in `__init__.py` and a name->False mapping in the new
  modules. Deliberate, so flags are denied by value; flagged as an inconsistency to unify.
- **Blocks a later task:** `select_primary` returns a provider, but with direct construction
  and `dataclasses.replace` both refused on StorageObject there is no way to write that
  answer back into an object's `primary_backend`. Task 4/5 needs an explicit
  `with_placement(...)` on the model that preserves `object_id` and `content_sha256`
  exactly — re-placement must not change identity, because identity is the content.
- Replication obligations (spec S8: CRITICAL >=2 independent copies) are enforced nowhere
  yet. `select_primary` returning a provider does NOT mean a CRITICAL object's replication
  requirement is satisfiable. That is Task 5.

## Task 3 review — the same class, a third time, and the guard that should end it

The independent review returned 10 findings, 5 MAJOR. Findings 1-4 were all one defect:
**an allowed field whose value nothing bounds.** I verified every one before dispatching
the fix. A 2KB credential rode through `adapter_type` on every row. A registry row could
declare `authority: true` and all eight authority flags true and still be admitted. An
owned row's `free_status_evidence` was never closed at all, because it was only checked
inside the external-only cost path. A CONFIDENTIAL object carrying 2052 characters in
`encryption.nonce` was **placed on an external backend**. `_object_is_placeable` was true
for a record with no `object_id` and no `content_sha256`. A malformed `max_object_bytes`
made the size gate vanish rather than fail closed. And `bytes` is a `collections.abc
.Sequence`, so `privacy_classes_allowed=b"PUBLIC"` crashed `placement_report` with a
TypeError - failing open with a crash, against Spec S14's degrade-don't-crash rule.

Three occurrences now: Learning Fabric (unbounded field), Task 2 (admitted-but-unchecked
encryption metadata), Task 3 (nearly every allowed field). Each time the closed vocabulary
was sound and each time it was the wrong question. **A closed key set bounds which fields
exist, not what fits inside them.**

### The fix is the guard, not the patches
Both modules now carry a table with one checker per schema property -
`capacity.PROVIDER_VALUE_CHECKS` (29 entries) and `placement.MANIFEST_VALUE_CHECKS` (24) -
and every declared field's value runs through its entry. Four structural tests drive the
field list from the schema on disk: the table's key set must equal the schema's property
set, and a hostile-value sweep asserts the module is never looser than the schema that
`jsonschema` enforces. 166 provider combinations and 189 manifest combinations were RED.
Each sweep is paired with a "a schema-valid record is not gratuitously refused" test, so
"quarantine everything" cannot pass.

The weaker duplicate checkers were deleted, not left beside the new ones: both modules now
bind manifest.py's checkers at a single commented import block. That is the structural
answer to a third copy drifting from the first two.

### Controller verification
All ten reproductions refused; valid records still admitted (external HEALTHY, owned
HEALTHY, object placed on both); schema property sets equal the table key sets exactly
(29/29, 24/24); and removing one checker makes the guard fire. 424 storage tests green.

### Judgement calls in the fix that a reader should know about
- **Finding 7 was answered by correcting the claim, not the code.** The review said "now=
  can only narrow" was false. Clamping to `min(now, wall clock)` would break the legitimate
  forward-narrowing an existing test asserts, and `max(...)` would make every result depend
  on the real clock. So `_clock` now states the true invariant: `now` is an evaluation
  instant, not a permission boundary, it does not only narrow, and it must come from the
  mesh and never from anything being judged. A test fails if the old claim returns. I
  prefer this to a clamp that would have made the docstring true by making the behaviour
  worse.
- **`REQUIRED_MANIFEST_FIELDS` is 10 of the schema's 15.** `primary_backend`,
  `replica_backends`, `created_at`, `lifecycle_state` and `reproducible` are validated when
  present but not required, because choosing the backends is what this module is *for* - a
  manifest handed to the engine before its placement exists legitimately has none.
- **`capacity.py` now imports `manifest.py`**, and through it `_check_backend` lazily reads
  `providers.yaml` via `mesh_validator`. The purity tests still pass because they scan each
  module's own source, but the module is no longer transitively file-free. Chosen over
  mirroring the registry-derived backend enum a fourth time. Flagged here because it is a
  real coupling the purity tests do not describe.

### Open, carried forward
- The manifest schema's cross-field `allOf` rules (LOCAL_ONLY implies local backends;
  CONFIDENTIAL external implies ciphertext at manifest level; supabase implies METADATA
  tier; CANONICAL/METADATA size ceiling) are not mirrored in `_object_is_placeable`.
  manifest.py enforces them at construction and placement's gates cover the
  placement-relevant half. **The structural sweep does not catch these**, because its
  hostile values never trip those conditionals - a known gap that closes honestly only with
  a record-level fuzz over field *combinations*, which is larger than this task.
- manifest.py should export the checkers the siblings now bind privately
  (`_check_bounded_int`, `_check_evidence_ref`, `_check_timestamp`, `_check_opaque_token`,
  `_check_key_ref`, `_check_backend`, and the shared patterns) under public names. Not done
  here: manifest.py was out of this fix's scope.

| 3 | done | 98048541 | subagent | 217 focused / 424 storage | review: 10 findings, 5 MAJOR | 1 (c8d45fe3) | Same allowed-but-unbounded class, third time. Fix is a schema-driven per-property checker table plus a structural guard. |
| 4 | committed UNREVIEWED snapshot | c8d45fe3 | subagent | 99 focused / 523 storage | not started | - | metadata.py, recovery.py, adapters/supabase_metadata.py, recovery_manifest.json. |

## Ruling 006 — committing Task 4 before hand-back, and saying so
I have refused several times this session to commit an implementer's work mid-flight,
because gating on "the tests look green" instead of on hand-back is an error I made
earlier and corrected. I am making an exception here and recording it rather than letting
it pass as routine.

The conditions that made the earlier refusals right do not hold: all seven files exist, the
full storage suite is green at 523 tests, ci_validate fails only on the two pre-existing
SIGILL crashes, and the modules reach no network. The conditions that argue for committing
do hold: this container is ephemeral, the work is only on disk, and the implementer has
been in self-review long enough that waiting is no longer obviously cheaper than the risk
of losing it.

What this commit is NOT: reviewed. No independent review has run on Task 4, and the
implementer has not handed back. If it hands back with changes I will commit again. The
independent review is still owed and is next.

## Controller spot-check of Task 4 (pre-review, not a substitute for one)
`AUTHORITY = False` in all three modules. The Supabase adapter constructs nothing at import
or at construction - it pattern-matches a project URL and refuses userinfo, so
`https://user:key@ref.supabase.co` cannot smuggle a credential through the URL. No project,
table or credential is created anywhere; provisioning remains an unauthorized human action.
`recovery_manifest.json` carries `caps`, `entry_count` and a `critical_object_index`, i.e.
it is bounded by construction rather than by convention.

`can_perform_destructive_lifecycle` requires the argument to *be* a `MetadataStore`, not
merely to answer `healthy() -> True`. My duck-typed fake returned False and looked like a
bug until I read it: an object that answers healthy has asserted nothing, and the gate
refuses it. **This is a deliberate divergence from the plan's own test sketch**, which
passes a `FakeMetadataStore(healthy=False)` and would therefore also fail closed for
`healthy=True`. The plan's snippet illustrates the intent; the implementation is stricter,
and stricter is the right direction for a gate whose job is to block deletion when the
record of what exists is uncertain. Same reasoning as Ruling 005.

Third time this session an incomplete fixture of my own looked like a module bug. Recording
it because the pattern is now a habit worth naming: when a fail-closed module refuses my
test input, the first hypothesis should be my input.

## Task 4 hand-back — arrived after the snapshot commit, and confirms it
The implementer handed back after I committed 46d7d746 and confirms that commit holds its
final state, including the last hardening pass. So Ruling 006's exception turned out to
have committed complete work rather than a half-finished tree. That is luck, not
vindication: I could not know it at the time, which is exactly why the commit says
unreviewed on its face.

### What I verified myself
Caps are real values, not decoration: 256 entries / 256 KiB / 256 characters per string.
The snapshot is a 13-field whitelist projection, not a copy. The adapter has no
provisioning method of any kind (`provision`/`create_table`/`ensure`/`migrate` all absent)
and imports no driver — no `psycopg`, no `supabase`, no `create_client`, no `cursor(`, no
`execute(`. The credential is not a constructor parameter and not an attribute; a
zero-argument `credential_provider` is called per request, so the key never rests on the
object.

`SNAPSHOT_ENCRYPTION_FIELDS = ("algorithm", "scheme_version", "key_ref")` — `nonce`, `tag`
and `key_rotation_generation` are excluded.

### Decision the owner should confirm: key_ref reaches GitHub
Three of six encryption fields reach the checkpoint, including `key_ref`. It is a
*reference* (`env://NAME`-shaped, re-validated on the way back in) and never key material,
and Spec S23 lists key references as a rebuild input — without it a CLIENT_SIDE_ENCRYPTED
object cannot be reconstructed as a valid record at all, because manifest requires
algorithm/scheme_version/key_ref together. The implementer stated the trade honestly and
asked. **I am not deciding this alone.** If the owner wants `key_ref` out of Git, the
consequence is that encrypted objects become unrebuildable from the snapshot alone.

### Other judgement calls, recorded not buried
- **Reads require health, which is stricter than Spec S18.** S18 permits "existing runtime
  reads may use cached manifest state where policy allows"; the implementer read that as a
  cache layer *above* the store rather than the store serving stale rows, so
  `get_manifest`/`list_manifests` raise `MetadataStoreUnavailable`. I agree: a store that
  answers from stale state while unhealthy is how a destructive action gets the wrong
  answer. If caching is wanted it belongs in a decorator.
- **A snapshot naming a backend no longer in providers.yaml fails the whole rebuild**, not
  just that entry. Fail-closed and correct per S19/S20 (a lost provider is marked
  OFFLINE/QUARANTINED, its registry row is not deleted), but it is an operational sharp
  edge worth knowing before a real disaster drill.
- `healthy()` catches `BaseException` including KeyboardInterrupt. Deliberate: it is an I/O
  boundary whose caller is a destructive-action gate. Ctrl-C during a probe yields False.
- `MAX_RECORD_BYTES`/`MAX_SNAPSHOT_BYTES` are unreachable by well-formed input today —
  defence in depth against a future carelessly-bounded field, and the code says so rather
  than implying they do work they do not.

### Two things carried into Task 5
1. `manifest.py` still needs `with_placement(...)` preserving `object_id` and
   `content_sha256`. Task 4 worked around it (`rebuild_manifest` has no bytes, so it builds
   validated dicts directly), but that means manifest-record construction now exists in
   **two** places. Task 5's rebalance path will hit this properly.
2. The shared working tree bit the implementer: it measured 274 failures / 23 errors that
   were my uncommitted in-flight Task 3 edits, not its own work. Two agents in one checkout
   is a real cost of Ruling 001 and worth naming.

### Fourth fixture false alarm
My probe could not instantiate the MetadataStore ABC (it requires private hooks), and
before that I checked `key_ref` at the wrong granularity — it lives inside the nested
`encryption` projection, not in ENTRY_FIELDS. Both times the module was right and my probe
was wrong. Noted for the fourth time this session.

## Task 4 review — the fourth occurrence, and the structural answer that is finally right

The review returned 8 findings, 2 BLOCKER. I reproduced both before dispatching.

`manifest_schema_version` was a declared snapshot field with **no validator of any kind** —
in `SNAPSHOT_FIELDS`, written by the exporter, present in the checked-in
`recovery_manifest.json`, skipped by `assert_snapshot_is_clean`, referenced by no test. Via
that one field: an AWS-secret-shaped string passed untouched; a snapshot declaring schema
version 99 was certified clean while the rebuild stamped records version 1; and **177 KB of
arbitrary attacker-chosen keys and values was certified clean in the file GitHub carries**
(181300 bytes smuggled, document 183113 of a 262144 cap). The per-string cap of 256 chars
does not stop bulk because it bounds each string, not how many there are, so
`MAX_SNAPSHOT_ENTRIES` was routed around by not using an entry at all. Spec S6/S32 forbid
exactly this.

**Why it happened is the second blocker, and it is the interesting one.** `metadata.py` did
build Task 3's schema-driven guard, correctly - the reviewer's fuzz found nothing in it.
`recovery.py` did not: three hand-listed field tuples and ~110 lines of `if`, with neither
`SNAPSHOT_FIELDS` nor `PROVIDER_RECORD_FIELDS` referenced by a single test. One half of one
task used the guard and held; the other half skipped it and produced the fourth occurrence
of this class on this branch.

### The fix is stronger than Task 3's, and the difference matters
Task 3 kept a field tuple beside a checker table and asserted they were equal. Task 4's fix
**derives the tuple from the table**: `SNAPSHOT_FIELDS = tuple(SNAPSHOT_VALUE_CHECKS)`,
`ENTRY_FIELDS = tuple(ENTRY_VALUE_CHECKS)`, `PROVIDER_RECORD_FIELDS` likewise. An
allowed-but-unvalidated field is no longer something a test catches; it is something the
code cannot express. That is the right shape, and Task 3's parallel-tuple version should
eventually follow it.

Plus real bounds where the per-string cap was not enough: `MAX_SNAPSHOT_FIELD_BYTES = 4096`
on every non-entry field, `MAX_SNAPSHOT_ENTRY_BYTES = 2048` per entry and provider record,
`MAX_SNAPSHOT_DEPTH = 8`. `entries` and `critical_object_index` are exempt from the byte
budget because they are bounded by element count x per-element bound instead, which is
documented rather than implicit.

### The other finding that mattered
`get_manifest(object_id)` never checked the returned record was *for* that object. A
substituted row was accepted: asked about a CRITICAL/`reproducible=False` object, answered
with an EPHEMERAL/`reproducible=True` one. That is a fail-**open** on precisely the
criticality read that `can_perform_destructive_lifecycle` exists to gate, and it reproduced
through the base class, so it was not an adapter defect. Fixed, along with
`list_manifests` silently returning duplicate object ids.

`assert_snapshot_is_clean` also certified snapshots documenting five policy violations
(LOCAL_ONLY on an external backend, REPRODUCIBLE contradiction, METADATA tier holding 1 TB,
supabase as a HOT bulk backend, CONFIDENTIAL plaintext external). Now shares one copy of
the rules via `metadata.check_placement_cross_field_rules` rather than growing a second.

### Controller verification
All three exploits refused. No non-entry snapshot field accepts bulk. The cross-field and
critical-index cases refused. `SNAPSHOT_FIELDS`/`ENTRY_FIELDS` confirmed derived from their
tables, not parallel to them. 554 storage tests green; ci_validate fails only on the two
pre-existing SIGILL crashes.

### Still open, stated not buried
- **EXPLOIT1 is half-closed.** `manifest_schema_version` is a constant now and can hold no
  string at all, but `manifest.assert_no_credential_material` still has no pattern for an
  AWS *secret* access key or a generic opaque base64 run - it covers AKIA ids, GitHub,
  Slack, JWT, bearer, `sk-`. `manifest.py` was out of scope for this fix. **Any future
  string-valued snapshot field inherits that gap.** Follow-up task owed against manifest.py,
  which should also export the checkers its siblings currently bind privately.
- `last_successful_export_ref` accepts a scheme-qualified reference such as
  `https://evil.example.com/x`, because it reuses the lane's shared `_check_evidence_ref`
  rather than growing a second stricter copy. It is documentation read by nothing; the
  pointer fields a rebuild actually reads keep the strict `_POINTER_RE`. Reusing the shared
  rule over duplicating it is the right call and the residual is recorded.
- Two pre-existing adapter tests were edited. Neither was weakened: both now use the
  documented `manifest` column envelope, which is the F7 fix landing rather than a check
  being relaxed.
