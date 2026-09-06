import fs from "node:fs";

const CFG =
  "/opt/meme-alpha/app/config/runtime.json";

const PAPER =
  "/var/lib/meme-alpha/data/paper/state.json";

const PERSIST =
  "/var/lib/meme-alpha/data/paper/persistence-state.json";

const SCANNER =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

const RISK =
  "/var/lib/meme-alpha/data/paper/risk-state.json";

const cfg = JSON.parse(
  fs.readFileSync(CFG, "utf8")
);

if (cfg.mode !== "PAPER") {
  throw new Error(
    "SAFETY BLOCK: NOT PAPER MODE"
  );
}

if (
  !fs.existsSync(PERSIST) ||
  !fs.existsSync(SCANNER)
) {
  throw new Error(
    "Scanner/Persistence state missing"
  );
}

const persistence =
  JSON.parse(fs.readFileSync(PERSIST, "utf8"));

const scanner =
  JSON.parse(fs.readFileSync(SCANNER, "utf8"));

if (!fs.existsSync(RISK)) {
  throw new Error("RISK_STATE_MISSING");
}

const risk =
  JSON.parse(fs.readFileSync(RISK, "utf8"));

let paper =
  JSON.parse(fs.readFileSync(PAPER, "utf8"));

paper.openPositions ||= [];
paper.trades ||= [];
paper.realizedPnlSol ||=
  0;

paper.highWaterEquitySol ||=
  paper.equitySol;

paper.unrealizedPnlSol ||= 0;

const WSOL =
  "So11111111111111111111111111111111111111112";

const SOURCE_HEALTH =
  "/var/lib/meme-alpha/data/paper/scanner-source-health.json";
const RISK_STATE_MAX_AGE_SEC = 120;
const SOURCE_HEALTH_MAX_AGE_SEC = 180;

function clamp(x, min, max) {
  return Math.max(
    min,
    Math.min(max, x)
  );
}

function n(v, d = 0) {
  const x = Number(v);
  return Number.isFinite(x)
    ? x
    : d;
}

async function getJSON(url) {
  const r = await fetch(url, {
    signal: AbortSignal.timeout(10000)
  });

  if (!r.ok) {
    throw new Error(
      `HTTP ${r.status}`
    );
  }

  return await r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10000)
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

async function mintDecimals(mint) {
  const j = await postJSON(cfg.rpc, {
    jsonrpc: "2.0",
    id: 1,
    method: "getAccountInfo",
    params: [mint, { encoding: "jsonParsed" }]
  });
  const d = Number(j?.result?.value?.data?.parsed?.info?.decimals);
  if (!Number.isInteger(d) || d < 0 || d > 18) {
    throw new Error("TOKEN_DECIMALS_UNAVAILABLE");
  }
  return d;
}

function toRawAmount(amountUi, decimals) {
  const scaled = Math.floor(Number(amountUi) * 10 ** Number(decimals));
  if (!Number.isSafeInteger(scaled) || scaled <= 0) {
    throw new Error("RAW_AMOUNT_UNSAFE_OR_ZERO");
  }
  return BigInt(scaled);
}

async function jupiterExactIn(inputMint, outputMint, amountRaw) {
  const u = new URL(`${cfg.jupiter}/swap/v2/order`);
  u.searchParams.set("inputMint", inputMint);
  u.searchParams.set("outputMint", outputMint);
  u.searchParams.set("amount", amountRaw.toString());
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const r = await fetch(u, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(12000)
      });
      if (!r.ok) throw new Error(`JUPITER_ORDER_HTTP_${r.status}`);
      const j = await r.json();
      if (!j?.outAmount || BigInt(j.outAmount) <= 0n) {
        throw new Error("JUPITER_ORDER_NO_OUT_AMOUNT");
      }
      return j;
    } catch (e) {
      lastError = e;
      if (attempt < 2) {
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
    }
  }
  throw lastError || new Error("JUPITER_ORDER_FAILED");
}

async function bestDexPrice(mint) {
  const body =
    await getJSON(
      `${cfg.dexscreener}/latest/dex/tokens/${mint}`
    );

  const pairs =
    (body.pairs || [])
      .filter(
        p =>
          p.chainId === "solana" &&
          n(p.priceUsd) > 0
      )
      .sort(
        (a, b) =>
          n(b.liquidity?.usd) -
          n(a.liquidity?.usd)
      );

  if (!pairs.length) {
    throw new Error(
      "NO_DEX_PRICE"
    );
  }

  const p = pairs[0];

  return {
    priceUsd: n(p.priceUsd),
    liquidityUsd:
      n(p.liquidity?.usd),
    volume5m:
      n(p.volume?.m5),
    buys5m:
      n(p.txns?.m5?.buys),
    sells5m:
      n(p.txns?.m5?.sells),
    pair:
      p.pairAddress || null,
    dex:
      p.dexId || null
  };
}

