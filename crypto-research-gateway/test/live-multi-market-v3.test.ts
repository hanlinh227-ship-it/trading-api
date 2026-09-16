import { describe, expect, it } from 'vitest';
import { DEFAULT_MARKET_UNIVERSE, resolveUniverse } from '../src/intelligence/market-universe.js';
import { buildDataAcquisitionPlan } from '../src/intelligence/source-planner.js';

describe('live multi-market V3 market universe', () => {
  it('contains bounded intent-level coverage for all six research domains', () => {
    const domains = new Set(DEFAULT_MARKET_UNIVERSE.map((entry) => entry.domain));
    expect(domains).toEqual(new Set(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']));
  });

  it('never guesses an unknown requested symbol', () => {
    const resolved = resolveUniverse(['futures'], { futures: ['MADEUP'] });
    expect(resolved.entries).toEqual([]);
    expect(resolved.unresolved).toEqual([
      { domain: 'futures', symbol: 'MADEUP', reason: 'UNVERIFIED_SYMBOL' },
    ]);
  });

  it('resolves verified canonical forex symbols without changing execution authority', () => {
    const resolved = resolveUniverse(['forex'], { forex: ['EURUSD', 'GBPJPY'] });
    expect(resolved.unresolved).toEqual([]);
    expect(resolved.entries.map((entry) => entry.canonicalSymbol)).toEqual(['EURUSD', 'GBPJPY']);
    expect(resolved.entries.every((entry) => entry.domain === 'forex')).toBe(true);
  });

  it('keeps futures/metals/commodities as product intents rather than permanent dated contracts', () => {
    for (const symbol of ['NQ', 'ES', 'GC', 'CL']) {
      const entry = DEFAULT_MARKET_UNIVERSE.find((item) => item.canonicalSymbol === symbol);
      expect(entry).toBeDefined();
      expect(entry?.productCode).toBe(symbol);
      for (const mapping of Object.values(entry?.mappings ?? {})) {
        expect(mapping.symbol).not.toMatch(/\d{2}$/);
      }
    }
  });
});

describe('live multi-market V3 source planner', () => {
  it('plans all six domains for a broad scan without inventing provider coverage', () => {
    const plan = buildDataAcquisitionPlan({
      capabilities: [
        {
          source: 'crypto-gateway',
          sourceType: 'gateway',
          domains: ['crypto'],
          entitlement: 'VERIFIED_REALTIME',
          available: true,
        },
        {
          source: 'massive',
          sourceType: 'connector',
          domains: ['forex', 'futures', 'indices', 'metals', 'commodities'],
          entitlement: 'NOT_ENTITLED',
          available: true,
        },
      ],
    });

    expect(plan.requestedDomains).toEqual(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']);
    expect(plan.sourcesByDomain.crypto).toEqual(['crypto-gateway']);
    expect(plan.gaps).toEqual(expect.arrayContaining([
      { domain: 'forex', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'futures', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'indices', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'metals', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'commodities', reason: 'NO_ENTITLED_SOURCE' },
    ]));
    expect(plan.researchOnly).toBe(true);
    expect(plan.productionExecutionAuthority).toBe(false);
  });

  it('uses an available verified source only for domains that source actually covers', () => {
    const plan = buildDataAcquisitionPlan({
      requestedDomains: ['forex', 'indices'],
      capabilities: [
        {
          source: 'fx-free',
          sourceType: 'connector',
          domains: ['forex'],
          entitlement: 'VERIFIED_REALTIME',
          available: true,
        },
      ],
    });

    expect(plan.sourcesByDomain.forex).toEqual(['fx-free']);
    expect(plan.sourcesByDomain.indices).toBeUndefined();
    expect(plan.gaps).toContainEqual({ domain: 'indices', reason: 'NO_AVAILABLE_SOURCE' });
  });

  it('treats delayed entitlement as context-only and not an entitled live source', () => {
    const plan = buildDataAcquisitionPlan({
      requestedDomains: ['forex'],
      capabilities: [
        {
          source: 'delayed-fx',
          sourceType: 'connector',
          domains: ['forex'],
          entitlement: 'VERIFIED_DELAYED',
          available: true,
        },
      ],
    });

    expect(plan.sourcesByDomain.forex).toBeUndefined();
    expect(plan.gaps).toContainEqual({ domain: 'forex', reason: 'NO_ENTITLED_SOURCE' });
    expect(plan.entitlementStateBySource['delayed-fx']).toBe('VERIFIED_DELAYED');
  });
});
