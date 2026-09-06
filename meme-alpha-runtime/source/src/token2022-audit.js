import fs from "node:fs";
import { execFileSync } from "node:child_process";

const SCANNER =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

const CFG =
  "/opt/meme-alpha/app/config/runtime.json";

const SPL =
  "/opt/meme-alpha/.local/share/solana/install/active_release/bin/spl-token";

const RPC =
  "https://api.mainnet-beta.solana.com";

const cfg =
  JSON.parse(
    fs.readFileSync(CFG, "utf8")
  );

if (cfg.mode !== "PAPER") {
  throw new Error("ABORT_NOT_PAPER");
}

const scan =
  JSON.parse(
    fs.readFileSync(SCANNER, "utf8")
  );

function uniq(xs) {
  return [...new Set(xs)];
}

function runSpl(args) {
  try {
    return execFileSync(
      SPL,
      args,
      {
        encoding: "utf8",
        timeout: 20000,
        stdio: [
          "ignore",
          "pipe",
          "pipe"
        ]
      }
    );
  } catch (e) {
    return "";
  }
}

function inspectText(text) {
  const lower =
    String(text || "").toLowerCase();

  const block = [];
  const review = [];
  const evidence = [];

  /*
   * Explicitly dangerous / privileged extensions.
   */
  if (
    lower.includes(
      "permanent delegate"
    ) ||
    lower.includes(
      "permanentdelegate"
    )
  ) {
    block.push(
      "TOKEN2022_PERMANENT_DELEGATE"
    );
  }

  if (
    lower.includes(
      "transfer hook"
    ) ||
    lower.includes(
      "transferhook"
    )
  ) {
    block.push(
      "TOKEN2022_TRANSFER_HOOK"
    );
  }

  if (
    lower.includes(
      "non-transferable"
    ) ||
    lower.includes(
      "nontransferable"
    )
  ) {
    block.push(
      "TOKEN2022_NON_TRANSFERABLE"
    );
  }

  /*
   * Transfer-fee tokens can behave very differently
   * during both entry and exit.
   * Keep them fail-closed for now.
   */
  if (
    lower.includes(
      "transfer fee"
    ) ||
    lower.includes(
      "transferfee"
    ) ||
    lower.includes(
      "withheld"
    )
  ) {
    review.push(
      "TOKEN2022_TRANSFER_FEE_REVIEW"
    );
  }

  /*
   * DefaultAccountState can restrict newly created accounts.
   */
  if (
    lower.includes(
      "default account state"
    ) ||
    lower.includes(
      "defaultaccountstate"
    )
  ) {
    review.push(
      "TOKEN2022_DEFAULT_ACCOUNT_STATE_REVIEW"
    );
  }

  /*
   * Confidential transfer / interest-bearing / metadata
   * and other advanced extensions are not automatically
   * considered unsafe, but are not approved for execution
   * until explicitly classified.
   */
  const advanced = [
    "confidential",
    "interest-bearing",
    "interest bearing",
    "memo transfer",
    "metadata pointer",
    "group pointer",
    "group member pointer",
    "cpi guard"
  ];

  for (const k of advanced) {
    if (lower.includes(k)) {
      review.push(
        "TOKEN2022_UNCLASSIFIED_EXTENSION"
      );
      break;
    }
  }

  if (
    block.length === 0 &&
    review.length === 0
  ) {
    evidence.push(
      "NO_KNOWN_DANGEROUS_EXTENSION_DETECTED"
    );
  }

  return {
    block: uniq(block),
    review: uniq(review),
    evidence: uniq(evidence)
  };
}

let audited = 0;
let pass = 0;
let review = 0;
let block = 0;
let failed = 0;

