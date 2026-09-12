export function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('provider_shape_invalid');
  return value as Record<string, unknown>;
}

export function asArray(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('provider_shape_invalid');
  return value;
}

export function text(value: unknown, field: string): string {
  if (typeof value !== 'string' && typeof value !== 'number') throw new Error(`provider_field_${field}_invalid`);
  return String(value);
}

export function numberValue(value: unknown, field: string): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`provider_field_${field}_invalid`);
  return parsed;
}

export function positivePrice(value: unknown, field: string): number {
  const parsed = numberValue(value, field);
  if (parsed <= 0) throw new Error(`provider_field_${field}_invalid`);
  return parsed;
}

export async function probe(operation: () => Promise<unknown>): Promise<{ ok: boolean; latencyMs: number; error?: string }> {
  const started = Date.now();
  try {
    await operation();
    return { ok: true, latencyMs: Date.now() - started };
  } catch (error) {
    return { ok: false, latencyMs: Date.now() - started, error: error instanceof Error ? error.message : 'provider_probe_failed' };
  }
}
