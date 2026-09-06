# Meme Alpha V378 behavior diagnostic

- checked_at_utc: `2026-09-06T05:21:27Z`
- executor_marker: `true`
- micro_live_service: `active`
- paper_service: `active`
- signer_service: `active`
- micro_live_pid_count: `1`

## Runtime files

### /opt/meme-alpha/app/runtime-status/micro-live-gate.json
```json
{
  "version": "2.4.0",
  "timestamp": "2026-09-06T05:21:07.034Z",
  "allowed": false,
  "analysisMode": "PAPER",
  "executionMode": "MICRO_LIVE",
  "armOk": false,
  "signer": {
    "ok": true,
    "mode": "READY",
    "signingEnabled": true,
    "walletLoaded": true,
    "arbitraryRawSign": false
  },
  "sourceHealthy": true,
  "riskEntryAllowed": false,
  "paperRiskEntryAllowed": false,
  "liveRiskReady": false,
  "paperCapacityBlocksIgnoredForMicroLive": [],
  "riskGlobalBlockReasons": [
    "SOURCE_HEALTH_DEGRADED"
  ],
  "riskLiveBlockReasons": [
    "SOURCE_HEALTH_DEGRADED"
  ],
  "policyRevision": "2.6.0-trend-autopilot",
  "validationStatus": "ACCUMULATING",
  "validationCompletedLifecycles": 1,
  "stressStatus": "INSUFFICIENT_DATA",
  "stressFail": 0,
  "evidenceReady": false,
  "scaleAllowed": false,
  "reasons": [
    "ROOT_ARMING_FILE_ABSENT_OR_INVALID",
    "RISK_NOT_READY"
  ]
}
```

