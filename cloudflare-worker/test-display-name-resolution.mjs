// Turning a vendor display name into a live API id.
//
// NVIDIA Build shows display names; the API speaks ids. Doing that conversion
// by hand is how two model ids that did not exist got admitted earlier in this
// work, so the mapping is mechanical: exactly one live id must normalize to the
// same key, and anything else is reported rather than resolved.
//
// The live ids below are verbatim from probe run 35048454601.
import assert from 'node:assert/strict';
import {CHAT_MODALITIES, classifyModality, normalizeModelKey, resolveDisplayName, resolveDisplayNames} from './model-mesh/catalog-shape.js';

const LIVE = [
  '01-ai/yi-large', 'adept/fuyu-8b', 'deepseek-ai/deepseek-v4-flash-0731',
  'google/diffusiongemma-26b-a4b-it', 'google/gemma-4-31b-it', 'meta/llama-guard-4-12b',
  'meta/llama-3.2-11b-vision-instruct', 'meta/llama-3.2-90b-vision-instruct',
  'meta/muse-glimmer-30b', 'mistralai/mistral-nemotron', 'moonshotai/kimi-k3',
  'nvidia/ai-synthetic-video-detector', 'nvidia/ising-calibration-1.5-31b',
  'nvidia/llama-3.1-nemoguard-8b-content-safety', 'nvidia/llama-3.1-nemotron-safety-guard-8b-v3',
  'nvidia/nemotron-3-embed-1b', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
  'nvidia/nemotron-3-super-120b-a12b', 'nvidia/nemotron-3-ultra-550b-a55b',
  'nvidia/nemotron-3.5-content-safety', 'nvidia/nemotron-3.5-lightning-30b-a3b',
  'nvidia/riva-translate-4b-instruct-v1.1', 'nvidia/riva-translate-4b-instruct-v2',
  'nvidia/nv-embedqa-mistral-7b-v2', 'openai/gpt-oss-20b', 'poolside/laguna-xs-2.1',
  'z-ai/glm-5.3', 'z-ai/glm-5.3-flash',
];

// --- normalization ---------------------------------------------------------
assert.equal(normalizeModelKey('meta/muse-glimmer-30b'), 'museglimmer30b');
assert.equal(normalizeModelKey('muse-glimmer-30b'), 'museglimmer30b');
assert.equal(normalizeModelKey('riva-translate-4b-instruct-v1_1'), 'rivatranslate4binstructv11');
assert.equal(normalizeModelKey('nvidia/riva-translate-4b-instruct-v1.1'), 'rivatranslate4binstructv11');
assert.equal(normalizeModelKey('glm-5-3'), 'glm53');
assert.equal(normalizeModelKey('z-ai/glm-5.3'), 'glm53');
assert.equal(normalizeModelKey(''), '');

// --- names that resolve to exactly one live id -----------------------------
for (const [display, expected] of [
  ['muse-glimmer-30b', 'meta/muse-glimmer-30b'],
  ['deepseek-v4-flash-0731', 'deepseek-ai/deepseek-v4-flash-0731'],
  ['nemotron-3.5-lightning-30b-a3b', 'nvidia/nemotron-3.5-lightning-30b-a3b'],
  ['riva-translate-4b-instruct-v2', 'nvidia/riva-translate-4b-instruct-v2'],
  ['riva-translate-4b-instruct-v1_1', 'nvidia/riva-translate-4b-instruct-v1.1'],
  ['gpt-oss-20b', 'openai/gpt-oss-20b'],
  ['gemma-4-31b-it', 'google/gemma-4-31b-it'],
  ['llama-guard-4-12b', 'meta/llama-guard-4-12b'],
  ['mistral-nemotron', 'mistralai/mistral-nemotron'],
  ['kimi-k3', 'moonshotai/kimi-k3'],
  ['glm-5-3', 'z-ai/glm-5.3'],
  ['laguna-xs-2.1', 'poolside/laguna-xs-2.1'],
  ['nemotron-3-embed-1b', 'nvidia/nemotron-3-embed-1b'],
]) {
  const row = resolveDisplayName(display, LIVE);
  assert.equal(row.status, 'matched', `${display} -> ${row.status} ${row.reason || ''}`);
  assert.equal(row.id, expected, display);
}

