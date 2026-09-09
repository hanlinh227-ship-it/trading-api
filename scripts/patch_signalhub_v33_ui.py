from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACT=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java'
MON=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java'
API=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java'
GRADLE=ROOT/'signalhub-android/app/build.gradle'


def replace_method(src, signature, new_method):
    start=src.find(signature)
    if start<0: raise RuntimeError('method not found: '+signature)
    brace=src.find('{',start)
    if brace<0: raise RuntimeError('brace not found: '+signature)
    depth=0
    end=None
    for i in range(brace,len(src)):
        c=src[i]
        if c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0:
                end=i+1
                break
    if end is None: raise RuntimeError('method end not found: '+signature)
    return src[:start]+new_method+src[end:]

src=ACT.read_text(encoding='utf-8')
src=src.replace('import android.graphics.Color;','import android.graphics.Color;\nimport android.graphics.Canvas;\nimport android.graphics.Paint;\nimport android.graphics.RectF;')
src=src.replace('import android.view.View;','import android.view.View;\nimport android.content.SharedPreferences;')
src=src.replace('private static final String APP_VERSION="3.2.0";','private static final String APP_VERSION="3.3.0";')
src=src.replace('private static final long LIVE_REFRESH_MS=1000L;','private static final long LIVE_REFRESH_MS=500L;')
src=src.replace('private String screen="SIGNALS",style="SCALP",filter="ALL";','private String screen="HOME",style="SCALP",filter="ALL";')
src=src.replace('private final Map<String,TextView> sourceViews=new ConcurrentHashMap<>();','private final Map<String,TextView> sourceViews=new ConcurrentHashMap<>();\n    private final Map<String,TradeGauge> gaugeViews=new ConcurrentHashMap<>();\n    private final Map<String,TextView> pnlViews=new ConcurrentHashMap<>();')
src=src.replace('root.addView(bottom);setContentView(root);drawBottom();','root.addView(bottom);setContentView(root);drawBottom();signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);')

src=replace_method(src,'    private void selectScreen(String s)', '''    private void selectScreen(String s){
        if(screen.equals(s)&&!detail)return;
        screen=s;detail=false;selectedSignal=null;
        signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
        drawBottom();renderCurrent(true);refreshPage(true);
    }''')

src=replace_method(src,'    private void drawBottom()', '''    private void drawBottom(){
        bottom.removeAllViews();
        String[] keys={"HOME","SIGNALS","STATS","ALERTS","SETTINGS"};
        String[] names={"⌂\\nTRANG CHỦ","⚡\\nTÍN HIỆU","▥\\nTHỐNG KÊ","♢\\nTHÔNG BÁO","⚙\\nCÀI ĐẶT"};
        for(int i=0;i<keys.length;i++){
            final String x=keys[i];Button b=button(names[i],screen.equals(x),v->selectScreen(x));
            b.setTextSize(8);b.setGravity(Gravity.CENTER);b.setPadding(dp(2),0,dp(2),0);
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(54),1f);p.setMargins(dp(1),0,dp(1),0);bottom.addView(b,p);
        }
    }''')

src=replace_method(src,'    private void renderCurrent(boolean animate)', '''    private void renderCurrent(boolean animate){
        if(screen.equals("HOME"))renderHome(animate);
        else if(screen.equals("SIGNALS"))renderSignals(animate);
        else if(screen.equals("STATS"))renderStats(animate);
        else if(screen.equals("ALERTS"))renderAlerts(animate);
        else renderSettings(animate);
    }''')

src=replace_method(src,'    private void refreshPage(boolean force)', '''    private void refreshPage(boolean force){
        if(!resumed&&!force)return;
        if(!pageBusy.compareAndSet(false,true))return;
        final String scr=screen,st=style;
        io.execute(()->{try{
            if(scr.equals("HOME"))loadDashboardData();
            else if(scr.equals("SIGNALS"))loadSignalPartitions(st);
            else if(scr.equals("STATS"))loadAllPerformance();
            else if(scr.equals("SETTINGS"))loadSystemStatus();
        }finally{pageBusy.set(false);}});
        if(scr.equals("SIGNALS"))kickScanIfDue();
    }''')

