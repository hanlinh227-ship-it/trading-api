import fs from "node:fs";

const scannerFile =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

const historyFile =
  "/var/lib/meme-alpha/data/paper/scanner-history.jsonl";

const stateFile =
  "/var/lib/meme-alpha/data/paper/persistence-state.json";

const paperFile =
  "/var/lib/meme-alpha/data/paper/state.json";

const MAX_OBSERVATIONS = 20;

/*
 * Scanner normally runs every ~60 sec.
 * Missing from current candidate set immediately destroys
 * consecutive-entry readiness.
 */
const READY_MAX_AGE_MS =
  3 * 60 * 1000;

/*
 * Old inactive tokens are removed from state after 24 h.
 * Open PAPER positions are always preserved.
 */
const TOKEN_TTL_MS =
  24 * 60 * 60 * 1000;

if (!fs.existsSync(scannerFile)) {
  throw new Error(
    "SCANNER_STATE_MISSING"
  );
}

const scan =
  JSON.parse(
    fs.readFileSync(
      scannerFile,
      "utf8"
    )
  );

const now =
  new Date().toISOString();

const nowMs =
  Date.now();

let state = {
  version: "0.7",
  tokens: {},
  updatedAt: null
};

if (fs.existsSync(stateFile)) {
  try {
    const old =
      JSON.parse(
        fs.readFileSync(
          stateFile,
          "utf8"
        )
      );

    state = {
      ...state,
      ...old,
      version: "0.7",
      tokens: old.tokens || {}
    };
  } catch {
    throw new Error(
      "PERSISTENCE_STATE_CORRUPT"
    );
  }
}

/*
 * Preserve tokens belonging to currently open positions
 * even when pruning stale persistence state.
 */
const openPositionMints =
  new Set();

if (fs.existsSync(paperFile)) {
  try {
    const paper =
      JSON.parse(
        fs.readFileSync(
          paperFile,
          "utf8"
        )
      );

    for (
      const p of
      paper.openPositions || []
    ) {
      if (p.mint) {
        openPositionMints.add(
          p.mint
        );
      }
    }
  } catch {
    /*
     * Fail safe for persistence pruning:
     * if paper state cannot be parsed,
     * do not prune any existing token this cycle.
     */
    for (
      const mint of
      Object.keys(state.tokens)
    ) {
      openPositionMints.add(mint);
    }
  }
}

const current =
  scan.candidates || [];

const seenMints =
  new Set(
    current
      .map(x => x.mint)
      .filter(Boolean)
  );

/*
 * FIRST:
 * Reset readiness for anything that disappeared
 * from the latest scanner candidate set.
 */
for (
  const [mint, t] of
  Object.entries(state.tokens)
) {
  if (seenMints.has(mint)) {
    continue;
  }

  t.consecutiveEligible = 0;
  t.missedScans =
    Number(t.missedScans || 0) + 1;

  /*
   * Any token absent from the current scanner candidate set
   * is stale for NEW ENTRY purposes, regardless of its
   * previous OBSERVE/CONFIRMING/READY state.
   */
  t.persistenceDecision = "STALE";
  t.stale = true;
}

/*
 * SECOND:
 * Process tokens present in latest scan.
 */
