from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
s=p.read_text()

marker='async function loadCryptoSnapshotResilient(env){'
assert marker in s, 'loadCryptoSnapshotResilient marker missing'
if 'async function retireAllLegacyActiveSignals(env){' not in s:
    helper="""async function retireAllLegacyActiveSignals(env){
  // V3.23.1 uses a fresh Durable Object namespace, so old-version active rows
  // cannot enter the live registry. Historical KV rows are intentionally kept
  // forever by the resilient ledger and must never be deleted during a scan.
  // This compatibility hook therefore performs no destructive retirement.
  return [];
}
"""
    s=s.replace(marker,helper+marker,1)

# Remove inherited health-model label from the canonical decision policy/status.
s=s.replace("healthModel:'V3227_REALTIME_SIGNAL_HEALTH_1S'","healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'")
s=s.replace("signal.healthModel='V3227_REALTIME_SIGNAL_HEALTH_1S'","signal.healthModel='V3231_PRECISION_HEALTH_HYSTERESIS_1S'")

assert 'async function retireAllLegacyActiveSignals(env){' in s
assert "healthModel:'V3231_PRECISION_HEALTH_HYSTERESIS_1S'" in s
p.write_text(s)
print('V3.23.1 scan runtime compatibility helper fixed without deleting history')
