import { ALL_MARKET_DOMAINS, getMarketProfile, resolveMarketScope, type MarketDomain } from './multi-market.js';
import { resolveUniverse } from './market-universe.js';

export type SourceEntitlement = 'VERIFIED_REALTIME' | 'VERIFIED_DELAYED' | 'UNVERIFIED' | 'NOT_ENTITLED';
export type SourceOperationalState = 'AVAILABLE' | 'DEGRADED' | 'RATE_LIMITED' | 'UNAVAILABLE' | 'UNVERIFIED';

export type SourceCapability = {
  source: string;
  sourceType: 'gateway' | 'connector';
  domains: MarketDomain[];
  entitlement: SourceEntitlement;
  available: boolean;
  state?: SourceOperationalState;
};

export type DataAcquisitionGap = {
  domain: MarketDomain;
  reason: string;
};

export type DataAcquisitionPlan = {
  requestedDomains: MarketDomain[];
  resolvedDomains: MarketDomain[];
  symbolsByDomain: Partial<Record<MarketDomain, string[]>>;
  sourcesByDomain: Partial<Record<MarketDomain, string[]>>;
  timeframesByDomain: Partial<Record<MarketDomain, string[]>>;
  requiredEvidenceByDomain: Partial<Record<MarketDomain, string[]>>;
  entitlementStateBySource: Record<string, string>;
  sourceStateBySource: Record<string, SourceOperationalState>;
  fallbackPolicy: 'FAIL_CLOSED_CONTINUE_COVERED';
  gaps: DataAcquisitionGap[];
  researchOnly: true;
  productionExecutionAuthority: false;
};

export type BuildDataAcquisitionPlanInput = {
  requestedDomains?: MarketDomain[];
  requestedSymbols?: Partial<Record<MarketDomain, string[]>>;
  capabilities?: SourceCapability[];
};

const DEFAULT_TIMEFRAMES: Record<MarketDomain, string[]> = {
  crypto: ['1h', '15m', '5m'],
  forex: ['1h', '15m'],
  futures: ['1h', '15m'],
  indices: ['1h', '15m'],
  metals: ['1h', '15m'],
  commodities: ['1h', '15m'],
};

function pushGrouped(
  target: Partial<Record<MarketDomain, string[]>>,
  domain: MarketDomain,
  value: string,
): void {
  const current = target[domain] ?? [];
  if (!current.includes(value)) target[domain] = [...current, value];
}

function addGap(gaps: DataAcquisitionGap[], gap: DataAcquisitionGap): void {
  if (!gaps.some((item) => item.domain === gap.domain && item.reason === gap.reason)) {
    gaps.push(gap);
  }
}

function effectiveSourceState(capability: SourceCapability): SourceOperationalState {
  if (!capability.state) return capability.available ? 'AVAILABLE' : 'UNAVAILABLE';
  if (capability.state === 'AVAILABLE' && !capability.available) return 'UNAVAILABLE';
  return capability.state;
}

function operationalGapReason(states: readonly SourceOperationalState[]): string | null {
  if (states.includes('RATE_LIMITED')) return 'SOURCE_RATE_LIMITED';
  if (states.includes('DEGRADED')) return 'SOURCE_DEGRADED';
  if (states.includes('UNVERIFIED')) return 'SOURCE_UNVERIFIED';
  return null;
}

export function buildDataAcquisitionPlan(
  input: BuildDataAcquisitionPlanInput = {},
): DataAcquisitionPlan {
  const requestedDomains = resolveMarketScope(input.requestedDomains);
  const resolution = resolveUniverse(requestedDomains, input.requestedSymbols);
  const capabilities = input.capabilities ?? [];

  const symbolsByDomain: Partial<Record<MarketDomain, string[]>> = {};
  const sourcesByDomain: Partial<Record<MarketDomain, string[]>> = {};
  const timeframesByDomain: Partial<Record<MarketDomain, string[]>> = {};
  const requiredEvidenceByDomain: Partial<Record<MarketDomain, string[]>> = {};
  const entitlementStateBySource: Record<string, string> = {};
  const sourceStateBySource: Record<string, SourceOperationalState> = {};
  const gaps: DataAcquisitionGap[] = [];

  for (const capability of capabilities) {
    entitlementStateBySource[capability.source] = capability.entitlement;
    sourceStateBySource[capability.source] = effectiveSourceState(capability);
  }

  for (const entry of resolution.entries) {
    pushGrouped(symbolsByDomain, entry.domain, entry.canonicalSymbol);
  }

  const resolvedDomains = requestedDomains.filter((domain) => (symbolsByDomain[domain]?.length ?? 0) > 0);

  for (const unresolved of resolution.unresolved) {
    if ((symbolsByDomain[unresolved.domain]?.length ?? 0) === 0) {
      addGap(gaps, { domain: unresolved.domain, reason: unresolved.reason });
    }
  }

  for (const domain of requestedDomains) {
    timeframesByDomain[domain] = [...DEFAULT_TIMEFRAMES[domain]];
    requiredEvidenceByDomain[domain] = [...getMarketProfile(domain).requiredEvidence];

    if ((symbolsByDomain[domain]?.length ?? 0) === 0) {
      if (!gaps.some((item) => item.domain === domain)) {
        addGap(gaps, { domain, reason: 'NO_VERIFIED_SYMBOL' });
      }
      continue;
    }

    const domainCapabilities = capabilities.filter((capability) => capability.domains.includes(domain));
    const operationallyAvailable = domainCapabilities.filter(
      (capability) => effectiveSourceState(capability) === 'AVAILABLE' && capability.available,
    );
    const realtimeCapabilities = operationallyAvailable.filter(
      (capability) => capability.entitlement === 'VERIFIED_REALTIME',
    );

    for (const capability of realtimeCapabilities) {
      pushGrouped(sourcesByDomain, domain, capability.source);
    }

    if (realtimeCapabilities.length > 0) continue;

    const states = domainCapabilities.map(effectiveSourceState);
    const operationalReason = operationalGapReason(states);
    if (operationalReason) {
      addGap(gaps, { domain, reason: operationalReason });
    } else if (operationallyAvailable.length === 0) {
      addGap(gaps, { domain, reason: 'NO_AVAILABLE_SOURCE' });
    } else {
      addGap(gaps, { domain, reason: 'NO_ENTITLED_SOURCE' });
    }
  }

  return {
    requestedDomains: requestedDomains.length > 0 ? requestedDomains : [...ALL_MARKET_DOMAINS],
    resolvedDomains,
    symbolsByDomain,
    sourcesByDomain,
    timeframesByDomain,
    requiredEvidenceByDomain,
    entitlementStateBySource,
    sourceStateBySource,
    fallbackPolicy: 'FAIL_CLOSED_CONTINUE_COVERED',
    gaps,
    researchOnly: true,
    productionExecutionAuthority: false,
  };
}
