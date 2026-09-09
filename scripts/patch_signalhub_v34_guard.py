from pathlib import Path
p=Path(__file__).resolve().parents[1]/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java'
s=p.read_text(encoding='utf-8')
old='''    private boolean pendingTriggered(JSONObject s,double px){\n        if(!"PENDING".equalsIgnoreCase(s.optString("status",""))||!(px>0))return false;\n        String type=s.optString("orderType","LIMIT").toUpperCase(Locale.US),side=sideVi(s.optString("side",""));double entry=s.optDouble("entry",0);if(!(entry>0))return false;\n'''
new='''    private boolean pendingTriggered(JSONObject s,double px){\n        if(!"PENDING".equalsIgnoreCase(s.optString("status",""))||!(px>0))return false;\n        String market=s.optString("market","FOREX").toUpperCase(Locale.US),sym=s.optString("symbol","");\n        if(market.equals("FOREX")&&(!fxPrices.containsKey(sym)||!fxState.equals("LIVE")))return false;\n        if(market.equals("CRYPTO")&&!cryptoPrices.containsKey(sym))return false;\n        String type=s.optString("orderType","LIMIT").toUpperCase(Locale.US),side=sideVi(s.optString("side",""));double entry=s.optDouble("entry",0);if(!(entry>0))return false;\n'''
if old not in s: raise SystemExit('pendingTriggered target not found')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('guard patched')
