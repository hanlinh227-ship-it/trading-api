# V78-002 — DecisionEvidence Schema

Status: IMPLEMENTED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE

## Integrity note
This document implements the V78-002 DecisionEvidence contract from the currently accepted V78 architecture requirements available to ChatGPT: every important trading decision must expose provider/source identity, timestamps, freshness, evidence, reasons and execution suitability without fabricating missing information.

The complete verbatim Claude Phase 2 body is still not retrievable from the current GitHub bus/session context available to ChatGPT. Therefore this document is **not falsely attributed as a verbatim Claude paste**. Claude must compare this contract against its exact Phase 2 schema before any production source begins consuming it. Any field-level mismatch must be corrected in documentation first.

No runtime object is created by V78-002. No gate, score, execution path, KV key or order behavior changes.

---

## 1. Purpose

`DecisionEvidence` is the common evidence envelope for Signal advisory decisions and future execution-aware decision pipelines.

It exists to answer, deterministically:

1. What instrument/market was evaluated?
2. Which providers supplied the evidence?
3. When was each datum produced and observed?
4. Is each datum LIVE, DELAYED, STALE, DEGRADED, MISSING or UNKNOWN?
5. Which structure/context/trigger/risk observations support or oppose the decision?
6. Is the evidence suitable for advisory display only, or also suitable for a new executable order?
7. Which hard gate blocked the decision, if any?
8. Was any value derived/fallback, and can that fallback legally influence execution?

UNKNOWN/MISSING must remain explicit. They must not be converted to zero, PASS or LIVE merely to complete the object.

---

## 2. Canonical schema

```ts
type EvidenceFreshness =
  | "LIVE"
  | "DELAYED"
  | "STALE"
  | "DEGRADED"
  | "MISSING"
  | "UNKNOWN";

type EvidenceSuitability =
  | "ADVISORY_ONLY"
  | "EXECUTION_ELIGIBLE"
  | "EXECUTION_BLOCKED"
  | "UNKNOWN";

type GateState = "PASS" | "BLOCK" | "DEGRADED" | "UNKNOWN" | "NOT_APPLICABLE";

type DecisionAction =
  | "MARKET"
  | "LIMIT"
  | "WATCH"
  | "HOLD"
  | "TIGHTEN"
  | "CUT"
  | "NO_TRADE"
  | "UNKNOWN";

interface DecisionEvidenceSource {
  provider: string;
  endpoint?: string | null;
  providerSymbol?: string | null;
  requestedSymbol?: string | null;
  instrumentType?: string | null;
  providerTimestamp?: number | null;
  observedAt: number;
  ageSec?: number | null;
  freshness: EvidenceFreshness;
  analysisOnly?: boolean;
  executionVerified?: boolean;
  degradedReason?: string | null;
}

interface DecisionEvidenceGate {
  name: string;
  state: GateState;
  reason?: string | null;
  evidenceRefs?: string[];
  checkedAt: number;
  hard?: boolean;
}

interface DecisionEvidenceObservation {
  id: string;
  category:
    | "PRICE"
    | "CANDLE"
    | "CONTEXT"
    | "STRUCTURE"
    | "LOCATION"
    | "TRIGGER"
    | "MICROSTRUCTURE"
    | "NEWS"
    | "RISK"
    | "ACCOUNT"
    | "EXECUTION_QUOTE"
    | "PORTFOLIO"
    | "OTHER";
  value: unknown;
  sourceRef?: string | null;
  freshness?: EvidenceFreshness;
  supports?: boolean | null;
  reason?: string | null;
}

interface DecisionEvidence {
  schemaVersion: "V78-002";

  decisionId: string;
  createdAt: number;

  market: "forex" | "crypto" | "metal" | "index" | "hyro" | "unknown";
  symbol: string;
  side?: "BUY" | "SELL" | null;
  action: DecisionAction;

  sources: Record<string, DecisionEvidenceSource>;
  observations: DecisionEvidenceObservation[];
  gates: DecisionEvidenceGate[];

  decision: {
    status: string;
    reason: string;
    score?: number | null;
    rr?: number | null;
    entry?: number | null;
    sl?: number | null;
    tp?: number | null;
    strategy?: string | null;
    profile?: string | null;
  };

  dataIntegrity: {
    overallFreshness: EvidenceFreshness;
    providerAgreement?: "AGREE" | "DISAGREE" | "SINGLE_SOURCE" | "UNKNOWN";
    staleRefs: string[];
    missingRefs: string[];
    degradedRefs: string[];
    fabricatedValues: false;
  };

  execution: {
    suitability: EvidenceSuitability;
    executionAuthority?: "NONE" | "HYRO" | "BROKER" | "EXCHANGE" | "UNKNOWN";
    quoteRef?: string | null;
    quoteFreshness?: EvidenceFreshness;
    hardBlockReasons: string[];
    accountId?: string | null;
  };

  lineage: {
    engine?: string | null;
    runtimeVersion?: string | null;
    sourceCommit?: string | null;
    scanId?: string | null;
    setupId?: string | null;
    parentDecisionId?: string | null;
  };
}
```