src=replace_method(src,'    private void renderSignals(boolean animate)', '''    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}
        Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();pnlViews.clear();subtitle.setText("CẬP NHẬT THEO THỜI GIAN THỰC TỪ HỆ THỐNG");
            LinearLayout title=row();title.addView(tv("TÍN HIỆU GIAO DỊCH",16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));title.addView(chip(style,CYAN));content.addView(title);
            List<JSONObject> rows=collectSignals();
            LinearLayout summary=card();summary.addView(tv(rows.size()+" tín hiệu đang hiển thị",12,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));summary.addView(tv("SCALP / SWING tách độc lập • WR chỉ tính lệnh đã TP/SL",9,YELLOW,false));content.addView(summary);
            if(rows.isEmpty()){LinearLayout c=card();c.addView(tv(signalCache.containsKey("FOREX:"+style)||signalCache.containsKey("CRYPTO:"+style)?"Chưa có tín hiệu đạt chuẩn ở bộ lọc này.":"Đang đồng bộ tín hiệu live…",12,MUTED,true));c.addView(tv("Không ép lệnh khi dữ liệu stale hoặc entry đã chạy xa.",10,MUTED,false));content.addView(c);return;}
            for(JSONObject s:rows)content.addView(signalCard(s));
        };if(animate)swap(body);else body.run();updateAllPriceViews();
    }''')

src=replace_method(src,'    private View signalCard(JSONObject s)', '''    private View signalCard(JSONObject s){
        LinearLayout c=card();String sym=s.optString("symbol","—"),side=sideVi(s.optString("side","—")),order=s.optString("orderType","MARKET"),market=s.optString("market","FOREX"),signalStyle=s.optString("style",style);int col=side.equals("BUY")?GREEN:side.equals("SELL")?RED:MUTED;
        LinearLayout h=row();h.addView(tv(sym,18,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));TextView grade=chip(s.optString("qualityGrade",grade(s.optInt("score",0)))+" • "+s.optInt("score",0)+"/100",BLUE);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-2,-2);gp.setMargins(dp(7),0,0,0);h.addView(grade,gp);c.addView(h);
        LinearLayout meta=row();meta.addView(tv(signalStyle+" • "+order,10,CYAN,true),new LinearLayout.LayoutParams(0,-2,1f));meta.addView(chip(lifecycleVi(s),lifecycleColor(s)));c.addView(meta);
        String id=s.optString("signalId",s.optString("id",sym+":"+signalStyle));double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp3=s.optDouble("tp3",s.optDouble("tp",0));double px=priceFor(s,e);
        TextView pv=tv(fmt(px),21,CYAN,true);pv.setPadding(0,dp(8),0,0);c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);
        TextView sv=tv(sourceText(market),9,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        TextView pnl=tv(tradeStatusText(s,px),11,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(7),0,dp(2));c.addView(pnl);pnlViews.put(id,pnl);
        TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(58)));gaugeViews.put(id,gauge);
        LinearLayout levels=row();LinearLayout left=column(),right=column();left.addView(metric("ENTRY",fmt(e),TEXT));left.addView(metric("SL",fmt(sl),RED));left.addView(metric("RR","1 : "+String.format(Locale.US,"%.2f",targetR(s)),CYAN));right.addView(metric("TP1",fmt(s.optDouble("tp1",0)),GREEN));right.addView(metric("TP2",fmt(s.optDouble("tp2",0)),GREEN));right.addView(metric("TP3",fmt(tp3),GREEN));levels.addView(left,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(0,-2,1f);rp.setMargins(dp(16),0,0,0);levels.addView(right,rp);c.addView(levels);
        c.addView(tv("Setup quality "+s.optInt("score",0)+"/100 • "+historicalWr(market,signalStyle),9,MUTED,false));
        pressFeedback(c);c.setClickable(true);c.setOnClickListener(v->{selectedSignal=s;detail=true;renderDetail(s,true);});return c;
    }''')