// --- names that must NOT resolve -------------------------------------------
// A prefix is not a match. "ising-calibration" must never become the 1.5-31b
// build, and "synthetic-video-detector" must never become the ai- prefixed id.
for (const [display, reason] of [
  ['ising-calibration', 'NO_EXACT_MATCH'],
  ['synthetic-video-detector', 'NO_EXACT_MATCH'],
  ['Kumo Relational', 'NOT_IN_LIVE_LISTING'],
  ['Active Speaker Detection', 'NOT_IN_LIVE_LISTING'],
  ['Background Noise Removal', 'NOT_IN_LIVE_LISTING'],
  ['Studio Voice', 'NOT_IN_LIVE_LISTING'],
  ['cosmos3-nano', 'NOT_IN_LIVE_LISTING'],
  ['paligemma', 'NOT_IN_LIVE_LISTING'],
]) {
  const row = resolveDisplayName(display, LIVE);
  assert.equal(row.status, 'unresolved', `${display} unexpectedly ${row.status} -> ${row.id}`);
  assert.equal(row.reason, reason, display);
  assert.equal(row.id, undefined);
}
// A near miss still reports its candidates, so a human can confirm the real id.
assert.deepEqual(resolveDisplayName('ising-calibration', LIVE).candidates, ['nvidia/ising-calibration-1.5-31b']);
// Containment counts as a near miss too: the live id carries an extra prefix.
assert.deepEqual(resolveDisplayName('synthetic-video-detector', LIVE).candidates, ['nvidia/ai-synthetic-video-detector']);

// --- ambiguity is reported, never picked -----------------------------------
const twins = ['vendor-a/same-model', 'vendor-b/same-model'];
const ambiguous = resolveDisplayName('same-model', twins);
assert.equal(ambiguous.status, 'ambiguous');
assert.deepEqual(ambiguous.candidates, twins);
assert.equal(ambiguous.id, undefined);

// --- modality: do not push a non-chat model at /chat/completions -----------
assert.equal(classifyModality('nvidia/nemotron-3-embed-1b'), 'embedding');
assert.equal(classifyModality('nvidia/nv-embedqa-mistral-7b-v2'), 'embedding');
assert.equal(classifyModality('nvidia/llama-3.1-nemoguard-8b-content-safety'), 'safety');
assert.equal(classifyModality('nvidia/nemotron-3.5-content-safety'), 'safety');
assert.equal(classifyModality('nvidia/llama-3.1-nemotron-safety-guard-8b-v3'), 'safety');
assert.equal(classifyModality('nvidia/ai-synthetic-video-detector'), 'video');
assert.equal(classifyModality('nvidia/cosmos-transfer2.5-2b'), 'video');
assert.equal(classifyModality('nvidia/magpie-tts-zeroshot'), 'audio');
assert.equal(classifyModality('nvidia/nemotron-voicechat'), 'audio');
assert.equal(classifyModality('adept/fuyu-8b'), 'vision_specialized');
assert.equal(classifyModality('google/paligemma'), 'vision_specialized');
assert.equal(classifyModality('nvidia/nemotron-4-340b-reward'), 'reward');

// A vision-INSTRUCT model is a chat model that also takes images.
assert.equal(classifyModality('meta/llama-3.2-11b-vision-instruct'), 'text_chat');
assert.equal(classifyModality('meta/llama-3.2-90b-vision-instruct'), 'text_chat');
assert.equal(classifyModality('meta/muse-glimmer-30b'), 'text_chat');
assert.equal(classifyModality('openai/gpt-oss-20b'), 'text_chat');
assert.equal(classifyModality('z-ai/glm-5.3'), 'text_chat');
assert.equal(classifyModality(''), 'unknown');
assert.deepEqual([...CHAT_MODALITIES], ['text_chat']);

// --- batch resolution keeps every input accounted for ----------------------
const batch = resolveDisplayNames(['muse-glimmer-30b', 'Kumo Relational', 'gpt-oss-20b'], LIVE);
assert.equal(batch.length, 3);
assert.deepEqual(batch.map((row) => row.status), ['matched', 'unresolved', 'matched']);

console.log('display-name resolution and modality contracts ok');
