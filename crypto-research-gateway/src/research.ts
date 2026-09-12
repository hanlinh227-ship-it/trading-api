import { resolveObservations } from './normalization/conflict-resolver.js';
import type { MarketObservation } from './normalization/market-normalizer.js';
import { getProvider, PROVIDERS } from './providers/index.js';
import type { ProviderId, PublicInstrument } from './providers/types.js';
import { selectProviders, type ProviderHealth } from './routing/capability-router.js';

export type MarketAction = 'snapshot' | 'candles' | 'orderbook' | 'funding_oi';

export type MarketResearchInput = {
  action: MarketAction;
  symbol: string;
  instrument: PublicInstrument;
  preferredVenue?: string;
  interval?: string;
  limit?: number;
};

export type RuntimeOptions = {
  forceAllProvidersDown?: boolean;
};

const IDS = Object.keys(PROVIDERS) as ProviderId[];

function capabilityForAction(action: MarketAction): string {
  if (action === 'snapshot') return 'market_snapshot';
  if (action === 'candles') return 'market_candles';
  if (action === 'orderbook') return 'market_orderbook';
  return 'derivatives_funding_oi';
}

export class ResearchRuntime {
  private health: ProviderHealth;
  private lastProbeAt: number | null = null;

  constructor(options: RuntimeOptions = {}) {
    this.health = Object.fromEntries(
      IDS.map((id) => [id, { ok: options.forceAllProvidersDown ? false : false, checkedAt: 0 }]),
    );
  }

  forceAllDown(): void {
    this.health = Object.fromEntries(IDS.map((id) => [id, { ok: false, checkedAt: Date.now() }]));
  }

  getHealth(): ProviderHealth {
    return structuredClone(this.health);
  }

  getLastProbeAt(): number | null {
    return this.lastProbeAt;
  }

  async probeAll(): Promise<ProviderHealth> {
    const entries = await Promise.all(
      IDS.map(async (id) => {
        const result = await PROVIDERS[id].healthProbe();
        return [id, { ...result, checkedAt: Date.now() }] as const;
      }),
    );
    this.health = Object.fromEntries(entries);
    this.lastProbeAt = Date.now();
    return this.getHealth();
  }

  async runMarket(input: MarketResearchInput): Promise<Record<string, unknown>> {
    const capability = capabilityForAction(input.action);
    const selected = selectProviders({
      capability,
      preferredVenue: input.preferredVenue,
      maxCandidates: 3,
      health: this.health,
    });

    if (selected.length === 0) {
      return { ok: false, degraded: true, error: 'no_healthy_provider', capability };
    }

    const successes: Array<{ provider: string; data: unknown }> = [];
    const failures: Array<{ provider: string; error: string }> = [];
    const observations: MarketObservation[] = [];

    await Promise.all(selected.map(async (id) => {
      const provider = getProvider(id);
      if (!provider) return;
      try {
        if (input.action === 'snapshot') {
          const data = await provider.snapshot(input.symbol, input.instrument);
          observations.push(...data);
          successes.push({ provider: id, data });
          return;
        }
        if (input.action === 'candles') {
          successes.push({ provider: id, data: await provider.candles(input.symbol, input.instrument, input.interval ?? '1m', input.limit ?? 100) });
          return;
        }
        if (input.action === 'orderbook') {
          successes.push({ provider: id, data: await provider.orderbook(input.symbol, input.instrument, input.limit ?? 20) });
          return;
        }
        if (!provider.derivatives || input.instrument !== 'perpetual') {
          throw new Error('derivatives_not_supported');
        }
        successes.push({ provider: id, data: await provider.derivatives(input.symbol) });
      } catch (error) {
        failures.push({ provider: id, error: error instanceof Error ? error.message : 'provider_request_failed' });
      }
    }));

    if (successes.length === 0) {
      return { ok: false, degraded: true, error: 'all_selected_providers_failed', capability, failures };
    }

    if (input.action !== 'snapshot') {
      return { ok: true, degraded: failures.length > 0, capability, providers: selected, results: successes, failures };
    }

    const bySemantic = new Map<string, MarketObservation[]>();
    for (const observation of observations) {
      const group = `${observation.symbol}|${observation.instrumentType}|${observation.quoteCurrency}|${observation.priceSemantic}`;
      bySemantic.set(group, [...(bySemantic.get(group) ?? []), observation]);
    }
    const resolutions = [...bySemantic.entries()].map(([group, items]) => ({ group, ...resolveObservations(items) }));
    const conflict = resolutions.some((item) => item.status === 'conflict');

    return {
      ok: true,
      degraded: failures.length > 0,
      capability,
      providers: selected,
      observations,
      conflict,
      resolutions,
      failures,
    };
  }
}
