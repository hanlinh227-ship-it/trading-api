from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
s=p.read_text()

old="""    if(url.pathname==='/v3/data-integrity'&&req.method==='GET'){const p=await readStable100(env),audit=stable100Integrity(p);return json({ok:audit.ok,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,stable100:p?{count:p.count,target:p.target,provider:p.provider,providers:p.providers,refreshedAt:p.refreshedAt,complete:p.complete}:null,problems:audit.problems});}
"""
new="""    if(url.pathname==='/v3/data-integrity'&&req.method==='GET'){
      let p=await readStable100(env),refreshAttempted=false,refreshError=null;
      if(!p){
        refreshAttempted=true;
        try{
          const snap=await loadCryptoSnapshotResilient(env);
          if(snap?.live!==false&&Array.isArray(snap?.rows)&&snap.rows.length){
            await persistStable100(env,snap,snap.rows);
            p=await readStable100(env);
            if(!p)refreshError='REFRESH_DID_NOT_PRODUCE_VALID_STANDARDIZED_STABLE100';
          }else refreshError=String(snap?.error||'NO_FRESH_CRYPTO_SNAPSHOT');
        }catch(e){refreshError=String(e?.message||e);}
      }
      const audit=stable100Integrity(p),ageMs=p?Date.now()-Date.parse(p.refreshedAt||0):null;
      return json({ok:audit.ok,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,stable100:p?{count:p.count,target:p.target,provider:p.provider,providers:p.providers,refreshedAt:p.refreshedAt,complete:p.complete,ageMs}:null,refreshAttempted,refreshError,selfHealing:'REFRESH_STALE_OR_MISSING_STABLE100_THEN_REAUDIT',problems:audit.problems});
    }
"""

assert old in s, 'V3.23.0 data-integrity route marker missing'
s=s.replace(old,new,1)

# The live API previously exposed the complete inherited changelog, including
# obsolete 10/5 and LIMIT/STOP descriptions. Keep history in git, but make the
# current app-version contract unambiguous so old release text cannot conflict
# with the 5+2 MARKET-only runtime policy.
start=s.find('const V31_RELEASE = {')
assert start>=0, 'V31_RELEASE start missing'
end_marker='\n};\n\nconst json ='
end=s.find(end_marker,start)
assert end>start, 'V31_RELEASE end missing'
clean_notes="""
};
V31_RELEASE.notes = Object.freeze([
  'V3.23.0 consolidated runtime: exactly 5 SCALP + 2 SWING MARKET reference signals, globally unique symbols, no active LIMIT or STOP.',
  'Stable100 is dynamic and self-healing: stale or missing standardized universe data is refreshed and re-audited before integrity is declared failed.',
  'Live display continuity uses BYBIT/OKX/BINANCE failover with sequence-aware WebSocket plus REST reconciliation; terminal lifecycle authority stays provider-pinned.',
  'Signal history is permanent without TTL; strict TP/SL win rate stays separate from AUTO_CUT/all-exit statistics.',
  'AUTO_CUT retires the SignalHub reference signal only and does not close a manually opened exchange position.'
]);

const json ="""
s=s[:end]+clean_notes+s[end+len(end_marker):]

assert "selfHealing:'REFRESH_STALE_OR_MISSING_STABLE100_THEN_REAUDIT'" in s
assert "const snap=await loadCryptoSnapshotResilient(env);" in s
assert 'V31_RELEASE.notes = Object.freeze([' in s
assert "exactly 5 SCALP + 2 SWING MARKET" in s
p.write_text(s)
print('V3.23.0 Stable100 integrity self-healing + release-note conflict cleanup patched')