### /opt/meme-alpha/app/runtime-status/signal-snapshot.json
```json
 ],
      "entryGuardReasons": [],
      "token2022": false,
      "pairAddress": null,
      "sellRoute": null,
      "liquidityUsd": 4163585.195325569,
      "sellPriceImpactPct": null,
      "sellQuoteHttp": null,
      "sellQuoteError": null,
      "sellImpactPct": null,
      "priceImpactPct": null,
      "organicRatio5m": 0.0054,
      "netBuyers5m": 11,
      "priceChange5m": 0.28593965961101164,
      "buyVolume5m": 17740.6788822051,
      "sellVolume5m": 10141.333118448714,
      "dexVolume5m": 5315.26,
      "dexBuys5m": 22,
      "dexSells5m": 23,
      "buySellRatio5m": 1.7493438658406708,
      "sources": [
        "toptraded"
      ],
      "persistenceDecision": "IGNORE",
      "consecutiveEligible": 0,
      "fastTrackReady": false,
      "avgScoreLast2": 59.5,
      "avgNetBuyersLast2": 12,
      "scoreSlopeLast2": -5,
      "liquidityStableLast2": true,
      "holderAuditDecision": null,
      "holderReviewReasons": [],
      "holderBlockReasons": [],
      "holderEvidence": [],
      "securityReviewReasons": [
        "SELL_ROUTE_NOT_VERIFIED"
      ],
      "securityBlockReasons": [
        "NON_MEME_UNIVERSE"
      ],
      "securityEvidence": [
        "MINT_AUTHORITY_DISABLED",
        "FREEZE_AUTHORITY_DISABLED",
        "TOP_HOLDERS_ACCEPTABLE",
        "JUPITER_LIQUIDITY_PASS",
        "DEX_LIQUIDITY_PASS"
      ],
      "mintAuthorityDisabled": true,
      "freezeAuthorityDisabled": true,
      "topHoldersPct": 15.422288017390448,
      "dexLiquidityUsd": 480039.39,
      "needsExtensionAudit": false,
      "transferHookActive": false,
      "permanentDelegateActive": false,
      "nonTransferable": false,
      "liquidityChange5mPct": null,
      "intelMode": "FEED_HEALTHY_ROW_MISSING",
      "intelHaircut": 0.68,
      "realtimeFeedFresh": true,
      "whaleFeedFresh": true,
      "realtimeRowFresh": false,
      "whaleRowFresh": false,
      "whaleTop10Pct": null,
      "whaleDeltaTop10Pct": null,
      "strategyRouter": {
        "selectedLane": null,
        "promotionEligible": false,
        "boost": 0,
        "effectiveScore": 38.76,
        "marketRegime": "HOT_MOMENTUM",
        "radar": {
          "pairAgeSec": null,
          "fastDiscoveryLane": false,
          "preScore": null,
          "discoveryPriority": null,
          "ageBucket": null
        },
        "rtPulse": false,
        "rtBurst": false,
        "events5s": 0,
        "eventMomentum": 0,
        "lastEventAgeMs": null,
        "lanes": [
          {
            "lane": "LAUNCH_FAST",
            "eligible": false,
            "quality": 59.75,
            "conditions": {
              "launchFresh": false,
              "launchConfirm": false,
              "fastDiscoveryLane": false,
              "pairAgeSec": null,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": true
            }
          },
          {
            "lane": "MOMENTUM",
            "eligible": false,
            "quality": 60.44,
            "conditions": {
              "momentumConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": false
            }
          },
          {
            "lane": "RECOVERY_FLOW",
            "eligible": false,
            "quality": 59.42,
            "conditions": {
              "recoveryTrend": false,
              "recoveryConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": true,
              "slope": -5,
              "avgNetBuyersLast2": 12
            }
          },
          {
            "lane": "ESTABLISHED_ROTATION",
            "eligible": false,
            "quality": 66.66,
            "conditions": {
              "established": true,
              "rotationConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": true
            }
          }
        ]
      }
    },
    {
      "mint": "SKHYhSjuRWHgikq8eRKbtBbpABgJSkd7ytQV14i9EQ3",
      "symbol": "SKHY",
      "name": "SK Hynix - Backpack Securities",
      "score": 38.08,
      "originalScore": 56,
      "decision": "IGNORE",
      "universeClass": "UNCLASSIFIED",
      "universeConfidence": "LOW",
      "securityDecision": "BLOCK",
      "holderClusterDecision": null,
      "devIdentityProven": false,
      "holderClusterMaxAccountsSameOwner": 0,
      "hardReject": [
        "MEME_EVIDENCE_INSUFFICIENT",
        "SECURITY_BLOCK",
        "TOKEN2022_PERMANENT_DELEGATE",
        "TOKEN2022_TRANSFER_HOOK",
        "TOKEN2022_SECURITY_BLOCK",
        "V369_TOKEN2022_DANGEROUS"
      ],
      "entryGuardReasons": [],
      "token2022": true,
      "pairAddress": null,
      "sellRoute": null,
      "liquidityUsd": 1936148.3293104954,
      "sellPriceImpactPct": null,
      "sellQuoteHttp": null,
      "sellQuoteError": null,
      "sellImpactPct": null,
      "priceImpactPct": null,
      "organicRatio5m": 0,
      "netBuyers5m": 4,
      "priceChange5m": 0.08076681832477446,
      "buyVolume5m": 62333.86991188802,
      "sellVolume5m": 21558.7701482265,
      "dexVolume5m": 41481.19,
      "dexBuys5m": 34,
      "dexSells5m": 0,
      "buySellRatio5m": 2.8913462819684925,
      "sources": [
        "toptraded"
      ],
      "persistenceDecision": "IGNORE",
      "consecutiveEligible": 0,
      "fastTrackReady": false,
      "avgScoreLast2": 56,
      "avgNetBuyersLast2": 3,
      "scoreSlopeLast2": 0,
      "liquidityStableLast2": true,
      "holderAuditDecision": null,
      "holderReviewReasons": [],
      "holderBlockReasons": [],
      "holderEvidence": [],
      "securityReviewReasons": [
        "MINT_AUTHORITY_UNKNOWN",
        "FREEZE_AUTHORITY_UNKNOWN",
        "TOP_HOLDERS_ELEVATED",
        "TOKEN2022_EXTENSION_AUDIT_REQUIRED",
        "SELL_ROUTE_NOT_VERIFIED"
      ],
      "securityBlockReasons": [
        "MEME_EVIDENCE_INSUFFICIENT",
        "TOKEN2022_PERMANENT_DELEGATE",
        "TOKEN2022_TRANSFER_HOOK"
      ],
      "securityEvidence": [
        "JUPITER_LIQUIDITY_PASS",
        "DEX_LIQUIDITY_PASS"
      ],
      "mintAuthorityDisabled": null,
      "freezeAuthorityDisabled": null,
      "topHoldersPct": 36.97285834217009,
      "dexLiquidityUsd": 2467349.84,
      "needsExtensionAudit": true,
      "transferHookActive": false,
      "permanentDelegateActive": false,
      "nonTransferable": false,
      "liquidityChange5mPct": null,
      "intelMode": "FEED_HEALTHY_ROW_MISSING",
      "intelHaircut": 0.68,
      "realtimeFeedFresh": true,
      "whaleFeedFresh": true,
      "realtimeRowFresh": false,
      "whaleRowFresh": false,
      "whaleTop10Pct": null,
      "whaleDeltaTop10Pct": null,
      "strategyRouter": {
        "selectedLane": null,
        "promotionEligible": false,
        "boost": 0,
        "effectiveScore": 38.08,
        "marketRegime": "HOT_MOMENTUM",
        "radar": {
          "pairAgeSec": null,
          "fastDiscoveryLane": false,
          "preScore": null,
          "discoveryPriority": null,
          "ageBucket": null
        },
        "rtPulse": false,
        "rtBurst": false,
        "events5s": 0,
        "eventMomentum": 0,
        "lastEventAgeMs": null,
        "lanes": [
          {
            "lane": "LAUNCH_FAST",
            "eligible": false,
            "quality": 57,
            "conditions": {
              "launchFresh": false,
              "launchConfirm": false,
              "fastDiscoveryLane": false,
              "pairAgeSec": null,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": false,
              "flowOk": true,
              "momentumOk": false
            }
          },
          {
            "lane": "MOMENTUM",
            "eligible": false,
            "quality": 57.24,
            "conditions": {
              "momentumConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": false,
              "flowOk": true,
              "momentumOk": false
            }
          },
          {
            "lane": "RECOVERY_FLOW",
            "eligible": false,
            "quality": 56.88,
            "conditions": {
              "recoveryTrend": true,
              "recoveryConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": false,
              "flowOk": true,
              "momentumOk": false,
              "slope": 0,
              "avgNetBuyersLast2": 3
            }
          },
          {
            "lane": "ESTABLISHED_ROTATION",
            "eligible": false,
            "quality": 63.07,
            "conditions": {
              "established": true,
              "rotationConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": false
            }
          }
        ]
      }
    },
    {
      "mint": "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g",
      "symbol": "HYPE",
      "name": "HYPE",
      "score": 36.04,
      "originalScore": 53,
      "decision": "IGNORE",
      "universeClass": "UNCLASSIFIED",
      "universeConfidence": "LOW",
      "securityDecision": "BLOCK",
      "holderClusterDecision": null,
      "devIdentityProven": false,
      "holderClusterMaxAccountsSameOwner": 0,
      "hardReject": [
        "MEME_EVIDENCE_INSUFFICIENT",
        "SECURITY_BLOCK"
      ],
      "entryGuardReasons": [],
      "token2022": false,
      "pairAddress": null,
      "sellRoute": null,
      "liquidityUsd": 6508596.156967909,
      "sellPriceImpactPct": null,
      "sellQuoteHttp": null,
      "sellQuoteError": null,
      "sellImpactPct": null,
      "priceImpactPct": null,
      "organicRatio5m": 0.0156,
      "netBuyers5m": 7,
      "priceChange5m": 0.14994025703883448,
      "buyVolume5m": 148145.85543134247,
      "sellVolume5m": 94626.2605428319,
      "dexVolume5m": 12134.68,
      "dexBuys5m": 13,
      "dexSells5m": 13,
      "buySellRatio5m": 1.565589241099571,
      "sources": [
        "toptraded"
      ],
      "persistenceDecision": "IGNORE",
      "consecutiveEligible": 0,
      "fastTrackReady": false,
      "avgScoreLast2": 53,
      "avgNetBuyersLast2": 6.5,
      "scoreSlopeLast2": 0,
      "liquidityStableLast2": true,
      "holderAuditDecision": null,
      "holderReviewReasons": [],
      "holderBlockReasons": [],
      "holderEvidence": [],
      "securityReviewReasons": [
        "MINT_AUTHORITY_UNKNOWN",
        "SELL_ROUTE_NOT_VERIFIED"
      ],
      "securityBlockReasons": [
        "MEME_EVIDENCE_INSUFFICIENT"
      ],
      "securityEvidence": [
        "FREEZE_AUTHORITY_DISABLED",
        "TOP_HOLDERS_ACCEPTABLE",
        "JUPITER_LIQUIDITY_PASS",
        "DEX_LIQUIDITY_PASS"
      ],
      "mintAuthorityDisabled": null,
      "freezeAuthorityDisabled": true,
      "topHoldersPct": 29.197727896698584,
      "dexLiquidityUsd": 306428.73,
      "needsExtensionAudit": false,
      "transferHookActive": false,
      "permanentDelegateActive": false,
      "nonTransferable": false,
      "liquidityChange5mPct": null,
      "intelMode": "FEED_HEALTHY_ROW_MISSING",
      "intelHaircut": 0.68,
      "realtimeFeedFresh": true,
      "whaleFeedFresh": true,
      "realtimeRowFresh": false,
      "whaleRowFresh": false,
      "whaleTop10Pct": null,
      "whaleDeltaTop10Pct": null,
      "strategyRouter": {
        "selectedLane": null,
        "promotionEligible": false,
        "boost": 0,
        "effectiveScore": 36.04,
        "marketRegime": "HOT_MOMENTUM",
        "radar": {
          "pairAgeSec": null,
          "fastDiscoveryLane": false,
          "preScore": null,
          "discoveryPriority": null,
          "ageBucket": null
        },
        "rtPulse": false,
        "rtBurst": false,
        "events5s": 0,
        "eventMomentum": 0,
        "lastEventAgeMs": null,
        "lanes": [
          {
            "lane": "LAUNCH_FAST",
            "eligible": false,
            "quality": 54.75,
            "conditions": {
              "launchFresh": false,
              "launchConfirm": false,
              "fastDiscoveryLane": false,
              "pairAgeSec": null,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": false
            }
          },
          {
            "lane": "MOMENTUM",
            "eligible": false,
            "quality": 55.17,
            "conditions": {
              "momentumConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": false,
              "flowOk": true,
              "momentumOk": false
            }
          },
          {
            "lane": "RECOVERY_FLOW",
            "eligible": false,
            "quality": 54.54,
            "conditions": {
              "recoveryTrend": true,
              "recoveryConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": false,
              "flowOk": true,
              "momentumOk": false,
              "slope": 0,
              "avgNetBuyersLast2": 6.5
            }
          },
          {
            "lane": "ESTABLISHED_ROTATION",
            "eligible": false,
            "quality": 62.72,
            "conditions": {
              "established": true,
              "rotationConfirm": false,
              "scoreOk": true,
              "liquidityOk": true,
              "buyersOk": true,
              "flowOk": true,
              "momentumOk": false
            }
          }
        ]
      }
    }
  ]
}
```

