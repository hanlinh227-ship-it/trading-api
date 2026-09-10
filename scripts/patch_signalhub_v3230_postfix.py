from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
w=worker.read_text(); a=activity.read_text()

fixes={
    'async function trackV31Signalsasync function trackV31Signals':'async function trackV31Signals',
    'function setupPriority(s){function setupPriority(s){':'function setupPriority(s){',
    'async function setCryptoStandbysasync function setCryptoStandbys':'async function setCryptoStandbys',
    '  async alarm(){  async alarm(){':'  async alarm(){',
    'async function cryptoOnlyMaintenance(env){async function cryptoOnlyMaintenance(env){':'async function cryptoOnlyMaintenance(env){',
}
for old,new in fixes.items():
    if old in w:w=w.replace(old,new)

java_fixes={
    '    private void connectForexStream(){    private void connectForexStream(){':'    private void connectForexStream(){',
    '    private void updateConnectionViews(){    private void updateConnectionViews(){':'    private void updateConnectionViews(){',
}
for old,new in java_fixes.items():
    if old in a:a=a.replace(old,new)

# The consolidation release must not contain an inherited live 10/5 global policy.
assert w.count('const PORTFOLIO_POLICY=Object.freeze(')==1
assert "targetActiveByStyle:{SCALP:5,SWING:2}" in w
assert "function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}" in w
assert "coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE'" not in w
assert 'async function trackV31Signalsasync function' not in w
assert 'function setupPriority(s){function setupPriority' not in w
assert 'async function setCryptoStandbysasync function' not in w
assert 'async alarm(){  async alarm()' not in w
assert 'async function cryptoOnlyMaintenance(env){async function' not in w
assert 'private void connectForexStream(){    private void connectForexStream' not in a
assert 'private void updateConnectionViews(){    private void updateConnectionViews' not in a

worker.write_text(w); activity.write_text(a)
print('V3.23.0 postfix conflict cleanup applied')
