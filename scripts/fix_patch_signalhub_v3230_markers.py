from pathlib import Path
p=Path('scripts/patch_signalhub_v3230_resilient_ledger_clean.py')
s=p.read_text()
repls={
"w=block(w,'async function writeV31Signal(env,s){','async function trackV31Signals',history_block+'async function trackV31Signals','writeV31Signal/permanent history')":"w=block(w,'async function writeV31Signal(env,s){','async function trackV31Signals',history_block,'writeV31Signal/permanent history')",
"w=block(w,'function marketOnlySevenCandidate(raw){','function setupPriority(s){',market_converter+'function setupPriority(s){','marketOnlySevenCandidate')":"w=block(w,'function marketOnlySevenCandidate(raw){','function setupPriority(s){',market_converter,'marketOnlySevenCandidate')",
"w=block(w,'async function maybeCreateV31(env,market,style,setups){','async function setCryptoStandbys',maybe+'async function setCryptoStandbys','maybeCreateV31')":"w=block(w,'async function maybeCreateV31(env,market,style,setups){','async function analyzeCryptoBatch',maybe,'maybeCreateV31')",
"w=block(w,'  async cryptoMonitorCycle(){','  async alarm(){',cycle+'  async alarm(){','cryptoMonitorCycle')":"w=block(w,'  async cryptoMonitorCycle(){','  async alarm(){',cycle,'cryptoMonitorCycle')",
"w=block(w,'async function scanCrypto(env,style){','async function cryptoOnlyMaintenance(env){',scan+'async function cryptoOnlyMaintenance(env){','scanCrypto')":"w=block(w,'async function scanCrypto(env,style){','async function cryptoOnlyMaintenance(env){',scan,'scanCrypto')",
"a=block(a,'    private void ensureCryptoStream(){','    private void connectForexStream(){',stream_methods+'    private void connectForexStream(){','android crypto stream resilience')":"a=block(a,'    private void ensureCryptoStream(){','    private void connectForexStream(){',stream_methods,'android crypto stream resilience')",
"a=block(a,'    private void refreshCryptoLive(){','    private void updateConnectionViews(){',refresh+'    private void updateConnectionViews(){','android refreshCryptoLive')":"a=block(a,'    private void refreshCryptoLive(){','    private void updateConnectionViews(){',refresh,'android refreshCryptoLive')",
}
for old,new in repls.items():
    assert old in s, 'missing patch-source marker: '+old[:100]
    s=s.replace(old,new,1)
p.write_text(s)
print('V3.23.0 patch source markers fixed')