for (const c of current) {
  if (!c.mint) {
    continue;
  }

  let t =
    state.tokens[c.mint];

  if (!t) {
    t = {
      mint: c.mint,
      symbol: c.symbol,
      firstSeenAt: now,
      lastSeenAt: now,
      consecutiveEligible: 0,
      missedScans: 0,
      stale: false,
      observations: [],
      persistenceDecision:
        "OBSERVE",
      metrics: {}
    };

    state.tokens[c.mint] = t;
  }

  t.symbol =
    c.symbol || t.symbol;

  t.lastSeenAt = now;
  t.missedScans = 0;
  t.stale = false;

  t.observations.push({
    timestamp: now,

    score:
      Number(c.score || 0),

    decision:
      c.decision,

    universeClass:
      c.universeClass ||
      "UNKNOWN",

    liquidityUsd:
      Number(c.liquidityUsd || 0),

    holders:
      Number(c.holders || 0),

    netBuyers5m:
      Number(c.netBuyers5m || 0),

    priceChange5m:
      Number(
        c.priceChange5m || 0
      ),

    buyVolume5m:
      Number(
        c.buyVolume5m || 0
      ),

    sellVolume5m:
      Number(
        c.sellVolume5m || 0
      ),

    organicRatio5m:
      Number(
        c.organicRatio5m || 0
      ),

    sellRoute:
      c.sellRoute ?? null,

    sellPriceImpactPct:
      c.sellPriceImpactPct ??
      null,

    token2022:
      Boolean(c.token2022),

    securityDecision:
      c.securityDecision ||
      "UNKNOWN",

    securityBlockReasons:
      c.securityBlockReasons || [],

    securityReviewReasons:
      c.securityReviewReasons || [],

    token2022AuditDecision:
      c.token2022Audit?.decision ||
      "NOT_REQUIRED",

    token2022AuditBlockReasons:
      c.token2022Audit?.blockReasons || [],

    token2022AuditReviewReasons:
      c.token2022Audit?.reviewReasons || [],

    holderClusterDecision:
      c.holderClusterAudit?.decision ||
      "NOT_AUDITED",

    holderClusterReviewReasons:
      c.holderClusterAudit?.reviewReasons || [],

    holderClusterBlockReasons:
      c.holderClusterAudit?.blockReasons || [],

    hardReject:
      c.hardReject || [],

    reasons:
      c.reasons || []
  });

  if (
    t.observations.length >
    MAX_OBSERVATIONS
  ) {
    t.observations =
      t.observations.slice(
        -MAX_OBSERVATIONS
      );
  }

  /*
   * Strict eligibility:
   * NON_MEME cannot progress.
   * Token-2022 remains blocked until v0.8 audit.
   */
  const eligibleNow =
    c.decision ===
      "PROBE_CANDIDATE" &&

    // OPPORTUNITY_PERSISTENCE_V280: score is now a soft opportunity signal;
    // all hard security/holder/sellability gates below remain mandatory.
    Number(c.score || 0) >=
      62 &&

    c.universeClass ===
      "MEME_CONFIRMED" &&

    c.securityDecision ===
      "PASS" &&

    c.holderClusterAudit?.decision ===
      "PASS" &&

    (
      !c.token2022 ||
      (
        c.token2022Audit?.decision ===
          "PASS" &&
        c.needsExtensionAudit !== true
      )
    ) &&

    (c.hardReject || [])
      .length === 0 &&

    c.sellRoute === true;

  if (eligibleNow) {
    t.consecutiveEligible += 1;
  } else {
    t.consecutiveEligible = 0;
  }

  const obs =
    t.observations;

  const last3 =
    obs.slice(-3);

  const avgScore =
    last3.length
      ? last3.reduce(
          (sum, x) =>
            sum +
            Number(x.score || 0),
          0
        ) / last3.length
      : 0;

  const avgNetBuyers =
    last3.length
      ? last3.reduce(
          (sum, x) =>
            sum +
            Number(
              x.netBuyers5m || 0
            ),
          0
        ) / last3.length
      : 0;

  const liquidityValues =
    last3.map(
      x =>
        Number(
          x.liquidityUsd || 0
        )
    );

  const liquidityStable =
    last3.length < 2 ||
    (
      Math.min(
        ...liquidityValues
      ) >=
      0.75 *
      Math.max(
        ...liquidityValues
      )
    );

  const scoreTrend =
    last3.length >= 2
      ? Number(
          last3[
            last3.length - 1
          ].score
        ) -
        Number(
          last3[0].score
        )
      : 0;

  const last2 = obs.slice(-2);
  const avgScoreLast2 = last2.length
    ? last2.reduce((sum,x)=>sum+Number(x.score||0),0)/last2.length
    : 0;
  const avgNetBuyersLast2 = last2.length
    ? last2.reduce((sum,x)=>sum+Number(x.netBuyers5m||0),0)/last2.length
    : 0;
  const buyersPositiveLast2 = last2.length === 2 &&
    last2.every(x=>Number(x.netBuyers5m||0)>0);
  const liquidityLast2 = last2.map(x=>Number(x.liquidityUsd||0));
  const liquidityStableLast2 = last2.length < 2 ||
    Math.min(...liquidityLast2) >= 0.85*Math.max(...liquidityLast2);
  const scoreSlopeLast2 = last2.length === 2
    ? Number(last2[1].score||0)-Number(last2[0].score||0)
    : -Infinity;
  const currentPriceMove5m = Number(c.priceChange5m);
  const currentSellImpact = Number(c.sellPriceImpactPct);
  const currentSourceCount = new Set(c.sources||[]).size;
  const fastTrackReady =
    t.consecutiveEligible >= 2 &&
    c.universeClass === "MEME_CONFIRMED" &&
    c.securityDecision === "PASS" &&
    c.decision === "PROBE_CANDIDATE" &&
    !c.token2022 &&
    (c.hardReject||[]).length === 0 &&
    c.sellRoute === true &&
    Number(c.score||0) >= 80 &&
    avgScoreLast2 >= 78 &&
    avgNetBuyersLast2 > 0 &&
    buyersPositiveLast2 &&
    scoreSlopeLast2 >= 0 &&
    liquidityStableLast2 &&
    Number.isFinite(currentPriceMove5m) &&
    currentPriceMove5m >= -4 && currentPriceMove5m <= 18 &&
    Number.isFinite(currentSellImpact) &&
    Math.abs(currentSellImpact) <= 1.25 &&
    currentSourceCount >= 3;

  if (
    c.universeClass ===
      "NON_MEME"
  ) {
    t.persistenceDecision =
      "IGNORE";

    t.consecutiveEligible = 0;

  } else if (fastTrackReady) {
    t.persistenceDecision =
      "PAPER_ENTRY_READY";

  } else if (
    t.consecutiveEligible >= 3 &&
    avgScore >= 72 &&
    avgNetBuyers > 0 &&
    liquidityStable
  ) {
    t.persistenceDecision =
      "PAPER_ENTRY_READY";

  } else if (
    t.consecutiveEligible >= 2 &&
    avgScore >= 68
  ) {
    t.persistenceDecision =
      "CONFIRMING";

  } else if (
    c.decision === "WATCH" ||
    c.decision ===
      "PROBE_CANDIDATE"
  ) {
    t.persistenceDecision =
      "OBSERVE";

  } else {
    t.persistenceDecision =
      "IGNORE";
  }

  t.metrics = {
    fastTrackReady,
    avgScoreLast2:Number(avgScoreLast2.toFixed(2)),
    avgNetBuyersLast2:Number(avgNetBuyersLast2.toFixed(2)),
    scoreSlopeLast2:Number.isFinite(scoreSlopeLast2)?Number(scoreSlopeLast2.toFixed(2)):null,
    liquidityStableLast2,
    sourceCountCurrent:currentSourceCount,
    observations:
      obs.length,

    avgScoreLast3:
      Number(
        avgScore.toFixed(2)
      ),

    avgNetBuyersLast3:
      Number(
        avgNetBuyers.toFixed(2)
      ),

    scoreTrendLast3:
      Number(
        scoreTrend.toFixed(2)
      ),

    liquidityStable
  };
}

