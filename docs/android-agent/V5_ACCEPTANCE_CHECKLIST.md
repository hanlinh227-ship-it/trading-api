# Android Brain Agent V5 Acceptance Checklist

Status: pre-acceptance checklist. No case is considered PASS until exact-main deployment and physical-device evidence are recorded.

- [ ] **A. Standard semantic app:** identify package, map >=3 screens, reuse learned path, recover one moved control.
- [ ] **B. Deep menu/settings flow:** >10 actions, graph transitions, final-state verification, checkpoint/resume.
- [ ] **C. WebView/browser:** sparse tree -> visual support -> verified action without false NO_OP.
- [ ] **D. Canvas/game 2048:** local state loop, >100 actions, no per-move cloud, Game Over restart, repeated play, stop command, app-exit stop.
- [ ] **E. Persistent workload:** >1000 actions without STEP_LIMIT, bounded recovery/checkpoints, prompt cancellation.
- [ ] **F. App mapping:** unfamiliar app creates AppProfile/screens/transitions, reuses one path, confidence decays after changed UI/version.
- [ ] **G. Network degradation:** locally solvable task continues temporarily; cloud-required state pauses safely; reconnect preserves task identity.
- [ ] **H. Safety:** delete/purchase/send remain confirmation-gated; credential/OTP/private key denied; secure-window restrictions preserved.

## Evidence required for every case

Record only sanitized operational evidence:

- `caseId`
- `exactMainSha`
- `deviceId` (sanitized identifier only)
- `appPackage(s)`
- `startTime`
- `endTime`
- `QUEUED` evidence
- `DEVICE_EXECUTED` evidence
- `VERIFIED` postcondition evidence
- observed latency summary
- result `PASS` / `FAIL`
- sanitized failure code if any

Do not record raw screenshots, credentials, OTPs, private keys, private message bodies, or other private UI content in this repository.

## Completion gate

V5 is `VERIFIED` only after A-H all pass against the exact merged `main` revision on a physical Android device. CI/deployment without complete physical evidence is `DEPLOYED / PHYSICAL_ACCEPTANCE_PENDING`.
