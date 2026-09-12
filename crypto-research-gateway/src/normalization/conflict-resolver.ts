import type { MarketObservation } from './market-normalizer.js';

export type ObservationResolution = {
  status: 'ok' | 'conflict';
  observations: MarketObservation[];
  reason?: string;
};

function semanticKey(item: MarketObservation): string {
  return [item.symbol, item.instrumentType, item.quoteCurrency, item.priceSemantic].join('|');
}

export function resolveObservations(
  items: MarketObservation[],
  divergenceBps = 30,
): ObservationResolution {
  if (items.length <= 1) {
    return { status: 'ok', observations: items };
  }

  const keys = new Set(items.map(semanticKey));
  if (keys.size !== 1) {
    return {
      status: 'conflict',
      observations: items,
      reason: 'semantic_mismatch',
    };
  }

  const prices = items.map((item) => item.price);
  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const reference = (high + low) / 2;
  const observedBps = reference > 0 ? ((high - low) / reference) * 10_000 : Number.POSITIVE_INFINITY;
  if (observedBps > divergenceBps) {
    return {
      status: 'conflict',
      observations: items,
      reason: `price_divergence_${observedBps.toFixed(2)}bps`,
    };
  }

  return { status: 'ok', observations: items };
}
