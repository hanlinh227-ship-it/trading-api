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
assert "selfHealing:'REFRESH_STALE_OR_MISSING_STABLE100_THEN_REAUDIT'" in s
assert "const snap=await loadCryptoSnapshotResilient(env);" in s
p.write_text(s)
print('V3.23.0 Stable100 integrity self-healing refresh patched')
