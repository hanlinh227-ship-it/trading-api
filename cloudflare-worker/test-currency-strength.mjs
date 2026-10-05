import assert from "node:assert/strict";
import { FOREX_PAIRS, calculateCurrencyStrength } from "./currency-strength.js";

const factors = {
  EUR: -0.8, GBP: 0.2, AUD: 0.5, NZD: -0.1,
  USD: -0.4, CAD: 0.3, CHF: -0.2, JPY: 0.5,
};
const startTime = "2026-10-05T06:00:00.000Z";
const endTime = "2026-10-05T07:00:00.000Z";

function rows(pairs = FOREX_PAIRS, options = {}) {
  return pairs.map((pair, index) => {
    const base = pair.slice(0, 3);
    const quote = pair.slice(3, 6);
    const returnBps = (factors[base] - factors[quote]) * (options.scale ?? 1);
    return {
      pair,
      startClose: 1,
      endClose: Math.exp(returnBps / 10_000),
      startTime,
      endTime: options.offsetEndIndex === index ? "2026-10-05T07:00:20.000Z" : endTime,
      closed: options.running ? false : true,
      ...(options.volatility ? { pairVolatilityBps: 10 } : {}),
    };
  });
}

const full = calculateCurrencyStrength({ observations: rows() });
assert.equal(full.status, "FULL");
assert.equal(full.coverage.usable, 28);
assert.equal(full.barState, "CLOSED");
assert.equal(full.normalization, "raw_bps");
for (const score of full.scores) assert.ok(Math.abs(score.rawBps - factors[score.currency]) < 1e-8);
assert.ok(Math.abs(full.pairContext.find((entry) => entry.pair === "EURUSD").relativeStrengthBaseMinusQuote + 0.4) < 1e-8);

const normalized = calculateCurrencyStrength({ observations: rows(FOREX_PAIRS, { volatility: true }) });
assert.equal(normalized.normalization, "pair_volatility");
assert.ok(Math.abs(normalized.scores.find((score) => score.currency === "EUR").score + 0.08) < 1e-8);

const partial = calculateCurrencyStrength({ observations: rows(FOREX_PAIRS.slice(1)) });
assert.equal(partial.status, "PARTIAL");
assert.equal(partial.coverage.usable, 27);
assert.equal(partial.coverage.missing.length, 1);
assert.equal(partial.scores.length, 8);

const disconnected = calculateCurrencyStrength({ observations: rows().filter((row) => !row.pair.includes("CHF")) });
assert.equal(disconnected.status, "INSUFFICIENT_CONNECTED_UNIVERSE");
assert.deepEqual(disconnected.scores, []);

const misaligned = calculateCurrencyStrength({ observations: rows(FOREX_PAIRS, { offsetEndIndex: 0 }) });
assert.equal(misaligned.status, "MISALIGNED");
assert.deepEqual(misaligned.scores, []);

const running = calculateCurrencyStrength({ observations: rows(FOREX_PAIRS, { running: true }) });
assert.equal(running.status, "FULL");
assert.equal(running.barState, "RUNNING");

const mixedStateRows = rows();
mixedStateRows[0].closed = false;
const mixedState = calculateCurrencyStrength({ observations: mixedStateRows });
assert.equal(mixedState.status, "MIXED_BAR_STATE");
assert.deepEqual(mixedState.scores, []);

const mixedNormalizationRows = rows();
mixedNormalizationRows[0].pairVolatilityBps = 10;
const mixedNormalization = calculateCurrencyStrength({ observations: mixedNormalizationRows });
assert.equal(mixedNormalization.status, "MIXED_NORMALIZATION");

const constantRows = rows().map((row) => ({ ...row, endClose: 1 }));
const flat = calculateCurrencyStrength({ observations: constantRows });
assert.equal(flat.status, "FULL");
assert.ok(flat.scores.every((score) => score.zScore === 0));

const invalidRows = rows();
invalidRows[0] = { ...invalidRows[0], startClose: 0 };
const invalid = calculateCurrencyStrength({ observations: invalidRows });
assert.equal(invalid.status, "PARTIAL");
assert.equal(invalid.coverage.usable, 27);
assert.equal(invalid.coverage.invalid[0].reason, "INVALID_PRICE_TIME_OR_BAR_STATE");

const duplicate = calculateCurrencyStrength({ observations: [...rows(), rows()[0]] });
assert.equal(duplicate.coverage.invalid.some((error) => error.reason === "DUPLICATE_PAIR"), true);
assert.equal(duplicate.coverage.usable, 27);

console.log("currency-strength: all tests passed");