async function solPriceUsd() {
  const d =
    await bestDexPrice(WSOL);

  return d.priceUsd;
}

function currentCandidate(mint) {
  return (
    scanner.candidates || []
  ).find(
    x => x.mint === mint
  ) || null;
}

function persistenceToken(mint) {
  return (
    persistence.tokens || {}
  )[mint] || null;
}

function executionCostPct(
  positionUsd,
  liquidityUsd
) {
  const liquidityImpact =
    liquidityUsd > 0
      ? (
          positionUsd /
          liquidityUsd
        ) * 0.5
      : 0.05;

  return clamp(
    0.0075 +
      liquidityImpact,
    0.0075,
    0.05
  );
}

function allocationPct(
  token,
  candidate
) {
  const avgScore =
    n(
      token.metrics
        ?.avgScoreLast3
    );

  const liq =
    n(
      candidate?.liquidityUsd
    );

  const chg =
    Math.abs(
      n(
        candidate
          ?.priceChange5m
      )
    );

  let pct = 0.015;

  if (avgScore >= 75)
    pct += 0.01;

  if (avgScore >= 82)
    pct += 0.01;

  if (liq >= 250000)
    pct += 0.005;

  if (liq >= 1000000)
    pct += 0.005;

  if (chg > 12)
    pct -= 0.01;

  return clamp(
    pct,
    0.01,
    cfg.maxSinglePositionPct /
      100
  );
}

function latestObs(token) {
  const a =
    token?.observations || [];

  return a.length
    ? a[a.length - 1]
    : null;
}

function weakFlow(token) {
  const obs =
    (token?.observations || [])
      .slice(-2);

  if (obs.length < 2)
    return false;

  return obs.every(
    x =>
      n(x.netBuyers5m) <= 0 ||
      n(x.score) < 50
  );
}

function recordTrade(event) {
  paper.trades.push({
    ...event,
    timestamp:
      new Date().toISOString()
  });

  if (paper.trades.length >
      5000) {
    paper.trades =
      paper.trades.slice(-5000);
  }
}

async function closeFraction(
  pos,
  fraction,
  reason,
  market,
  solUsd
) {
  fraction =
    clamp(fraction, 0, 1);

  if (fraction <= 0)
    return;

  const qty =
    pos.qty * fraction;

  const grossUsd =
    qty * market.priceUsd;

  const grossSol =
    grossUsd / solUsd;

  const tokenDecimals =
    Number.isInteger(Number(pos.tokenDecimals))
      ? Number(pos.tokenDecimals)
      : await mintDecimals(pos.mint);

  pos.tokenDecimals = tokenDecimals;

  const sellAmountRaw =
    toRawAmount(qty, tokenDecimals);

  const sellQuote =
    await jupiterExactIn(
      pos.mint,
      WSOL,
      sellAmountRaw
    );

  const netSol =
    Number(sellQuote.outAmount) / 1e9;

  if (!Number.isFinite(netSol) || netSol <= 0) {
    throw new Error("JUPITER_SELL_INVALID_OUTPUT");
  }

  const costPct =
    grossSol > 0
      ? Math.max(0, 1 - netSol / grossSol)
      : 0;

  const costBasisSol =
    pos.remainingCostSol *
    fraction;

  const pnlSol =
    netSol -
    costBasisSol;

  pos.qty -= qty;

  pos.remainingCostSol -=
    costBasisSol;

  pos.realizedPnlSol +=
    pnlSol;

  paper.realizedPnlSol +=
    pnlSol;

  recordTrade({
    type: "PAPER_SELL",
    positionId: pos.id || null,
    symbol: pos.symbol,
    mint: pos.mint,
    reason,
    fraction,
    qty,
    priceUsd:
      market.priceUsd,
    proceedsSol:
      netSol,
    costBasisSol,
    pnlSol,
    simulatedExecutionCostPct:
      costPct * 100,
    executionModel:
      "JUPITER_SWAP_V2_ORDER",
    jupiterInputAmountRaw:
      sellAmountRaw.toString(),
    jupiterOutputAmountRaw:
      String(sellQuote.outAmount),
    jupiterPriceImpactPct:
      sellQuote.priceImpactPct ?? null
  });
}

