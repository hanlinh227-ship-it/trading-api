export const FOREX_CURRENCIES = Object.freeze([
  "EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY",
]);

export const FOREX_PAIRS = Object.freeze([
  "EURUSD", "EURJPY", "EURGBP", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
  "GBPUSD", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
  "AUDUSD", "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
  "NZDUSD", "NZDJPY", "NZDCHF", "NZDCAD",
  "USDJPY", "USDCHF", "USDCAD", "CADJPY", "CADCHF", "CHFJPY",
]);

const CURRENCY_SET = new Set(FOREX_CURRENCIES);
const PAIR_SET = new Set(FOREX_PAIRS);

function toMillis(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return NaN;
}

function solveLinearSystem(matrix, vector) {
  const size = vector.length;
  const augmented = matrix.map((row, index) => [...row, vector[index]]);

  for (let column = 0; column < size; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < size; row += 1) {
      if (Math.abs(augmented[row][column]) > Math.abs(augmented[pivot][column])) pivot = row;
    }
    if (Math.abs(augmented[pivot][column]) < 1e-10) return null;
    [augmented[column], augmented[pivot]] = [augmented[pivot], augmented[column]];

    const divisor = augmented[column][column];
    for (let cell = column; cell <= size; cell += 1) augmented[column][cell] /= divisor;
    for (let row = 0; row < size; row += 1) {
      if (row === column) continue;
      const factor = augmented[row][column];
      for (let cell = column; cell <= size; cell += 1) {
        augmented[row][cell] -= factor * augmented[column][cell];
      }
    }
  }
  return augmented.map((row) => row[size]);
}

function isConnected(edges) {
  const adjacency = new Map(FOREX_CURRENCIES.map((currency) => [currency, new Set()]));
  for (const edge of edges) {
    adjacency.get(edge.base).add(edge.quote);
    adjacency.get(edge.quote).add(edge.base);
  }
  const visited = new Set([FOREX_CURRENCIES[0]]);
  const pending = [FOREX_CURRENCIES[0]];
  while (pending.length) {
    const currency = pending.pop();
    for (const neighbor of adjacency.get(currency)) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        pending.push(neighbor);
      }
    }
  }
  return visited.size === FOREX_CURRENCIES.length;
}

function fitCurrencyFactors(edges, valueKey) {
  const count = FOREX_CURRENCIES.length;
  const matrix = Array.from({ length: count + 1 }, () => Array(count + 1).fill(0));
  const vector = Array(count + 1).fill(0);

  for (const edge of edges) {
    const baseIndex = FOREX_CURRENCIES.indexOf(edge.base);
    const quoteIndex = FOREX_CURRENCIES.indexOf(edge.quote);
    const value = edge[valueKey];
    matrix[baseIndex][baseIndex] += 1;
    matrix[quoteIndex][quoteIndex] += 1;
    matrix[baseIndex][quoteIndex] -= 1;
    matrix[quoteIndex][baseIndex] -= 1;
    vector[baseIndex] += value;
    vector[quoteIndex] -= value;
  }

  // Add the zero-sum constraint so the common offset is identifiable.
  for (let index = 0; index < count; index += 1) {
    matrix[index][count] = 1;
    matrix[count][index] = 1;
  }
  const solution = solveLinearSystem(matrix, vector);
  return solution ? solution.slice(0, count) : null;
}

function zScores(values) {
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const deviation = Math.sqrt(variance);
  return { deviation, scores: deviation === 0 ? values.map(() => 0) : values.map((value) => (value - mean) / deviation) };
}

/**
 * Estimate relative strength for the eight major currencies from one frozen,
 * time-aligned snapshot. Each observation describes one pair's move from a
 * common start price/time to an end price/time.
 *
 * pairVolatilityBps is optional. If supplied on every observation, the fitted
 * score uses return / pairVolatilityBps; otherwise it uses raw return bps.
 * These modes must not be mixed in one snapshot.
 */
