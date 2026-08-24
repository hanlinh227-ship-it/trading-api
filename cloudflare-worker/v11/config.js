// Canonical V11 runtime configuration.
// Restored as an infrastructure repair because active V11 modules import this file.
// Keep signal authority and market policy in the V11 modules; this file only owns
// shared runtime cadence / baseline thresholds.

export const V11_GROUPS = Object.freeze(['crypto','forex','metal','index']);

export const V11_CONFIG = Object.freeze({
  version: 'V11',
  scanCadenceSec: Object.freeze({
    crypto: 60,
    forex: 120,
    metal: 120,
    index: 120
  }),
  markets: Object.freeze({
    crypto: Object.freeze({ quality: 54, horizonMin: 75 }),
    forex: Object.freeze({ quality: 54, horizonMin: 90 }),
    metal: Object.freeze({ quality: 55, horizonMin: 85 }),
    index: Object.freeze({ quality: 54, horizonMin: 90 })
  })
});
