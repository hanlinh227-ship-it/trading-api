const DEFAULT_TIMEOUT_MS = 5_000;
const MAX_RESPONSE_BYTES = 2_000_000;

export async function fetchJson(url: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<unknown> {
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      accept: 'application/json',
      'user-agent': 'github-brain-zero-local/0.1',
    },
    signal: AbortSignal.timeout(timeoutMs),
    redirect: 'follow',
  });

  if (!response.ok) {
    throw new Error(`provider_http_${response.status}`);
  }

  const text = await response.text();
  if (Buffer.byteLength(text, 'utf8') > MAX_RESPONSE_BYTES) {
    throw new Error('provider_response_too_large');
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new Error('provider_invalid_json');
  }
}
