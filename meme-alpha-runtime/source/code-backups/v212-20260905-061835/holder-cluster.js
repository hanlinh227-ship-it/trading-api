import fs from "node:fs";

const SCANNER =
  "/var/lib/meme-alpha/data/paper/scanner-latest.json";

const CONFIG =
  "/opt/meme-alpha/app/config/runtime.json";

const cfg =
  JSON.parse(
    fs.readFileSync(CONFIG, "utf8")
  );

if (cfg.mode !== "PAPER") {
  throw new Error("ABORT_NOT_PAPER");
}

const scan =
  JSON.parse(
    fs.readFileSync(SCANNER, "utf8")
  );

const RPCS = [
  cfg.rpc,
  "https://api.mainnet-beta.solana.com",
  "https://solana-rpc.publicnode.com",
  "https://solana-mainnet.gateway.tatum.io"
].filter(Boolean);

const UNIQUE_RPCS =
  [...new Set(RPCS)];

function uniq(xs) {
  return [...new Set(xs)];
}

function sleep(ms) {
  return new Promise(
    resolve=>setTimeout(resolve,ms)
  );
}

async function rpcOne(
  endpoint,
  method,
  params
) {
  const controller =
    new AbortController();

  const timer =
    setTimeout(
      () => controller.abort(),
      12000
    );

  try {
    const r =
      await fetch(
        endpoint,
        {
          method: "POST",
          headers: {
            "content-type":
              "application/json"
          },
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: Date.now(),
            method,
            params
          }),
          signal: controller.signal
        }
      );

    if (!r.ok) {
      throw new Error(
        `HTTP_${r.status}`
      );
    }

    const j =
      await r.json();

    if (j.error) {
      const code =
        j.error?.code;

      const msg =
        j.error?.message ||
        "RPC_ERROR";

      throw new Error(
        `RPC_${code}_${msg}`
      );
    }

    return j.result;

  } finally {
    clearTimeout(timer);
  }
}

async function rpc(method, params) {
  const errors=[];

  for(
    const endpoint of
    UNIQUE_RPCS
  ){
    for(
      let attempt=1;
      attempt<=2;
      attempt++
    ){
      try {
        const result =
          await rpcOne(
            endpoint,
            method,
            params
          );

        return result;

      } catch(e) {
        const err =
          String(
            e?.message || e
          ).slice(0,200);

        errors.push(
          `${endpoint}#${attempt}:${err}`
        );

        /*
         * Small backoff only.
         * Do not hammer public RPC endpoints.
         */
        if(attempt<2){
          await sleep(
            600 * attempt
          );
        }
      }
    }
  }

  throw new Error(
    "ALL_RPC_FAILED | " +
    errors.join(" | ")
  );
}

async function largestAccounts(mint) {
  return await rpc(
    "getTokenLargestAccounts",
    [
      mint,
      {
        commitment: "confirmed"
      }
    ]
  );
}

async function tokenAccountOwners(
  addresses
) {
  if (!addresses.length) {
    return [];
  }

  const result =
    await rpc(
      "getMultipleAccounts",
      [
        addresses,
        {
          encoding: "jsonParsed",
          commitment: "confirmed"
        }
      ]
    );

  return (
    result?.value || []
  ).map((x, i) => {
    const info =
      x?.data?.parsed?.info;

    return {
      tokenAccount:
        addresses[i],

      owner:
        info?.owner || null,

      mint:
        info?.mint || null,

      tokenAmount:
        info?.tokenAmount || null
    };
  });
}