async function safeCloseFraction(pos, fraction, reason, market, solUsd) {
  try {
    await closeFraction(pos, fraction, reason, market, solUsd);
    return true;
  } catch (e) {
    recordTrade({
      type: "PAPER_EXIT_QUOTE_FAIL",
      positionId: pos.id || null,
      symbol: pos.symbol,
      mint: pos.mint,
      reason,
      error: e?.message || String(e)
    });
    console.log(`EXIT_QUOTE_FAIL ${pos.symbol} | ${reason} | ${e?.message || e}`);
    return false;
  }
}

console.log(
  "=== PAPER POSITION ENGINE v1.1.1 REACTIVE ORCHESTRATED JUPITER ==="
);

console.log(
  "LIVE_EXECUTION=DISABLED"
);

const solUsd =
  await solPriceUsd();

console.log(
  `SOL_USD=${solUsd.toFixed(4)}`
);

/*
 * 1. MANAGE EXISTING POSITIONS
 */

for (
  const pos of
    [...paper.openPositions]
) {
  let market;

  try {
    market =
      await bestDexPrice(
        pos.mint
      );
  } catch (e) {
    console.log(
      `PRICE_FAIL ${pos.symbol}: ${e.message}`
    );
    continue;
  }

  const token =
    persistenceToken(
      pos.mint
    );

  const cand =
    currentCandidate(
      pos.mint
    );

  const currentValueSol =
    (
      pos.qty *
      market.priceUsd
    ) / solUsd;

  const rawReturn =
    pos.remainingCostSol > 0
      ? (
          currentValueSol /
          pos.remainingCostSol -
          1
        )
      : 0;

  const returnPct =
    rawReturn * 100;

  pos.lastPriceUsd =
    market.priceUsd;

  pos.lastValueSol =
    currentValueSol;

  pos.lastUpdateAt =
    new Date().toISOString();

  pos.mfePct =
    Math.max(
      n(pos.mfePct),
      returnPct
    );

  pos.maePct =
    Math.min(
      n(pos.maePct),
      returnPct
    );

  const previousReturnPct =
    Number.isFinite(Number(pos.lastReturnPct))
      ? Number(pos.lastReturnPct)
      : returnPct;

  const oneTickDropPct =
    previousReturnPct - returnPct;

  pos.peakReturnPct =
    Math.max(
      Number.isFinite(Number(pos.peakReturnPct))
        ? Number(pos.peakReturnPct)
        : returnPct,
      returnPct
    );

  const givebackPct =
    pos.peakReturnPct - returnPct;

  const adversePulse =
    oneTickDropPct >= 4 && returnPct < 0;

  pos.fastAdverseCount =
    adversePulse
      ? Math.min(3, n(pos.fastAdverseCount) + 1)
      : Math.max(0, n(pos.fastAdverseCount) - 1);

  pos.lastReturnPct = returnPct;

  const latestNetBuyers =
    n(latestObs(token)?.netBuyers5m);

  const liquidityCollapse =
    n(pos.entryLiquidityUsd) > 0 &&
    n(market.liquidityUsd) < n(pos.entryLiquidityUsd) * 0.55 &&
    returnPct < -3;

  const fastShock =
    (oneTickDropPct >= 10 && returnPct < -2) ||
    (pos.fastAdverseCount >= 2 && oneTickDropPct >= 4 && returnPct <= -6);

  const profitGiveback =
    !pos.profitProtectDone &&
    pos.peakReturnPct >= 12 &&
    givebackPct >= 8 &&
    returnPct > 0 &&
    latestNetBuyers <= 0;

  const entryVol =
    Math.abs(
      n(
        pos.entryPriceChange5m
      )
    );

  const tp1 =
    clamp(
      15 +
        entryVol * 1.5,
      15,
      30
    );

  const tp2 =
    clamp(
      35 +
        entryVol * 2,
      35,
      65
    );

  const emergency =
    (
      cand &&
      (
        (cand.hardReject || [])
          .length > 0 ||
        cand.sellRoute === false
      )
    );

  const thesisBroken =
    weakFlow(token);

  if (emergency) {
    await safeCloseFraction(
      pos,
      1,
      "SAFETY_EMERGENCY",
      market,
      solUsd
    );

    continue;
  }

  if (liquidityCollapse) {
    await safeCloseFraction(
      pos,
      1,
      "FAST_LIQUIDITY_COLLAPSE",
      market,
      solUsd
    );
    continue;
  }

  if (fastShock) {
    const shockFraction =
      returnPct <= -12 ? 1 : 0.50;
    await safeCloseFraction(
      pos,
      shockFraction,
      "FAST_ADVERSE_SHOCK",
      market,
      solUsd
    );
    continue;
  }

  if (thesisBroken) {
    await safeCloseFraction(
      pos,
      1,
      "FLOW_THESIS_BROKEN",
      market,
      solUsd
    );

    continue;
  }

  if (profitGiveback) {
    const protectedOk = await safeCloseFraction(
      pos,
      0.35,
      "FAST_PROFIT_GIVEBACK",
      market,
      solUsd
    );
    if (protectedOk) pos.profitProtectDone = true;
  }

  if (
    !pos.tp1Done &&
    returnPct >= tp1
  ) {
    const tp1Ok = await safeCloseFraction(
      pos,
      0.20,
      "PARTIAL_TP1",
      market,
      solUsd
    );

    if (tp1Ok) pos.tp1Done = true;
  }

  if (
    !pos.tp2Done &&
    returnPct >= tp2
  ) {
    const tp2Ok = await safeCloseFraction(
      pos,
      0.25,
      "PARTIAL_TP2",
      market,
      solUsd
    );

    if (tp2Ok) pos.tp2Done = true;
  }

  const severeDrawdown =
    returnPct <=
      -clamp(
        15 +
          entryVol * 2,
        15,
        35
      );

  const flowNotStrong =
    !token ||
    n(
      latestObs(token)
        ?.netBuyers5m
    ) <= 0;

  if (
    severeDrawdown &&
    flowNotStrong
  ) {
    await safeCloseFraction(
      pos,
      1,
      "DRAWDOWN_PLUS_WEAK_FLOW",
      market,
      solUsd
    );
  }
}

