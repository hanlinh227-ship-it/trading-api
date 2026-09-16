// Reading a provider catalog without guessing its schema.
//
// A completion probe is a billable call if it lands on a paid model, so these
// filters decide whether real money is spent. The cases that matter are the
// negative ones: an absent label must read as "not free", and a word that
// merely contains "free" must not read as free at all.
import assert from 'node:assert/strict';
import {catalogShape, freeLabel, listedPrice, probeEligibility, sanitizeForLog} from './model-mesh/catalog-shape.js';

// --- prices, in the shapes providers actually return -----------------------
// SambaNova, as observed in probe run 35047130298.
assert.deepEqual(listedPrice({id: 'gpt-oss-120b', pricing: {input: 2.2e-7, output: 5.9e-7}}), {input: 2.2e-7, output: 5.9e-7});
assert.deepEqual(listedPrice({id: 'a', cost: {input: 0, output: 0}}), {input: 0, output: 0});
assert.deepEqual(listedPrice({id: 'a', input_price_per_million: 3, output_price_per_million: 15}), {input: 3, output: 15});
// A plain OpenAI-style row carries no economics at all; that is null, not zero.
assert.equal(listedPrice({id: 'x', object: 'model', created: 1, owned_by: 'nvidia'}), null);
assert.equal(listedPrice(null), null);
// Only one side priced still counts as priced.
assert.deepEqual(listedPrice({id: 'a', cost: {output: 2}}), {input: 0, output: 2});

// --- free labels ------------------------------------------------------------
assert.equal(freeLabel({id: 'x', object: 'model', owned_by: 'nvidia'}), null, 'no label reads as not-free, never as free');
assert.equal(freeLabel({id: 'a', free: true}), 'free=true');
assert.match(freeLabel({id: 'a', tier: 'Free Endpoint'}), /tier=Free Endpoint/);
assert.match(freeLabel({id: 'a', tags: ['preview', 'free']}), /tags=/);
assert.match(freeLabel({id: 'a', pricing_tier: 'free_tier'}), /pricing_tier=/);
assert.equal(freeLabel({id: 'a', tier: 'premium'}), null);
assert.equal(freeLabel({id: 'a', plan: 'freelancer-pro'}), null, 'a substring is not the word free');
assert.equal(freeLabel({id: 'a', free: false}), null);

// --- probe eligibility ------------------------------------------------------
const priced = {id: 'paid', pricing: {input: 3, output: 15}};
const zeroPriced = {id: 'zero', pricing: {input: 0, output: 0}};
const labelled = {id: 'labelled', tier: 'Free Endpoint'};
const bare = {id: 'bare', object: 'model'};

assert.equal(probeEligibility(priced).eligible, false, 'never spend money to learn a model costs money');
assert.match(probeEligibility(priced).note, /SKIPPED_PAID_MODEL/);
assert.equal(probeEligibility(zeroPriced).eligible, true);
assert.equal(probeEligibility(labelled).eligible, true);
assert.equal(probeEligibility(bare, {allowUnpriced: true}).eligible, true);
assert.equal(probeEligibility(bare, {allowUnpriced: false}).eligible, false);

// requireFreeLabel is what keeps "whatever answered first" out of the pool when
// the account holder reports a free tier the catalog may not expose.
assert.equal(probeEligibility(bare, {requireFreeLabel: true}).eligible, false);
assert.equal(probeEligibility(labelled, {requireFreeLabel: true}).eligible, true);
assert.equal(probeEligibility(zeroPriced, {requireFreeLabel: true}).eligible, false, 'a zero price is not the provider saying free');
// A price above zero vetoes a free label: the label is a claim, the price is evidence.
assert.equal(probeEligibility({id: 'x', tier: 'free', pricing: {input: 1, output: 2}}, {requireFreeLabel: true}).eligible, false);

// --- redaction --------------------------------------------------------------
assert.equal(sanitizeForLog('key sk-abcdefghijklmnop here'), 'key [REDACTED] here');
assert.equal(sanitizeForLog('nvapi-ABCDEFGHIJ'), '[REDACTED]');
assert.equal(sanitizeForLog('x'.repeat(500)).length, 120);
assert.deepEqual(sanitizeForLog({a: {b: {c: {d: 1}}}}), {a: {b: '[nested]'}});
assert.deepEqual(sanitizeForLog([1, 2, 3]), [1, 2, 3]);

// --- shape reporting --------------------------------------------------------
const shape = catalogShape([{id: 'a', tier: 'free'}, {id: 'b', owned_by: 'x'}]);
assert.deepEqual(shape.keys, ['id', 'owned_by', 'tier']);
assert.deepEqual(shape.sample, {id: 'a', tier: 'free'});
assert.deepEqual(catalogShape([]), {keys: [], sample: null});

// --- the shape both NVIDIA and Zen actually return -------------------------
// Confirmed by probe run 35048454601: a bare OpenAI listing, no price, no free
// marking. This is the case that must fail closed rather than read as free.
const bareRow = {id: 'meta/muse-glimmer-30b', object: 'model', created: 735790403, owned_by: 'meta'};
assert.equal(listedPrice(bareRow), null);
assert.equal(freeLabel(bareRow), null);
assert.equal(probeEligibility(bareRow, {requireFreeLabel: true}).eligible, false);
assert.equal(probeEligibility(bareRow, {requireFreeLabel: true}).note, 'SKIPPED_NO_FREE_LABEL_IN_CATALOG');
assert.deepEqual(catalogShape([bareRow]).keys, ['created', 'id', 'object', 'owned_by']);

// A documented free id is still just an id: the suffix proves nothing, so the
// allowlist narrows what gets probed and never substitutes for the probe.
const documentedFree = {id: 'mimo-v2.5-free', object: 'model', created: 1, owned_by: 'opencode'};
assert.equal(freeLabel(documentedFree), null, 'a -free suffix is not a catalog free marking');
assert.equal(probeEligibility(documentedFree, {requireFreeLabel: true}).eligible, false);
assert.equal(probeEligibility(documentedFree, {allowUnpriced: true}).eligible, true);

console.log('provider catalog shape and probe-eligibility contracts ok');
