import fs from "node:fs";

const cfg = JSON.parse(
  fs.readFileSync(
    new URL("../config/runtime.json", import.meta.url),
    "utf8"
  )
);

const WSOL = "So11111111111111111111111111111111111111112";
const USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

const TOKEN2022 =
  "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";

const ENDPOINTS = [
  ["recent", "recent"],
  ["toptraded", "toptraded/5m?limit=50"],
  ["toptrending", "toptrending/5m?limit=50"],
  ["organic", "toporganicscore/5m?limit=50"]
];

const DISCOVERY_CACHE =
  "/var/lib/meme-alpha/data/paper/discovery-last-good.json";

const DISCOVERY_HEALTH =
  "/var/lib/meme-alpha/data/paper/scanner-source-health.json";

const DISCOVERY_MIN_UNIQUE = 20;
const DISCOVERY_MIN_SOURCES = 2;
const DISCOVERY_RADAR_MIN_MATCHES = 3;
const DISCOVERY_RADAR_ONLY_MAX = 240; // FAST_DISCOVERY_V372_CAP
const DISCOVERY_CACHE_MAX_AGE_MS = 5 * 60 * 1000;

// NEW_LISTING_RADAR_V312: discovery-only cross-confirmation.
const NEW_LISTING_RADAR =
  "/opt/meme-alpha/app/runtime-status/new-listing-radar.json";


let discoveryHealth = {
  status: "INIT",
  checkedAt: null,
  successfulSources: 0,
  failedSources: 0,
  discoveredUnique: 0,
  usingCache: false,
  cacheAgeMs: null,
  allowNewEntries: false,
  failures: []
};

function sleep(ms) {
  return new Promise(
    resolve => setTimeout(resolve, ms)
  );
}

function atomicJSON(path, value) {
  const tmp =
    `${path}.tmp-${process.pid}`;

  fs.writeFileSync(
    tmp,
    JSON.stringify(
      value,
      null,
      2
    )
  );

  fs.renameSync(
    tmp,
    path
  );
}

const JUPITER_MIN_INTERVAL_MS = 3200;
let lastJupiterRequestAt = 0;
async function paceJupiter() {
  const wait = Math.max(0, JUPITER_MIN_INTERVAL_MS - (Date.now() - lastJupiterRequestAt));
  if (wait > 0) await new Promise(resolve => setTimeout(resolve, wait));
  lastJupiterRequestAt = Date.now();
}

async function getJSON(url) {
  if (String(url).startsWith(String(cfg.jupiter))) await paceJupiter();
  const maxAttempts = 1;
  let lastError = null;

  for (
    let attempt = 1;
    attempt <= maxAttempts;
    attempt++
  ) {
    const controller =
      new AbortController();

    const timer =
      setTimeout(
        () => controller.abort(),
        6000
      );

    try {
      const r = await fetch(
        url,
        {
          headers: {
            "accept":
              "application/json"
          },
          signal:
            controller.signal
        }
      );

      if (r.ok) {
        return await r.json();
      }

      const retryAfter =
        Number(
          r.headers.get(
            "retry-after"
          )
        );

      const err =
        new Error(
          `HTTP ${r.status}: ${url}`
        );

      err.httpStatus =
        r.status;

      lastError = err;

      if (
        r.status === 429 &&
        attempt < maxAttempts
      ) {
        const delay =
          Number.isFinite(retryAfter) &&
          retryAfter > 0
            ? Math.min(
                retryAfter * 1000,
                10000
              )
            : 1200 *
              Math.pow(
                2,
                attempt - 1
              );

        console.error(
          `RATE_LIMIT attempt=${attempt}/${maxAttempts} wait=${delay}ms ${url}`
        );

        await sleep(delay);
        continue;
      }

      if (
        r.status >= 500 &&
        attempt < maxAttempts
      ) {
        const delay =
          1000 *
          Math.pow(
            2,
            attempt - 1
          );

        console.error(
          `UPSTREAM_RETRY attempt=${attempt}/${maxAttempts} wait=${delay}ms ${url}`
        );

        await sleep(delay);
        continue;
      }

      throw err;

    } catch (err) {
      lastError = err;

      if (
        (
          err?.name ===
          "AbortError"
        ) &&
        attempt < maxAttempts
      ) {
        await sleep(
          1000 *
          Math.pow(
            2,
            attempt - 1
          )
        );

        continue;
      }

      if (
        err?.httpStatus === 429 ||
        err?.httpStatus >= 500
      ) {
        if (
          attempt < maxAttempts
        ) {
          continue;
        }
      }

      throw err;

    } finally {
      clearTimeout(timer);
    }
  }

  throw (
    lastError ||
    new Error(
      `FETCH_FAILED: ${url}`
    )
  );
}

