import fs from "node:fs";

const FILE =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

if (!fs.existsSync(FILE)) {
  throw new Error("SCANNER_STATE_MISSING");
}

const scan = JSON.parse(
  fs.readFileSync(FILE, "utf8")
);

/*
 * v0.7 conservative universe gate.
 *
 * This is NOT intended to prove a token is a meme.
 * It prevents obvious infrastructure / stable / wrapped assets
 * from ever reaching the entry pipeline.
 *
 * Unknown assets remain eligible for later security analysis.
 */

const EXACT_NON_MEME_SYMBOLS = new Set([
  "SOL",
  "WSOL",
  "USDC",
  "USDT",
  "PYTH",
  "HNT",
  "TRX",
  "CBBTC",
  "WBTC",
  "JUPUSD",
  "JITOSOL",
  "USDUC"
]);

const EXACT_NON_MEME_MINTS = new Set([
  // Wrapped SOL
  "So11111111111111111111111111111111111111112",

  // JitoSOL liquid staking token
  "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",

  // Native USDC on Solana
  "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
]);

const NON_MEME_NAME_PATTERNS = [
  /\bwrapped\s+sol\b/i,
  /\bwrapped\s+bitcoin\b/i,
  /\bcoinbase\s+wrapped\s+btc\b/i,
  /\busd\s+coin\b/i,
  /\btether\b/i,
  /\bpyth\s+network\b/i,
  /\bhelium\b/i,
  /\btron\b/i
];

function uniq(xs) {
  return [...new Set(xs)];
}

function classify(c) {
  const symbol =
    String(c.symbol || "")
      .trim()
      .toUpperCase();

  const mint =
    String(c.mint || "").trim();

  const name =
    String(
      c.name ||
      c.tokenName ||
      c.metadata?.name ||
      ""
    ).trim();

  const reasons = [];

  if (EXACT_NON_MEME_MINTS.has(mint)) {
    reasons.push("CANONICAL_NON_MEME_MINT");
  }

  /*
   * Symbol block is deliberately conservative.
   * A spoof token using one of these symbols is also rejected,
   * which creates a safe false-negative rather than unsafe entry.
   */
  if (EXACT_NON_MEME_SYMBOLS.has(symbol)) {
    reasons.push("KNOWN_NON_MEME_SYMBOL");
  }

  if (
    name &&
    NON_MEME_NAME_PATTERNS.some(
      re => re.test(name)
    )
  ) {
    reasons.push("KNOWN_NON_MEME_NAME");
  }

  if (reasons.length > 0) {
    return {
      universeClass: "NON_MEME",
      universeReasons: reasons
    };
  }

  return {
    /*
     * UNKNOWN intentionally does not mean SAFE.
     * Security/Rug Engine v0.8 must still approve it.
     */
    universeClass: "UNKNOWN",
    universeReasons: []
  };
}

let blocked = 0;

for (const c of scan.candidates || []) {
  const u = classify(c);

  c.universeClass =
    u.universeClass;

  c.universeReasons =
    u.universeReasons;

  if (u.universeClass === "NON_MEME") {
    blocked += 1;

    c.decision = "IGNORE";

    c.hardReject =
      uniq([
        ...(c.hardReject || []),
        "NON_MEME_UNIVERSE"
      ]);

    c.reasons =
      uniq([
        ...(c.reasons || []),
        ...u.universeReasons
      ]);
  }
}

scan.universe = {
  version: "0.7",
  filteredAt:
    new Date().toISOString(),
  blockedCandidates: blocked,
  authority:
    "CONSERVATIVE_PRE_ENTRY_UNIVERSE_GATE"
};

/*
 * Atomic replace:
 * never leave a half-written scanner state.
 */
const tmp =
  `${FILE}.tmp-${process.pid}`;

fs.writeFileSync(
  tmp,
  JSON.stringify(scan, null, 2)
);

fs.renameSync(
  tmp,
  FILE
);

console.log(
  "=== MEME ALPHA UNIVERSE v0.7 ==="
);

console.log(
  `BLOCKED_NON_MEME=${blocked}`
);

for (
  const c of
  (scan.candidates || [])
    .filter(
      x =>
        x.universeClass ===
        "NON_MEME"
    )
) {
  console.log(
    `BLOCK | ${c.symbol} | ${
      c.universeReasons.join(",")
    }`
  );
}

console.log(
  "UNKNOWN_DOES_NOT_MEAN_SAFE"
);

console.log(
  "UNIVERSE_STATUS=PASS"
);
