import type { MarketObservation, PriceSemantic } from '../normalization/market-normalizer.js';

export type TradeSide = 'LONG' | 'SHORT';
export type ExecutionStatus = 'OK' | 'STALE_PRICE' | 'PRICE_DIVERGENCE' | 'SEMANTIC_MISMATCH' | 'VENUE_UNAVAILABLE';

export type LivePricePolicy = {
  executableTargetMs: number;
  executableHardStaleMs: number;
  contextualMaxAgeMs: number;
  divergenceBps: number;
};

export type CrossVenueQuote = {
  venue: string;
  semantic: 'bid' | 'ask' | 'last' | 'mark' | 'index' | 'mid';
  price: number;
  sourceTimestampMs: number;
  quoteAgeMs: number;
  deviationBps: number;
};

export type ExecutionQuote = {
  venue: string;
  symbol: string;
  instrumentType: 'perpetual' | 'spot';
  side: TradeSide;
  executableSemantic?: 'ask' | 'bid';
  executablePrice?: number;
  bid?: number;
  ask?: number;
  mid?: number;
  last?: number;
  mark?: number;
  index?: number;
  sourceTimestampMs?: number;
  receivedTimestampMs?: number;
  quoteAgeMs?: number;
  spreadBps?: number;
  fresh: boolean;
  executionVerified: boolean;
  status: ExecutionStatus;
  reason?: string;
  crossVenue?: CrossVenueQuote[];
};

const DEFAULT_POLICY: LivePricePolicy = {
  executableTargetMs: 2_000,
  executableHardStaleMs: 5_000,
  contextualMaxAgeMs: 10_000,
  divergenceBps: 30,
};

function canonical(value: string): string {
  return value.replace(/[-_/]/g, '').toUpperCase();
}

function timestampValid(item: MarketObservation): boolean {
  return Number.isFinite(item.sourceTimestampMs)
    && item.sourceTimestampMs > 0
    && Number.isFinite(item.receivedTimestampMs)
    && item.receivedTimestampMs > 0;
}

function quoteAgeMs(item: MarketObservation): number {
  return Math.max(0, item.receivedTimestampMs - item.sourceTimestampMs);
}

function latest(items: MarketObservation[], semantic: PriceSemantic): MarketObservation | undefined {
  return items
    .filter((item) => item.priceSemantic === semantic)
    .sort((a, b) => b.sourceTimestampMs - a.sourceTimestampMs)[0];
}

function failure(input: {
  venue: string;
  symbol: string;
  instrumentType: 'perpetual' | 'spot';
  side: TradeSide;
  status: Exclude<ExecutionStatus, 'OK'>;
  reason: string;
  executableSemantic?: 'ask' | 'bid';
  executablePrice?: number;
  bid?: number;
  ask?: number;
  mid?: number;
  sourceTimestampMs?: number;
  receivedTimestampMs?: number;
  quoteAgeMs?: number;
  spreadBps?: number;
  crossVenue?: CrossVenueQuote[];
}): ExecutionQuote {
  return {
    venue: input.venue,
    symbol: canonical(input.symbol),
    instrumentType: input.instrumentType,
    side: input.side,
    executableSemantic: input.executableSemantic,
    executablePrice: input.executablePrice,
    bid: input.bid,
    ask: input.ask,
    mid: input.mid,
    sourceTimestampMs: input.sourceTimestampMs,
    receivedTimestampMs: input.receivedTimestampMs,
    quoteAgeMs: input.quoteAgeMs,
    spreadBps: input.spreadBps,
    fresh: false,
    executionVerified: false,
    status: input.status,
    reason: input.reason,
    crossVenue: input.crossVenue,
  };
}

