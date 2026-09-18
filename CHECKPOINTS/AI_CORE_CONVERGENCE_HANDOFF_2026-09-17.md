# AI Core convergence — handoff, 2026-09-17

**Branch:** `claude/magical-euler-uu98r8` · **PR:** #442 (not merged) · **Trading:** not started

## The three facts, kept apart

| Flag | Value |
|---|---|
| `AI_CORE_DONE` | **true** |
| `AI_CORE_ALL_CAPABILITIES_COVERED` | **false** |
| `AI_CORE_ALL_EXACT_MODELS_AVAILABLE` | **false** |

`AI_CORE_DONE` means **nothing measurable is left undone**. It does not mean
everything is covered, and it does not mean the models that were asked for are
the ones running. Those are the other two lines, and they are false. Any
summary that collapses these into one word is wrong.

Verdicts are produced by `ai_core_convergence.py`, which reads the three wave
gates, the release gate and the fabric proofs rather than asserting anything
itself.

## Per-wave

| Wave | Kind | Closed | Covered | Exact models |
|---|---|---|---|---|
| 3 | candidate | true | n/a — closes on candidates | **false** |
| 4 | capability | true | 6/13 | **false** |
| 5 | capability | true | 15/16 | **false** |

### Wave 3 — unchanged
Two candidates quarantined on provenance, one needing a machine no attached
worker provides. `WAVE3_ALL_EXACT_MODELS_AVAILABLE` remains false and that has
not been relaxed to make the closure look better.

### Wave 5 — 15 of 16
`local_advanced_intelligence_v1` (hash `7b7c361cbfe9`) was written and run on
two admitted local models at a 16384 context ceiling:

| Capability | Qwen3-8B | Qwen3-4B |
|---|---|---|
| tool_calling | 6/6 | 6/6 |
| agentic_planning | 6/6 | 6/6 |
| scientific_reasoning | 6/6 | 5/6 |
| long_context (~6k tokens) | 5/6 | **6/6** |
| multilingual (6 languages) | 5/6 | 3/6 |
| **overall** | 0.933 | 0.867 |

The 4B beating the 8B at long-context recall is not the expected direction and
is recorded because it is what happened. `multilingual` is the thinnest row in
the file: one model holds it at any useful level.

`long_context` is covered **at ~6k tokens and at nothing larger**. A 128k window
exists on `@cf/openai/gpt-oss-20b`; an available window is a specification, not
a measurement.

`large_model_synthesis`, `reranking` and `retrieval` are covered by provider
models under their own names — `gpt-oss-120b`, `bge-reranker-base`, `bge-m3`
(recall@1 1.0 over six documents). The local fleet still has no model of that
size, which is why `ALL_EXACT_MODELS_AVAILABLE` is false.

`finance_analysis` is declared, deliberately uncovered, and carries **no**
trading, wallet, transfer, signing or order authority anywhere it appears.

### Wave 4 — 6 of 13, seven classified gaps
Covered: vision, image_understanding, ocr (llava-1.5-7b), speech_to_text
(whisper-large-v3-turbo, 0.875 word recall), text_to_speech (aura-1),
document_embedding (bge-m3, 1024 dims).

Five gaps are **`HUMAN_GATE_REQUIRED`**: `@cf/meta/llama-3.2-11b-vision-instruct`
returns 403 demanding the prompt `agree` before use. That is a model licence and
only the operator may accept it, so it was not accepted. llava — the one
image-capable model that passes the image control — genuinely fails all five,
and its wrong answers are recorded as results about llava.

Two gaps are **`NO_MODEL_IN_VERIFIED_CATALOG`**: the catalog carries no
audio-question-answering model and no image embedding model. `resnet-50`
returning fixed labels is not a substitute for a vector.

One tag is a `PLACEHOLDER_TAG` and is excluded from the denominator.

**Unresolved:** `mistral-small-3.1-24b` and `llama-4-scout-17b` returned 200 to
all three request shapes tried and answered without the image every time. Whether
a fourth shape would reach them is not settled, and is recorded as unresolved
rather than as those models being incapable.

## How a wave closes

`wave_closure_gate.py --wave N`. The rule is **not** "every capability covered";
it is **nothing measurable is left undone**. Each gap carries a `blocker_class`,
and `NO_SUITE_YET` — meaning a suite could be written and run at zero cost —
**blocks closure**. Three Wave 5 tags blocked closure and then stopped blocking
it because they were measured, not because they were reclassified.

Both gates run in CI, because a closure flag is a claim that goes stale silently.

## Capacity

`worker_capacity_matrix.py`. Every figure carries `MEASURED` / `DECLARED` /
`ESTIMATED`, and an estimate never becomes a measurement by being copied.

| Load | Executors | RAM | Satisfied by host alone |
|---|---|---|---|
| MINIMUM_OPERATIONAL | 1 | 8655 MB (MEASURED) | yes |
| NORMAL_CONCURRENT | 2 | 9296 MB (ESTIMATED) | yes |
| PEAK_FEDERATION | 3 | — (NOT_APPLICABLE) | no |

`PEAK_FEDERATION` carries no RAM figure on purpose: one executor is this host,
one is a runner with its own memory, one is a catalog bounded by quota. Adding
them would invent a number. Its binding constraint is the daily free quota and
the runner's cold start.

**Single point of failure:** one host holds every local weight. If this container
dies, exact-model execution stops and only the hosted catalog answers — under a
different model's name.

## Four harness faults found and fixed

Each was mine, and none was evidence about a model:

1. The response `id` was scored as gpt-oss's answer.
2. A reasoning model was given 64 tokens, spent them all reasoning, and returned
   `content: null` with `finish_reason: length`.
3. A correct answer failed because it contained a narrow no-break space.
4. Two multimodal models answered document questions **without receiving the
   image** and were scored `LOCATED_INCORRECTLY`. A vision control now runs
   first, and a model that fails it has its answers not scored at all.

The fourth is the important one: it was recording a hallucination as a
measurement of vision.

## What was not done, deliberately

- PR #442 not merged.
- Trading not started.
- No paid service enabled, no account created, no licence accepted.
- No parallel Brain, router, Model Mesh, registry, scheduler or authority created.
- No capability marked available because a substitute covers it.
