from pathlib import Path

p=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
s=p.read_text()
if 'private void renderSignals(boolean animate)' not in s:
    marker='    private void renderDetail(JSONObject s,boolean animate)'
    if marker not in s:
        raise SystemExit('renderDetail marker missing')
    method=r'''    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}
        Runnable body=()->{
            content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();
            subtitle.setText("CRYPTO REALTIME • SCALP / SWING • LIVE / LIMIT / STOP");
            LinearLayout title=row();title.addView(tv("CRYPTO SIGNALS",16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));title.addView(chip(style,CYAN));content.addView(title);
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),limitRows=new ArrayList<>(),stopRows=new ArrayList<>();
            for(JSONObject x:rows){double px=priceFor(x,x.optDouble("entry",0));if(isDisplayLive(x,px))liveRows.add(x);else if("STOP".equalsIgnoreCase(x.optString("orderType","")))stopRows.add(x);else limitRows.add(x);}
            LinearLayout summary=card();summary.addView(tv("CRYPTO ONLY • QUALITY-FIRST",10,CYAN,true));summary.addView(tv("SCALP / SWING độc lập • LIVE "+liveRows.size()+" • LIMIT "+limitRows.size()+" • STOP "+stopRows.size(),12,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));content.addView(summary);
            addCryptoSignalGroup("●  LIVE",liveRows,GREEN);
            addCryptoSignalGroup("◷  LIMIT",limitRows,YELLOW);
            addCryptoSignalGroup("△  STOP",stopRows,YELLOW);
        };
        if(animate)swap(body);else body.run();updateAllPriceViews();
    }

    private void addCryptoSignalGroup(String name,List<JSONObject> rows,int color){
        LinearLayout h=row();h.addView(tv(name,13,color,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(String.valueOf(rows.size()),color));content.addView(h);
        if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có setup đạt hard-quality trong nhóm này.",10,MUTED,true));content.addView(z);return;}
        for(JSONObject x:rows)content.addView(signalCard(x));
    }

'''
    s=s.replace(marker,method+marker,1)
p.write_text(s)
print('V313_ANDROID_RENDERER_OK')
