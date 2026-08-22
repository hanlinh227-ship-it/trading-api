# AI Infrastructure Repair Validation Targets

The repair must make the existing AI loop selftest pass by fixing implementation/workflow/contract defects rather than weakening, deleting, skipping, or bypassing the failing assertions.

Observed failing categories from run 32590437675:
- missing DeepSeek secret classification in workflow;
- workflow permissions not least-privilege;
- expected PR trigger/trusted review path mismatch;
- explicit no-secret-print invariant absent;
- missing TESTING contract state;
- reviewer not proven to run from trusted base revision;
- selftest not isolated in CI;
- audit suite not guaranteed from trusted base copy;
- missing bootstrap trust level;
- missing stale-head guard;
- browser-independence contract missing;
- ADVERSARIAL_REVIEWER role missing;
- no-live-state-on-main/state-churn rule missing.

Acceptance requires `node scripts/ai/ai-loop-selftest.mjs` PASS and preservation of all V11 hard trading invariants.