src=replace_method(src,'    private void renderDetail(JSONObject s,boolean animate)', '''    private void renderDetail(JSONObject s,boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();pnlViews.clear();subtitle.setText("CHI TIẾT TÍN HIỆU • LIVE");
        Button back=button("‹  QUAY LẠI",false,v->{detail=false;selectedSignal=null;renderSignals(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(42)));
        LinearLayout c=card();String market=s.optString("market","FOREX"),signalStyle=s.optString("style",style),side=sideVi(s.optString("side","—")),id=s.optString("signalId",s.optString("id","detail"));int col=side.equals("BUY")?GREEN:RED;
        LinearLayout h=row();h.addView(tv(s.optString("symbol","—"),24,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));c.addView(h);c.addView(tv(signalStyle+" • "+s.optString("orderType","MARKET")+" • "+lifecycleVi(s),10,CYAN,true));
        double px=priceFor(s,s.optDouble("entry",0));TextView pv=tv(fmt(px),29,TEXT,true);pv.setPadding(0,dp(10),0,dp(3));c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);TextView sv=tv(sourceText(market),10,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        TextView pnl=tv(tradeStatusText(s,px),14,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(12),0,dp(5));c.addView(pnl);pnlViews.put(id,pnl);TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(72)));gaugeViews.put(id,gauge);
        c.addView(line("ENTRY",fmt(s.optDouble("entry",0)),TEXT));c.addView(line("SL",fmt(s.optDouble("sl",0)),RED));c.addView(line("TP1",fmt(s.optDouble("tp1",0)),GREEN));c.addView(line("TP2",fmt(s.optDouble("tp2",0)),GREEN));c.addView(line("TP3",fmt(s.optDouble("tp3",s.optDouble("tp",0))),GREEN));c.addView(line("RR","1 : "+String.format(Locale.US,"%.2f",targetR(s)),CYAN));
        c.addView(line("SETUP QUALITY",s.optInt("score",0)+"/100 • "+s.optString("qualityGrade",grade(s.optInt("score",0))),BLUE));c.addView(tv("Điểm setup không phải xác suất thắng. "+historicalWr(market,signalStyle)+".",9,YELLOW,false));
        JSONArray why=s.optJSONArray("rationale");if(why!=null&&why.length()>0){TextView w=tv("LÝ DO VÀO LỆNH",11,TEXT,true);w.setPadding(0,dp(10),0,dp(2));c.addView(w);for(int i=0;i<why.length();i++)c.addView(tv("• "+why.optString(i),10,MUTED,false));}
        c.addView(tv("Phát: "+time(s.optString("issuedAt",""))+" • ID: "+id,9,MUTED,false));content.addView(c);
    };if(animate)swap(body);else body.run();updateAllPriceViews();}''')

src=replace_method(src,'    private void updateAllPriceViews()', '''    private void updateAllPriceViews(){
        for(Map.Entry<String,TextView> e:priceViews.entrySet()){
            String id=e.getKey(),m=viewMarkets.getOrDefault(id,"FOREX");JSONObject s=findSignal(id);double fallback=s==null?0:s.optDouble("entry",0),px=s==null?fallback:priceFor(s,fallback);
            e.getValue().setText(fmt(px));e.getValue().setTextColor(TEXT);
            TextView sv=sourceViews.get(id);if(sv!=null){String state=m.equals("FOREX")?fxState:cryptoState;sv.setText(sourceText(m));sv.setTextColor(stateColor(state));}
            if(s!=null){TextView pnl=pnlViews.get(id);if(pnl!=null){pnl.setText(tradeStatusText(s,px));pnl.setTextColor(tradeStatusColor(s,px));}TradeGauge g=gaugeViews.get(id);if(g!=null)g.setData(currentR(s,px),targetR(s));}
        }
    }''')

