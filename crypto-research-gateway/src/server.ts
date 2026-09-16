import Fastify, { type FastifyInstance } from 'fastify';
import { pathToFileURL } from 'node:url';
import { z } from 'zod';
import { listenPort, RUNTIME_MODE, SERVICE_NAME, SERVICE_VERSION } from './config.js';
import {
  buildCandidatesFromObservations,
  buildTimeframePlan,
  validateObservationSemantics,
  type NormalizedMarketObservation,
} from './intelligence/autonomous-scan.js';
import { buildCoverageReport } from './intelligence/coverage-report.js';
import { inferMarketDomainsFromIntent } from './intelligence/intent-domain-resolver.js';
import {
  rankOpportunities,
  resolveMarketScope,
  type MarketDomain,
} from './intelligence/multi-market.js';
import {
  buildDataAcquisitionPlan,
  type SourceCapability,
} from './intelligence/source-planner.js';
import { READ_ONLY_TOOL_NAMES, registerMcpRoute } from './mcp/server.js';
import { buildDataEnvelope, type DataFreshness } from './normalization/data-contract.js';
import { ResearchRuntime } from './research.js';

export type BuildAppOptions = {
  probeOnStart?: boolean;
  forceAllProvidersDown?: boolean;
  nowMs?: number;
};

const marketRequestSchema = z.object({
  action: z.enum(['snapshot', 'candles', 'orderbook', 'funding_oi', 'execution_quote']),
  symbol: z.string().min(3).max(40),
  instrument: z.enum(['spot', 'perpetual']).default('spot'),
  preferredVenue: z.string().min(2).max(20).optional(),
  interval: z.string().min(1).max(12).optional(),
  limit: z.number().int().min(1).max(500).optional(),
  side: z.enum(['LONG', 'SHORT']).optional(),
  executionVenue: z.enum(['bybit', 'binance']).optional(),
}).strict().superRefine((value, ctx) => {
  if (value.action === 'execution_quote' && !value.side) {
    ctx.addIssue({
      code: 'custom',
      path: ['side'],
      message: 'side_required_for_execution_quote',
    });
  }
});

