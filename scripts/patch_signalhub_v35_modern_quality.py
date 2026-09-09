from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
worker=ROOT/'signalhub-worker/gateway-v3.js'
activity=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java'
gradle=ROOT/'signalhub-android/app/build.gradle'
monitor=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java'

w=worker.read_text(encoding='utf-8')
a=activity.read_text(encoding='utf-8')
g=gradle.read_text(encoding='utf-8')
m=monitor.read_text(encoding='utf-8')

# ---------------- Backend V3.5 quality policy ----------------
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.4.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.5.0';")
w=w.replace("versionCode: 10,\n  versionName: '3.4.0',\n  title: 'SignalHub 3.4.0',","versionCode: 11,\n  versionName: '3.5.0',\n  title: 'SignalHub 3.5.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.4.0',","artifactName: 'SignalHub-Android-v3.5.0',")
w=w.replace("'Realtime Durable Object price bus + WebSocket stream for Exness MT5 quotes.',","'V3.5 strict admission gate: fewer but higher-quality signals; historical win rate remains resolved TP/SL only.',\n    'Modern LIVE / LIMIT / STOP UI with yellow pending-entry progress gauge.',\n    'Realtime Durable Object price bus + WebSocket stream for Exness MT5 quotes.',")

anchor="const sleep = ms => new Promise(r => setTimeout(r, ms));\n"
quality="""

const V35_QUALITY_POLICY = Object.freeze({
  FOREX_SCALP: {minScore:90,minRR:2.0},
  FOREX_SWING: {minScore:90,minRR:2.3},
  CRYPTO_SCALP:{minScore:92,minRR:2.0},
  CRYPTO_SWING:{minScore:90,minRR:2.3},
});
function v35Policy(market,style){
  return V35_QUALITY_POLICY[`${String(market||'FOREX').toUpperCase()}_${String(style||'SCALP').toUpperCase()}`]||{minScore:90,minRR:2.0};
}
function passesV35QualityGate(signal,market,style){
  if(!signal)return false;
  const p=v35Policy(market,style),score=Number(signal.score||0),rr=Number(signal.targetRR||0),entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0))return false;
  if(Math.abs(entry-sl)<=0)return false;
  if(score<p.minScore)return false;
  if(!(rr>=p.minRR))return false;
  const side=String(signal.side||'').toUpperCase();
  const dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  const order=String(signal.orderType||'MARKET').toUpperCase();
  if(!['MARKET','LIMIT','STOP'].includes(order))return false;
  return true;
}
function stampV35Quality(signal,market,style){
  const p=v35Policy(market,style);
  signal.admissionGate='V35_STRICT';
  signal.admissionMinScore=p.minScore;
  signal.admissionMinRR=p.minRR;
  signal.entryState=String(signal.orderType||'MARKET').toUpperCase()==='MARKET'?'LIVE':'PENDING_ENTRY';
  return signal;
}
"""
if 'const V35_QUALITY_POLICY' not in w:
    if anchor not in w: raise SystemExit('worker anchor missing')
    w=w.replace(anchor,anchor+quality,1)

old="""  const made=[];
  for(const setup of setups){
    if(made.length>=maxNew)break;
"""
new="""  const made=[];
  for(const setup of setups){
    if(made.length>=maxNew)break;
    if(!passesV35QualityGate(setup,market,style))continue;
    stampV35Quality(setup,market,style);
"""
if old not in w: raise SystemExit('maybeCreate gate anchor missing')
w=w.replace(old,new,1)

old="""  rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
"""
new="""  rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  // V3.5 admission is intentionally applied to ACTIVE delivery only. Closed history is never rewritten,
  // so historical WR remains honest and comparable instead of being retroactively cherry-picked.
  if(status==='active') rows=rows.filter(s=>passesV35QualityGate(s,market,style)).map(s=>stampV35Quality(s,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
"""
if old not in w: raise SystemExit('unifiedSignals anchor missing')
w=w.replace(old,new,1)