insert='''
    private void loadDashboardData(){
        loadSignalPartitions("SCALP");loadSignalPartitions("SWING");loadAllPerformance();loadSystemStatus();
        if(screen.equals("HOME"))main.post(()->renderHome(false));
    }

    private List<JSONObject> allSignals(){
        List<JSONObject> out=new ArrayList<>();
        for(String st:new String[]{"SCALP","SWING"})for(String m:new String[]{"FOREX","CRYPTO"}){JSONArray a=signalCache.get(m+":"+st);if(a==null)continue;for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null)out.add(s);}}
        out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }

    private int activeCount(String st){int n=0;for(JSONObject s:allSignals())if(st==null||st.equals(s.optString("style","")))n++;return n;}
    private double totalNetR(){double r=0;for(JSONObject p:perfCache.values())r+=p.optDouble("netRResolved",0);return r;}
    private String combinedWr(){int tp=0,sl=0;for(JSONObject p:perfCache.values()){tp+=p.optInt("tp",0);sl+=p.optInt("sl",0);}int n=tp+sl;return n==0?"—":String.format(Locale.US,"%.0f%%",tp*100.0/n);}

    private View statTile(String icon,String title,String value,String sub,int color){LinearLayout c=card();LinearLayout h=row();h.addView(tv(icon,18,color,true));TextView t=tv(title,9,MUTED,true);LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(0,-2,1f);tp.setMargins(dp(8),0,0,0);h.addView(t,tp);c.addView(h);c.addView(tv(value,23,TEXT,true));c.addView(tv(sub,9,color,false));return c;}

    private void renderHome(boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();pnlViews.clear();subtitle.setText("TRADE SMARTER • REAL SIGNALS • REAL RESULTS");
        LinearLayout hero=card();LinearLayout h=row();LinearLayout l=column();l.addView(tv("TÍN HIỆU CHẤT LƯỢNG",17,TEXT,true));l.addView(tv("CƠ HỘI THẬT",20,CYAN,true));l.addView(tv("KỶ LUẬT  •  DỮ LIỆU  •  KẾT QUẢ",9,MUTED,true));h.addView(l,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(fxState,stateColor(fxState)));hero.addView(h);content.addView(hero);
        LinearLayout r1=row();View a=statTile("◎","Tín hiệu đang chạy",String.valueOf(activeCount(null)),"SCALP + SWING",CYAN);View b=statTile("⚡","Scalp",String.valueOf(activeCount("SCALP")),"đang theo dõi",GREEN);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,0,dp(3),0);LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(3),0,0,0);r1.addView(a,p1);r1.addView(b,p2);content.addView(r1);
        LinearLayout r2=row();View d=statTile("▥","Swing",String.valueOf(activeCount("SWING")),"đang theo dõi",BLUE);View e=statTile("★","Tỷ lệ thắng",combinedWr(),"resolved TP/SL",GREEN);r2.addView(d,p1);r2.addView(e,p2);content.addView(r2);
        LinearLayout r3=row();View f=statTile("$","Net kết quả",String.format(Locale.US,"%+.1fR",totalNetR()),"lịch sử đã đóng",totalNetR()>=0?GREEN:RED);View g=statTile("✓","Hệ thống",systemState,"API + engine",stateColor(systemState));r3.addView(f,p1);r3.addView(g,p2);content.addView(r3);
        LinearLayout conn=card();conn.addView(tv("KẾT NỐI",12,TEXT,true));conn.addView(statusRow("Quote Feed • Exness MT5",fxState));conn.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));conn.addView(statusRow("Signal Engine",systemState));content.addView(conn);
        content.addView(tv("TÍN HIỆU ĐANG CHẠY",13,TEXT,true));List<JSONObject> rows=allSignals();int max=Math.min(4,rows.size());if(max==0){LinearLayout z=card();z.addView(tv("Đang đồng bộ tín hiệu…",10,MUTED,false));content.addView(z);}else for(int i=0;i<max;i++)content.addView(signalCard(rows.get(i)));
    };if(animate)swap(body);else body.run();updateAllPriceViews();}

    private void renderAlerts(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("THÔNG BÁO • TÍN HIỆU • TP/SL • HỆ THỐNG");content.addView(tv("THÔNG BÁO",16,TEXT,true));
        SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);String raw=p.getString("alert_history_v33","[]");try{JSONArray a=new JSONArray(raw);if(a.length()==0){LinearLayout z=card();z.addView(tv("Chưa có thông báo mới.",11,MUTED,true));z.addView(tv("SignalHub sẽ lưu các sự kiện MỚI / ACTIVE / TP / SL tại đây.",9,MUTED,false));content.addView(z);}for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x==null)continue;LinearLayout c=card();String title=x.optString("title","SignalHub"),bodyText=x.optString("body","");int color=title.contains("SL")?RED:title.contains("TP")||title.contains("BUY")?GREEN:title.contains("SELL")?RED:CYAN;c.addView(tv(title,12,color,true));c.addView(tv(bodyText,9,MUTED,false));long ts=x.optLong("ts",0);if(ts>0)c.addView(tv(relativeAge(Math.max(0,System.currentTimeMillis()-ts)),8,MUTED,false));content.addView(c);}}catch(Exception ex){LinearLayout z=card();z.addView(tv("Không đọc được lịch sử thông báo.",10,RED,true));content.addView(z);}
    };if(animate)swap(body);else body.run();}

    private void renderSettings(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CÀI ĐẶT • NGUỒN DỮ LIỆU • HỆ THỐNG");content.addView(tv("CÀI ĐẶT",16,TEXT,true));
        LinearLayout notify=card();notify.addView(tv("🔔  THÔNG BÁO",12,TEXT,true));notify.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));notify.addView(statusRow("Quyền thông báo",notifyPermission()?"ONLINE":"OFFLINE"));if(!monitorStarted){Button b=button("BẬT PUSH MONITOR",true,v->ensureMonitor(true));notify.addView(b,new LinearLayout.LayoutParams(-1,dp(42)));}content.addView(notify);
        LinearLayout source=card();source.addView(tv("◉  NGUỒN DỮ LIỆU",12,TEXT,true));source.addView(statusRow("Exness MT5",fxState));source.addView(line("Quote age",fxQuoteAgeMs<0?"—":String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0),stateColor(fxState)));source.addView(line("Forex symbols",String.valueOf(fxCount),TEXT));source.addView(statusRow(cryptoProvider,cryptoState));source.addView(line("Crypto symbols",String.valueOf(cryptoCount),TEXT));content.addView(source);
        LinearLayout sys=card();sys.addView(tv("⚙  HỆ THỐNG",12,TEXT,true));sys.addView(statusRow("Signal Engine",systemState));sys.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));sys.addView(line("App version",APP_VERSION,BLUE));if(systemStatus!=null){sys.addView(line("Backend",systemStatus.optString("version","—"),TEXT));sys.addView(line("Checkpoint",systemStatus.optString("checkpoint","—"),MUTED));}content.addView(sys);
        LinearLayout ui=card();ui.addView(tv("✦  GIAO DIỆN",12,TEXT,true));ui.addView(line("Chủ đề","Dark cyber-finance",CYAN));ui.addView(line("Ngôn ngữ","Tiếng Việt",TEXT));ui.addView(line("Live refresh","500 ms",GREEN));content.addView(ui);
    };if(animate)swap(body);else body.run();}

    private String historicalWr(String market,String st){JSONObject p=perfCache.get(market+":"+st);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}
    private double targetR(JSONObject s){double rr=s.optDouble("targetRR",0);if(rr>0)return rr;double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp3",s.optDouble("tp",0));double risk=Math.abs(e-sl);return risk>0&&tp>0?Math.max(0.1,Math.abs(tp-e)/risk):1.0;}
    private double currentR(JSONObject s,double px){double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),risk=Math.abs(e-sl);if(!(risk>0)||!(px>0))return 0;String side=sideVi(s.optString("side",""));return (side.equals("SELL")?(e-px):(px-e))/risk;}
    private String tradeStatusText(JSONObject s,double px){String life=lifecycleVi(s);if(life.contains("CHỜ"))return "CHỜ ENTRY • giá hiện tại "+fmt(px);double r=currentR(s,px),rr=targetR(s);if(r<0){int pct=(int)Math.round(Math.min(100,Math.max(0,-r*100)));return String.format(Locale.US,"ÂM  %+.2fR  •  %d%% TỚI SL",r,pct);}int pct=(int)Math.round(Math.min(100,Math.max(0,r/Math.max(.1,rr)*100)));return String.format(Locale.US,"DƯƠNG  %+.2fR  •  %d%% TỚI TP3",r,pct);}
    private int tradeStatusColor(JSONObject s,double px){if(lifecycleVi(s).contains("CHỜ"))return YELLOW;return currentR(s,px)>=0?GREEN:RED;}

    private class TradeGauge extends View{
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double r=0,target=1;
        TradeGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setData(double rr,double t){r=Double.isFinite(rr)?rr:0;target=t>0?t:1;invalidate();}
        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.58f,barH=dp(12),mid=w*.5f;p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(120,25,39));c.drawRoundRect(new RectF(dp(2),cy-barH/2,mid,cy+barH/2),barH/2,barH/2,p);p.setColor(Color.rgb(12,112,75));c.drawRoundRect(new RectF(mid,cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);p.setColor(Color.WHITE);p.setStrokeWidth(dp(2));c.drawLine(mid,cy-dp(13),mid,cy+dp(13),p);double clamped=r<0?Math.max(-1,Math.min(0,r)):Math.max(0,Math.min(target,r));float x=r<0?(float)(mid*(1+clamped)):(float)(mid+(w-mid)*(clamped/target));p.setColor(r>=0?GREEN:RED);p.setShadowLayer(dp(7),0,0,p.getColor());c.drawCircle(x,cy,dp(6),p);p.clearShadowLayer();p.setTextSize(dp(9));p.setTypeface(Typeface.create(Typeface.MONOSPACE,Typeface.BOLD));p.setColor(RED);p.setTextAlign(Paint.Align.LEFT);c.drawText("SL  -100%",dp(2),dp(12),p);p.setColor(TEXT);p.setTextAlign(Paint.Align.CENTER);c.drawText("ENTRY",mid,dp(12),p);p.setColor(GREEN);p.setTextAlign(Paint.Align.RIGHT);c.drawText("TP3  +100%",w-dp(2),dp(12),p);}
    }

'''
marker='    private void loadAllPerformance()'
if marker not in src: raise RuntimeError('insert marker missing')
src=src.replace(marker,insert+marker,1)

