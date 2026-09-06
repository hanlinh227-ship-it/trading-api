import fs from "node:fs";

const CFG =
  "/opt/meme-alpha/app/config/runtime.json";

const SCANNER =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

if (!fs.existsSync(SCANNER)) {
  throw new Error("SCANNER_STATE_MISSING");
}

const cfg =
  JSON.parse(
    fs.readFileSync(CFG, "utf8")
  );

const scan =
  JSON.parse(
    fs.readFileSync(SCANNER, "utf8")
  );

if (cfg.mode !== "PAPER") {
  throw new Error(
    "SAFETY_BLOCK_NOT_PAPER"
  );
}

function n(v, fallback = null) {
  const x = Number(v);

  return Number.isFinite(x)
    ? x
    : fallback;
}

function uniq(xs) {
  return [...new Set(xs)];
}

const minLiquidityUsd =
  Number(
    cfg.minLiquidityUsd || 25000
  );

const maxPriceImpactPct =
  Number(
    cfg.maxPriceImpactPct || 2
  );

/*
 * Conservative holder thresholds.
 *
 * >50% = BLOCK
 * 35–50% = REVIEW
 *
 * These are pre-entry safety thresholds,
 * not claims that <=35% is automatically safe.
 */
const HOLDER_BLOCK_PCT = 50;
const HOLDER_REVIEW_PCT = 35;

/*
 * Security verdict:
 *
 * PASS:
 *   all required currently-available safety data passes.
 *
 * REVIEW:
 *   incomplete / uncertain security data.
 *   Cannot become PROBE_CANDIDATE.
 *
 * BLOCK:
 *   explicit unsafe condition.
 *   Forced IGNORE.
 *
 * UNKNOWN is never treated as safe.
 */
function inspect(c) {
  const block = [];
  const review = [];
  const evidence = [];

  /*
   * Universe has absolute precedence.
   */
  if (
    c.universeClass === "NON_MEME"
  ) {
    block.push(
      "NON_MEME_UNIVERSE"
    );
  }

  /*
   * Authority safety.
   */
  if (
    c.mintAuthorityDisabled === false
  ) {
    block.push(
      "MINT_AUTHORITY_ACTIVE"
    );
  } else if (
    c.mintAuthorityDisabled !== true
  ) {
    review.push(
      "MINT_AUTHORITY_UNKNOWN"
    );
  } else {
    evidence.push(
      "MINT_AUTHORITY_DISABLED"
    );
  }

  if (
    c.freezeAuthorityDisabled === false
  ) {
    block.push(
      "FREEZE_AUTHORITY_ACTIVE"
    );
  } else if (
    c.freezeAuthorityDisabled !== true
  ) {
    review.push(
      "FREEZE_AUTHORITY_UNKNOWN"
    );
  } else {
    evidence.push(
      "FREEZE_AUTHORITY_DISABLED"
    );
  }

  /*
   * Holder concentration.
   */
  const top =
    n(c.topHoldersPct);

  if (top === null) {
    review.push(
      "TOP_HOLDERS_UNKNOWN"
    );
  } else if (
    top > HOLDER_BLOCK_PCT
  ) {
    block.push(
      "TOP_HOLDERS_TOO_CONCENTRATED"
    );
  } else if (
    top > HOLDER_REVIEW_PCT
  ) {
    review.push(
      "TOP_HOLDERS_ELEVATED"
    );
  } else {
    evidence.push(
      "TOP_HOLDERS_ACCEPTABLE"
    );
  }

  /*
   * Token-2022:
   * fail closed until actual extension audit exists.
   *
   * It is REVIEW rather than permanent BLOCK because a future
   * v0.8.x extension auditor may explicitly clear it.
   */
  if (
    c.token2022 ||
    c.needsExtensionAudit
  ) {
    review.push(
      "TOKEN2022_EXTENSION_AUDIT_REQUIRED"
    );
  }

  /*
   * Liquidity from Jupiter token data.
   */
  const liquidity =
    n(c.liquidityUsd, 0);

  if (
    liquidity < minLiquidityUsd
  ) {
    block.push(
      "LIQUIDITY_BELOW_MINIMUM"
    );
  } else {
    evidence.push(
      "JUPITER_LIQUIDITY_PASS"
    );
  }

  /*
   * DEX cross-check.
   */
  const dexLiquidity =
    n(c.dexLiquidityUsd);

  if (dexLiquidity === null) {
    review.push(
      "DEX_LIQUIDITY_UNKNOWN"
    );
  } else if (
    dexLiquidity <
    minLiquidityUsd
  ) {
    block.push(
      "DEX_LIQUIDITY_BELOW_MINIMUM"
    );
  } else {
    evidence.push(
      "DEX_LIQUIDITY_PASS"
    );
  }

  /*
   * Jupiter sellability is mandatory.
   *
   * false    => explicit BLOCK
   * undefined/null => REVIEW
   * true     => continue
   */
  if (c.sellRoute === false) {
    block.push(
      "NO_SELL_ROUTE"
    );
  } else if (
    c.sellRoute !== true
  ) {
    review.push(
      "SELL_ROUTE_NOT_VERIFIED"
    );
  } else {
    evidence.push(
      "SELL_ROUTE_VERIFIED"
    );

    const impact =
      n(c.sellPriceImpactPct);

    if (impact === null) {
      review.push(
        "SELL_IMPACT_UNKNOWN"
      );
    } else if (
      impact >
      maxPriceImpactPct
    ) {
      block.push(
        "SELL_IMPACT_TOO_HIGH"
      );
    } else {
      evidence.push(
        "SELL_IMPACT_PASS"
      );
    }
  }

  /*
   * Preserve scanner's existing explicit hard rejects.
   */
  for (
    const r of
    c.hardReject || []
  ) {
    block.push(r);
  }

  const blockUnique =
    uniq(block);

  const reviewUnique =
    uniq(review)
      .filter(
        x =>
          !blockUnique.includes(x)
      );

  let decision = "PASS";

  if (blockUnique.length > 0) {
    decision = "BLOCK";
  } else if (
    reviewUnique.length > 0
  ) {
    decision = "REVIEW";
  }

  return {
    decision,
    blockReasons: blockUnique,
    reviewReasons: reviewUnique,
    evidence: uniq(evidence)
  };
}