const marketDomainSchema = z.enum(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']);
const freshnessSchema = z.enum(['FRESH', 'DEGRADED', 'STALE', 'UNKNOWN']);
const scoreScaleSchema = z.object({
  min: z.number().finite(),
  max: z.number().finite(),
}).strict().refine((value) => value.max > value.min, { message: 'score_scale_invalid' });
const evidenceSchema = z.object({
  id: z.string().min(1).max(120),
  direction: z.enum(['LONG', 'SHORT', 'NO_TRADE']),
  strength: z.number().finite().min(0).max(1),
  freshness: freshnessSchema,
  source: z.string().min(1).max(160),
}).strict();
const chartSchema = z.object({
  provider: z.literal('tradingview'),
  symbol: z.string().min(1).max(120),
  timeframe: z.string().min(1).max(20).optional(),
  verified: z.boolean(),
}).strict();
const opportunityCandidateSchema = z.object({
  id: z.string().min(1).max(120),
  domain: marketDomainSchema,
  symbol: z.string().min(1).max(80),
  direction: z.enum(['LONG', 'SHORT']),
  rawScore: z.number().finite(),
  scoreScale: scoreScaleSchema,
  confidence: z.number().finite().min(0).max(1),
  riskReward: z.number().finite().min(0).max(100),
  invalidation: z.string().min(1).max(500).optional(),
  freshness: freshnessSchema,
  dataConflict: z.boolean().optional(),
  provenance: z.array(z.string().min(1).max(240)).min(1).max(32),
  evidence: z.array(evidenceSchema).min(1).max(64),
  chart: chartSchema.optional(),
}).strict();
const opportunityRequestSchema = z.object({
  requestedDomains: z.array(marketDomainSchema).min(1).max(6).optional(),
  candidates: z.array(opportunityCandidateSchema).min(1).max(100),
}).strict();

const observationMetadataValueSchema = z.union([z.string(), z.number().finite(), z.boolean(), z.null()]);
const normalizedObservationSchema = z.object({
  id: z.string().min(1).max(120),
  domain: marketDomainSchema,
  symbol: z.string().min(1).max(80),
  source: z.string().min(1).max(160),
  sourceType: z.enum(['connector', 'gateway']),
  eventTime: z.string().min(1).max(80),
  ingestTime: z.string().min(1).max(80),
  freshness: freshnessSchema,
  timeframe: z.string().min(1).max(20),
  open: z.number().finite(),
  high: z.number().finite(),
  low: z.number().finite(),
  close: z.number().finite(),
  bid: z.number().finite().optional(),
  ask: z.number().finite().optional(),
  volume: z.number().finite().optional(),
  session: z.string().min(1).max(80).optional(),
  metadata: z.record(z.string(), observationMetadataValueSchema).optional(),
  chart: chartSchema.optional(),
  latencyMs: z.number().finite().min(0).optional(),
  delayClass: z.enum(['REALTIME', 'DELAYED', 'UNKNOWN']).optional(),
  entitlement: z.enum(['VERIFIED_REALTIME', 'VERIFIED_DELAYED', 'UNVERIFIED']).optional(),
  instrumentType: z.enum(['spot', 'perpetual', 'forex', 'future', 'index']).optional(),
  providerSymbol: z.string().min(1).max(120).optional(),
  canonicalSymbol: z.string().min(1).max(120).optional(),
  contractExpiry: z.string().min(1).max(80).optional(),
  evidenceKind: z.enum(['quote', 'snapshot', 'bar', 'trade', 'session', 'context']).optional(),
}).strict();
const symbolSelectionSchema = z.object({
  crypto: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
  forex: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
  futures: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
  indices: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
  metals: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
  commodities: z.array(z.string().min(1).max(80)).min(1).max(50).optional(),
}).strict();
const sourceCapabilitySchema = z.object({
  source: z.string().min(1).max(160),
  sourceType: z.enum(['gateway', 'connector']),
  domains: z.array(marketDomainSchema).min(1).max(6),
  entitlement: z.enum(['VERIFIED_REALTIME', 'VERIFIED_DELAYED', 'UNVERIFIED', 'NOT_ENTITLED']),
  available: z.boolean(),
  state: z.enum(['AVAILABLE', 'DEGRADED', 'RATE_LIMITED', 'UNAVAILABLE', 'UNVERIFIED']).optional(),
}).strict();
const acquisitionContextSchema = z.object({
  sources: z.array(sourceCapabilitySchema).max(64).default([]),
}).strict();
const autoscanRequestSchema = z.object({
  intent: z.string().min(1).max(240).optional(),
  requestedDomains: z.array(marketDomainSchema).min(1).max(6).optional(),
  symbols: symbolSelectionSchema.optional(),
  externalObservations: z.array(normalizedObservationSchema).max(500).optional(),
  acquisitionContext: acquisitionContextSchema.optional(),
  maxResults: z.number().int().min(1).max(10).default(3),
}).strict();

function responseEventTime(result: Record<string, unknown>, fallback: Date): string {
  const observations = Array.isArray(result.observations) ? result.observations : [];
  const timestamps = observations
    .map((item) => item && typeof item === 'object' ? Number((item as Record<string, unknown>).sourceTimestampMs) : Number.NaN)
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (timestamps.length === 0) return fallback.toISOString();
  return new Date(Math.max(...timestamps)).toISOString();
}

function normalizedEvidenceEventTime(observations: readonly NormalizedMarketObservation[]): string | undefined {
  const timestamps = observations
    .map((item) => Date.parse(item.eventTime))
    .filter((value) => Number.isFinite(value));
  if (timestamps.length === 0) return undefined;
  return new Date(Math.max(...timestamps)).toISOString();
}

function attachDataContract(
  result: Record<string, unknown>,
  kind = 'crypto_market_research',
  eventTimeOverride?: string,
): Record<string, unknown> {
  const now = new Date();
  const degraded = result.degraded === true;
  const ok = result.ok === true;
  const freshness: DataFreshness = !ok ? 'UNKNOWN' : degraded ? 'DEGRADED' : 'FRESH';
  const sourceSha = process.env.DEPLOYMENT_SOURCE_SHA ?? process.env.RAILWAY_GIT_COMMIT_SHA ?? 'UNKNOWN';
  const provenance: Record<string, unknown> = {
    providers: Array.isArray(result.providers) ? result.providers : [],
    failures: Array.isArray(result.failures) ? result.failures : [],
    capability: result.capability ?? null,
  };
  const dataContract = buildDataEnvelope({
    kind,
    source: SERVICE_NAME,
    sourceSha,
    eventTime: eventTimeOverride ?? responseEventTime(result, now),
    ingestTime: now.toISOString(),
    freshness,
    payload: result,
    provenance,
  });
  return { ...result, dataContract };
}

function symbolAllowed(
  observation: NormalizedMarketObservation,
  symbols: Partial<Record<MarketDomain, string[]>> | undefined,
): boolean {
  const requested = symbols?.[observation.domain];
  return !requested || requested.includes(observation.symbol);
}

function sourceCoverageFromPlan(
  scope: readonly MarketDomain[],
  sourcesByDomain: Partial<Record<MarketDomain, string[]>>,
): Partial<Record<MarketDomain, { sources: string[]; status: 'COVERED' | 'GAP' }>> {
  const coverage: Partial<Record<MarketDomain, { sources: string[]; status: 'COVERED' | 'GAP' }>> = {};
  for (const domain of scope) {
    const sources = sourcesByDomain[domain] ?? [];
    coverage[domain] = {
      sources,
      status: sources.length > 0 ? 'COVERED' : 'GAP',
    };
  }
  return coverage;
}

function usesV3CoverageSemantics(
  observations: readonly NormalizedMarketObservation[],
  acquisitionCapabilities: readonly SourceCapability[],
): boolean {
  return acquisitionCapabilities.length > 0 || observations.some((observation) =>
    observation.entitlement !== undefined
    || observation.delayClass !== undefined
    || observation.instrumentType !== undefined
    || observation.providerSymbol !== undefined
    || observation.contractExpiry !== undefined);
}

export function buildApp(options: BuildAppOptions = {}): FastifyInstance {
  const app = Fastify({ logger: false, bodyLimit: 256_000 });
  const runtime = new ResearchRuntime({ forceAllProvidersDown: options.forceAllProvidersDown });
  if (options.forceAllProvidersDown) runtime.forceAllDown();

  if (options.probeOnStart !== false && !options.forceAllProvidersDown) {
    app.addHook('onReady', async () => {
      await runtime.probeAll();
    });
  }

  app.get('/health', async () => {
    const providers = runtime.getHealth();
    const healthyProviders = Object.entries(providers).filter(([, status]) => status.ok).map(([id]) => id);
    const degradedProviders = Object.entries(providers).filter(([, status]) => !status.ok).map(([id]) => id);
    const deploymentSourceSha = process.env.DEPLOYMENT_SOURCE_SHA ?? null;
    return {
      ok: true,
      service: SERVICE_NAME,
      version: SERVICE_VERSION,
      runtimeMode: RUNTIME_MODE,
      deploymentRelease: 'live-price-execution-v1',
      deploymentSourceSha,
      deploymentCommitSha: process.env.RAILWAY_GIT_COMMIT_SHA ?? deploymentSourceSha,
      localInstallRequired: false,
      lastPublicProbeTimestamp: runtime.getLastProbeAt(),
      healthyProviders,
      degradedProviders,
      providers,
    };
  });

  app.get('/capabilities', async () => ({
    service: SERVICE_NAME,
    version: SERVICE_VERSION,
    runtimeMode: RUNTIME_MODE,
    localInstallRequired: false,
    tools: READ_ONLY_TOOL_NAMES,
    researchSurfaces: ['multi_market_opportunity_ranking', 'autonomous_multi_market_research'],
    capabilityVersions: {
      autonomous_multi_market_research: 3,
    },
    autonomousMultiMarketResearch: {
      capabilityVersion: 3,
      researchOnly: true,
      productionExecutionAuthority: false,
      providerCalls: 'external-tool-plane-only',
      entitlementRequiredForLive: true,
    },
  }));

  app.post('/research/market', async (request, reply) => {
    const parsed = marketRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, degraded: false, error: 'invalid_research_request' });
    }
    const result = attachDataContract(await runtime.runMarket(parsed.data));
    if (result.degraded === true && result.ok === false) {
      return reply.code(503).send(result);
    }
    return reply.code(200).send(result);
  });

  app.post('/research/opportunities', async (request, reply) => {
    const parsed = opportunityRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, degraded: false, error: 'invalid_opportunity_request' });
    }

    const scope = resolveMarketScope(parsed.data.requestedDomains as MarketDomain[] | undefined);
    const candidates = parsed.data.candidates.filter((candidate) => scope.includes(candidate.domain));
    const excludedOutOfScope = parsed.data.candidates
      .filter((candidate) => !scope.includes(candidate.domain))
      .map((candidate) => candidate.id);
    const ranking = rankOpportunities(candidates);
    const degraded = ranking.decision === 'NO_TRADE' && ranking.blocked.length > 0;
    const result = attachDataContract({
      ok: true,
      degraded,
      capability: 'multi_market_opportunity_ranking',
      researchOnly: true,
      productionExecutionAuthority: false,
      scope,
      excludedOutOfScope,
      ...ranking,
    }, 'multi_market_research');
    return reply.code(200).send(result);
  });

  app.post('/research/autoscan', async (request, reply) => {
    const parsed = autoscanRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, degraded: false, error: 'invalid_autoscan_request' });
    }

    const observations = (parsed.data.externalObservations ?? []) as NormalizedMarketObservation[];
    const invalidObservations = observations
      .map((observation) => ({ id: observation.id, reasons: validateObservationSemantics(observation) }))
      .filter((item) => item.reasons.length > 0);
    if (invalidObservations.length > 0) {
      return reply.code(400).send({
        ok: false,
        degraded: false,
        error: 'invalid_autoscan_observation',
        invalidObservations,
      });
    }

    const requestedDomains = parsed.data.requestedDomains as MarketDomain[] | undefined;
    const inferredDomains = requestedDomains ? [] : inferMarketDomainsFromIntent(parsed.data.intent);
    const scope = resolveMarketScope(requestedDomains ?? (inferredDomains.length > 0 ? inferredDomains : undefined));
    const requestedSymbols = parsed.data.symbols as Partial<Record<MarketDomain, string[]>> | undefined;
    const scopedObservations = observations.filter((observation) =>
      scope.includes(observation.domain) && symbolAllowed(observation, requestedSymbols));
    const acquisitionCapabilities = (parsed.data.acquisitionContext?.sources ?? []) as SourceCapability[];
    const dataAcquisitionPlan = buildDataAcquisitionPlan({
      requestedDomains: scope,
      requestedSymbols,
      capabilities: acquisitionCapabilities,
    });
    const requestNowMs = options.nowMs ?? Date.now();
    const v3Coverage = usesV3CoverageSemantics(scopedObservations, acquisitionCapabilities);
    const coverage = v3Coverage
      ? buildCoverageReport(scope, scopedObservations, dataAcquisitionPlan.gaps, requestNowMs)
      : scope.map((domain) => {
        const domainObservations = scopedObservations.filter((item) => item.domain === domain);
        const usable = domainObservations.filter((item) => item.freshness === 'FRESH' || item.freshness === 'DEGRADED');
        if (usable.length > 0) {
          return {
            domain,
            requested: true,
            usableObservationCount: usable.length,
            status: 'COVERED' as const,
            reasons: [] as string[],
          };
        }
        return {
          domain,
          requested: true,
          usableObservationCount: 0,
          status: 'GAP' as const,
          reasons: [domainObservations.length > 0 ? 'NO_FRESH_EVIDENCE' : 'NO_USABLE_EVIDENCE'],
        };
      });

    const batch = buildCandidatesFromObservations(scopedObservations, requestNowMs);
    const ranking = rankOpportunities(batch.candidates);
    const blocked = [
      ...batch.blocked.map((item) => ({ id: `${item.domain}:${item.symbol}`, reasons: item.reasons })),
      ...ranking.blocked,
    ];
    const providers = [...new Set(scopedObservations.map((item) => `${item.sourceType}:${item.source}`))];
    const sourceCoverage = sourceCoverageFromPlan(scope, dataAcquisitionPlan.sourcesByDomain);
    const degraded = coverage.some((item) => v3Coverage ? item.status !== 'LIVE' : item.status === 'GAP')
      || (v3Coverage && dataAcquisitionPlan.gaps.length > 0)
      || blocked.length > 0
      || ranking.decision === 'NO_TRADE';

    const result = attachDataContract({
      ok: true,
      degraded,
      capability: 'autonomous_multi_market_research',
      capabilityVersion: 3,
      researchOnly: true,
      productionExecutionAuthority: false,
      intent: parsed.data.intent ?? null,
      scope,
      timeframePlan: buildTimeframePlan(),
      dataAcquisitionPlan,
      sourceCoverage,
      entitlementSummary: dataAcquisitionPlan.entitlementStateBySource,
      sourceStateSummary: dataAcquisitionPlan.sourceStateBySource,
      coverage,
      candidatesBuilt: batch.candidates.length,
      providers,
      decision: ranking.decision,
      ranked: ranking.ranked.slice(0, parsed.data.maxResults),
      blocked,
    }, 'autonomous_multi_market_research', normalizedEvidenceEventTime(scopedObservations));

    return reply.code(200).send(result);
  });

  const unavailable = async (_request: unknown, reply: { code: (status: number) => { send: (body: unknown) => unknown } }) =>
    reply.code(501).send({ ok: false, degraded: true, error: 'capability_not_available' });

  app.post('/research/token', unavailable);
  app.post('/research/news', unavailable);
  app.post('/research/risk', unavailable);

  registerMcpRoute(app, runtime);
  return app;
}

async function start(): Promise<void> {
  const app = buildApp();
  await app.listen({ host: '0.0.0.0', port: listenPort() });
}

const invokedPath = process.argv[1];
if (invokedPath && import.meta.url === pathToFileURL(invokedPath).href) {
  await start();
}