# Remove old 2-arg historicalWr to avoid duplicate ambiguity; keep overload used by old code if any.
src=src.replace('    private String historicalWr(String market){JSONObject p=perfCache.get(market+":"+style);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}\n','    private String historicalWr(String market){return historicalWr(market,style);}\n')

ACT.write_text(src,encoding='utf-8')

# Monitor: persist notification history for in-app Alerts screen.
mon=MON.read_text(encoding='utf-8')
mon=mon.replace('private static final String CH_MONITOR="signalhub_monitor_v32", CH_SIGNAL="signalhub_signal_v32";','private static final String CH_MONITOR="signalhub_monitor_v33", CH_SIGNAL="signalhub_signal_v33";')
mon=mon.replace('.setContentTitle("SignalHub V3.2 • LIVE MONITOR")','.setContentTitle("SignalHub V3.3 • LIVE MONITOR")')
needle='''        notifyHigh(title,b.toString(),key);'''
mon=mon.replace(needle,'''        appendHistory(title,b.toString());\n        notifyHigh(title,b.toString(),key);''')
helper='''\n    private void appendHistory(String title,String body){\n        try{\n            SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);\n            JSONArray old=new JSONArray(p.getString("alert_history_v33","[]"));\n            JSONArray out=new JSONArray();\n            JSONObject now=new JSONObject();now.put("ts",System.currentTimeMillis());now.put("title",title);now.put("body",body);out.put(now);\n            for(int i=0;i<old.length()&&i<49;i++)out.put(old.opt(i));\n            p.edit().putString("alert_history_v33",out.toString()).apply();\n        }catch(Throwable ignored){}\n    }\n'''
mon=mon.replace('    private Notification monitor(String text){',helper+'\n    private Notification monitor(String text){',1)
MON.write_text(mon,encoding='utf-8')

api=API.read_text(encoding='utf-8').replace('SignalHub-Android/3.2.0-low-latency','SignalHub-Android/3.3.0-cyber-ui')
API.write_text(api,encoding='utf-8')

g=GRADLE.read_text(encoding='utf-8').replace('versionCode 8','versionCode 9').replace("versionName '3.2.0'","versionName '3.3.0'")
GRADLE.write_text(g,encoding='utf-8')
print('SignalHub V3.3 UI patch applied')