let passCount = 0;
let reviewCount = 0;
let blockCount = 0;

for (
  const c of
  scan.candidates || []
) {
  const r = inspect(c);

  c.securityDecision =
    r.decision;

  c.securityBlockReasons =
    r.blockReasons;

  c.securityReviewReasons =
    r.reviewReasons;

  c.securityEvidence =
    r.evidence;

  c.securityVersion =
    "0.8";

  if (
    r.decision === "BLOCK"
  ) {
    blockCount += 1;

    c.decision = "IGNORE";

    c.hardReject =
      uniq([
        ...(c.hardReject || []),
        ...r.blockReasons,
        "SECURITY_BLOCK"
      ]);

  } else if (
    r.decision === "REVIEW"
  ) {
    reviewCount += 1;

    /*
     * REVIEW may remain visible in WATCH,
     * but can NEVER stay as a probe candidate.
     */
    if (
      c.decision ===
      "PROBE_CANDIDATE"
    ) {
      c.decision = "WATCH";
    }

    c.reasons =
      uniq([
        ...(c.reasons || []),
        ...r.reviewReasons,
        "SECURITY_REVIEW"
      ]);

  } else {
    passCount += 1;
  }
}

scan.security = {
  version: "0.8",
  checkedAt:
    new Date().toISOString(),

  policy:
    "FAIL_CLOSED_PRE_ENTRY",

  pass: passCount,
  review: reviewCount,
  block: blockCount,

  holderReviewPct:
    HOLDER_REVIEW_PCT,

  holderBlockPct:
    HOLDER_BLOCK_PCT,

  minLiquidityUsd,

  maxPriceImpactPct
};

/*
 * Atomic write.
 */
const tmp =
  `${SCANNER}.tmp-${process.pid}`;

fs.writeFileSync(
  tmp,
  JSON.stringify(
    scan,
    null,
    2
  )
);

fs.renameSync(
  tmp,
  SCANNER
);

console.log(
  "=== MEME ALPHA SECURITY v0.8 ==="
);

console.log(
  `PASS=${passCount}`
);

console.log(
  `REVIEW=${reviewCount}`
);

console.log(
  `BLOCK=${blockCount}`
);

console.log("");

const sorted =
  [...(scan.candidates || [])]
    .sort(
      (a,b) =>
        Number(b.score||0) -
        Number(a.score||0)
    );

for (
  const c of
  sorted.slice(0,30)
) {
  console.log(
    [
      String(
        c.securityDecision
      ).padEnd(7),

      String(
        c.symbol || "?"
      ).padEnd(12),

      `score=${c.score}`,

      `decision=${c.decision}`,

      `top=${
        c.topHoldersPct ?? "?"
      }`,

      `sell=${
        c.sellRoute ?? "?"
      }`,

      `impact=${
        c.sellPriceImpactPct ?? "?"
      }`,

      `T22=${
        Boolean(c.token2022)
      }`
    ].join(" | ")
  );
}

console.log("");
console.log(
  "UNKNOWN_SECURITY=NO_ENTRY"
);

console.log(
  "LIVE_EXECUTION=DISABLED"
);

console.log(
  "SECURITY_STATUS=PASS"
);