async function inspect(candidate) {
  const block = [];
  const review = [];
  const evidence = [];

  let result;

  try {
    result =
      await largestAccounts(
        candidate.mint
      );
  } catch (e) {
    return {
      decision: "REVIEW",
      blockReasons: [],
      reviewReasons: [
        "HOLDER_RPC_LARGEST_ACCOUNTS_FAILED"
      ],
      evidence: [],
      error:
        String(
          e?.message || e
        ).slice(0,200)
    };
  }

  const largest =
    result?.value || [];

  if (!largest.length) {
    return {
      decision: "REVIEW",
      blockReasons: [],
      reviewReasons: [
        "HOLDER_DATA_EMPTY"
      ],
      evidence: [],
      error: null
    };
  }

  const addresses =
    largest
      .slice(0,20)
      .map(x=>x.address)
      .filter(Boolean);

  let owners;

  try {
    owners =
      await tokenAccountOwners(
        addresses
      );
  } catch (e) {
    return {
      decision: "REVIEW",
      blockReasons: [],
      reviewReasons: [
        "HOLDER_OWNER_RESOLUTION_FAILED"
      ],
      evidence: [],
      error:
        String(
          e?.message || e
        ).slice(0,200)
    };
  }

  const supplyAmounts =
    largest
      .slice(0,20)
      .map(x =>
        Number(
          x.uiAmountString ??
          x.uiAmount ??
          0
        )
      );

  const totalTop =
    supplyAmounts.reduce(
      (a,b)=>a+b,
      0
    );

  const ownerMap =
    new Map();

  for (
    let i=0;
    i<owners.length;
    i++
  ) {
    const owner =
      owners[i]?.owner;

    const amount =
      supplyAmounts[i] || 0;

    if (!owner) {
      continue;
    }

    ownerMap.set(
      owner,
      (ownerMap.get(owner)||0)
        + amount
    );
  }

  const ownerRows =
    [...ownerMap.entries()]
      .map(
        ([owner,amount]) => ({
          owner,
          amount
        })
      )
      .sort(
        (a,b)=>
          b.amount-a.amount
      );

  const unresolved =
    owners.filter(
      x=>!x.owner
    ).length;

  if (unresolved > 0) {
    review.push(
      "TOP_ACCOUNT_OWNER_UNRESOLVED"
    );
  }

  /*
   * We do not have total supply here reliably
   * across every token/program, so we use the
   * Jupiter topHoldersPct as total concentration
   * and RPC owner aggregation as clustering evidence.
   */

  const topHoldersPct =
    Number(
      candidate.topHoldersPct
    );

  if (
    !Number.isFinite(
      topHoldersPct
    )
  ) {
    review.push(
      "TOP_HOLDERS_PERCENT_UNKNOWN"
    );
  }

  /*
   * Detect one owner controlling multiple
   * accounts among the largest 20.
   */
  const counts =
    new Map();

  for (const x of owners) {
    if (!x.owner) continue;

    counts.set(
      x.owner,
      (counts.get(x.owner)||0)+1
    );
  }

  const clusteredOwners =
    [...counts.entries()]
      .filter(
        ([,count])=>count>=2
      )
      .sort(
        (a,b)=>b[1]-a[1]
      );

  const maxAccountsSameOwner =
    clusteredOwners.length
      ? clusteredOwners[0][1]
      : 1;

  if (
    maxAccountsSameOwner >= 5
  ) {
    block.push(
      "SEVERE_MULTI_ACCOUNT_OWNER_CLUSTER"
    );
  } else if (
    maxAccountsSameOwner >= 3
  ) {
    review.push(
      "MULTI_ACCOUNT_OWNER_CLUSTER"
    );
  } else {
    evidence.push(
      "NO_LARGE_MULTI_ACCOUNT_CLUSTER"
    );
  }

  /*
   * Existing total top-holder concentration
   * remains an independent guard.
   */
  if (
    Number.isFinite(
      topHoldersPct
    )
  ) {
    if (topHoldersPct > 50) {
      block.push(
        "TOP_HOLDERS_OVER_50"
      );
    } else if (
      topHoldersPct > 35
    ) {
      review.push(
        "TOP_HOLDERS_OVER_35"
      );
    } else {
      evidence.push(
        "TOP_HOLDERS_UNDER_35"
      );
    }
  }

  /*
   * This audit does not prove the identity
   * of the dev/creator wallet.
   */
  review.push(
    "DEV_IDENTITY_NOT_PROVEN"
  );

  let decision = "PASS";

  if (block.length) {
    decision = "BLOCK";
  } else if (review.length) {
    decision = "REVIEW";
  }

  return {
    decision,

    blockReasons:
      uniq(block),

    reviewReasons:
      uniq(review),

    evidence:
      uniq(evidence),

    largestAccountCount:
      largest.length,

    resolvedOwners:
      owners.length-unresolved,

    unresolvedOwners:
      unresolved,

    uniqueOwners:
      ownerMap.size,

    maxAccountsSameOwner,

    clusteredOwnerCount:
      clusteredOwners.length,

    topOwners:
      ownerRows
        .slice(0,5)
        .map(x=>({
          owner:x.owner,
          amount:x.amount
        })),

    top20Amount:
      totalTop,

    error:null
  };
}