### /opt/meme-alpha/app/runtime-status/whale-flow-intel.json
```json
{
  "version": "3.70.0-adaptive-whale",
  "fallbackRevision": "rugcheck-holder-fallback-v1",
  "scheduleRevision": "held-priority-2of3",
  "updatedAt": "2026-09-06T05:21:23.937Z",
  "status": "HEALTHY_CACHED_RATE_SHAPED",
  "rpcConfigured": true,
  "providerCount": 3,
  "providers": [
    {
      "index": 0,
      "label": "api.mainnet-beta.solana.com",
      "kind": "PUBLIC_READ_ONLY_FALLBACK",
      "failures": 13,
      "cooldownMsRemaining": 216012,
      "lastOkAt": "2026-09-06T05:19:58.621Z",
      "lastError": "RPC_429"
    },
    {
      "index": 1,
      "label": "solana-rpc.publicnode.com",
      "kind": "PUBLIC_READ_ONLY_FALLBACK",
      "failures": 280,
      "cooldownMsRemaining": 59122,
      "lastOkAt": null,
      "lastError": "RPC_403_-32602"
    },
    {
      "index": 2,
      "label": "api.mainnet.solana.com",
      "kind": "PUBLIC_READ_ONLY_FALLBACK",
      "failures": 61,
      "cooldownMsRemaining": 218341,
      "lastOkAt": null,
      "lastError": "RPC_429"
    }
  ],
  "rugcheckFallback": true,
  "rateShaped": true,
  "cycleMs": 15000,
  "rpcSpacingMs": 1800,
  "rugcheckSpacingMs": 15000,
  "oneMintPerCycle": true,
  "singleFlightCycles": true,
  "supplyCacheMs": 600000,
  "rowFreshnessTtlMs": 180000,
  "heldRowTtlMs": 600000,
  "heldPositionsAlwaysMonitored": true,
  "readOnlyPublicFallbacks": true,
  "inspectedMint": "2fUFhZyd47Mapv9wcfXh5gnQwFXtqcYu9xAN4THBpump",
  "inspectedKind": "HELD",
  "heldQueueSize": 4,
  "otherQueueSize": 15,
  "rows": [
    {
      "mint": "2fUFhZyd47Mapv9wcfXh5gnQwFXtqcYu9xAN4THBpump",
      "observedAt": "2026-09-06T05:21:23.937Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 19.1211,
      "top10Pct": 38.3242,
      "deltaTop10Pct": 0,
      "holderPressureScore": 4.335,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 1,
      "rugcheckScoreNormalised": 1,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_403_-32602"
    },
    {
      "mint": "G8aVC4nk5oPWzTHp4PDm3kAuixCebv9WRQMD93h9pump",
      "observedAt": "2026-09-06T05:20:51.009Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 6.6739,
      "top10Pct": 20.5838,
      "deltaTop10Pct": 0,
      "holderPressureScore": 7.883,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 1,
      "rugcheckScoreNormalised": 1,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_429_BACKOFF"
    },
    {
      "mint": "8PzFWyLpCVEmbZmVJcaRTU5r69XKJx1rd7YGpWvnpump",
      "observedAt": "2026-09-06T05:20:35.341Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 8.1819,
      "top10Pct": 26.4173,
      "deltaTop10Pct": 0,
      "holderPressureScore": 6.717,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 1,
      "rugcheckScoreNormalised": 1,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_429_BACKOFF"
    },
    {
      "mint": "HgBRWfYxEfvPhtqkaeymCQtHCrKE46qQ43pKe8HCpump",
      "observedAt": "2026-09-06T05:20:19.462Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 8.5755,
      "top10Pct": 31.4714,
      "deltaTop10Pct": 0,
      "holderPressureScore": 5.706,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 1,
      "rugcheckScoreNormalised": 1,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_403_-32602"
    },
    {
      "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
      "observedAt": "2026-09-06T05:21:07.786Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 24.7726,
      "top10Pct": 66.2728,
      "deltaTop10Pct": 0,
      "holderPressureScore": -1.255,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 101,
      "rugcheckScoreNormalised": 7,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_429_BACKOFF"
    },
    {
      "mint": "CaWZeUM4FvX9dPkjGc2xHS6tSN3qJfTWyvaG77aM5o7h",
      "observedAt": "2026-09-06T05:19:27.219Z",
      "sourceMode": "RUGCHECK_CACHED",
      "externalFallback": true,
      "top1Pct": 3.3556,
      "top10Pct": 21.2856,
      "deltaTop10Pct": 0,
      "holderPressureScore": 7.743,
      "whaleFlowScore": 0,
      "supplyCached": true,
      "supply": null,
      "providerCount": 3,
      "rugcheckScore": 1,
      "rugcheckScoreNormalised": 1,
      "rugcheckRiskLevel": null,
      "lpLockedPct": null,
      "mintAuthority": null,
      "freezeAuthority": null,
      "dangerRisks": [],
      "rpcFallbackReason": "RPC_429_BACKOFF"
    }
  ],
  "error": null
}
```