async function discovery() {
  const map = new Map();

  let successfulSources = 0;
  let failedSources = 0;

  const failures = [];

  for (
    let i = 0;
    i < ENDPOINTS.length;
    i++
  ) {
    const [source, endpoint] =
      ENDPOINTS[i];

    try {
      const rows = await getJSON(
        `${cfg.jupiter}/tokens/v2/${endpoint}`
      );

      if (!Array.isArray(rows)) {
        throw new Error(
          `INVALID_RESPONSE_${source}`
        );
      }

      successfulSources++;

      for (const token of rows) {
        if (!token?.id) {
          continue;
        }

        if (!map.has(token.id)) {
          map.set(
            token.id,
            {
              ...token,
              sources: []
            }
          );
        }

        const existing =
          map.get(token.id);

        existing.sources.push(
          source
        );

        for (
          const [k, v] of
          Object.entries(token)
        ) {
          if (
            v !== null &&
            v !== undefined
          ) {
            existing[k] = v;
          }
        }
      }

    } catch (err) {
      failedSources++;

      failures.push({
        source,
        error:
          String(
            err?.message || err
          ).slice(0,200)
      });

      console.error(
        `DISCOVERY_FAIL ${source}:`,
        err.message
      );
    }

    /*
     * Avoid burst requests against
     * the unauthenticated Jupiter API.
     */
    if (
      i <
      ENDPOINTS.length - 1
    ) {
      await sleep(750);
    }
    if (i >= 1 && successfulSources >= 1 && map.size >= DISCOVERY_MIN_UNIQUE) {
      break;
    }
  }

  // FAST_DISCOVERY_V372_MERGE
  // Two discovery lanes:
  //   CONFIRMED = >=2 discovery providers, same conservative v3.67 behavior.
  //   FAST = >=1 very-fresh provider + new/high-velocity evidence.
  // FAST candidates are analysis-only. This block NEVER grants entry; downstream
  // security, sellability, holder, liquidity, quote/impact and live execution gates stay authoritative.
  let radarHealthy = false;
  let radarMatches = 0;
  let radarOnlyAdded = 0;
  let radarProviderCount = 0;
  let radarFastProviderCount = 0;
  let radarFastUsable = false;
  let radarFastMatches = 0;
  try {
    const radar = JSON.parse(fs.readFileSync(NEW_LISTING_RADAR, "utf8"));
    const radarAgeMs = Date.now() - Date.parse(radar.updatedAt || 0);
    radarProviderCount = n(radar.providerCount);
    radarFastProviderCount = n(radar.fastProviderCount, radarProviderCount);
    const radarFresh = Number.isFinite(radarAgeMs) && radarAgeMs >= 0 && radarAgeMs <= 45000;
    radarHealthy = radar.status === "HEALTHY" && radarFresh && radarProviderCount >= 2;
    radarFastUsable = ["HEALTHY","DEGRADED"].includes(radar.status) && radarFresh && radarFastProviderCount >= 1;
    if (radarHealthy || radarFastUsable) {
      for (const r of (radar.candidates || [])) {
        if (!r?.mint || r.currentFeed !== true) continue;
        const ageSec = Number.isFinite(Number(r.pairAgeSec)) ? Number(r.pairAgeSec) : Infinity;
        const confidence = n(r.discoveryConfidence);
        const preScore = n(r.preScore);
        const liq = n(r.liquidityUsd), buys = n(r.buys5m), vol = n(r.volume5m), ratio = n(r.buySellTxnRatio), chg = Math.abs(n(r.priceChange5m));
        const confirmedAccept = radarHealthy && confidence >= 0.35 && (ageSec <= 7 * 24 * 3600 || preScore >= 55);
        const fastFlow = (buys >= 3 && ratio >= 1.03) || vol >= 1500 || chg >= 5;
        const fastMetric = ageSec >= 0 && ageSec <= 6 * 3600 && confidence >= 0.24 && preScore >= 32 && (liq >= 4000 || ageSec <= 3600) && fastFlow;
        const fastAccept = radarFastUsable && (r.fastDiscoveryLane === true || fastMetric);
        let existing = map.get(r.mint);
        if (!existing) {
          if (radarOnlyAdded >= DISCOVERY_RADAR_ONLY_MAX) continue;
          if (!confirmedAccept && !fastAccept) continue;
          existing = {
            id:r.mint,
            symbol:r.symbol||null,
            name:r.name||null,
            sources:[],
            firstPool:r.pairAddress?{id:r.pairAddress,createdAt:r.pairCreatedAt||null}:null,
            liquidity:n(r.liquidityUsd),
            holderCount:n(r.holderCount),
            organicScore:n(r.organicScore),
            stats5m:{
              numBuys:n(r.buys5m), numSells:n(r.sells5m),
              buyVolume:n(r.volume5m) * (n(r.buys5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m)))),
              sellVolume:n(r.volume5m) * (n(r.sells5m)/(Math.max(1,n(r.buys5m)+n(r.sells5m))))
            },
            radarDiscoveryOnly:true,
            radarFastDiscoveryOnly:fastAccept && !confirmedAccept,
            radarAgeBucket:r.ageBucket||null,
            radarDiscoveryConfidence:confidence,
            radarDexId:r.dexId||null
          };
          map.set(r.mint, existing);
          radarOnlyAdded++;
        }
        existing.sources = Array.isArray(existing.sources) ? existing.sources : [];
        if (!existing.sources.includes("solana-dex-universe")) existing.sources.push("solana-dex-universe");
        if (fastAccept && !existing.sources.includes("fast-discovery-v372")) existing.sources.push("fast-discovery-v372");
        for (const src of (r.sources || [])) {
          const tag=`radar:${src}`;
          if (!existing.sources.includes(tag)) existing.sources.push(tag);
        }
        existing.newListingRadar = {
          pairCreatedAt:r.pairCreatedAt||null,
          pairAgeSec:Number.isFinite(Number(r.pairAgeSec))?Number(r.pairAgeSec):null,
          ageBucket:r.ageBucket||null,
          preScore,
          discoveryConfidence:confidence,
          discoveryPriority:n(r.discoveryPriority,preScore),
          fastDiscoveryLane:fastAccept,
          liquidityUsd:n(r.liquidityUsd),
          buys5m:n(r.buys5m), sells5m:n(r.sells5m),
          volume5m:n(r.volume5m), priceChange5m:n(r.priceChange5m),
          providers:Array.isArray(r.providers)?r.providers:[],
          sources:Array.isArray(r.sources)?r.sources:[],
          dexId:r.dexId||null
        };
        if (!existing.firstPool && r.pairCreatedAt) existing.firstPool={id:r.pairAddress||null,createdAt:r.pairCreatedAt};
        radarMatches++;
        if (fastAccept) radarFastMatches++;
      }
    }
  } catch (e) {
    console.error(`FAST_DISCOVERY_V372_READ_FAIL=${String(e?.message||e).slice(0,120)}`);
  }
  console.log(`FAST_DISCOVERY_V372 MATCHES=${radarMatches} FAST=${radarFastMatches} RADAR_ONLY_ADDED=${radarOnlyAdded} PROVIDERS=${radarProviderCount} FAST_PROVIDERS=${radarFastProviderCount} CONFIRMED_HEALTHY=${radarHealthy} FAST_USABLE=${radarFastUsable}`);

  const liveRows =
    [...map.values()];

  const providerRedundancy =
    successfulSources >= DISCOVERY_MIN_SOURCES ||
    (successfulSources >= 1 && radarHealthy && radarProviderCount >= 2 && radarMatches >= DISCOVERY_RADAR_MIN_MATCHES);

  const liveHealthy =
    providerRedundancy &&
    liveRows.length >= DISCOVERY_MIN_UNIQUE;

  if (liveHealthy) {
    const cache = {
      savedAt:
        new Date().toISOString(),

      tokens:
        liveRows
    };

    atomicJSON(
      DISCOVERY_CACHE,
      cache
    );

    discoveryHealth = {
      status: "HEALTHY",
      checkedAt:
        new Date().toISOString(),

      successfulSources,
      failedSources,
      radarHealthy,
      radarMatches,
      radarOnlyAdded,
      radarProviderCount,
      radarFastProviderCount,
      radarFastUsable,
      radarFastMatches,
      providerRedundancy,

      discoveredUnique:
        liveRows.length,

      usingCache: false,
      cacheAgeMs: 0,

      allowNewEntries: true,

      failures
    };

    atomicJSON(
      DISCOVERY_HEALTH,
      discoveryHealth
    );

    return liveRows;
  }

  /*
   * Current fetch is degraded.
   *
   * Keep last-good token state for
   * continuity/position management,
   * but absolutely disable new entries.
   */
  let cachedRows = [];
  let cacheAgeMs = null;

  try {
    const cached =
      JSON.parse(
        fs.readFileSync(
          DISCOVERY_CACHE,
          "utf8"
        )
      );

    const saved =
      Date.parse(
        cached.savedAt
      );

    cacheAgeMs =
      Number.isFinite(saved)
        ? Date.now() - saved
        : Infinity;

    if (
      Array.isArray(
        cached.tokens
      ) &&
      cacheAgeMs >= 0 &&
      cacheAgeMs <=
        DISCOVERY_CACHE_MAX_AGE_MS
    ) {
      cachedRows =
        cached.tokens;
    }

  } catch {}

  discoveryHealth = {
    status:
      cachedRows.length
        ? "DEGRADED_CACHE"
        : "DEGRADED_NO_CACHE",

    checkedAt:
      new Date().toISOString(),

    successfulSources,
    failedSources,
    radarHealthy,
    radarMatches,
    radarOnlyAdded,
    radarProviderCount,
    radarFastProviderCount,
    radarFastUsable,
    radarFastMatches,
    providerRedundancy,

    discoveredUnique:
      liveRows.length,

    usingCache:
      cachedRows.length > 0,

    cacheAgeMs,

    allowNewEntries: false,

    failures
  };

  atomicJSON(
    DISCOVERY_HEALTH,
    discoveryHealth
  );

  console.error(
    "DISCOVERY_DEGRADED",
    JSON.stringify(
      discoveryHealth
    )
  );

  if (cachedRows.length) {
    return cachedRows;
  }

  return liveRows;
}

