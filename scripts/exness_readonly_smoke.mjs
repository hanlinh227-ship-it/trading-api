#!/usr/bin/env node
// Rerun trigger after the user updated Exness credentials.
import assert from "node:assert/strict";
import {
  createPrivateKey,
  createPublicKey,
  sign as cryptoSign,
  verify as cryptoVerify,
} from "node:crypto";

const b64url = (input) => Buffer.from(input).toString("base64url");
const EMPTY_BODY_HASH = "47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU";
const PKCS8_ED25519_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");

function rawSeedToPrivateKey(seed) {
  if (seed.length !== 32) throw new Error("unsupported private-key encoding");
  return createPrivateKey({
    key: Buffer.concat([PKCS8_ED25519_PREFIX, seed]),
    format: "der",
    type: "pkcs8",
  });
}

function parsePrivateKey(secret) {
  let value = secret.trim();
  if ((value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1).trim();
  }
  if (value.startsWith("{")) {
    const jwk = JSON.parse(value);
    if (jwk.kty !== "OKP" || jwk.crv !== "Ed25519" || !jwk.d) {
      throw new Error("not an Ed25519 JWK");
    }
    return createPrivateKey({ key: jwk, format: "jwk" });
  }
  if (/-----BEGIN (?:PRIVATE KEY|ED25519 PRIVATE KEY)-----/.test(value)) {
    const key = createPrivateKey(value);
    if (key.asymmetricKeyType !== "ed25519") throw new Error("not an Ed25519 key");
    return key;
  }

  let bytes;
  if (/^0x[0-9a-fA-F]{64}$/i.test(value)) value = value.slice(2);
  if (/^[0-9a-fA-F]{64}$/.test(value)) {
    bytes = Buffer.from(value, "hex");
  } else if (/^[0-9a-fA-F]{128}$/.test(value)) {
    bytes = Buffer.from(value, "hex");
  } else {
    const normalized = value.replace(/\s/g, "").replace(/-/g, "+").replace(/_/g, "/");
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(normalized)) {
      throw new Error("unsupported private-key encoding");
    }
    bytes = Buffer.from(normalized, "base64");
    if (bytes.toString("base64").replace(/=+$/, "") !== normalized.replace(/=+$/, "")) {
      throw new Error("unsupported private-key encoding");
    }
  }

  if (bytes.length === 64) {
    const privateKey = rawSeedToPrivateKey(bytes.subarray(0, 32));
    const derivedPublic = createPublicKey(privateKey).export({ format: "der", type: "spki" }).subarray(-32);
    if (!derivedPublic.equals(bytes.subarray(32))) throw new Error("invalid private-key encoding");
    return privateKey;
  }
  if (bytes.length === 96) {
    const matches = [];
    for (let seedOffset = 0; seedOffset <= 64; seedOffset++) {
      const privateKey = rawSeedToPrivateKey(bytes.subarray(seedOffset, seedOffset + 32));
      const derivedPublic = createPublicKey(privateKey).export({ format: "der", type: "spki" }).subarray(-32);
      for (let publicOffset = 0; publicOffset <= 64; publicOffset += 32) {
        if (Math.abs(seedOffset - publicOffset) >= 32 &&
            derivedPublic.equals(bytes.subarray(publicOffset, publicOffset + 32))) {
          matches.push({ privateKey, seedOffset });
        }
      }
    }
    const unique = new Map(matches.map((match) => [match.seedOffset, match.privateKey]));
    if (unique.size === 1) return [...unique.values()][0];
    throw new Error("96-byte key bundle has no unique Ed25519 seed/public pair");
  }
  if (bytes.length === 32) return rawSeedToPrivateKey(bytes);
  try {
    const key = createPrivateKey({ key: bytes, format: "der", type: "pkcs8" });
    if (key.asymmetricKeyType === "ed25519") return key;
  } catch {}
  throw new Error("unsupported private-key encoding");
}