export function buildExecutionQuote(input: {
  venue: string;
  symbol: string;
  instrumentType: 'spot' | 'perpetual';
  side: TradeSide;
  observations: MarketObservation[];
  crossVenueObservations?: MarketObservation[];
  policy?: LivePricePolicy;
}): ExecutionQuote {
  const policy = input.policy ?? DEFAULT_POLICY;
  const wantedSymbol = canonical(input.symbol);
  const venue = input.venue.toLowerCase();
  const semantic: 'ask' | 'bid' = input.side === 'LONG' ? 'ask' : 'bid';

  const venueRows = input.observations.filter((item) =>
    item.venue.toLowerCase() === venue && canonical(item.symbol) === wantedSymbol,
  );
  if (venueRows.length === 0) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'VENUE_UNAVAILABLE',
      reason: 'execution_venue_has_no_observations',
      executableSemantic: semantic,
    });
  }

  const exactRows = venueRows.filter((item) => item.instrumentType === input.instrumentType);
  if (exactRows.length === 0) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'SEMANTIC_MISMATCH',
      reason: 'instrument_mismatch',
      executableSemantic: semantic,
    });
  }

  const quoteCurrencies = new Set(exactRows.map((item) => item.quoteCurrency.toUpperCase()));
  if (quoteCurrencies.size !== 1) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'SEMANTIC_MISMATCH',
      reason: 'quote_currency_mismatch',
      executableSemantic: semantic,
    });
  }

  const bidRow = latest(exactRows, 'bid');
  const askRow = latest(exactRows, 'ask');
  if (!bidRow || !askRow || !timestampValid(bidRow) || !timestampValid(askRow)) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'SEMANTIC_MISMATCH',
      reason: 'missing_or_invalid_executable_semantics',
      executableSemantic: semantic,
    });
  }

  const bid = bidRow.price;
  const ask = askRow.price;
  if (!Number.isFinite(bid) || !Number.isFinite(ask) || bid <= 0 || ask <= 0 || ask < bid) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'SEMANTIC_MISMATCH',
      reason: 'invalid_execution_book',
      executableSemantic: semantic,
      bid,
      ask,
    });
  }

  const mid = (bid + ask) / 2;
  const spreadBps = ((ask - bid) / mid) * 10_000;
  if (!Number.isFinite(mid) || !Number.isFinite(spreadBps)) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'SEMANTIC_MISMATCH',
      reason: 'invalid_execution_spread',
      executableSemantic: semantic,
      bid,
      ask,
    });
  }

  const executableRow = semantic === 'ask' ? askRow : bidRow;
  const executablePrice = executableRow.price;
  const age = quoteAgeMs(executableRow);
  if (age > policy.executableHardStaleMs) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'STALE_PRICE',
      reason: 'executable_quote_too_old',
      executableSemantic: semantic,
      executablePrice,
      bid,
      ask,
      mid,
      sourceTimestampMs: executableRow.sourceTimestampMs,
      receivedTimestampMs: executableRow.receivedTimestampMs,
      quoteAgeMs: age,
      spreadBps,
    });
  }

  const crossVenue: CrossVenueQuote[] = [];
  const quoteCurrency = executableRow.quoteCurrency.toUpperCase();
  for (const item of input.crossVenueObservations ?? []) {
    if (
      item.venue.toLowerCase() === venue
      || canonical(item.symbol) !== wantedSymbol
      || item.instrumentType !== input.instrumentType
      || item.quoteCurrency.toUpperCase() !== quoteCurrency
      || item.priceSemantic !== semantic
      || !timestampValid(item)
    ) {
      continue;
    }
    const secondaryAge = quoteAgeMs(item);
    if (secondaryAge > policy.executableHardStaleMs) continue;
    const deviationBps = Math.abs(item.price - executablePrice) / executablePrice * 10_000;
    crossVenue.push({
      venue: item.venue,
      semantic,
      price: item.price,
      sourceTimestampMs: item.sourceTimestampMs,
      quoteAgeMs: secondaryAge,
      deviationBps,
    });
  }

  if (crossVenue.some((item) => item.deviationBps > policy.divergenceBps)) {
    return failure({
      venue,
      symbol: wantedSymbol,
      instrumentType: input.instrumentType,
      side: input.side,
      status: 'PRICE_DIVERGENCE',
      reason: 'material_same_semantic_cross_venue_divergence',
      executableSemantic: semantic,
      executablePrice,
      bid,
      ask,
      mid,
      sourceTimestampMs: executableRow.sourceTimestampMs,
      receivedTimestampMs: executableRow.receivedTimestampMs,
      quoteAgeMs: age,
      spreadBps,
      crossVenue,
    });
  }

  const lastRow = latest(exactRows, 'last');
  const markRow = latest(exactRows, 'mark');
  const indexRow = latest(exactRows, 'index');
  const contextual = (row: MarketObservation | undefined): number | undefined => {
    if (!row || !timestampValid(row) || quoteAgeMs(row) > policy.contextualMaxAgeMs) return undefined;
    return row.price;
  };

  return {
    venue,
    symbol: wantedSymbol,
    instrumentType: input.instrumentType,
    side: input.side,
    executableSemantic: semantic,
    executablePrice,
    bid,
    ask,
    mid,
    last: contextual(lastRow),
    mark: contextual(markRow),
    index: contextual(indexRow),
    sourceTimestampMs: executableRow.sourceTimestampMs,
    receivedTimestampMs: executableRow.receivedTimestampMs,
    quoteAgeMs: age,
    spreadBps,
    fresh: age <= policy.executableTargetMs,
    executionVerified: true,
    status: 'OK',
    crossVenue,
  };
}
