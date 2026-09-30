#!/usr/bin/env node
import assert from "node:assert/strict";
import {
  createHash,
  createPrivateKey,
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
  const value = secret.trim();
  if (/-----BEGIN (?:PRIVATE KEY|ED25519 PRIVATE KEY)-----/.test(value)) {
    return createPrivateKey(value);
  }

  let bytes;
  if (/^[0-9a-fA-F]{64}$/.test(value)) {
    bytes = Buffer.from(value, "hex");
  } else {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
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
  return rawSeedToPrivateKey(bytes);
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
  process.stdout.write("SELF_TEST PASS (Ed25519 RFC 8032)\n");
}

async function main() {
  if (process.argv.includes("--self-test")) {
    selfTest();
    return;
  }

  const apiKey = process.env.EXNESS_API_KEY;
  const privateKeyText = process.env.EXNESS_PRIVATE_KEY;
  const accountId = process.env.EXNESS_ACCOUNT_ID;
  const baseUrl = process.env.EXNESS_API_BASE_URL;

  for (const [label, value] of [
    ["EXNESS_API_KEY", apiKey],
    ["EXNESS_PRIVATE_KEY", privateKeyText],
    ["EXNESS_ACCOUNT_ID", accountId],
    ["EXNESS_API_BASE_URL", baseUrl],
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

  let endpoint;
  try {
    const host = new URL(baseUrl);
    if (host.protocol !== "https:" ||
        !/(^|\.)(exness\.com|exness-api\.com)$/i.test(host.hostname) ||
        (host.pathname !== "/" && host.pathname !== "")) {
      throw new Error("invalid host");
    }
    const path = `/v1/configuration/accounts/${accountId.trim()}/account`;
    endpoint = new URL(path, host);
  } catch {
    process.stderr.write("FAIL: EXNESS_API_BASE_URL must be the HTTPS host copied from Exness DNS settings\n");
    process.exitCode = 2;
    return;
  }

  let privateKey;
  try {
    privateKey = parsePrivateKey(privateKeyText);
  } catch {
    process.stderr.write("FAIL: private-key format unsupported; secret value was not displayed\n");
    process.exitCode = 2;
    return;
  }

  const timestamp = Date.now();
  const payload = {
    api_key: apiKey,
    idempotency_key: "",
    timestamp,
    sign_version: 1,
    method: "GET",
    path: endpoint.pathname,
    body_hash: EMPTY_BODY_HASH,
  };
  const payloadBytes = Buffer.from(JSON.stringify(payload), "utf8");
  const headers = {
    "EXN-API-KEY": apiKey,
    "EXN-IDEMPOTENCY-KEY": "",
    "EXN-TIMESTAMP": String(timestamp),
    "EXN-SIGN-VERSION": "1",
    "EXN-DATA": b64url(payloadBytes),
    "EXN-SIGN": b64url(cryptoSign(null, payloadBytes, privateKey)),
    "Accept": "application/json",
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(endpoint, { method: "GET", headers, signal: controller.signal });
    if (response.ok) {
      // Consume but deliberately do not print account details.
      await response.arrayBuffer();
      process.stdout.write(JSON.stringify({
        status: "PASS",
        http_status: response.status,
        authenticated: true,
        read_only_endpoint: "GET /v1/configuration/accounts/{account_id}/account",
        account_details_suppressed: true,
      }) + "\n");
      return;
    }

    let apiError = "";
    try {
      const result = await response.json();
      const candidate = String(result.error_message || "");
      if (/^[A-Z0-9_]{1,80}$/.test(candidate)) apiError = candidate;
      else if (Number.isInteger(result.code)) apiError = `API_CODE_${result.code}`;
    } catch {}
    process.stdout.write(JSON.stringify({
      status: "FAIL",
      http_status: response.status,
      api_error: apiError || "response body suppressed",
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
  } finally {
    clearTimeout(timeout);
    createHash("sha256").update("cleanup").digest();
  }
}

await main();