function privateKeyShape(secret) {
  const value = secret.trim();
  return {
    characters: value.length,
    decodedBase64Bytes: /^[A-Za-z0-9+/_=-]+$/.test(value) ? Buffer.from(value.replace(/-/g, "+").replace(/_/g, "/"), "base64").length : null,
    hasLineBreaks: /[\r\n]/.test(value),
    looksLikePem: /^-----BEGIN [A-Z0-9 ]+-----/.test(value),
    looksLikeJson: value.startsWith("{"),
    is64Hex: /^(?:0x)?[0-9a-f]{64}$/i.test(value),
    is128Hex: /^[0-9a-f]{128}$/i.test(value),
    isBase64AlphabetOnly: /^[A-Za-z0-9+/_=-]+$/.test(value),
    hasOuterQuotes: (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'")),
  };
}

function selfTest() {
  const seed = Buffer.from("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", "hex");
  const expectedPublic = Buffer.from("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "hex");
  const expectedSignature = "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
    + "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b";
  const key = rawSeedToPrivateKey(seed);
  const publicDer = createPublicKey(key).export({ format: "der", type: "spki" });
  assert.deepEqual(publicDer.subarray(-32), expectedPublic);
  const signature = cryptoSign(null, Buffer.alloc(0), key);
  assert.equal(signature.toString("hex"), expectedSignature);
  assert.equal(cryptoVerify(null, Buffer.alloc(0), createPublicKey(key), signature), true);

  const headers = signedGetHeaders("test-key", key, "/v1/trading/access-point?account_id=123");
  const signedPayload = Buffer.from(headers["EXN-DATA"], "base64url");
  const decodedPayload = JSON.parse(signedPayload.toString("utf8"));
  assert.equal(decodedPayload.path, "/v1/trading/access-point?account_id=123");
  assert.equal(headers["EXN-TIMESTAMP"], String(decodedPayload.timestamp));
  assert.equal(
    cryptoVerify(null, signedPayload, createPublicKey(key), Buffer.from(headers["EXN-SIGN"], "base64url")),
    true,
  );
  process.stdout.write("SELF_TEST PASS (Ed25519 and query-string signing)\n");
}

function signedGetHeaders(apiKey, privateKey, pathAndQuery) {
  const timestamp = Date.now();
  const payload = {
    api_key: apiKey,
    idempotency_key: "",
    timestamp,
    sign_version: 1,
    method: "GET",
    path: pathAndQuery,
    body_hash: EMPTY_BODY_HASH,
  };
  const payloadBytes = Buffer.from(JSON.stringify(payload), "utf8");
  return {
    "EXN-API-KEY": apiKey,
    "EXN-IDEMPOTENCY-KEY": "",
    "EXN-TIMESTAMP": String(timestamp),
    "EXN-SIGN-VERSION": "1",
    "EXN-DATA": b64url(payloadBytes),
    "EXN-SIGN": b64url(cryptoSign(null, payloadBytes, privateKey)),
    "Accept": "application/json",
  };
}

async function getJson(url, apiKey, privateKey) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: signedGetHeaders(apiKey, privateKey, url.pathname + url.search),
      signal: controller.signal,
    });
    let data = null;
    try { data = await response.json(); } catch {}
    return { response, data };
  } finally {
    clearTimeout(timeout);
  }
}

function safeApiError(data) {
  if (!data || typeof data !== "object") return "response body suppressed";
  const candidate = String(data.error_message || data.error?.message || "");
  if (/^[A-Z0-9_]{1,80}$/.test(candidate)) return candidate;
  const code = data.code ?? data.error?.code;
  if (Number.isInteger(code)) return `API_CODE_${code}`;
  return "response body suppressed";
}