---

## 3. Required invariants

### 3.1 No fabricated values
`dataIntegrity.fabricatedValues` is permanently `false` by contract.

If a field is unavailable:
- use `null` where the schema allows;
- mark the corresponding source/evidence as MISSING or UNKNOWN;
- add a gate/block/degraded reason when that absence matters.

Never synthesize a numeric quote, spread, P/L, account equity or news clearance merely to avoid nulls.

### 3.2 Freshness is first-class evidence
Every price/candle/execution-sensitive provider datum must carry either:
- a provider timestamp and computed age; or
- explicit UNKNOWN/MISSING freshness when no trustworthy timestamp exists.

Do not label data LIVE without evidence.

### 3.3 Advisory and execution suitability are separate
A setup can remain useful as WATCH/advisory even when it is not safe for execution.

Examples:
- market structure valid but authoritative news unavailable → advisory may remain; executable order can be BLOCKED when policy requires news clearance;
- Twelve Data analysis quote fresh enough for analysis but lacks execution bid/ask → advisory can remain; execution must use an execution-authoritative quote;
- Signal crypto public Bybit/OKX analysis path does not acquire execution authority merely because its market data is fresh.

### 3.4 Hard gates cannot disappear inside a score
Freshness, hard-news policy, structural SL, account connection/risk and execution authority must remain separately inspectable gates.

A high score cannot override a BLOCK hard gate.

### 3.5 Provider disagreement is explicit
If two providers materially disagree:
- `providerAgreement = "DISAGREE"`;
- preserve each source independently;
- do not average them into a fabricated authoritative price;
- execution suitability follows the current execution-authority policy.

---

## 4. Recommended evidence categories by pipeline stage

Current target lifecycle:

```text
DISCOVERY
→ DATA INTEGRITY
→ CONTEXT
→ STRUCTURE
→ LOCATION
→ TRIGGER
→ RISK
→ EXECUTION QUOTE
→ DECISION
→ LIFECYCLE
```

Suggested evidence mapping:

| Stage | DecisionEvidence fields |
|---|---|
| Discovery | market/symbol, provider universe evidence, liquidity/turnover observations |
| Data integrity | sources, timestamps, freshness, agreement, missing/degraded refs |
| Context | macro/session/relative/market-regime observations |
| Structure | HTF trend/range/liquidity/swing observations |
| Location | premium/discount/retest/distance/ATR/location observations |
| Trigger | M5/M15 trigger, displacement/reclaim/breakout/retest observations |
| Risk | structural SL, RR, room, account/portfolio gates |
| Execution quote | authoritative quoteRef, bid/ask/mark/age, executionVerified |
| Decision | action/status/reason/score/entry/SL/TP |
| Lifecycle | lineage IDs and later decision chaining via parentDecisionId |

---

## 5. Signal-specific policy

Signal markets remain advisory unless a separately authorized execution adapter exists.