function n(v, fallback = 0) {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
}

function boolField(obj, paths) {
  for (const p of paths) {
    const parts = p.split(".");
    let x = obj;

    for (const key of parts) {
      x = x?.[key];
    }

    if (typeof x === "boolean") {
      return x;
    }
  }

  return null;
}

function analyze(token) {
  const s = token.stats5m || {};

  const liquidity = n(token.liquidity);
  const holders = n(token.holderCount);

  const buyVolume = n(s.buyVolume);
  const sellVolume = n(s.sellVolume);

  const organicBuy = n(s.buyOrganicVolume);
  const organicSell = n(s.sellOrganicVolume);

  const buys = n(s.numBuys);
  const sells = n(s.numSells);

  const netBuyers = n(s.numNetBuyers);
  const traders = n(s.numTraders);

  const priceChange = n(s.priceChange);

  // NEW_LISTING_RADAR_V312_AGE
  const poolCreatedMs = Date.parse(token.firstPool?.createdAt || token.newListingRadar?.pairCreatedAt || "");
  const pairAgeMin = Number.isFinite(poolCreatedMs) ? Math.max(0,(Date.now()-poolCreatedMs)/60000) : Infinity;
  const radarPreScore = n(token.newListingRadar?.preScore);


  const mintDisabled = boolField(token, [
    "audit.mintAuthorityDisabled",
    "mintAuthorityDisabled"
  ]);

  const freezeDisabled = boolField(token, [
    "audit.freezeAuthorityDisabled",
    "freezeAuthorityDisabled"
  ]);

  const topHoldersPct = n(
    token.audit?.topHoldersPercentage ??
    token.topHoldersPercentage,
    -1
  );

  const token2022 =
    token.tokenProgram === TOKEN2022;

  const reasons = [];
  const hardReject = [];

  /*
   * Cached / degraded discovery may be used
   * to maintain continuity, but NEVER to
   * create a new entry.
   */
  if (
    discoveryHealth.allowNewEntries
      !== true
  ) {
    hardReject.push(
      "DATA_SOURCE_DEGRADED"
    );

    reasons.push(
      discoveryHealth.status ||
      "DATA_DEGRADED"
    );
  }

  // -------- HARD GATES --------

  if (
    token.id === WSOL ||
    token.id === USDC
  ) {
    hardReject.push("CORE_ASSET");
  }

  if (liquidity < cfg.minLiquidityUsd) {
    hardReject.push("LOW_LIQUIDITY");
  }

  if (holders < 30) {
    hardReject.push("TOO_FEW_HOLDERS");
  }

  if (mintDisabled === false) {
    hardReject.push("MINT_AUTHORITY_ACTIVE");
  }

  if (freezeDisabled === false) {
    hardReject.push("FREEZE_AUTHORITY_ACTIVE");
  }

  if (
    topHoldersPct >= 0 &&
    topHoldersPct > 50
  ) {
    hardReject.push("TOP_HOLDERS_TOO_CONCENTRATED");
  }

  // Token-2022 is not automatically bad,
  // but requires extension audit before execution.
  const needsExtensionAudit = token2022;

  // -------- SCORE --------

  let score = 0;

  // Liquidity: max 20
  if (liquidity >= 250000) score += 20;
  else if (liquidity >= 100000) score += 16;
  else if (liquidity >= 50000) score += 12;
  else if (liquidity >= 25000) score += 8;

  // Holders: max 10
  if (holders >= 1000) score += 10;
  else if (holders >= 300) score += 8;
  else if (holders >= 100) score += 5;
  else if (holders >= 50) score += 3;

  // Net buyer expansion: max 15
  if (netBuyers >= 100) score += 15;
  else if (netBuyers >= 30) score += 12;
  else if (netBuyers >= 10) score += 8;
  else if (netBuyers > 0) score += 4;

  // Buy pressure: max 15
  const volRatio =
    sellVolume > 0
      ? buyVolume / sellVolume
      : buyVolume > 0
        ? 3
        : 0;

  if (volRatio >= 2) score += 15;
  else if (volRatio >= 1.5) score += 12;
  else if (volRatio >= 1.15) score += 8;
  else if (volRatio >= 0.9) score += 4;

  // Transaction flow: max 10
  const txnRatio =
    sells > 0
      ? buys / sells
      : buys > 0
        ? 3
        : 0;

  if (txnRatio >= 2) score += 10;
  else if (txnRatio >= 1.4) score += 8;
  else if (txnRatio >= 1.0) score += 5;

  // Organic component: max 10
  const totalVolume =
    buyVolume + sellVolume;

  const organicVolume =
    organicBuy + organicSell;

  const organicRatio =
    totalVolume > 0
      ? organicVolume / totalVolume
      : 0;

  if (organicRatio >= 0.5) score += 10;
  else if (organicRatio >= 0.25) score += 7;
  else if (organicRatio >= 0.1) score += 4;

  // NEW_LISTING_RADAR_V312_RECENCY_BONUS
  // Recency can rank a safe candidate earlier but cannot bypass any hard gate.
  const newListingFlowOk = liquidity >= cfg.minLiquidityUsd && netBuyers > 0 && organicRatio >= 0.10;
  if (newListingFlowOk && pairAgeMin <= 5) { score += 10; reasons.push("NEW_LISTING_EARLY_FLOW"); }
  else if (newListingFlowOk && pairAgeMin <= 15) { score += 7; reasons.push("NEW_LISTING_FRESH_FLOW"); }
  else if (newListingFlowOk && pairAgeMin <= 60) { score += 4; reasons.push("NEW_LISTING_RECENT_FLOW"); }
  if (newListingFlowOk && radarPreScore >= 70) { score += 3; reasons.push("DEX_RADAR_CONFIRMATION"); }

  // Discovery agreement: max 10
  const sourceCount =
    new Set(token.sources).size;

  if (sourceCount >= 4) score += 10;
  else if (sourceCount === 3) score += 8;
  else if (sourceCount === 2) score += 5;
  else score += 2;

  // Momentum but penalize mania: max 10
  if (
    priceChange >= 1 &&
    priceChange <= 15
  ) {
    score += 10;
  } else if (
    priceChange > 15 &&
    priceChange <= 35
  ) {
    score += 6;
    reasons.push("HOT");
  } else if (priceChange > 35) {
    score += 1;
    reasons.push("PARABOLIC_RISK");
  } else if (priceChange > 0) {
    score += 5;
  }

  if (priceChange < -20) {
    score -= 10;
    reasons.push("FAST_DRAWDOWN");
  }

  if (needsExtensionAudit) {
    score -= 10;
    reasons.push("TOKEN2022_AUDIT_REQUIRED");
  }

  score = Math.max(
    0,
    Math.min(100, score)
  );

  let decision = "IGNORE";

  if (hardReject.length === 0) {
    if (
      score >= 70 &&
      !needsExtensionAudit
    ) {
      decision = "PROBE_CANDIDATE";
    } else if (score >= 50) {
      decision = "WATCH";
    }
  }

  return {
    mint: token.id,
    symbol: token.symbol || "?",
    name: token.name || "?",
    launchpad: token.launchpad || null,
    pairAgeMin: Number.isFinite(pairAgeMin) ? Number(pairAgeMin.toFixed(3)) : null,
    radarPreScore,
    newListingRadar: token.newListingRadar || null,

    score,
    decision,

    sources: [...new Set(token.sources)],

    liquidityUsd: liquidity,
    holders,

    priceUsd: n(token.usdPrice),
    mcap: n(token.mcap),

    priceChange5m: priceChange,

    buyVolume5m: buyVolume,
    sellVolume5m: sellVolume,

    buys5m: buys,
    sells5m: sells,
    traders5m: traders,
    netBuyers5m: netBuyers,

    organicRatio5m:
      Number(organicRatio.toFixed(4)),

    token2022,
    needsExtensionAudit,

    mintAuthorityDisabled: mintDisabled,
    freezeAuthorityDisabled: freezeDisabled,
    topHoldersPct,

    hardReject,
    reasons
  };
}