/*
 * Only candidates that are realistically
 * approaching entry need expensive RPC audit.
 */
const targets =
  (scan.candidates||[])
    .filter(c =>
      c.universeClass !== "NON_MEME" &&
      c.securityDecision === "PASS" &&
      Number(c.score||0) >= 70
    )
    .slice(0,8);

let pass=0;
let review=0;
let block=0;
let failed=0;

for (const c of targets) {
  const r =
    await inspect(c);

  c.holderClusterAudit = {
    version:"0.9.1",
    checkedAt:
      new Date().toISOString(),
    ...r
  };

  if (
    r.error ||
    r.reviewReasons.includes(
      "HOLDER_RPC_LARGEST_ACCOUNTS_FAILED"
    ) ||
    r.reviewReasons.includes(
      "HOLDER_OWNER_RESOLUTION_FAILED"
    )
  ) {
    failed++;
  }

  if (r.decision==="BLOCK") {
    block++;

    c.securityDecision =
      "BLOCK";

    c.decision =
      "IGNORE";

    c.securityBlockReasons =
      uniq([
        ...(c.securityBlockReasons||[]),
        ...r.blockReasons
      ]);

    c.hardReject =
      uniq([
        ...(c.hardReject||[]),
        ...r.blockReasons,
        "HOLDER_CLUSTER_BLOCK"
      ]);

  } else if (
    r.decision==="REVIEW"
  ) {
    review++;

    /*
     * Cannot be entry-ready while
     * dev identity remains unresolved.
     */
    c.securityDecision =
      "REVIEW";

    if (
      c.decision ===
      "PROBE_CANDIDATE"
    ) {
      c.decision="WATCH";
    }

    c.securityReviewReasons =
      uniq([
        ...(c.securityReviewReasons||[]),
        ...r.reviewReasons
      ]);

  } else {
    pass++;
  }
}

/*
 * Candidates >=70 that should have
 * been audited but weren't are fail-closed.
 */
for (
  const c of
  scan.candidates||[]
) {
  if (
    c.universeClass === "NON_MEME" ||
    Number(c.score||0) < 70 ||
    c.securityDecision === "BLOCK"
  ) {
    continue;
  }

  if (!c.holderClusterAudit) {
    c.holderClusterAudit = {
      version:"0.9.1",
      decision:"REVIEW",
      blockReasons:[],
      reviewReasons:[
        "HOLDER_CLUSTER_NOT_AUDITED"
      ],
      evidence:[]
    };

    c.securityDecision =
      "REVIEW";

    if (
      c.decision ===
      "PROBE_CANDIDATE"
    ) {
      c.decision="WATCH";
    }
  }
}

scan.holderClusterAudit = {
  version:"0.9.1",
  checkedAt:
    new Date().toISOString(),

  policy:
    "FAIL_CLOSED_DEV_IDENTITY_UNKNOWN",

  targetCount:
    targets.length,

  pass,
  review,
  block,
  failed,

  note:
    "RPC owner clustering is not equivalent to proven dev/insider identity"
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
  "=== MEME ALPHA HOLDER CLUSTER v0.9.1 ==="
);

console.log(
  `TARGETS=${targets.length}`
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

for (const c of targets) {
  const a =
    c.holderClusterAudit;

  console.log(
    [
      c.symbol,
      `score=${c.score}`,
      `audit=${a.decision}`,
      `owners=${a.uniqueOwners ?? "?"}`,
      `maxSameOwner=${a.maxAccountsSameOwner ?? "?"}`,
      `security=${c.securityDecision}`,
      `scan=${c.decision}`
    ].join(" | ")
  );
}

console.log(
  "DEV_IDENTITY_UNKNOWN=NO_LIVE_APPROVAL"
);

console.log(
  "LIVE_EXECUTION=DISABLED"
);