/*
 * Remove fully closed positions.
 */

paper.openPositions =
  paper.openPositions.filter(
    p => p.qty > 0.0000000001
  );

/*
 * 2. CALCULATE CURRENT EQUITY
 */

let openValueSol = 0;

for (
  const pos of
    paper.openPositions
) {
  openValueSol +=
    n(pos.lastValueSol);
}

const committedCostSol =
  paper.openPositions.reduce(
    (s, p) =>
      s +
      n(p.remainingCostSol),
    0
  );

const baseCapital =
  paper.startingEquitySol +
  paper.realizedPnlSol;

paper.unrealizedPnlSol =
  openValueSol -
  committedCostSol;

paper.equitySol =
  baseCapital +
  paper.unrealizedPnlSol;

paper.highWaterEquitySol =
  Math.max(
    paper.highWaterEquitySol,
    paper.equitySol
  );

const drawdownPct =
  paper.highWaterEquitySol > 0
    ? (
        1 -
        paper.equitySol /
          paper.highWaterEquitySol
      ) * 100
    : 0;

const preRiskTmp = `${PAPER}.tmp-prerisk-${process.pid}`;
fs.writeFileSync(preRiskTmp, JSON.stringify(paper, null, 2));
fs.renameSync(preRiskTmp, PAPER);

const manageOnly = process.env.MEME_ALPHA_MANAGE_ONLY === "1";
if (manageOnly) {
  console.log("PHASE=FAST_MANAGE_ONLY");
  console.log(`FAST_EQUITY=${paper.equitySol.toFixed(6)} SOL`);
  console.log(`FAST_OPEN_POSITIONS=${paper.openPositions.length}`);
  console.log("FAST_MANAGE_STATUS=PASS");
  process.exit(0);
}

await import(`./risk.js?refresh=${Date.now()}`);
const entryRisk = JSON.parse(fs.readFileSync(RISK, "utf8"));
console.log("ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY");

/*
 * 3. OPEN NEW PAPER PROBE
 */

const maxPositions = 3;

const currentExposureSol =
  paper.openPositions.reduce(
    (s, p) =>
      s +
      n(p.lastValueSol),
    0
  );

const maxExposureSol =
  paper.equitySol *
  (
    cfg.maxPortfolioExposurePct /
    100
  );