async function main() {
  if (process.argv.includes("--self-test")) {
    selfTest();
    return;
  }

  const apiKey = process.env.EXNESS_API_KEY;
  const privateKeyText = process.env.EXNESS_PRIVATE_KEY;
  const accountId = process.env.EXNESS_ACCOUNT_ID;

  for (const [label, value] of [
    ["EXNESS_API_KEY", apiKey],
    ["EXNESS_PRIVATE_KEY", privateKeyText],
    ["EXNESS_ACCOUNT_ID", accountId],
  ]) {
    if (!value || !value.trim()) {
      process.stderr.write(`FAIL: missing ${label}\n`);
      process.exitCode = 2;
      return;
    }
  }

  if (!/^\d{1,20}$/.test(accountId.trim())) {
    process.stderr.write("FAIL: EXNESS_ACCOUNT_ID format invalid\n");
    process.exitCode = 2;
    return;
  }

  let privateKey;
  try {
    privateKey = parsePrivateKey(privateKeyText);
  } catch {
    process.stderr.write(`FAIL: private-key format unsupported; safe shape only: ${JSON.stringify(privateKeyShape(privateKeyText))}\n`);
    process.exitCode = 2;
    return;
  }

  const discoveryUrl = new URL(
    `/v1/trading/access-point?account_id=${encodeURIComponent(accountId.trim())}`,
    "https://api.exness.com",
  );

  try {
    const { response: discoveryResponse, data: discoveryData } =
      await getJson(discoveryUrl, apiKey, privateKey);
    if (!discoveryResponse.ok) {
      process.stdout.write(JSON.stringify({
        status: "FAIL",
        stage: "access_point_discovery",
        http_status: discoveryResponse.status,
        api_error: safeApiError(discoveryData),
        secrets_or_account_data_printed: false,
      }) + "\n");
      process.exitCode = 1;
      return;
    }

    const rawAccessPoint =
      discoveryData?.access_point ??
      discoveryData?.data?.access_point ??
      discoveryData?.result?.access_point;
    let accessPointUrl;
    try {
      if (typeof rawAccessPoint !== "string" || !rawAccessPoint.trim()) {
        throw new Error("missing access point");
      }
      const raw = rawAccessPoint.trim();
      accessPointUrl = new URL(/^https:\/\//i.test(raw) ? raw : `https://${raw}`);
      const hostname = accessPointUrl.hostname.replace(/\.$/, "");
      if (accessPointUrl.protocol !== "https:" ||
          accessPointUrl.username || accessPointUrl.password ||
          (accessPointUrl.port && accessPointUrl.port !== "443") ||
          (accessPointUrl.pathname !== "/" && accessPointUrl.pathname !== "") ||
          accessPointUrl.search || accessPointUrl.hash ||
          !/^ap-[a-z0-9-]+(?:\.trading)?\.exness\.com$/i.test(hostname)) {
        throw new Error("untrusted host");
      }
      accessPointUrl.hostname = hostname;
    } catch {
      process.stdout.write(JSON.stringify({
        status: "FAIL",
        stage: "access_point_discovery",
        reason: "unexpected_access_point_host",
        response_fields: discoveryData && typeof discoveryData === "object"
          ? Object.keys(discoveryData).filter((key) => /^[a-zA-Z0-9_]{1,40}$/.test(key)).slice(0, 12)
          : [],
        nested_data_fields: discoveryData?.data && typeof discoveryData.data === "object"
          ? Object.keys(discoveryData.data).filter((key) => /^[a-zA-Z0-9_]{1,40}$/.test(key)).slice(0, 12)
          : [],
        access_point_type: typeof rawAccessPoint,
        secrets_or_account_data_printed: false,
      }) + "\n");
      process.exitCode = 1;
      return;
    }

    const accountUrl = new URL(
      `/v1/configuration/accounts/${accountId.trim()}/account`,
      accessPointUrl,
    );
    const { response: accountResponse, data: accountData } =
      await getJson(accountUrl, apiKey, privateKey);
    if (accountResponse.ok) {
      process.stdout.write(JSON.stringify({
        status: "PASS",
        http_status: accountResponse.status,
        authenticated: true,
        read_only_endpoint: "GET /v1/configuration/accounts/{account_id}/account",
        account_details_suppressed: true,
      }) + "\n");
      return;
    }

    process.stdout.write(JSON.stringify({
      status: "FAIL",
      stage: "account_read",
      http_status: accountResponse.status,
      api_error: safeApiError(accountData),
      secrets_or_account_data_printed: false,
    }) + "\n");
    process.exitCode = 1;
  } catch (error) {
    process.stdout.write(JSON.stringify({
      status: "FAIL",
      reason: error?.name === "AbortError" ? "timeout after 15 seconds" : "network or TLS error",
      secrets_or_account_data_printed: false,
    }) + "\n");
    process.exitCode = 1;
  }
}

await main();