export function calculateCurrencyStrength({ observations, alignmentToleranceMs = 10_000 } = {}) {
  if (!Array.isArray(observations)) throw new TypeError("observations must be an array");
  if (!Number.isFinite(alignmentToleranceMs) || alignmentToleranceMs < 0) {
    throw new TypeError("alignmentToleranceMs must be a non-negative number");
  }

  const errors = [];
  const seen = new Set();
  const valid = [];
  for (const [index, observation] of observations.entries()) {
    if (!observation || typeof observation !== "object") {
      errors.push({ index, reason: "INVALID_ROW" });
      continue;
    }
    const pair = typeof observation.pair === "string" ? observation.pair.toUpperCase() : "";
    if (!PAIR_SET.has(pair)) {
      errors.push({ index, pair: pair || null, reason: "UNKNOWN_PAIR" });
      continue;
    }
    if (seen.has(pair)) {
      errors.push({ index, pair, reason: "DUPLICATE_PAIR" });
      continue;
    }
    seen.add(pair);

    const base = pair.slice(0, 3);
    const quote = pair.slice(3, 6);
    const baseMatches = observation.base === undefined
      || (typeof observation.base === "string" && observation.base.toUpperCase() === base);
    const quoteMatches = observation.quote === undefined
      || (typeof observation.quote === "string" && observation.quote.toUpperCase() === quote);
    if (!CURRENCY_SET.has(base) || !CURRENCY_SET.has(quote) || !baseMatches || !quoteMatches) {
      errors.push({ index, pair, reason: "PAIR_ORIENTATION_MISMATCH" });
      continue;
    }
    const startClose = Number(observation.startClose);
    const endClose = Number(observation.endClose);
    const startMs = toMillis(observation.startTime);
    const endMs = toMillis(observation.endTime);
    if (!(startClose > 0) || !(endClose > 0) || !Number.isFinite(startMs)
      || !Number.isFinite(endMs) || endMs <= startMs || typeof observation.closed !== "boolean") {
      errors.push({ index, pair, reason: "INVALID_PRICE_TIME_OR_BAR_STATE" });
      continue;
    }
    const returnBps = 10_000 * Math.log(endClose / startClose);
    const hasVolatility = observation.pairVolatilityBps !== undefined
      && observation.pairVolatilityBps !== null;
    const pairVolatilityBps = hasVolatility ? Number(observation.pairVolatilityBps) : null;
    if (!Number.isFinite(returnBps) || (hasVolatility && !(pairVolatilityBps > 0))) {
      errors.push({ index, pair, reason: "INVALID_RETURN_OR_VOLATILITY" });
      continue;
    }
    valid.push({
      pair, base, quote, startClose, endClose, startMs, endMs, closed: observation.closed,
      returnBps, pairVolatilityBps,
    });
  }

  const used = valid.filter((edge) => !errors.some((error) => error.pair === edge.pair));
  const coverage = {
    usable: used.length,
    total: FOREX_PAIRS.length,
    missing: FOREX_PAIRS.filter((pair) => !seen.has(pair)),
    invalid: errors,
  };
  const empty = (status, extra = {}) => ({
    status,
    coverage,
    scores: [],
    pairContext: [],
    errors,
    ...extra,
  });
  if (used.length === 0) return empty("NO_DATA");

  const normalizationModes = new Set(used.map((edge) => edge.pairVolatilityBps === null ? "raw_bps" : "pair_volatility"));
  if (normalizationModes.size > 1) return empty("MIXED_NORMALIZATION");
  const startTimes = used.map((edge) => edge.startMs);
  const endTimes = used.map((edge) => edge.endMs);
  const startSkewMs = Math.max(...startTimes) - Math.min(...startTimes);
  const endSkewMs = Math.max(...endTimes) - Math.min(...endTimes);
  if (startSkewMs > alignmentToleranceMs || endSkewMs > alignmentToleranceMs) {
    return empty("MISALIGNED", { startSkewMs, endSkewMs, alignmentToleranceMs });
  }
  const barStates = new Set(used.map((edge) => edge.closed ? "CLOSED" : "RUNNING"));
  if (barStates.size > 1) return empty("MIXED_BAR_STATE", { startSkewMs, endSkewMs });
  if (!isConnected(used)) return empty("INSUFFICIENT_CONNECTED_UNIVERSE", { startSkewMs, endSkewMs });

  const normalizedEdges = used.map((edge) => ({
    ...edge,
    strengthInput: edge.pairVolatilityBps === null ? edge.returnBps : edge.returnBps / edge.pairVolatilityBps,
  }));
  const fittedScores = fitCurrencyFactors(normalizedEdges, "strengthInput");
  const rawBpsScores = fitCurrencyFactors(normalizedEdges, "returnBps");
  if (!fittedScores || !rawBpsScores) return empty("INSUFFICIENT_CONNECTED_UNIVERSE", { startSkewMs, endSkewMs });
  const { deviation, scores: z } = zScores(fittedScores);
  const pairCounts = new Map(FOREX_CURRENCIES.map((currency) => [currency, 0]));
  for (const edge of used) {
    pairCounts.set(edge.base, pairCounts.get(edge.base) + 1);
    pairCounts.set(edge.quote, pairCounts.get(edge.quote) + 1);
  }

  const scores = FOREX_CURRENCIES.map((currency, index) => ({
    currency,
    score: fittedScores[index],
    rawBps: rawBpsScores[index],
    zScore: z[index],
    counterparts: pairCounts.get(currency),
  })).sort((left, right) => right.score - left.score)
    .map((score, index) => ({ ...score, rank: index + 1 }));
  const scoreByCurrency = new Map(scores.map((score) => [score.currency, score]));
  const pairContext = used.map((edge) => ({
    pair: edge.pair,
    relativeStrengthBaseMinusQuote: scoreByCurrency.get(edge.base).score - scoreByCurrency.get(edge.quote).score,
  }));

  return {
    status: used.length === FOREX_PAIRS.length ? "FULL" : "PARTIAL",
    coverage,
    normalization: normalizationModes.values().next().value,
    barState: barStates.values().next().value,
    snapshot: {
      startTime: new Date(startTimes.reduce((sum, time) => sum + time, 0) / startTimes.length).toISOString(),
      endTimeFrom: new Date(Math.min(...endTimes)).toISOString(),
      endTimeTo: new Date(Math.max(...endTimes)).toISOString(),
      startSkewMs,
      endSkewMs,
      alignmentToleranceMs,
    },
    crossSectionStandardDeviation: deviation,
    scores,
    pairContext,
    errors,
    interpretation: "Reference only; currency strength is not an entry signal or a trade veto.",
  };
}