const riskAgeSec = entryRisk.timestamp ? (Date.now() - new Date(entryRisk.timestamp).getTime()) / 1000 : Infinity;
let sourceHealth = null;
try { sourceHealth = JSON.parse(fs.readFileSync(SOURCE_HEALTH, "utf8")); } catch {}
const sourceHealthAgeSec = sourceHealth?.checkedAt ? (Date.now() - new Date(sourceHealth.checkedAt).getTime()) / 1000 : Infinity;
const riskStateFresh = Number.isFinite(riskAgeSec) && riskAgeSec >= 0 && riskAgeSec < RISK_STATE_MAX_AGE_SEC;
const sourceHealthAllowsEntries = Boolean(sourceHealth && sourceHealth.status === "HEALTHY" && sourceHealth.allowNewEntries === true && sourceHealth.usingCache !== true && sourceHealthAgeSec >= 0 && sourceHealthAgeSec < SOURCE_HEALTH_MAX_AGE_SEC);
console.log(`RISK_STATE_FRESH=${riskStateFresh} age=${Number.isFinite(riskAgeSec)?riskAgeSec.toFixed(1):"INF"}s`);
console.log(`SOURCE_HEALTH_ENTRY_GATE=${sourceHealthAllowsEntries}`);

const riskCandidates =
  new Map(
    (entryRisk.candidates || []).map(
      x => [x.mint, x]
    )
  );

const ready =
  Object.values(
    persistence.tokens || {}
  )
  .filter(
    t => {
      const r =
        riskCandidates.get(t.mint);

      return (
        riskStateFresh &&
        sourceHealthAllowsEntries &&
        entryRisk.entryAllowed === true &&
        r?.allowed === true &&
        t.persistenceDecision ===
          "PAPER_ENTRY_READY" &&
        !paper.openPositions.some(
          p => p.mint === t.mint
        )
      );
    }
  )
  .sort(
    (a, b) =>
      n(
        b.metrics
          ?.avgScoreLast3
      ) -
      n(
        a.metrics
          ?.avgScoreLast3
      )
  );