/*
 * THIRD:
 * Readiness expiry based on wall clock.
 */
for (
  const t of
  Object.values(state.tokens)
) {
  const ageMs =
    t.lastSeenAt
      ? nowMs -
        new Date(
          t.lastSeenAt
        ).getTime()
      : Infinity;

  t.ageSec =
    Number.isFinite(ageMs)
      ? Math.max(
          0,
          Math.round(
            ageMs / 1000
          )
        )
      : null;

  if (
    ageMs >
    READY_MAX_AGE_MS
  ) {
    t.consecutiveEligible = 0;

    if (
      t.persistenceDecision ===
        "PAPER_ENTRY_READY" ||
      t.persistenceDecision ===
        "CONFIRMING"
    ) {
      t.persistenceDecision =
        "STALE";
    }

    t.stale = true;
  }
}

/*
 * FOURTH:
 * Prune old inactive tokens.
 * Never prune a currently open PAPER position.
 */
let pruned = 0;

for (
  const [mint, t] of
  Object.entries(state.tokens)
) {
  if (
    openPositionMints.has(mint)
  ) {
    continue;
  }

  const last =
    t.lastSeenAt
      ? new Date(
          t.lastSeenAt
        ).getTime()
      : 0;

  if (
    last > 0 &&
    nowMs - last >
      TOKEN_TTL_MS
  ) {
    delete state.tokens[mint];
    pruned += 1;
  }
}

