import { z } from 'zod';

export const instrumentTypeSchema = z.enum(['spot', 'perpetual', 'delivery_futures', 'index']);
export const priceSemanticSchema = z.enum(['last', 'mark', 'index', 'bid', 'ask', 'mid']);

export type InstrumentType = z.infer<typeof instrumentTypeSchema>;
export type PriceSemantic = z.infer<typeof priceSemanticSchema>;

export const marketObservationSchema = z.object({
  provider: z.string().min(1),
  venue: z.string().min(1),
  symbol: z.string().min(1),
  instrumentType: instrumentTypeSchema,
  quoteCurrency: z.string().min(1),
  priceSemantic: priceSemanticSchema,
  price: z.number().finite().positive(),
  sourceTimestampMs: z.number().finite().nonnegative(),
  receivedTimestampMs: z.number().finite().nonnegative(),
}).strict();

export type MarketObservation = z.infer<typeof marketObservationSchema>;

export function normalizeObservation(input: unknown): MarketObservation {
  return marketObservationSchema.parse(input);
}