async function dexCheck(candidate) {
  try {
    const body = await getJSON(
      `${cfg.dexscreener}/latest/dex/tokens/${candidate.mint}`
    );

    const pairs =
      (body.pairs || [])
        .filter(p => p.chainId === "solana")
        .sort(
          (a, b) =>
            n(b.liquidity?.usd) -
            n(a.liquidity?.usd)
        );

    const best = pairs[0];

    if (!best) {
      return {
        dexOk: false,
        dexReason: "NO_SOLANA_PAIR"
      };
    }

    return {
      dexOk: true,
      dexId: best.dexId || null,
      pair: best.pairAddress || null,
      dexLiquidityUsd: n(best.liquidity?.usd),
      dexVolume5m: n(best.volume?.m5),
      dexBuys5m: n(best.txns?.m5?.buys),
      dexSells5m: n(best.txns?.m5?.sells)
    };

  } catch (err) {
    return {
      dexOk: false,
      dexReason: err.message
    };
  }
}

async function sellability(candidate) {
  const transient = (http, message='') => ({
    sellRoute: null,
    sellQuoteHttp: http ?? null,
    sellOutAmount: null,
    sellPriceImpactPct: null,
    sellQuoteError: message || 'SELLABILITY_TRANSIENT'
  });

  try {
    const decimals = Math.max(0, Math.min(12, Number(candidate.decimals ?? 6)));
    let tokens = 1;
    if (candidate.priceUsd > 0) {
      tokens = Math.min(1_000_000, Math.max(1, 1 / candidate.priceUsd));
    }
    const raw = BigInt(Math.max(1, Math.floor(tokens * 10 ** decimals)));
    const url = `${cfg.jupiter}/swap/v2/order` +
      `?inputMint=${candidate.mint}` +
      `&outputMint=${WSOL}` +
      `&amount=${raw}`;

    for (let attempt=0; attempt<2; attempt++) {
      await paceJupiter();
      try {
        const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
        let body = {};
        try { body = await r.json(); } catch { body = {}; }

        if (r.status === 429 || r.status >= 500) {
          if (attempt === 0) { await new Promise(x=>setTimeout(x,2200)); continue; }
          return transient(r.status, `JUPITER_TRANSIENT_HTTP_${r.status}`);
        }

        if (!r.ok) {
          return {
            sellRoute: false,
            sellQuoteHttp: r.status,
            sellOutAmount: body.outAmount ?? null,
            sellPriceImpactPct: body.priceImpactPct ?? null,
            sellQuoteError: String(body.error || body.errorMessage || `JUPITER_HTTP_${r.status}`).slice(0,180)
          };
        }

        const ok = Boolean(body.outAmount) && Number(body.outAmount) > 0;
        return {
          sellRoute: ok,
          sellQuoteHttp: r.status,
          sellOutAmount: body.outAmount ?? null,
          sellPriceImpactPct: body.priceImpactPct ?? null,
          ...(ok ? {} : { sellQuoteError: 'NO_POSITIVE_OUT_AMOUNT' })
        };
      } catch (err) {
        if (attempt === 0) { await new Promise(x=>setTimeout(x,2200)); continue; }
        return transient(null, String(err?.message || err).slice(0,180));
      }
    }
    return transient(null, 'SELLABILITY_RETRY_EXHAUSTED');
  } catch (err) {
    return transient(null, String(err?.message || err).slice(0,180));
  }
}


