import { describe, expect, it } from 'vitest';
import { DEFAULT_SCANNER_CONFIG, loadScannerConfig } from '../src/scanner/config.js';

describe('multi-coin scanner config', () => {
  it('loads positive staged-scan thresholds with no BTC preference', () => {
    const config = loadScannerConfig();
    expect(config.venues).toEqual(['bybit', 'binance', 'okx']);
    expect(config.minVenueCoverage).toBe(2);
    expect(config.broadCandidateLimit).toBeGreaterThan(0);
    expect(config.deepCandidateLimit).toBeGreaterThan(0);
    expect(config.deepCandidateLimit).toBeLessThanOrEqual(config.broadCandidateLimit);
    expect(config.minQuoteVolumeUsd).toBeGreaterThan(0);
    expect(config.maxSpreadBps).toBeGreaterThan(0);
    expect(config.minNearTouchDepthUsd).toBeGreaterThan(0);
    expect(config.minCandleHistory).toBeGreaterThan(0);
    expect(config.minRewardRisk).toBeGreaterThan(0);
    expect(config.tieToleranceScore).toBeGreaterThan(0);
    expect(JSON.stringify(config).toLowerCase()).not.toContain('preferredsymbol');
    expect(JSON.stringify(config).toLowerCase()).not.toContain('btcbonus');
    expect(DEFAULT_SCANNER_CONFIG.researchOnly).toBe(true);
    expect(DEFAULT_SCANNER_CONFIG.productionExecutionAuthority).toBe(false);
  });

  it('rejects invalid staged-scan thresholds', () => {
    expect(() => loadScannerConfig({ broadCandidateLimit: 0 })).toThrow();
    expect(() => loadScannerConfig({ deepCandidateLimit: -1 })).toThrow();
    expect(() => loadScannerConfig({ minVenueCoverage: 1 })).toThrow();
    expect(() => loadScannerConfig({ minRewardRisk: 0 })).toThrow();
    expect(() => loadScannerConfig({ broadCandidateLimit: 4, deepCandidateLimit: 5 })).toThrow();
  });

  it('keeps authority fixed to research-only regardless of overrides', () => {
    const config = loadScannerConfig({ maxSpreadBps: 12 });
    expect(config.authorityToken).toBe('MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0');
    expect(config.researchOnly).toBe(true);
    expect(config.productionExecutionAuthority).toBe(false);
    expect(config.livePricePolicyPath).toBe('AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml');
  });
});
