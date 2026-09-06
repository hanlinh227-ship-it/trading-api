import fs from "node:fs";

const cfg = JSON.parse(
  fs.readFileSync(new URL("../config/runtime.json", import.meta.url))
);

const SOL = "So11111111111111111111111111111111111111112";
const USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

async function rpcHealth() {
  const start = Date.now();

  const r = await fetch(cfg.rpc, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "getHealth"
    })
  });

  const body = await r.json();

  return {
    ok: r.ok && body.result === "ok",
    http: r.status,
    latencyMs: Date.now() - start
  };
}

async function jupiterHealth() {
  const url =
    `${cfg.jupiter}/swap/v2/order` +
    `?inputMint=${SOL}` +
    `&outputMint=${USDC}` +
    `&amount=10000000`;

  const r = await fetch(url);
  const body = await r.json();

  return {
    ok: r.ok && Boolean(body.outAmount),
    http: r.status,
    outAmount: body.outAmount ?? null,
    priceImpactPct: body.priceImpactPct ?? null,
    transactionCreated: Boolean(body.transaction)
  };
}

async function dexHealth() {
  const r = await fetch(
    `${cfg.dexscreener}/latest/dex/tokens/${SOL}`
  );

  const body = await r.json();

  return {
    ok: r.ok && Array.isArray(body.pairs),
    http: r.status,
    pairs: body.pairs?.length ?? 0
  };
}

console.log("=== MEME ALPHA HEALTH ===");
console.log("MODE:", cfg.mode);

const results = {
  timestamp: new Date().toISOString(),
  mode: cfg.mode,
  solana: await rpcHealth(),
  jupiter: await jupiterHealth(),
  dexscreener: await dexHealth()
};

console.log(JSON.stringify(results, null, 2));

if (
  !results.solana.ok ||
  !results.jupiter.ok ||
  !results.dexscreener.ok
) {
  process.exit(1);
}

console.log("HEALTH_STATUS=PASS");
