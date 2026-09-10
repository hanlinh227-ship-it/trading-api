from pathlib import Path
p=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
a=p.read_text()
if 'private void applyRealtimeSignal(JSONObject sig)' not in a:
    marker='    private void updateConnectionViews(){'
    assert marker in a,'updateConnectionViews marker missing'
    method=r'''    private void applyRealtimeSignal(JSONObject sig){
        try{
            String market="CRYPTO",st=sig.optString("style","SCALP").toUpperCase(Locale.US),key=market+":"+st,id=sig.optString("signalId",sig.optString("id",""));
            JSONArray old=signalCache.get(key),next=new JSONArray();boolean found=false,active="OPEN".equalsIgnoreCase(sig.optString("status",""))&&"MARKET".equalsIgnoreCase(sig.optString("orderType","MARKET"));
            if(old!=null)for(int i=0;i<old.length();i++){JSONObject x=old.optJSONObject(i);if(x==null)continue;String xid=x.optString("signalId",x.optString("id",""));if(xid.equals(id)){found=true;if(active)next.put(sig);}else next.put(x);}
            if(!found&&active)next.put(sig);signalCache.put(key,next);
            if(selectedSignal!=null){String sid=selectedSignal.optString("signalId",selectedSignal.optString("id",""));if(sid.equals(id))selectedSignal=active?sig:null;}
            main.post(()->{if(screen.equals("SIGNALS")){if(detail&&selectedSignal!=null)renderDetail(selectedSignal,false);else{detail=false;renderSignals(false);}}else if(screen.equals("HOME"))renderHome(false);});
        }catch(Throwable ignored){}
    }

'''
    a=a.replace(marker,method+marker,1)
p.write_text(a)
assert 'private void applyRealtimeSignal(JSONObject sig)' in a
print('V3.22.9 Android realtime signal helper restored R2')