old="return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,signals:rows});"
new="return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,qualityPolicy:{name:'V35_STRICT',...v35Policy(market,style),historicalWinRateMode:'RESOLVED_TP_SL_ONLY'},signals:rows});"
if old not in w: raise SystemExit('unified response anchor missing')
w=w.replace(old,new,1)

# ---------------- Android V3.5 modern order-state UI ----------------
a=a.replace('private static final String APP_VERSION="3.4.0";','private static final String APP_VERSION="3.5.0";')
a=a.replace('private static final int BG=Color.rgb(3,7,11),PANEL=Color.rgb(9,16,23),PANEL2=Color.rgb(15,25,35),BORDER=Color.rgb(30,49,64);','private static final int BG=Color.rgb(2,6,10),PANEL=Color.rgb(7,14,21),PANEL2=Color.rgb(12,23,33),BORDER=Color.rgb(28,52,70);')
a=a.replace('private static final int TEXT=Color.rgb(238,246,252),MUTED=Color.rgb(126,151,169),GREEN=Color.rgb(44,226,155),RED=Color.rgb(255,82,104),YELLOW=Color.rgb(246,194,76),BLUE=Color.rgb(68,170,255),CYAN=Color.rgb(60,220,235);','private static final int TEXT=Color.rgb(242,248,252),MUTED=Color.rgb(123,148,166),GREEN=Color.rgb(48,232,159),RED=Color.rgb(255,76,102),YELLOW=Color.rgb(255,201,67),BLUE=Color.rgb(78,154,255),CYAN=Color.rgb(59,224,238);')

old='private final Map<String,TradeGauge> gaugeViews=new ConcurrentHashMap<>();\n    private final Map<String,TextView> pnlViews=new ConcurrentHashMap<>();'
new='private final Map<String,TradeGauge> gaugeViews=new ConcurrentHashMap<>();\n    private final Map<String,EntryGauge> entryGaugeViews=new ConcurrentHashMap<>();\n    private final Map<String,TextView> pnlViews=new ConcurrentHashMap<>();'
if old not in a: raise SystemExit('gauge map anchor missing')
a=a.replace(old,new,1)
a=a.replace('gaugeViews.clear();pnlViews.clear();','gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();')

a=a.replace('TextView logo=tv("SignalHub V3",22,TEXT,true);subtitle=tv("LIVE TRADING SIGNALS • FAST • CLEAR • ACTIONABLE",8,MUTED,true);','TextView logo=tv("SIGNALHUB",22,TEXT,true);subtitle=tv("REALTIME EXECUTION INTELLIGENCE • V3.5",8,MUTED,true);')

old="""            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),pendingRows=new ArrayList<>();
            for(JSONObject s:rows){double px=priceFor(s,s.optDouble("entry",0));if(isDisplayLive(s,px))liveRows.add(s);else pendingRows.add(s);}
            LinearLayout summary=card();summary.addView(tv("LIVE "+liveRows.size()+"   •   LIMIT/STOP "+pendingRows.size(),12,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));summary.addView(tv("LIMIT/STOP tự chuyển sang LIVE ngay khi giá realtime chạm điều kiện kích hoạt.",9,YELLOW,false));content.addView(summary);
            addOrderSection("●  LỆNH LIVE",liveRows,GREEN,"Đã khớp / đang chạy theo giá hiện tại");
            addOrderSection("◷  LỆNH CHỜ • LIMIT / STOP",pendingRows,YELLOW,"Chưa khớp Entry • tách riêng khỏi lệnh đang chạy");
"""
new="""            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),limitRows=new ArrayList<>(),stopRows=new ArrayList<>();
            for(JSONObject s:rows){double px=priceFor(s,s.optDouble("entry",0));if(isDisplayLive(s,px))liveRows.add(s);else if("STOP".equalsIgnoreCase(s.optString("orderType","")))stopRows.add(s);else limitRows.add(s);}
            LinearLayout summary=card();summary.addView(tv("EXECUTION BOARD",10,CYAN,true));summary.addView(tv("LIVE "+liveRows.size()+"   •   LIMIT "+limitRows.size()+"   •   STOP "+stopRows.size(),14,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));summary.addView(tv("V3.5 STRICT • chỉ phát setup vượt quality gate; WR vẫn chỉ tính TP/SL đã đóng.",9,YELLOW,false));content.addView(summary);
            addOrderSection("●  LỆNH LIVE",liveRows,GREEN,"Đã khớp • thanh đỏ/xanh đo tiến độ SL ↔ TP3");
            addOrderSection("◷  LỆNH LIMIT",limitRows,YELLOW,"Thanh vàng đo tiến độ giá hiện tại → Entry");
            addOrderSection("△  LỆNH STOP",stopRows,YELLOW,"Thanh vàng đo tiến độ giá hiện tại → Entry");
"""
if old not in a: raise SystemExit('renderSignals block missing')
a=a.replace(old,new,1)