### /opt/meme-alpha/app/runtime-status/trend-pulse.json
```json
{
  "version": "2.9.0",
  "timestamp": "2026-09-06T05:21:26.106Z",
  "source": "DEXSCREENER_TOKENS_V1",
  "pollMs": 3000,
  "signalTimestamp": "2026-09-06T05:21:06.953Z",
  "candidateCount": 15,
  "pairRows": 15,
  "rows": [
    {
      "mint": "GbbesPbaYh5uiAZSYNXTc7w9jty1rpg3P9L4JeN4LkKc",
      "symbol": "TRX",
      "name": "TRON",
      "pairAddress": "HpgV2jnzgrGfrZjeZGkHgTnEgRFAhtzCVuk3BRFTFJwk",
      "dexId": "raydium",
      "narrative": "OTHER",
      "status": "BREAKOUT",
      "pulseScore": 100,
      "price5m": 0.06,
      "price1h": 0.04,
      "buys5": 66,
      "sells5": 0,
      "tx5": 66,
      "volume5mUsd": 16231.54,
      "volume1hUsd": 45440.86,
      "volumeAcceleration": 6.113,
      "txnAcceleration": 14.235,
      "buySellRatio": 20,
      "buyPressure": 1,
      "liquidityUsd": 12393833.87,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 551006.5
    },
    {
      "mint": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",
      "symbol": "USELESS",
      "name": "USELESS COIN",
      "pairAddress": "Q2sPHPdUWFMg7M7wwrQKLrn619cAucfRsmhVJffodSp",
      "dexId": "raydium",
      "narrative": "ABSURD_ANTI_VALUE",
      "status": "BREAKOUT",
      "pulseScore": 87,
      "price5m": 5.68,
      "price1h": 3.26,
      "buys5": 331,
      "sells5": 224,
      "tx5": 555,
      "volume5mUsd": 108735.63,
      "volume1hUsd": 806289.7,
      "volumeAcceleration": 1.715,
      "txnAcceleration": 2.218,
      "buySellRatio": 1.476,
      "buyPressure": 0.193,
      "liquidityUsd": 4898457.32,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 696418.2
    },
    {
      "mint": "SKHYhSjuRWHgikq8eRKbtBbpABgJSkd7ytQV14i9EQ3",
      "symbol": "SKHY",
      "name": "SK Hynix - Backpack Securities",
      "pairAddress": "DPAU7wDyMXDgNAfzQYMfyNqmTjzcoRsSPA2LeGH71hgi",
      "dexId": "meteora",
      "narrative": "OTHER",
      "status": "WARMING",
      "pulseScore": 86,
      "price5m": 0,
      "price1h": 0.2,
      "buys5": 34,
      "sells5": 0,
      "tx5": 34,
      "volume5mUsd": 41481.19,
      "volume1hUsd": 43000.24,
      "volumeAcceleration": 20,
      "txnAcceleration": 20,
      "buySellRatio": 20,
      "buyPressure": 1,
      "liquidityUsd": 2467349.84,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 82317.7
    },
    {
      "mint": "taoC6xyv2v8tDLcev4uaGUgV4vdQsWJrGft2kcBRrBY",
      "symbol": "TAO",
      "name": "Bittensor",
      "pairAddress": "8j5pX8SQnTLQ5zU28gbcRmKrUKEYvrqdvEm4GEPxmqki",
      "dexId": "meteora",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 85,
      "price5m": 9.7,
      "price1h": 2143859,
      "buys5": 1287,
      "sells5": 1001,
      "tx5": 2288,
      "volume5mUsd": 182418.03,
      "volume1hUsd": 242598.57,
      "volumeAcceleration": 20,
      "txnAcceleration": 14.456,
      "buySellRatio": 1.285,
      "buyPressure": 0.125,
      "liquidityUsd": 36765.02,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 67985.2
    },
    {
      "mint": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
      "symbol": "ORCA",
      "name": "Orca",
      "pairAddress": "Hxw77h9fEx598afiiZunwHaX3vYu9UskDk9EpPNZp1mG",
      "dexId": "orca",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 69,
      "price5m": 0.78,
      "price1h": 0.6,
      "buys5": 32,
      "sells5": 56,
      "tx5": 88,
      "volume5mUsd": 19896.21,
      "volume1hUsd": 133779.1,
      "volumeAcceleration": 1.922,
      "txnAcceleration": 1.126,
      "buySellRatio": 0.579,
      "buyPressure": -0.273,
      "liquidityUsd": 544224.36,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 1404517.7
    },
    {
      "mint": "Ai66LHZG9MCzg1WKdawwqduVAXpNDUuV8M3uyq5ppump",
      "symbol": "CATE",
      "name": "Cate",
      "pairAddress": "HMzvsEEmtzHhvZNw9uwbaG85HCTmFnkbhzUx16cy7ca3",
      "dexId": "pumpswap",
      "narrative": "CAT",
      "status": "NEUTRAL",
      "pulseScore": 62,
      "price5m": 1.33,
      "price1h": -10.83,
      "buys5": 111,
      "sells5": 31,
      "tx5": 142,
      "volume5mUsd": 21745.79,
      "volume1hUsd": 577432.24,
      "volumeAcceleration": 0.43,
      "txnAcceleration": 0.679,
      "buySellRatio": 3.5,
      "buyPressure": 0.563,
      "liquidityUsd": 1829852.87,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 59808.7
    },
    {
      "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "symbol": "Bonk",
      "name": "Bonk",
      "pairAddress": "5zpyutJu9ee6jFymDGoK7F6S5Kczqtc9FomP3ueKuyA9",
      "dexId": "orca",
      "narrative": "DOG_WIF",
      "status": "NEUTRAL",
      "pulseScore": 61,
      "price5m": 0.62,
      "price1h": 2.17,
      "buys5": 23,
      "sells5": 116,
      "tx5": 139,
      "volume5mUsd": 2678.56,
      "volume1hUsd": 36084.46,
      "volumeAcceleration": 0.882,
      "txnAcceleration": 1.867,
      "buySellRatio": 0.205,
      "buyPressure": -0.669,
      "liquidityUsd": 324473.02,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 1944861
    },
    {
      "mint": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",
      "symbol": "BOME",
      "name": "BOOK OF MEME",
      "pairAddress": "DSUvc5qf5LJHHV5e2tD184ixotSnCnwj7i4jJa4Xsrmt",
      "dexId": "raydium",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 60,
      "price5m": 0.58,
      "price1h": 4.88,
      "buys5": 104,
      "sells5": 46,
      "tx5": 150,
      "volume5mUsd": 51174.12,
      "volume1hUsd": 1380059.32,
      "volumeAcceleration": 0.424,
      "txnAcceleration": 0.477,
      "buySellRatio": 2.234,
      "buyPressure": 0.387,
      "liquidityUsd": 16948613.2,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 1304514.6
    },
    {
      "mint": "HxQhDGYqyjorgogMJx7YbBHADEDxuHhLnMMmr6VYpyn",
      "symbol": "MANLET",
      "name": "MANLET",
      "pairAddress": "BNEeD53WYjj8qfHEZtbUXyc1eL1cQv5HLb5H6yKgN7eo",
      "dexId": "raydium",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 59,
      "price5m": 5.32,
      "price1h": -8.23,
      "buys5": 6,
      "sells5": 0,
      "tx5": 6,
      "volume5mUsd": 2538.71,
      "volume1hUsd": 61517.22,
      "volumeAcceleration": 0.473,
      "txnAcceleration": 0.504,
      "buySellRatio": 7,
      "buyPressure": 1,
      "liquidityUsd": 219566.39,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 45052.3
    },
    {
      "mint": "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx",
      "symbol": "STONK",
      "name": "STONK",
      "pairAddress": "7a8xxAJBELDo6P9dikSYctdw6ce8F4mWr3ahcAD8Ao49",
      "dexId": "raydium",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 55,
      "price5m": 2.43,
      "price1h": 1.25,
      "buys5": 30,
      "sells5": 0,
      "tx5": 30,
      "volume5mUsd": 9215.69,
      "volume1hUsd": 534085.43,
      "volumeAcceleration": 0.193,
      "txnAcceleration": 0.379,
      "buySellRatio": 20,
      "buyPressure": 1,
      "liquidityUsd": 1291000.58,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 63974.2
    },
    {
      "mint": "CaWZeUM4FvX9dPkjGc2xHS6tSN3qJfTWyvaG77aM5o7h",
      "symbol": "AGI",
      "name": "artificial gooner intelligence",
      "pairAddress": "DPh4Cfctg8yycPZP6zVmhQJZ1tHSvByKAbBLjhLBVitW",
      "dexId": "raydium",
      "narrative": "AI_TECH_PARODY",
      "status": "NEUTRAL",
      "pulseScore": 55,
      "price5m": 4.96,
      "price1h": 61.37,
      "buys5": 60,
      "sells5": 29,
      "tx5": 89,
      "volume5mUsd": 17617.62,
      "volume1hUsd": 866392.99,
      "volumeAcceleration": 0.228,
      "txnAcceleration": 0.393,
      "buySellRatio": 2.033,
      "buyPressure": 0.348,
      "liquidityUsd": 306345.94,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 2314.5
    },
    {
      "mint": "A7bdiYdS5GjqGFtxf17ppRHtDKPkkRqbKtR27dxvQXaS",
      "symbol": "ZEC",
      "name": "Zcash",
      "pairAddress": "GTHKH8s82ZR8GTSFZ1dUu6wfdxhy59wpMShxzG5zjiPm",
      "dexId": "orca",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 47,
      "price5m": 0.62,
      "price1h": 7.86,
      "buys5": 51,
      "sells5": 52,
      "tx5": 103,
      "volume5mUsd": 17926.99,
      "volume1hUsd": 418730.6,
      "volumeAcceleration": 0.492,
      "txnAcceleration": 0.805,
      "buySellRatio": 0.981,
      "buyPressure": -0.01,
      "liquidityUsd": 2733787.48,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 456751.5
    },
    {
      "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
      "symbol": "JUP",
      "name": "Jupiter",
      "pairAddress": "C1MgLojNLWBKADvu9BHdtgzz1oZX4dZ5zGdGcgvvW8Wz",
      "dexId": "orca",
      "narrative": "CRYPTO_META",
      "status": "NEUTRAL",
      "pulseScore": 47,
      "price5m": 0.19,
      "price1h": 1.02,
      "buys5": 30,
      "sells5": 29,
      "tx5": 59,
      "volume5mUsd": 7064.77,
      "volume1hUsd": 117370.49,
      "volumeAcceleration": 0.705,
      "txnAcceleration": 0.522,
      "buySellRatio": 1.033,
      "buyPressure": 0.017,
      "liquidityUsd": 480001.43,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 1366606
    },
    {
      "mint": "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g",
      "symbol": "HYPE",
      "name": "HYPE",
      "pairAddress": "6oQ9wVex4mKZti2GsGCfD8FWTMMC9PLQkztRU5cd6MK8",
      "dexId": "meteora",
      "narrative": "OTHER",
      "status": "NEUTRAL",
      "pulseScore": 43,
      "price5m": 0.16,
      "price1h": 1.01,
      "buys5": 13,
      "sells5": 15,
      "tx5": 28,
      "volume5mUsd": 12140.17,
      "volume1hUsd": 223816.9,
      "volumeAcceleration": 0.631,
      "txnAcceleration": 0.496,
      "buySellRatio": 0.875,
      "buyPressure": -0.071,
      "liquidityUsd": 306254.23,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 453062.7
    },
    {
      "mint": "HcRLc9VDgjLeK154xDawfb1dmVJ98DoSqcwTHGqiDeJR",
      "symbol": "ZCAT",
      "name": "Anonymous Cat",
      "pairAddress": "BTccxxTFi7a9xJTE1exKn38Jgie35s6gNeRxd8DM61Rc",
      "dexId": "raydium",
      "narrative": "CAT",
      "status": "NEUTRAL",
      "pulseScore": 35,
      "price5m": -7.62,
      "price1h": 30.3,
      "buys5": 185,
      "sells5": 40,
      "tx5": 225,
      "volume5mUsd": 211186.43,
      "volume1hUsd": 3132123.59,
      "volumeAcceleration": 0.795,
      "txnAcceleration": 0.794,
      "buySellRatio": 4.537,
      "buyPressure": 0.644,
      "liquidityUsd": 1478448.89,
      "activeBoosts": 0,
      "promotionFlag": false,
      "pairAgeMin": 8991.5
    }
  ],
  "themes": [
    {
      "narrative": "ABSURD_ANTI_VALUE",
      "count": 1,
      "breakouts": 1,
      "warming": 0,
      "avgPulse": 87,
      "avgVolAccel": 1.72,
      "totalVolume5mUsd": 108735.63,
      "promoted": 0,
      "symbols": [
        "USELESS"
      ],
      "strength": 57
    },
    {
      "narrative": "CAT",
      "count": 2,
      "breakouts": 0,
      "warming": 0,
      "avgPulse": 48.5,
      "avgVolAccel": 0.61,
      "totalVolume5mUsd": 232932.22,
      "promoted": 0,
      "symbols": [
        "CATE",
        "ZCAT"
      ],
      "strength": 38
    },
    {
      "narrative": "DOG_WIF",
      "count": 1,
      "breakouts": 0,
      "warming": 0,
      "avgPulse": 61,
      "avgVolAccel": 0.88,
      "totalVolume5mUsd": 2678.56,
      "promoted": 0,
      "symbols": [
        "Bonk"
      ],
      "strength": 31
    },
    {
      "narrative": "AI_TECH_PARODY",
      "count": 1,
      "breakouts": 0,
      "warming": 0,
      "avgPulse": 55,
      "avgVolAccel": 0.23,
      "totalVolume5mUsd": 17617.62,
      "promoted": 0,
      "symbols": [
        "AGI"
      ],
      "strength": 29
    },
    {
      "narrative": "CRYPTO_META",
      "count": 1,
      "breakouts": 0,
      "warming": 0,
      "avgPulse": 47,
      "avgVolAccel": 0.7,
      "totalVolume5mUsd": 7064.77,
      "promoted": 0,
      "symbols": [
        "JUP"
      ],
      "strength": 26
    }
  ]
}
```