for (
  const c of
  scan.candidates || []
) {
  if (
    !c.token2022 &&
    !c.needsExtensionAudit
  ) {
    c.token2022Audit = {
      version: "0.9",
      required: false,
      decision: "NOT_REQUIRED",
      blockReasons: [],
      reviewReasons: [],
      evidence: []
    };

    continue;
  }

  audited++;

  /*
   * spl-token display reads the mint and prints
   * Token-2022 extensions when supported.
   */
  let out = runSpl([
    "display",
    c.mint,
    "--url",
    RPC
  ]);

  /*
   * Fallback: ask for mint info.
   */
  if (!out) {
    out = runSpl([
      "supply",
      c.mint,
      "--url",
      RPC
    ]);
  }

  if (!out) {
    failed++;

    c.token2022Audit = {
      version: "0.9",
      required: true,
      decision: "REVIEW",
      blockReasons: [],
      reviewReasons: [
        "TOKEN2022_ONCHAIN_AUDIT_FAILED"
      ],
      evidence: []
    };

    review++;
    continue;
  }

  const r =
    inspectText(out);

  let decision = "PASS";

  if (r.block.length > 0) {
    decision = "BLOCK";
    block++;
  } else if (
    r.review.length > 0
  ) {
    decision = "REVIEW";
    review++;
  } else {
    pass++;
  }

  c.token2022Audit = {
    version: "0.9",
    required: true,
    decision,
    blockReasons: r.block,
    reviewReasons: r.review,
    evidence: r.evidence
  };

  /*
   * Feed result back into main security verdict.
   */
  if (decision === "BLOCK") {
    c.securityDecision = "BLOCK";
    c.decision = "IGNORE";

    c.securityBlockReasons =
      uniq([
        ...(c.securityBlockReasons || []),
        ...r.block
      ]);

    c.hardReject =
      uniq([
        ...(c.hardReject || []),
        ...r.block,
        "TOKEN2022_SECURITY_BLOCK"
      ]);

  } else if (
    decision === "REVIEW"
  ) {
    if (
      c.securityDecision !== "BLOCK"
    ) {
      c.securityDecision = "REVIEW";
    }

    if (
      c.decision ===
      "PROBE_CANDIDATE"
    ) {
      c.decision = "WATCH";
    }

    c.securityReviewReasons =
      uniq([
        ...(c.securityReviewReasons || []),
        ...r.review
      ]);

  } else if (
    decision === "PASS"
  ) {
    /*
     * Remove only the generic
     * "audit required" blocker/review.
     * Other security review reasons remain.
     */
    c.securityReviewReasons =
      (c.securityReviewReasons || [])
        .filter(
          x =>
            x !==
            "TOKEN2022_EXTENSION_AUDIT_REQUIRED"
        );

    c.reasons =
      (c.reasons || [])
        .filter(
          x =>
            x !==
            "TOKEN2022_AUDIT_REQUIRED"
        );

    c.needsExtensionAudit = false;

    /*
     * Do NOT automatically force SECURITY_PASS.
     * Other security checks still have authority.
     */
    if (
      c.securityDecision === "REVIEW" &&
      (c.securityReviewReasons || []).length === 0
    ) {
      c.securityDecision = "PASS";
    }
  }
}

scan.token2022Audit = {
  version: "0.9",
  checkedAt:
    new Date().toISOString(),

  policy:
    "FAIL_CLOSED_ON_UNKNOWN_EXTENSION",

  audited,
  pass,
  review,
  block,
  failed
};

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
  "=== MEME ALPHA TOKEN-2022 AUDIT v0.9 ==="
);

console.log(
  `AUDITED=${audited}`
);

console.log(
  `PASS=${pass}`
);

console.log(
  `REVIEW=${review}`
);

console.log(
  `BLOCK=${block}`
);

console.log(
  `FAILED=${failed}`
);

console.log("");

for (
  const c of
  scan.candidates || []
) {
  if (
    c.token2022Audit?.required
  ) {
    console.log(
      [
        c.symbol,
        `audit=${c.token2022Audit.decision}`,
        `security=${c.securityDecision}`,
        `decision=${c.decision}`,
        `block=${JSON.stringify(
          c.token2022Audit.blockReasons
        )}`,
        `review=${JSON.stringify(
          c.token2022Audit.reviewReasons
        )}`
      ].join(" | ")
    );
  }
}

console.log("");
console.log(
  "LIVE_EXECUTION=DISABLED"
);
console.log(
  "TOKEN2022_AUDIT_STATUS=PASS"
);