// SCANNER_FAST_PIPELINE_V216
async function dexBatchChecks(items) {
  const out = new Map();
  const mints = [...new Set(items.map(x=>x?.result?.mint).filter(Boolean))];
  for (let i=0; i<mints.length; i+=30) {
    const chunk=mints.slice(i,i+30);
    const url=`${cfg.dexscreener}/tokens/v1/solana/${chunk.join(',')}`;
    try {
      const r=await fetch(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(5000)});
      if(!r.ok) throw new Error(`DEX_BATCH_HTTP_${r.status}`);
      const rows=await r.json();
      const pairs=Array.isArray(rows)?rows:[];
      for(const mint of chunk){
        const xs=pairs.filter(q=>q?.chainId==='solana'&&(q?.baseToken?.address===mint||q?.quoteToken?.address===mint)).sort((a,b)=>n(b?.liquidity?.usd)-n(a?.liquidity?.usd));
        const best=xs[0];
        if(!best){out.set(mint,{dexOk:false,dexReason:'NO_SOLANA_PAIR'});continue;}
        out.set(mint,{dexOk:true,dexId:best.dexId||null,pair:best.pairAddress||null,dexLiquidityUsd:n(best.liquidity?.usd),dexVolume5m:n(best.volume?.m5),dexBuys5m:n(best.txns?.m5?.buys),dexSells5m:n(best.txns?.m5?.sells)});
      }
    } catch(e) {
      for(const mint of chunk) out.set(mint,{dexOk:false,dexReason:`DEX_BATCH_TRANSIENT_${String(e?.message||e).slice(0,100)}`});
    }
  }
  return out;
}
const MAX_SELLABILITY_CHECKS_V216=3; // V307 latency budget: verify only top opportunity candidates each cycle

