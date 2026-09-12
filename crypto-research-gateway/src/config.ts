export const SERVICE_NAME = 'crypto-research-gateway';
export const SERVICE_VERSION = '0.1.0';
export const RUNTIME_MODE = 'zero-local-research-safe';

export function listenPort(): number {
  const value = Number(process.env.PORT ?? 3000);
  return Number.isInteger(value) && value > 0 && value < 65536 ? value : 3000;
}
