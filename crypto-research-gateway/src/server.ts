import Fastify, { type FastifyInstance } from 'fastify';
import { pathToFileURL } from 'node:url';
import { z } from 'zod';
import { listenPort, RUNTIME_MODE, SERVICE_NAME, SERVICE_VERSION } from './config.js';
import {
  rankOpportunities,
  resolveMarketScope,
  type MarketDomain,
} from './intelligence/multi-market.js';
import { READ_ONLY_TOOL_NAMES, registerMcpRoute } from './mcp/server.js';
import { buildDataEnvelope, type DataFreshness } from './normalization/data-contract.js';
import { ResearchRuntime } from './research.js';

export type BuildAppOptions = {
  probeOnStart?: boolean;
  forceAllProvidersDown?: boolean;
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

function responseEventTime(result: Record<string, unknown>, fallback: Date): string {
  const observations = Array.isArray(result.observations) ? result.observations : [];
  const timestamps = observations
    .map((item) => item && typeof item === 'object' ? Number((item as Record<string, unknown>).sourceTimestampMs) : Number.NaN)
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (timestamps.length === 0) return fallback.toISOString();
  return new Date(Math.max(...timestamps)).toISOString();
}

function attachDataContract(
  result: Record<string, unknown>,
  kind = 'crypto_market_research',
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
    eventTime: responseEventTime(result, now),
    ingestTime: now.toISOString(),
    freshness,
    payload: result,
    provenance,
  });
  return { ...result, dataContract };
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
    researchSurfaces: ['multi_market_opportunity_ranking'],
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