console.log("=== MEME ALPHA SCANNER v0.2 ===");
console.log("MODE=PAPER");
console.log("LIVE_EXECUTION=DISABLED");

const tokens = await discovery();

console.log(
  `DISCOVERED_UNIQUE=${tokens.length}`
);

let ranked =
  tokens
    .map(t => ({
      raw: t,
      result: analyze(t)
    }))
    .sort(
      (a, b) =>
        b.result.score -
        a.result.score
    );

const preliminary =
  ranked.filter(
    x =>
      x.result.decision !== "IGNORE"
  );

console.log(
  `PRELIMINARY=${preliminary.length}`
);

// v2.2: keep the best 30, then add at most 10 high-signal meme/launchpad candidates.
// This preserves rate-limit headroom while preventing credible memes just below the
// global top-20 from being invisible to DEX/sellability checks.
const baseDeep = preliminary.slice(0, 24);
const baseMints = new Set(baseDeep.map(x => x.result?.mint));
const canonicalMemeMints = new Set([
  "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", // dogwifhat
  "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv", // PENGU
  "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9"  // GIGA
]);
const memeHint = /(?:meme|doge|shib|pepe|bonk|wif|dogwifhat|cat|dog|frog|goat|ape|pnut|peanut|popcat|chillguy|fart|pengu|pudgy|wojak|mog|floki|inu|giga|gigachad|troll)/i;
const extraMeme = preliminary
  .slice(20)
  .filter(x => {
    const r=x.result||{};
    const mint=String(r.mint||"");
    const text=`${r.symbol||""} ${r.name||""}`;
    return !baseMints.has(mint) && (mint.toLowerCase().endsWith("pump") || canonicalMemeMints.has(mint) || memeHint.test(text));
  })
  .slice(0, 6);
