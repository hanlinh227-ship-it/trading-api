import { z } from 'zod';
import type { ScannerVenue } from './types.js';

export const SCANNER_AUTHORITY_TOKEN = 'MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0' as const;
export const SCANNER_VENUES = ['bybit', 'binance', 'okx'] as const satisfies readonly ScannerVenue[];
export const LIVE_PRICE_POLICY_PATH = 'AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml' as const;

const scannerConfigSchema = z.object({
  authorityToken: z.literal(SCANNER_AUTHORITY_TOKEN),
  researchOnly: z.literal(true),
  productionExecutionAuthority: z.literal(false),
  livePricePolicyPath: z.literal(LIVE_PRICE_POLICY_PATH),
  venues: z.tuple([z.literal('bybit'), z.literal('binance'), z.literal('okx')]),
  minVenueCoverage: z.number().int().min(2).max(3),
  broadCandidateLimit: z.number().int().positive(),
  deepCandidateLimit: z.number().int().positive(),
  minQuoteVolumeUsd: z.number().positive(),
  maxSpreadBps: z.number().positive(),
  minNearTouchDepthUsd: z.number().positive(),
  minCandleHistory: z.number().int().positive(),
  minRewardRisk: z.number().positive(),
  tieToleranceScore: z.number().positive(),
  weights: z.object({
    structure: z.number().nonnegative(),
    triggerQuality: z.number().nonnegative(),
    executedFlow: z.number().nonnegative(),
    l2Microprice: z.number().nonnegative(),
    openInterest: z.number().nonnegative(),
    fundingCrowding: z.number().nonnegative(),
    liquidationContext: z.number().nonnegative(),
    crossVenueConsistency: z.number().nonnegative(),
    liquidityExecutionQuality: z.number().nonnegative(),
    rewardRisk: z.number().nonnegative(),
    freshnessCompleteness: z.number().nonnegative(),
  }),
}).superRefine((value, ctx) => {
  if (value.deepCandidateLimit > value.broadCandidateLimit) {
    ctx.addIssue({
      code: 'custom',
      path: ['deepCandidateLimit'],
      message: 'deepCandidateLimit must be <= broadCandidateLimit',
    });
  }
  const totalWeight = Object.values(value.weights).reduce((sum, weight) => sum + weight, 0);
  if (totalWeight <= 0) {
    ctx.addIssue({ code: 'custom', path: ['weights'], message: 'scanner weights must sum to a positive value' });
  }
});

export type ScannerConfig = z.infer<typeof scannerConfigSchema>;
export type ScannerConfigOverrides = Partial<Pick<ScannerConfig,
  | 'minVenueCoverage'
  | 'broadCandidateLimit'
  | 'deepCandidateLimit'
  | 'minQuoteVolumeUsd'
  | 'maxSpreadBps'
  | 'minNearTouchDepthUsd'
  | 'minCandleHistory'
  | 'minRewardRisk'
  | 'tieToleranceScore'
>> & { weights?: Partial<ScannerConfig['weights']> };

const defaultScannerConfigValue = scannerConfigSchema.parse({
  authorityToken: SCANNER_AUTHORITY_TOKEN,
  researchOnly: true,
  productionExecutionAuthority: false,
  livePricePolicyPath: LIVE_PRICE_POLICY_PATH,
  venues: SCANNER_VENUES,
  minVenueCoverage: 2,
  broadCandidateLimit: 30,
  deepCandidateLimit: 8,
  minQuoteVolumeUsd: 10_000_000,
  maxSpreadBps: 8,
  minNearTouchDepthUsd: 100_000,
  minCandleHistory: 120,
  minRewardRisk: 2,
  tieToleranceScore: 1.5,
  weights: {
    structure: 24,
    triggerQuality: 14,
    executedFlow: 12,
    l2Microprice: 8,
    openInterest: 8,
    fundingCrowding: 6,
    liquidationContext: 4,
    crossVenueConsistency: 8,
    liquidityExecutionQuality: 8,
    rewardRisk: 5,
    freshnessCompleteness: 3,
  },
});

export const DEFAULT_SCANNER_CONFIG: Readonly<ScannerConfig> = Object.freeze(defaultScannerConfigValue);

export function loadScannerConfig(overrides: ScannerConfigOverrides = {}): ScannerConfig {
  return scannerConfigSchema.parse({
    ...DEFAULT_SCANNER_CONFIG,
    ...overrides,
    weights: {
      ...DEFAULT_SCANNER_CONFIG.weights,
      ...(overrides.weights ?? {}),
    },
  });
}