### /opt/meme-alpha/app/runtime-status/realtime-pool-pulse.json
```json
"pairAgeSec": 84096.614,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 482536,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 40925
    },
    {
      "mint": "MukLDtJ8Cx9DxLbeyLRSWPSposTMWuwHANbuaudpump",
      "symbol": "OTC",
      "pair": "DA4pM4xSDY4M9V4CgAKKBVH1pw1yscTQQa5nEkGHuKpt",
      "preScore": 38,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 53.146,
      "pairAgeSec": 748089.614,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 7861044,
      "events1s": 0,
      "events5s": 3,
      "events15s": 4,
      "eventRate5s": 0.6,
      "eventMomentum": 2.25,
      "lastEventAgeMs": 1226
    },
    {
      "mint": "8H5yfL1GoDETLDaLYZzrgQuZs37eiKJjdfP21b6ypump",
      "symbol": "SAAR",
      "pair": "6hzdUCkrzgoJ5ugz2vWwKd56odxziZwyMEN7CCF7hSKy",
      "preScore": 41,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 51.738,
      "pairAgeSec": 109536.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 5702495,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 37321
    },
    {
      "mint": "EEpng77ZPn9FbgbT4xsRjwuxNCcMBYq3HTwEscyTpump",
      "symbol": "HeeHaw",
      "pair": "6QyYdc6jgeKnfP1FWhiexMYq3JQ3sidSYoubjWUTo3rm",
      "preScore": 36,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 49.602,
      "pairAgeSec": 565816.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 934192,
      "events1s": 1,
      "events5s": 1,
      "events15s": 2,
      "eventRate5s": 0.2,
      "eventMomentum": 1.5,
      "lastEventAgeMs": 15
    },
    {
      "mint": "2NffKvfZTcFj2tyoY1Ev84PkqxA7DZnstyv6EwELpump",
      "symbol": "Sue",
      "pair": "GjYdVt5LSsp7J7uVDCb2svtQHGkmXcQR2tGGB8RqHtbb",
      "preScore": 37,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 46.852,
      "pairAgeSec": 3098893.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 482536,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 97653
    },
    {
      "mint": "HF5dFJqSxbPMTMj1bBBpGv42sngvgasinLGbJviJQ7gH",
      "symbol": "HOOD",
      "pair": "BiZ3vGK5JNRqrVXhSJzmtZKnuZMyrgGmphHDCodFwbSe",
      "preScore": 37,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 42.55,
      "pairAgeSec": 78908.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 1243622,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2",
      "symbol": "TROLL",
      "pair": "4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama",
      "preScore": 30,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 35.322,
      "pairAgeSec": 43498254.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 482536,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 191807
    },
    {
      "mint": "HmJDgky11u77hpBss6D8sjNpYPD5B6fWgSVDj58jpump",
      "symbol": "SOLCAT",
      "pair": "6imhRyMYu5xoGJ5W7yveymB5o5yfyAvXxveozWpbU5ix",
      "preScore": 28,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 34.574,
      "pairAgeSec": 403512.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 934192,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 31166
    },
    {
      "mint": "CYAQyGC9Nc9RV5MiSiJxdE8utWZtdjtt3tKe1Uvjpump",
      "symbol": "memestonk",
      "pair": "Bw4vQqXVAij7NCQQxitnyMAkBf3nSsKBFhrRiEHAoM8w",
      "preScore": 25,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 31.727,
      "pairAgeSec": 94623.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 224650,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 630383
    },
    {
      "mint": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
      "symbol": "PENGU",
      "pair": "D4J77RpC5k8Nkh6h8bUw2CJBJrykSRqMuNz49f2Fbx3a",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23.795,
      "pairAgeSec": 7033902.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 482536,
      "events1s": 0,
      "events5s": 0,
      "events15s": 1,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 11312
    },
    {
      "mint": "EcZMqqYxFdcKSMMEYuacVoaeeRxpc7R7G7zWma9zpump",
      "symbol": "STONKGUY",
      "pair": "5miPLrTZrMWqN5ubb22GPCjjyZgbQMB5jei7zNwDweZ8",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 30789.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 224650,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 1268467
    },
    {
      "mint": "FcJegUTgNh3NGpemzrEzSW7AUYHfz2fALpWU9V8krF2W",
      "symbol": "TIKTOK",
      "pair": "4E4SFVHucocmC1fwUSjGtzq99GFnjquT2wwa4CcyfFq6",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 44708.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 224650,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "7ovkGaxPxVAxDa37WwZhmo2xppTYkUnRzMfNocmnpiLd",
      "symbol": "NVDA",
      "pair": "Eo8o2igVDCnsLLjEWZQBAVTMSWDd2jGJRkRWLYQsQGoF",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 62857.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 224650,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "Ryhr8FXfCwz7AKJfEkZiNJ8vH3XT1bKWrzPMGu4fpsd",
      "symbol": "FLORK",
      "pair": "JBu9cMcdy69WZFTkT5oeUUcUuTxNVLhm1UqCjZhSDofQ",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 31307.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 224546,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 7813151
    },
    {
      "mint": "8Ge69MMq3SN6G2UfvhqYt5ywUDVzXeBtASnZjQXbpump",
      "symbol": "STONKCHUMP",
      "pair": "7cVxjTKeAUxUS7RrCaGwtStxZEboQZTiHg8Y9AcV28h5",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 46965.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31869,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 2139284
    },
    {
      "mint": "FStcHmpFPhL6QA5qgmD6Se9WfMgWQg8TtvMZDAH4kKp3",
      "symbol": "AAPL",
      "pair": "FjWSU4RatQuHio9puKTvcpE6YX86kb4SQYJWnPjVk7zK",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 37640.615,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31869,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "HyrTLkRCXQkJ88LC5dAt1VB1jQNVyFKd8njAZ2rmCPPi",
      "symbol": "HOOD",
      "pair": "8kqscGR2Y7s543sjUTUs6avyhEKYgGVZzwfw5YR28HJ6",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 54646.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31869,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "5LkgvpvBcLAsdLRKtWobNzY7MjJQzWRUaKTFGEW5Nbur",
      "symbol": "AMZN",
      "pair": "9cNYqC4bowst1smsxEmFNUnrbCqZXkDhzF5yk6VZNvxK",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 72370.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31767,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "FHqgFAJYR8hNVLKHXoWL8YTQnB9oPEBgdVU7CFQjjxge",
      "symbol": "Claude",
      "pair": "DjnB5N44vHE9bnB9PigTmVUCRJq8x66ye96NLp9VjKEs",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 74378.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31767,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "FVRpiYTjMcPWJXPaMdukbP4k1LTuA2QjC4VqGQCKpump",
      "symbol": "WOTF",
      "pair": "3hapnsEjT9w4kopwqbbkhzTxUSKsB6rvxGz9viCfkerz",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 55127.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": 3332981
    },
    {
      "mint": "9ZKYe1S79xAtxLxmaMPjybWdpgg3GsRjCAioF1hwALyN",
      "symbol": "SNDKB",
      "pair": "3Ap8NbmE2kntq96fCczRCFP9Sj5FUUABNUiyPQNiEYZp",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 78019.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "DKwc8cMLMC1UyHDfjyrKhUSd6KpgizTPqWgqjJZhsLfT",
      "symbol": "FLORK",
      "pair": "7CifBeoqHCdnFXsyVkLcxQh8Zr165tGpzwD2S9ikw9xx",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 47402.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "9qVbd6ZLoJi6daRYtBiKgAKmmbuT5GQ36ATHY4K4pump",
      "symbol": "PONS",
      "pair": "EypigtrBfqMdbDfq1oDk3qEJssiFSAcgbKcjDAKAiRa7",
      "preScore": 20,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 23,
      "pairAgeSec": 42488.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "7J6P7sQb8iD8Gwefjrp8ZkDyZ5Bt5PGSUCRMYZcLCv4i",
      "symbol": "NVDA",
      "pair": "CuurYiKd2hgSR1UD3Zy6EjoHbfkxmXnKsDtiYAg9Cqt1",
      "preScore": 17,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 19.55,
      "pairAgeSec": 103361.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "9MM4LrZMBnG45HQE2YbH6TLUQ1S77ECZcxxjAfY9dWqu",
      "symbol": "GOOGL",
      "pair": "GuBS5Su71DsP8jDR1tz4w2NNTpk726KEY7ebDvdkExZS",
      "preScore": 17,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 19.55,
      "pairAgeSec": 87919.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31766,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "8JeedaDsn3F83dinx6XmHmieHhU61d3CCYPZjXDSLWSg",
      "symbol": "OPENAI",
      "pair": "5e4DDEwDCA5UohnfBM9hYW2jpG6AnmMD8wJMsj5YBKyx",
      "preScore": 17,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 19.55,
      "pairAgeSec": 103336.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31647,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    },
    {
      "mint": "287DCQ3fw4ubE813ss3rm8JEY3H5vX23rMRaWkAqMAW1",
      "symbol": "klkn",
      "pair": "3wxHUrgmu4LtKs1yArzXrTkugiCf4WSC4bZxDF5yFVkt",
      "preScore": 10,
      "fastDiscoveryLane": false,
      "held": false,
      "priority": 11.5,
      "pairAgeSec": 46797241.616,
      "pairSource": "RADAR",
      "subscribed": true,
      "subscriptionAgeMs": 31647,
      "events1s": 0,
      "events5s": 0,
      "events15s": 0,
      "eventRate5s": 0,
      "eventMomentum": 0,
      "lastEventAgeMs": null
    }
  ]
}
```

