const TRUST = Object.freeze({
  issuer: 'https://token.actions.githubusercontent.com',
  audience: 'android-brain-agent-gateway',
  repository: 'hanlinh227-ship-it/trading-api',
  repositoryId: '1335593524',
  owner: 'hanlinh227-ship-it',
  actor: 'hanlinh227-ship-it',
  eventName: 'issues',
})

function base64UrlToBytes(value) {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)
  const binary = atob(padded)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i)
  return out
}

function decodeJsonPart(value) {
  return JSON.parse(new TextDecoder().decode(base64UrlToBytes(value)))
}

export function validateGitHubClaims(claims, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!claims || claims.iss !== TRUST.issuer) throw new Error('invalid_issuer')
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (!aud.includes(TRUST.audience)) throw new Error('invalid_audience')
  if (claims.repository !== TRUST.repository) throw new Error('invalid_repository')
  if (String(claims.repository_id) !== TRUST.repositoryId) throw new Error('invalid_repository_id')
  if (claims.repository_owner !== TRUST.owner) throw new Error('invalid_repository_owner')
  if (claims.actor !== TRUST.actor) throw new Error('invalid_actor')
  if (claims.event_name !== TRUST.eventName) throw new Error('invalid_event')
  if (!Number.isFinite(Number(claims.exp)) || Number(claims.exp) <= nowSeconds) throw new Error('token_expired')
  if (claims.nbf != null && Number(claims.nbf) > nowSeconds + 30) throw new Error('token_not_yet_valid')
  return true
}

let cachedJwks = null
let cachedAt = 0

async function loadJwks(fetchImpl) {
  if (cachedJwks && Date.now() - cachedAt < 5 * 60 * 1000) return cachedJwks
  const configResponse = await fetchImpl(`${TRUST.issuer}/.well-known/openid-configuration`, { cf: { cacheTtl: 300 } })
  if (!configResponse.ok) throw new Error('oidc_config_unavailable')
  const config = await configResponse.json()
  if (!config.jwks_uri) throw new Error('oidc_jwks_uri_missing')
  const jwksResponse = await fetchImpl(config.jwks_uri, { cf: { cacheTtl: 300 } })
  if (!jwksResponse.ok) throw new Error('oidc_jwks_unavailable')
  cachedJwks = await jwksResponse.json()
  cachedAt = Date.now()
  return cachedJwks
}

export async function verifyGitHubOidcToken(token, fetchImpl = fetch) {
  if (!token || typeof token !== 'string') throw new Error('oidc_token_missing')
  const parts = token.split('.')
  if (parts.length !== 3) throw new Error('invalid_jwt')
  const [encodedHeader, encodedPayload, encodedSignature] = parts
  const header = decodeJsonPart(encodedHeader)
  const claims = decodeJsonPart(encodedPayload)
  if (header.alg !== 'RS256' || !header.kid) throw new Error('unsupported_jwt_header')

  const jwks = await loadJwks(fetchImpl)
  const jwk = (jwks.keys ?? []).find(key => key.kid === header.kid && key.kty === 'RSA')
  if (!jwk) throw new Error('oidc_signing_key_not_found')
  const key = await crypto.subtle.importKey(
    'jwk',
    jwk,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  )
  const ok = await crypto.subtle.verify(
    { name: 'RSASSA-PKCS1-v1_5' },
    key,
    base64UrlToBytes(encodedSignature),
    new TextEncoder().encode(`${encodedHeader}.${encodedPayload}`),
  )
  if (!ok) throw new Error('invalid_oidc_signature')
  validateGitHubClaims(claims)
  return claims
}