const deep = [...baseDeep, ...extraMeme];
console.log(`DEEPCHECK_BASE=${baseDeep.length} MEME_EXTRA=${extraMeme.length} TOTAL=${deep.length}`);

const final = [];
const dexBatchMap = await dexBatchChecks(deep);
let sellChecksUsedV216 = 0;

for (const item of deep) {
  const dex = dexBatchMap.get(item.result.mint) || { dexOk:false, dexReason:'DEX_BATCH_MISSING' };

  const enriched = {
    ...item.result,
    decimals: item.raw.decimals,
    ...dex
  };

  if (
    !dex.dexOk ||
    dex.dexLiquidityUsd <
      cfg.minLiquidityUsd
  ) {
    enriched.decision = "IGNORE";
    enriched.hardReject.push(
      "DEX_LIQUIDITY_FAIL"
    );
  }

  // OPPORTUNITY_WATCH_SELLABILITY_V280: verification only; never grants BUY by itself.
  const opportunitySellCheck =
    enriched.decision === "PROBE_CANDIDATE" ||
    (
      enriched.decision === "WATCH" &&
      (enriched.hardReject||[]).length === 0 &&
      Number(enriched.dexLiquidityUsd||enriched.liquidityUsd||0) >= cfg.minLiquidityUsd &&
      Number(enriched.score||0) >= 55 &&
      (Number(enriched.netBuyers5m||0) >= 1 || Number(enriched.priceChange5m||0) >= 0.15)
    );
  if (opportunitySellCheck && sellChecksUsedV216 < MAX_SELLABILITY_CHECKS_V216) {
    sellChecksUsedV216++;
    const sell =
      await sellability(enriched);

    Object.assign(
      enriched,
      sell
    );

    if (sell.sellRoute === false) {
      enriched.decision = "IGNORE";
      enriched.hardReject.push(
        "NO_SELL_ROUTE"
      );
    } else if (sell.sellRoute !== true) {
      enriched.decision = "WATCH";
      enriched.reasons.push(
        "SELLABILITY_TEMPORARILY_UNAVAILABLE"
      );
    }

    const impact =
      Math.abs(
        Number(
          sell.sellPriceImpactPct ?? 0
        )
      );

    if (
      sell.sellRoute &&
      impact >
        cfg.maxPriceImpactPct
    ) {
      enriched.decision = "WATCH";
      enriched.reasons.push(
        "HIGH_EXIT_IMPACT"
      );
    }
  }

  final.push(enriched);
}