### /opt/meme-alpha/app/runtime-status/v378-deployed.json
```json
{"version":"3.78.0","status":"DEPLOYED","profile":"AGGRESSIVE_ROTATION","activation":"PAPER_HANDOFF","timestamp":"2026-09-06T05:00:06Z"}

```

## Recent textual runtime logs

### /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log
```text
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:07Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:13Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:20Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:26Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:32Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:39Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:46Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=43 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:15:52Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=42 watch=418
RADAR_HEARTBEAT_START 2026-09-06T05:15:58Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=114 current=114 fast=42 watch=406
RADAR_HEARTBEAT_START 2026-09-06T05:16:05Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:16:11Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:18Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:24Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:30Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:37Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:44Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:50Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:16:56Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:17:03Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=113 current=113 fast=43 watch=407
RADAR_HEARTBEAT_START 2026-09-06T05:17:09Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=116 current=116 fast=44 watch=418
RADAR_HEARTBEAT_START 2026-09-06T05:17:16Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=116 current=116 fast=44 watch=404
RADAR_HEARTBEAT_START 2026-09-06T05:17:22Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=116 current=116 fast=44 watch=404
RADAR_HEARTBEAT_START 2026-09-06T05:17:28Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=116 current=116 fast=44 watch=404
RADAR_HEARTBEAT_START 2026-09-06T05:17:34Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=118 current=118 fast=43 watch=432
RADAR_HEARTBEAT_START 2026-09-06T05:17:41Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=418
RADAR_HEARTBEAT_START 2026-09-06T05:17:48Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:17:54Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:00Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:07Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:13Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:20Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:27Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:33Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:40Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=105 current=105 fast=32 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:46Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=107 current=107 fast=39 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:18:53Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=107 current=107 fast=39 watch=413
RADAR_HEARTBEAT_START 2026-09-06T05:19:00Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=107 current=107 fast=39 watch=413
RADAR_HEARTBEAT_START 2026-09-06T05:19:06Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=107 current=107 fast=39 watch=413
RADAR_HEARTBEAT_START 2026-09-06T05:19:12Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=107 current=107 fast=39 watch=413
RADAR_HEARTBEAT_START 2026-09-06T05:19:18Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=108 current=108 fast=41 watch=427
RADAR_HEARTBEAT_START 2026-09-06T05:19:25Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=108 current=108 fast=41 watch=412
RADAR_HEARTBEAT_START 2026-09-06T05:19:31Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=108 current=108 fast=41 watch=412
RADAR_HEARTBEAT_START 2026-09-06T05:19:37Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=2 feedMints=108 current=108 fast=41 watch=412
RADAR_HEARTBEAT_START 2026-09-06T05:19:43Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=107 current=107 fast=41 watch=445
RADAR_HEARTBEAT_START 2026-09-06T05:19:50Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=44 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:19:57Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=44 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:20:03Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=44 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:20:09Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=45 watch=415
RADAR_HEARTBEAT_START 2026-09-06T05:20:16Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=45 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:20:22Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=45 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:20:29Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=110 current=110 fast=45 watch=410
RADAR_HEARTBEAT_START 2026-09-06T05:20:35Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=112 current=112 fast=46 watch=414
RADAR_HEARTBEAT_START 2026-09-06T05:20:42Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=112 current=112 fast=46 watch=408
RADAR_HEARTBEAT_START 2026-09-06T05:20:48Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=112 current=112 fast=46 watch=408
RADAR_HEARTBEAT_START 2026-09-06T05:20:54Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=98 current=98 fast=33 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:21:01Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=98 current=98 fast=33 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:21:08Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=98 current=98 fast=33 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:21:14Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=98 current=98 fast=33 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:21:20Z user=meme-alpha
FAST_DISCOVERY v=3.72.0 status=HEALTHY providers=3 fastProviders=3 feedMints=98 current=98 fast=33 watch=422
RADAR_HEARTBEAT_START 2026-09-06T05:21:26Z user=meme-alpha
```