old='private String pendingDistanceText(JSONObject s,double px){double e=s.optDouble("entry",0),sl=s.optDouble("sl",0);double base=Math.max(Math.abs(e-sl),1e-12),dist=Math.abs(px-e)/base;return s.optString("orderType","LIMIT").toUpperCase(Locale.US)+" • CHỜ KHỚP • cách Entry "+String.format(Locale.US,"%.2fR",dist);}'
new='private double entryProgressPct(JSONObject s,double px){double e=s.optDouble("entry",0),start=s.optDouble("sourcePrice",s.optDouble("lastPrice",0));double initial=Math.abs(start-e);if(!(initial>0)){double sl=s.optDouble("sl",0);initial=Math.max(Math.abs(e-sl),1e-12);}double remaining=Math.abs(px-e);return Math.max(0,Math.min(100,(1.0-remaining/initial)*100.0));}\n    private String pendingDistanceText(JSONObject s,double px){double e=s.optDouble("entry",0);double pct=entryProgressPct(s,px),remain=Math.abs(px-e);return s.optString("orderType","LIMIT").toUpperCase(Locale.US)+" • CHỜ ENTRY • "+String.format(Locale.US,"%.0f%% tiến độ • còn %s",pct,fmt(remain));}'
if old not in a: raise SystemExit('pending distance anchor missing')
a=a.replace(old,new,1)

old='TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(58)));gaugeViews.put(id,gauge);'
new='if(isDisplayLive(s,px)){TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(58)));gaugeViews.put(id,gauge);}else{EntryGauge eg=new EntryGauge();eg.setData(s,px);c.addView(eg,new LinearLayout.LayoutParams(-1,dp(64)));entryGaugeViews.put(id,eg);}'
if old not in a: raise SystemExit('signalCard gauge anchor missing')
a=a.replace(old,new,1)

old='TextView pnl=tv(tradeStatusText(s,px),14,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(12),0,dp(5));c.addView(pnl);pnlViews.put(id,pnl);TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(72)));gaugeViews.put(id,gauge);'
new='TextView pnl=tv(tradeStatusText(s,px),14,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(12),0,dp(5));c.addView(pnl);pnlViews.put(id,pnl);if(isDisplayLive(s,px)){TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(72)));gaugeViews.put(id,gauge);}else{EntryGauge eg=new EntryGauge();eg.setData(s,px);c.addView(eg,new LinearLayout.LayoutParams(-1,dp(76)));entryGaugeViews.put(id,eg);}'
if old not in a: raise SystemExit('detail gauge anchor missing')
a=a.replace(old,new,1)

a=a.replace('subtitle.setText("CHI TIẾT TÍN HIỆU • LIVE");','subtitle.setText("CHI TIẾT LỆNH • LIVE / PENDING ENTRY");')

a=a.replace('ui.addView(line("Fallback refresh","500 ms",MUTED));content.addView(ui);','ui.addView(line("Fallback refresh","500 ms",MUTED));ui.addView(line("Quality Gate","V3.5 STRICT",YELLOW));ui.addView(line("Forex Scalp","score ≥90 • RR ≥2.0",TEXT));ui.addView(line("Forex Swing","score ≥90 • RR ≥2.3",TEXT));ui.addView(line("Crypto Scalp","score ≥92 • RR ≥2.0",TEXT));ui.addView(line("Crypto Swing","score ≥90 • RR ≥2.3",TEXT));content.addView(ui);')