state.updatedAt = now;

state.health = {
  version: "0.7",
  scanTimestamp:
    scan.timestamp || null,
  scanCandidateCount:
    current.length,
  trackedTokens:
    Object.keys(
      state.tokens
    ).length,
  prunedThisCycle:
    pruned,
  readyMaxAgeSec:
    READY_MAX_AGE_MS / 1000,
  tokenTtlSec:
    TOKEN_TTL_MS / 1000
};

/*
 * Atomic persistence write.
 */
const tmp =
  `${stateFile}.tmp-${process.pid}`;

fs.writeFileSync(
  tmp,
  JSON.stringify(
    state,
    null,
    2
  )
);

fs.renameSync(
  tmp,
  stateFile
);

/*
 * History remains append-only.
 */
fs.appendFileSync(
  historyFile,
  JSON.stringify({
    timestamp: now,
    discovered:
      scan.discovered,
    counts:
      scan.counts,
    universe:
      scan.universe || null,
    candidates:
      scan.candidates
  }) + "\n"
);

const ranked =
  Object.values(
    state.tokens
  )
    .filter(
      x =>
        x.persistenceDecision !==
          "IGNORE" &&
        x.persistenceDecision !==
          "STALE"
    )
    .sort(
      (a, b) =>
        Number(
          b.metrics
            ?.avgScoreLast3 ||
          0
        ) -
        Number(
          a.metrics
            ?.avgScoreLast3 ||
          0
        )
    );

console.log(
  "=== MEME ALPHA PERSISTENCE v0.7 ==="
);

for (
  const t of
  ranked.slice(0, 20)
) {
  console.log(
    [
      String(
        t.persistenceDecision
      ).padEnd(18),

      String(
        t.symbol || "?"
      ).padEnd(12),

      `eligible=${
        t.consecutiveEligible
      }`,

      `obs=${
        t.metrics
          ?.observations || 0
      }`,

      `avg3=${
        t.metrics
          ?.avgScoreLast3 || 0
      }`,

      `trend=${
        t.metrics
          ?.scoreTrendLast3 || 0
      }`,

      `net=${
        t.metrics
          ?.avgNetBuyersLast3 || 0
      }`,

      `liqStable=${
        t.metrics
          ?.liquidityStable
      }`
    ].join(" | ")
  );
}

console.log("");
console.log(
  `TRACKED_TOKENS=${
    Object.keys(
      state.tokens
    ).length
  }`
);

console.log(
  `PRUNED=${pruned}`
);

console.log(
  `STATE=${stateFile}`
);

console.log(
  `HISTORY=${historyFile}`
);

console.log(
  "LIVE_EXECUTION=DISABLED"
);

console.log(
  "PERSISTENCE_STATUS=PASS"
);
