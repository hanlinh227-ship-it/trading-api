import type { FastifyInstance } from 'fastify';
import { toNodeHandler } from '@modelcontextprotocol/node';
import { createMcpHandler, McpServer } from '@modelcontextprotocol/server';
import { z } from 'zod';
import { SERVICE_NAME, SERVICE_VERSION } from '../config.js';
import type { MarketAction, ResearchRuntime } from '../research.js';

export const READ_ONLY_TOOL_NAMES = [
  'market_snapshot',
  'market_candles',
  'market_orderbook',
  'market_execution_quote',
  'derivatives_funding_oi',
  'token_research',
  'token_risk_check',
  'crypto_news_research',
] as const;

const READ_ONLY_TOOL_SET = new Set<string>(READ_ONLY_TOOL_NAMES);

export function isReadOnlyToolName(name: string): boolean {
  return READ_ONLY_TOOL_SET.has(name);
}

const marketInput = z.object({
  symbol: z.string().min(3).max(40),
  instrument: z.enum(['spot', 'perpetual']).default('spot'),
  preferredVenue: z.string().min(2).max(20).optional(),
  interval: z.string().min(1).max(12).optional(),
  limit: z.number().int().min(1).max(500).optional(),
});

const executionInput = z.object({
  symbol: z.string().min(3).max(40),
  instrument: z.enum(['spot', 'perpetual']).default('perpetual'),
  side: z.enum(['LONG', 'SHORT']),
  executionVenue: z.enum(['bybit', 'binance']).optional(),
});

function asTextResult(value: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(value) }],
  };
}

function createServer(runtime: ResearchRuntime): McpServer {
  const server = new McpServer({ name: SERVICE_NAME, version: SERVICE_VERSION });

  const registerMarket = (
    name: 'market_snapshot' | 'market_candles' | 'market_orderbook' | 'derivatives_funding_oi',
    action: Exclude<MarketAction, 'execution_quote'>,
    description: string,
  ) => {
    server.registerTool(name, { description, inputSchema: marketInput }, async (input) => {
      const result = await runtime.runMarket({ ...input, action });
      return asTextResult(result);
    });
  };

  registerMarket('market_snapshot', 'snapshot', 'Read normalized public market prices from approved providers.');
  registerMarket('market_candles', 'candles', 'Read public candlestick data from approved providers.');
  registerMarket('market_orderbook', 'orderbook', 'Read public order-book data from approved providers.');
  registerMarket('derivatives_funding_oi', 'funding_oi', 'Read public derivatives funding and open-interest context.');

  server.registerTool(
    'market_execution_quote',
    {
      description: 'Read a venue-bound executable bid/ask quote with freshness and same-semantic divergence gates.',
      inputSchema: executionInput,
    },
    async (input) => asTextResult(await runtime.runMarket({ ...input, action: 'execution_quote' })),
  );

  const unavailableInput = z.object({ query: z.string().min(1).max(500) });
  for (const name of ['token_research', 'token_risk_check', 'crypto_news_research'] as const) {
    server.registerTool(name, { description: 'Read-only research capability; returns explicit unavailable until a safe public adapter is configured.', inputSchema: unavailableInput }, async () =>
      asTextResult({ ok: false, degraded: true, error: 'capability_not_available' }),
    );
  }

  return server;
}

export function registerMcpRoute(app: FastifyInstance, runtime: ResearchRuntime): void {
  const handler = createMcpHandler(() => createServer(runtime));
  const nodeHandler = toNodeHandler(handler);

  app.all('/mcp', async (request, reply) => {
    reply.hijack();
    await nodeHandler(request.raw, reply.raw, request.body);
  });
}