old='if(s!=null){TextView pnl=pnlViews.get(id);if(pnl!=null){pnl.setText(tradeStatusText(s,px));pnl.setTextColor(tradeStatusColor(s,px));}TradeGauge g=gaugeViews.get(id);if(g!=null)g.setData(currentR(s,px),targetR(s));}'
new='if(s!=null){TextView pnl=pnlViews.get(id);if(pnl!=null){pnl.setText(tradeStatusText(s,px));pnl.setTextColor(tradeStatusColor(s,px));}TradeGauge g=gaugeViews.get(id);if(g!=null)g.setData(currentR(s,px),targetR(s));EntryGauge eg=entryGaugeViews.get(id);if(eg!=null)eg.setData(s,px);}'
if old not in a: raise SystemExit('price update anchor missing')
a=a.replace(old,new,1)

trade_anchor='''    private class TradeGauge extends View{\n        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double r=0,target=1;'''
if trade_anchor not in a: raise SystemExit('TradeGauge class anchor missing')
entry_class='''    private class EntryGauge extends View{\n        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double progress=0,current=0,entry=0;\n        EntryGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}\n        void setData(JSONObject s,double px){current=px;entry=s.optDouble("entry",0);progress=entryProgressPct(s,px);invalidate();}\n        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.62f,barH=dp(11);p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(47,42,20));c.drawRoundRect(new RectF(dp(2),cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);float x=dp(2)+(float)((w-dp(4))*progress/100.0);p.setColor(YELLOW);p.setShadowLayer(dp(8),0,0,YELLOW);c.drawRoundRect(new RectF(dp(2),cy-barH/2,Math.max(dp(3),x),cy+barH/2),barH/2,barH/2,p);p.clearShadowLayer();p.setColor(TEXT);c.drawCircle(x,cy,dp(5),p);p.setTypeface(Typeface.create(Typeface.MONOSPACE,Typeface.BOLD));p.setTextSize(dp(9));p.setTextAlign(Paint.Align.LEFT);p.setColor(MUTED);c.drawText("NOW  "+fmt(current),dp(2),dp(13),p);p.setTextAlign(Paint.Align.RIGHT);p.setColor(YELLOW);c.drawText("ENTRY  "+fmt(entry),w-dp(2),dp(13),p);p.setTextAlign(Paint.Align.CENTER);p.setColor(YELLOW);c.drawText(String.format(Locale.US,"%.0f%% TỚI ENTRY",progress),w*.5f,h-dp(3),p);}\n    }\n\n'''
a=a.replace(trade_anchor,entry_class+trade_anchor,1)

# Make top dashboard language modern but still compact.
a=a.replace('subtitle.setText("TRADE SMARTER • REAL SIGNALS • REAL RESULTS");','subtitle.setText("REALTIME CONTROL CENTER • EXNESS + SIGNAL ENGINE");')
a=a.replace('l.addView(tv("TÍN HIỆU CHẤT LƯỢNG",17,TEXT,true));l.addView(tv("CƠ HỘI THẬT",20,CYAN,true));l.addView(tv("KỶ LUẬT  •  DỮ LIỆU  •  KẾT QUẢ",9,MUTED,true));','l.addView(tv("EXECUTION INTELLIGENCE",15,TEXT,true));l.addView(tv("REALTIME CONTROL",21,CYAN,true));l.addView(tv("LIVE  •  LIMIT  •  STOP  •  QUALITY GATE",9,MUTED,true));')

# Android metadata.
g=g.replace('versionCode 10','versionCode 11').replace("versionName '3.4.0'","versionName '3.5.0'")

# Notification service copy: clearer order states / release marker where present.
m=m.replace('signalhub_monitor_v32','signalhub_monitor_v35')
m=m.replace('SignalHub Monitor V3.2','SignalHub Realtime V3.5')

worker.write_text(w,encoding='utf-8')
activity.write_text(a,encoding='utf-8')
gradle.write_text(g,encoding='utf-8')
monitor.write_text(m,encoding='utf-8')
print('patched SignalHub V3.5 modern quality')
