export type ScannerVenue = 'bybit' | 'binance' | 'okx';
export type TradeDirection = 'LONG' | 'SHORT';
export type CandidateState = 'A+ LIVE CANDIDATE' | 'WATCHLIST' | 'NO A+ SETUP';
export type SetupFamily = 'SWEEP_RECLAIM' | 'BREAK_RETEST' | 'DISPLACEMENT_RETEST' | 'REGIME_CONTINUATION';

export type PerpetualMarketSummary = {
  venue: ScannerVenue;
  symbol: string;
  rawSymbol: string;
  instrumentType: 'perpetual';
  quoteCurrency: 'USDT';
  active: boolean;
  bid?: number;
  ask?: number;
  last?: number;
  quoteVolumeUsd?: number;
  sourceTimestampMs: number;
  receivedTimestampMs: number;
};

export type NormalizedCandle = {
  openTimeMs: number;
  closeTimeMs: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
};

export type TradePrint = {
  venue: ScannerVenue;
  symbol: string;
  price: number;
  quantity: number;
  notional: number;
  side: 'BUYER_TAKER' | 'SELLER_TAKER';
  sourceTimestampMs: number;
};

export type BookLevel = { price: number; quantity: number };
export type OrderBookSnapshot = {
  venue: ScannerVenue;
  symbol: string;
  bids: BookLevel[];
  asks: BookLevel[];
  sourceTimestampMs: number;
  receivedTimestampMs: number;
};

export type DerivativesContext = {
  venue: ScannerVenue;
  symbol: string;
  openInterest?: number;
  openInterestChangePct?: number;
  fundingRate?: number;
  premiumBps?: number;
  globalLongShortRatio?: number;
  topTraderLongShortRatio?: number;
  sourceTimestampMs?: number;
};

export type StructureSignal = {
  family: SetupFamily;
  direction: TradeDirection;
  trigger: string;
  entryZone: { low: number; high: number };
  invalidation: string;
  stop: number;
  targets: number[];
  rewardRisk: number;
  timeframe: string;
  sourceTimestampMs: number;
};

export type GateResult = {
  gate: string;
  passed: boolean;
  reason?: string;
};

export type CandidateEvidence = {
  symbol: string;
  direction: TradeDirection;
  structure: StructureSignal;
  gates: GateResult[];
  componentScores: Record<string, number>;
  selectedVenue?: ScannerVenue;
  quoteAgeMs?: number;
  executablePrice?: number;
  crossVenueDeviationBps?: number;
  researchOnly: true;
  productionExecutionAuthority: false;
  executionAuthority: 'none';
};

export type ScanCandidate = CandidateEvidence & {
  state: Exclude<CandidateState, 'NO A+ SETUP'>;
  score: number;
  rationale: string[];
};

export type ScanResult = {
  state: CandidateState;
  scannerAuthority: 'MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0';
  topCandidate?: ScanCandidate;
  watchlist: ScanCandidate[];
  rejected: Record<string, string[]>;
  researchOnly: true;
  productionExecutionAuthority: false;
  executionAuthority: 'none';
};
