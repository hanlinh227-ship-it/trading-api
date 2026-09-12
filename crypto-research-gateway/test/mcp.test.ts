import { describe, expect, it } from 'vitest';
import { READ_ONLY_TOOL_NAMES, isReadOnlyToolName } from '../src/mcp/server.js';

describe('MCP tool surface', () => {
  it('exposes only the approved read-only tool names', () => {
    expect(READ_ONLY_TOOL_NAMES).toEqual([
      'market_snapshot',
      'market_candles',
      'market_orderbook',
      'market_execution_quote',
      'derivatives_funding_oi',
      'token_research',
      'token_risk_check',
      'crypto_news_research',
    ]);
  });

  it('recognizes market_execution_quote as read-only', () => {
    expect(isReadOnlyToolName('market_execution_quote')).toBe(true);
  });

  it('rejects write-oriented tool names', () => {
    for (const name of ['place_order', 'cancel_order', 'withdraw', 'transfer', 'swap', 'bridge', 'wallet_send', 'payment']) {
      expect(isReadOnlyToolName(name)).toBe(false);
    }
  });
});