For current Signal crypto:
- public Bybit/OKX market data may populate analysis evidence;
- `execution.executionAuthority = "NONE"` for the Signal path;
- `execution.suitability = "ADVISORY_ONLY"` even when the analysis quote is fresh;
- no occurrence of a public market-data call should be interpreted as order authorization.

For advisory MARKET/LIMIT labels, `DecisionEvidence` must still preserve the distinction between recommendation style and actual broker/exchange execution.

---

## 6. Hyro-specific policy

Hyro is the current real-capital execution authority.

Before a new executable Hyro order can be marked `EXECUTION_ELIGIBLE`, evidence must support all currently mandatory gates, including:
- critical telemetry connected;
- account equity available;
- manual pause/auto-execution policy;
- daily target/hard-stop/risk caps;
- portfolio constraints;
- structural SL and order sizing;
- fresh execution-authoritative market state;
- idempotency/reconciliation requirements;
- hard-news/context evidence where active policy requires it.

Funding-rate evidence is MICROSTRUCTURE/CARRY evidence. It does not set the NEWS gate to PASS.

Optional/degraded `closedPnl` telemetry must remain visible as degraded freshness/availability and must not fabricate realized P/L.

---

## 7. Example — advisory crypto setup

```json
{
  "schemaVersion": "V78-002",
  "decisionId": "signal:crypto:XRPUSDT:example",
  "createdAt": 0,
  "market": "crypto",
  "symbol": "XRPUSDT",
  "side": "BUY",
  "action": "WATCH",
  "sources": {
    "analysisQuote": {
      "provider": "Bybit Spot",
      "providerSymbol": "XRPUSDT",
      "requestedSymbol": "XRPUSDT",
      "providerTimestamp": null,
      "observedAt": 0,
      "ageSec": null,
      "freshness": "UNKNOWN",
      "analysisOnly": true,
      "executionVerified": false
    }
  },
  "observations": [],
  "gates": [],
  "decision": {
    "status": "WATCH",
    "reason": "EXAMPLE_ONLY"
  },
  "dataIntegrity": {
    "overallFreshness": "UNKNOWN",
    "providerAgreement": "SINGLE_SOURCE",
    "staleRefs": [],
    "missingRefs": [],
    "degradedRefs": [],
    "fabricatedValues": false
  },
  "execution": {
    "suitability": "ADVISORY_ONLY",
    "executionAuthority": "NONE",
    "quoteRef": null,
    "quoteFreshness": "UNKNOWN",
    "hardBlockReasons": []
  },
  "lineage": {}
}
```

The numeric/timestamp values above are intentionally not invented; the example uses null/zero placeholders only as schema illustration and is not trading evidence.

---

## 8. Migration / adoption plan — not authorized by V78-002

V78-002 is documentation only. Future source adoption must be separate issues and should proceed shadow-first:

1. define a shared schema/helper module;
2. populate `DecisionEvidence` alongside existing decision objects;
3. compare output deterministically without changing decisions;
4. expose evidence in diagnostics/logging;
5. only after parity review, let downstream UI/execution consumers rely on the shared object;
6. remove legacy duplicated evidence fields only in later reviewed cutovers.

No current production consumer is changed by this issue.

---

## 9. Acceptance criteria

- [x] Common evidence envelope is documented.
- [x] Provider identity, provider symbol, timestamps, age and freshness are first-class fields.
- [x] Missing/stale/degraded states remain explicit.
- [x] Advisory suitability is separate from execution eligibility.
- [x] Hard gates remain inspectable and cannot be overridden by a score.
- [x] Provider disagreement is explicit.
- [x] Signal public-data analysis cannot imply execution authority.
- [x] Hyro execution-specific evidence requirements are represented.
- [x] Funding does not substitute for news evidence.
- [x] No runtime behavior, risk, state key, order, Telegram route or provider call changed.

## Reviewer request
Claude should compare this document field-for-field against its exact Phase 2 `DecisionEvidence` schema. Return PASS/WARN/BLOCK and provide an exact replacement block for any schema difference before a future source/shadow implementation begins.