final.sort(
  (a, b) =>
    b.score - a.score
);

const output = {
  timestamp: new Date().toISOString(),
  mode: "PAPER",
  liveExecution: false,
  discovered: tokens.length,

  counts: {
    ignore:
      ranked.filter(
        x =>
          x.result.decision === "IGNORE"
      ).length,

    watch:
      final.filter(
        x => x.decision === "WATCH"
      ).length,

    probeCandidates:
      final.filter(
        x =>
          x.decision ===
          "PROBE_CANDIDATE"
      ).length
  },

  candidates: final
};

const outFile =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

fs.writeFileSync(
  outFile,
  JSON.stringify(output, null, 2)
);

console.log("");
console.log("=== TOP CANDIDATES ===");

for (const x of final.slice(0, 15)) {
  console.log(
    [
      x.decision.padEnd(16),
      String(x.score).padStart(3),
      String(x.symbol).padEnd(12),
      `liq=$${Math.round(x.liquidityUsd)}`,
      `holders=${x.holders}`,
      `net5m=${x.netBuyers5m}`,
      `chg5m=${x.priceChange5m.toFixed(2)}%`,
      x.token2022
        ? "TOKEN2022"
        : "TOKEN"
    ].join(" | ")
  );
}

console.log("");
console.log(
  `OUTPUT=${outFile}`
);

console.log(
  "LIVE_EXECUTION=DISABLED"
);
console.log(
  "SCANNER_STATUS=PASS"
);