if (
  riskStateFresh &&
  sourceHealthAllowsEntries &&
  paper.openPositions.length <
    maxPositions &&
  ready.length > 0 &&
  currentExposureSol <
    maxExposureSol
) {
  const t =
    ready[0];

  const cand =
    currentCandidate(
      t.mint
    );

  if (
    cand &&
    cand.decision ===
      "PROBE_CANDIDATE" &&
    !cand.token2022 &&
    (cand.hardReject || [])
      .length === 0
  ) {
    try {
      const market =
        await bestDexPrice(
          t.mint
        );

      let pct =
        allocationPct(
          t,
          cand
        );

      const riskCandidate =
        riskCandidates.get(
          t.mint
        );

      if (
        riskCandidate &&
        Number.isFinite(
          Number(
            riskCandidate.suggestedPositionPct
          )
        )
      ) {
        pct = Math.min(
          pct,
          Number(
            riskCandidate.suggestedPositionPct
          ) / 100
        );
      }

      /*
       * Automatic drawdown de-risking.
       */
      if (drawdownPct >= 10)
        pct *= 0.50;
      else if (
        drawdownPct >= 5
      )
        pct *= 0.75;

      let allocationSol =
        paper.equitySol *
        pct;

      allocationSol =
        Math.min(
          allocationSol,
          maxExposureSol -
            currentExposureSol
        );

      if (
        allocationSol >
        0.001
      ) {
        const tokenDecimals =
          Number.isInteger(Number(cand.decimals))
            ? Number(cand.decimals)
            : await mintDecimals(t.mint);

        const inputLamports =
          toRawAmount(allocationSol, 9);

        const buyQuote =
          await jupiterExactIn(
            WSOL,
            t.mint,
            inputLamports
          );

        const exactEntryImpactPct =
          Number(buyQuote.priceImpactPct);

        if (!Number.isFinite(exactEntryImpactPct)) {
          throw new Error("JUPITER_BUY_IMPACT_UNKNOWN");
        }

        if (Math.max(0, exactEntryImpactPct) > n(cfg.maxPriceImpactPct, 2)) {
          throw new Error(`JUPITER_BUY_IMPACT_TOO_HIGH_${exactEntryImpactPct}`);
        }

        const tokenQty =
          Number(buyQuote.outAmount) /
          10 ** tokenDecimals;

        if (!Number.isFinite(tokenQty) || tokenQty <= 0) {
          throw new Error("JUPITER_BUY_INVALID_OUTPUT");
        }

        const entryPriceUsd =
          (allocationSol * solUsd) /
          tokenQty;

        const deploySol =
          (tokenQty * market.priceUsd) /
          solUsd;

        const costPct =
          allocationSol > 0
            ? Math.max(0, 1 - deploySol / allocationSol)
            : 0;

        const obs =
          latestObs(t);

        const pos = {
          id:
            `${Date.now()}-${t.mint.slice(0,8)}`,

          symbol:
            t.symbol,

          mint:
            t.mint,

          openedAt:
            new Date().toISOString(),

          entryPriceUsd:
            entryPriceUsd,

          entrySolUsd:
            solUsd,

          entryScore:
            n(
              t.metrics
                ?.avgScoreLast3
            ),

          entryPriceChange5m:
            n(
              obs
                ?.priceChange5m
            ),

          qty:
            tokenQty,

          tokenDecimals,

          initialCostSol:
            allocationSol,

          remainingCostSol:
            allocationSol,

          realizedPnlSol: 0,

          lastPriceUsd:
            market.priceUsd,

          lastValueSol:
            deploySol,

          mfePct: 0,
          maePct: 0,

          tp1Done: false,
          tp2Done: false,
          profitProtectDone: false,
          peakReturnPct: 0,
          lastReturnPct: 0,
          fastAdverseCount: 0,

          status:
            "PAPER_PROBE",

          entryLiquidityUsd:
            market.liquidityUsd,

          simulatedEntryCostPct:
            costPct * 100,

          executionModel:
            "JUPITER_SWAP_V2_ORDER",

          jupiterInputAmountRaw:
            inputLamports.toString(),

          jupiterOutputAmountRaw:
            String(buyQuote.outAmount),

          jupiterPriceImpactPct:
            buyQuote.priceImpactPct ?? null
        };

        paper.openPositions.push(
          pos
        );

        recordTrade({
          type:
            "PAPER_BUY_PROBE",

          positionId:
            pos.id,

          symbol:
            t.symbol,

          mint:
            t.mint,

          allocationSol,

          tokenQty,

          entryPriceUsd:
            entryPriceUsd,

          entryScore:
            pos.entryScore,

          simulatedExecutionCostPct:
            costPct * 100,

          executionModel:
            "JUPITER_SWAP_V2_ORDER",

          jupiterInputAmountRaw:
            inputLamports.toString(),

          jupiterOutputAmountRaw:
            String(buyQuote.outAmount),

          jupiterPriceImpactPct:
            buyQuote.priceImpactPct ?? null
        });

        console.log(
          `OPEN_PROBE ${t.symbol}` +
          ` | ${allocationSol.toFixed(6)} SOL` +
          ` | score=${pos.entryScore}`
        );
      }
    } catch (e) {
      console.log(
        `ENTRY_FAIL ${t.symbol}: ${e.message}`
      );
    }
  }
}

/*
 * Recalculate after any new position.
 */

let finalOpenValue = 0;
let finalCost = 0;

for (
  const p of
    paper.openPositions
) {
  finalOpenValue +=
    n(p.lastValueSol);

  finalCost +=
    n(p.remainingCostSol);
}

paper.unrealizedPnlSol =
  finalOpenValue -
  finalCost;

paper.equitySol =
  paper.startingEquitySol +
  paper.realizedPnlSol +
  paper.unrealizedPnlSol;

paper.highWaterEquitySol =
  Math.max(
    paper.highWaterEquitySol,
    paper.equitySol
  );

paper.lastPositionEngineAt =
  new Date().toISOString();

fs.writeFileSync(
  PAPER,
  JSON.stringify(
    paper,
    null,
    2
  )
);

console.log("");
console.log(
  `Equity=${paper.equitySol.toFixed(6)} SOL`
);

console.log(
  `Realized=${paper.realizedPnlSol.toFixed(6)} SOL`
);

console.log(
  `Unrealized=${paper.unrealizedPnlSol.toFixed(6)} SOL`
);

console.log(
  `OpenPositions=${paper.openPositions.length}`
);

for (
  const p of
    paper.openPositions
) {
  console.log(
    `${p.status} | ${p.symbol}` +
    ` | cost=${p.remainingCostSol.toFixed(6)} SOL` +
    ` | MFE=${n(p.mfePct).toFixed(2)}%` +
    ` | MAE=${n(p.maePct).toFixed(2)}%`
  );
}

console.log("");
console.log(
  "LIVE_EXECUTION=DISABLED"
);

console.log(
  "POSITION_ENGINE_STATUS=PASS"
);
