import Fastify, { type FastifyInstance } from 'fastify';
import { pathToFileURL } from 'node:url';
import { z } from 'zod';
import { listenPort, RUNTIME_MODE, SERVICE_NAME, SERVICE_VERSION } from './config.js';
import { READ_ONLY_TOOL_NAMES, registerMcpRoute } from './mcp/server.js';
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
    return {
      ok: true,
      service: SERVICE_NAME,
      version: SERVICE_VERSION,
      runtimeMode: RUNTIME_MODE,
      deploymentRelease: 'live-price-execution-v1',
      deploymentCommitSha: process.env.RAILWAY_GIT_COMMIT_SHA ?? null,
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
  }));

  app.post('/research/market', async (request, reply) => {
    const parsed = marketRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, degraded: false, error: 'invalid_research_request' });
    }
    const result = await runtime.runMarket(parsed.data);
    if (result.degraded === true && result.ok === false) {
      return reply.code(503).send(result);
    }
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
