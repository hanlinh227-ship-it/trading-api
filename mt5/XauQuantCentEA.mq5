#property strict
#property version   "1.000"
#property description "XAU quantitative symmetric BUY/SELL EA for Exness Standard Cent/Standard. Research-first, news-aware, anti-martingale risk."

#include <Trade/Trade.mqh>

input string InpSymbol="XAUUSDc";
input bool   InpAllowLiveTrading=false;
input long   InpMagic=7261001;
input int    InpTimerSeconds=1;

// Equity/risk policy. Threshold is REAL USD, not raw USC display.
input double InpSafeThresholdUsd=10000.0;
input double InpAccountUnitToUsd=0.0;       // 0=auto: USC->0.01, USD->1.0. Set manually for other account currencies.
input double InpGrowthRiskPct=1.00;
input double InpSafeRiskPct=0.35;
input double InpSafeCompoundFactor=0.25;    // above $10k only 25% of incremental equity participates in sizing
input double InpGrowthAggregateRiskPct=3.00;
input double InpSafeAggregateRiskPct=1.25;
input double InpHardDrawdownStopPct=10.0;
input double InpMinMarginLevelPct=300.0;
input double InpMinFreeMarginPct=35.0;

// Quant model / execution.
input double InpTrendScoreThreshold=1.55;
input double InpMeanScoreThreshold=1.45;
input double InpTrendRR=1.60;
input double InpMeanRR=1.15;
input double InpTrendSlAtr=1.45;
input double InpMeanSlAtr=1.10;
input double InpMaxSlAtr=2.80;
input double InpMaxSpreadPrice=1.00;
input double InpMaxSpreadAtrFrac=0.12;
input int    InpMaxSlippagePoints=50;
input int    InpMaxTickAgeSec=20;

// Economic/geopolitical news safety.
input bool   InpUseMt5EconomicCalendar=true;
input int    InpHighNewsBeforeMin=45;
input int    InpHighNewsAfterMin=30;
input int    InpMediumNewsBeforeMin=20;
input int    InpMediumNewsAfterMin=15;
input string InpExternalNewsFile="XAU_QUANT\\news_state.json";
input int    InpNewsCautionStaleSec=300;
input int    InpNewsBlockStaleSec=900;

CTrade Trade;
datetime LastM5Bar=0;
double PeakEquityRaw=0.0;
string PeakGV="";
string LastState="INIT";
string LastReason="";
string LastRegime="NONE";
double LastScore=0.0;
double LastRiskPct=0.0;

struct QuantView {
   bool ok;
   bool shock;
   string regime;
   int direction;
   double score;
   double atrM5;
   double atrM15;
   double h1TrendNorm;
   double efficiency;
   double zscore;
};

struct NewsView {
   bool ok;
   bool block;
   double riskMult;
   string state;
   string reason;
   datetime blockUntil;
   long ageSec;
};

string U(string s){StringToUpper(s);return s;}
double Clamp(double x,double lo,double hi){return MathMax(lo,MathMin(hi,x));}
int Sign(double x){return x>0?1:(x<0?-1:0);}
string ModeName(double usd){return usd>=InpSafeThresholdUsd?"CAPITAL_PRESERVATION":"GROWTH";}

bool IsCentCurrency(string cur){cur=U(cur);return cur=="USC"||cur=="EUC"||cur=="GBC"||cur=="CHC"||cur=="AUC"||cur=="CAC";}

double UnitToUsdFactor(){
   if(InpAccountUnitToUsd>0)return InpAccountUnitToUsd;
   string c=U(AccountInfoString(ACCOUNT_CURRENCY));
   if(c=="USD")return 1.0;
   if(c=="USC")return 0.01;
   // Non-USD cent currencies require explicit FX conversion input for an exact USD threshold.
   if(IsCentCurrency(c))return 0.0;
   return 0.0;
}

double EquityUsd(bool &ok){
   double f=UnitToUsdFactor();ok=f>0;
   if(!ok)return 0.0;
   return AccountInfoDouble(ACCOUNT_EQUITY)*f;
}

double EffectiveSizingEquityRaw(double rawEq,double usdEq){
   if(rawEq<=0||usdEq<=0)return 0;
   if(usdEq<InpSafeThresholdUsd)return rawEq;
   double effectiveUsd=InpSafeThresholdUsd+MathMax(0.0,usdEq-InpSafeThresholdUsd)*Clamp(InpSafeCompoundFactor,0.0,1.0);
   return rawEq*(effectiveUsd/usdEq);
}

void UpdatePeak(){
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq<=0)return;
   if(PeakEquityRaw<=0)PeakEquityRaw=eq;
   if(eq>PeakEquityRaw){PeakEquityRaw=eq;GlobalVariableSet(PeakGV,PeakEquityRaw);}
}

double DrawdownPct(){
   UpdatePeak();double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(PeakEquityRaw<=0||eq<=0)return 100.0;
   return MathMax(0.0,(PeakEquityRaw-eq)/PeakEquityRaw*100.0);
}

double DrawdownRiskMult(double dd){
   if(dd>=InpHardDrawdownStopPct)return 0.0;
   if(dd>=8.0)return 0.25;
   if(dd>=5.0)return 0.50;
   if(dd>=3.0)return 0.75;
   return 1.0;
}

int LossStreak(){
   datetime to=TimeCurrent(),from=to-60*60*24*30;
   if(!HistorySelect(from,to))return 0;
   int streak=0;
   for(int i=HistoryDealsTotal()-1;i>=0;i--){
      ulong d=HistoryDealGetTicket(i);if(d==0)continue;
      if((long)HistoryDealGetInteger(d,DEAL_MAGIC)!=InpMagic)continue;
      if(HistoryDealGetString(d,DEAL_SYMBOL)!=InpSymbol)continue;
      long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT&&entry!=DEAL_ENTRY_OUT_BY)continue;
      double pnl=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
      if(pnl<0){streak++;if(streak>=6)return streak;}
      else if(pnl>0)break;
   }
   return streak;
}

double LossRiskMult(int streak){
   if(streak>=4)return 0.35;
   if(streak==3)return 0.45;
   if(streak==2)return 0.60;
   if(streak==1)return 0.80;
   return 1.0;
}

bool LoadRates(string sym,ENUM_TIMEFRAMES tf,int count,MqlRates &r[]){
   ArraySetAsSeries(r,true);int got=CopyRates(sym,tf,0,count,r);return got>=count;
}

double EMA(MqlRates &r[],int period,int shift){
   int n=ArraySize(r);int oldest=n-1;if(n<period+shift+10)return 0;
   double a=2.0/(period+1.0),x=r[oldest].close;
   for(int i=oldest-1;i>=shift;i--)x=a*r[i].close+(1.0-a)*x;
   return x;
}

double ATR(MqlRates &r[],int period,int shift){
   int n=ArraySize(r);if(n<shift+period+2)return 0;
   double s=0;
   for(int i=shift;i<shift+period;i++){
      double pc=r[i+1].close;
      double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-pc),MathAbs(r[i].low-pc)));
      s+=tr;
   }
   return s/period;
}

double Efficiency(MqlRates &r[],int len,int shift){
   if(ArraySize(r)<shift+len+2)return 0;
   double net=MathAbs(r[shift].close-r[shift+len].close),path=0;
   for(int i=shift;i<shift+len;i++)path+=MathAbs(r[i].close-r[i+1].close);
   return path>0?net/path:0;
}

double ZScore(MqlRates &r[],int len,int shift){
   if(ArraySize(r)<shift+len+2)return 0;
   double m=0;for(int i=shift;i<shift+len;i++)m+=r[i].close;m/=len;
   double v=0;for(int i=shift;i<shift+len;i++){double d=r[i].close-m;v+=d*d;}v/=MathMax(1,len-1);
   double sd=MathSqrt(v);return sd>0?(r[shift].close-m)/sd:0;
}

double AvgATR(MqlRates &r[],int period,int samples,int shift){
   double s=0;int n=0;
   for(int k=0;k<samples;k++){double a=ATR(r,period,shift+k);if(a>0){s+=a;n++;}}
   return n>0?s/n:0;
}

bool BullCandle(MqlRates &r[],int i){return r[i].close>r[i].open;}
bool BearCandle(MqlRates &r[],int i){return r[i].close<r[i].open;}

QuantView BuildQuantView(){
   QuantView q;q.ok=false;q.shock=false;q.regime="NONE";q.direction=0;q.score=0;q.atrM5=0;q.atrM15=0;q.h1TrendNorm=0;q.efficiency=0;q.zscore=0;
   MqlRates m5[],m15[],h1[];
   if(!LoadRates(InpSymbol,PERIOD_M5,140,m5)||!LoadRates(InpSymbol,PERIOD_M15,120,m15)||!LoadRates(InpSymbol,PERIOD_H1,140,h1))return q;
   int s=1; // closed-bar decisions only
   double a5=ATR(m5,14,s),a15=ATR(m15,14,s),a1=ATR(h1,14,s);
   if(a5<=0||a15<=0||a1<=0)return q;
   q.atrM5=a5;q.atrM15=a15;
   double h20=EMA(h1,20,s),h50=EMA(h1,50,s),m20=EMA(m15,20,s),m5e=EMA(m5,20,s);
   double trend=(h20-h50)/a1;
   double er=Efficiency(m15,20,s),z=ZScore(m15,48,s);
   double mom=(m5[s].close-m5[s+6].close)/a5;
   double atrBase=AvgATR(m5,14,36,s+1),atrRatio=atrBase>0?a5/atrBase:1.0;
   double lastRange=(m5[s].high-m5[s].low)/a5;
   q.h1TrendNorm=trend;q.efficiency=er;q.zscore=z;
   q.shock=(atrRatio>=2.20||lastRange>=2.60);
   if(q.shock){q.ok=true;q.regime="SHOCK";return q;}

   double close5=m5[s].close,close15=m15[s].close;
   double d5=(close5-m5e)/a5,d15=(close15-m20)/a15;
   int td=Sign(trend);
   bool trendRegime=(MathAbs(trend)>=0.18&&er>=0.27&&td!=0);
   bool neutralRegime=(MathAbs(trend)<=0.16&&er<=0.30);

   if(trendRegime){
      // Perfectly mirrored LONG/SHORT: same magnitudes, sign comes only from trend direction.
      bool aligned15=(td>0?d15>-0.30:d15<0.30);
      bool reclaim=(td>0?(BullCandle(m5,s)&&d5>=-0.20&&d5<=0.55):(BearCandle(m5,s)&&d5<=0.20&&d5>=-0.55));
      double alignMom=td*mom;
      double magnitude=0.80+Clamp(MathAbs(trend)*1.10,0,1.10)+Clamp(er*1.50,0,0.80)+Clamp(alignMom*0.22,-0.20,0.45);
      if(aligned15&&reclaim){q.score=td*magnitude;q.direction=td;q.regime="TREND";}
   } else if(neutralRegime){
      // Mean-reversion symmetry: positive z -> SELL, negative z -> BUY.
      int rd=-Sign(z);
      bool reversal=(rd>0?BullCandle(m5,s):rd<0?BearCandle(m5,s):false);
      bool notBreaking=(MathAbs(d15)<=1.30);
      double magnitude=Clamp(MathAbs(z)*0.95,0,2.60)+Clamp((0.30-er)*1.80,0,0.50);
      if(rd!=0&&MathAbs(z)>=1.15&&reversal&&notBreaking){q.score=rd*magnitude;q.direction=rd;q.regime="MEAN_REVERT";}
   }
   q.ok=true;return q;
}

bool TradeSessionOpen(){
   long mode=SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_MODE);
   if(mode==SYMBOL_TRADE_MODE_DISABLED||mode==SYMBOL_TRADE_MODE_CLOSEONLY)return false;
   MqlTick tick;if(!SymbolInfoTick(InpSymbol,tick))return false;
   datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();
   if(tick.time<=0||(now-tick.time)>InpMaxTickAgeSec)return false;

   MqlDateTime dt;TimeToStruct(now,dt);ENUM_DAY_OF_WEEK dow=(ENUM_DAY_OF_WEEK)dt.day_of_week;
   long secNow=dt.hour*3600+dt.min*60+dt.sec;
   bool any=false;
   for(uint k=0;k<12;k++){
      datetime from=0,to=0;if(!SymbolInfoSessionTrade(InpSymbol,dow,k,from,to))break;any=true;
      MqlDateTime f,t;TimeToStruct(from,f);TimeToStruct(to,t);
      long sf=f.hour*3600+f.min*60+f.sec,st=t.hour*3600+t.min*60+t.sec;
      bool inside=(sf<=st?(secNow>=sf&&secNow<st):(secNow>=sf||secNow<st));
      if(inside)return true;
   }
   return !any; // if broker exposes no sessions, tick freshness + trade mode remain the fallback
}

bool SpreadOk(double atr,string &reason){
   MqlTick t;if(!SymbolInfoTick(InpSymbol,t)){reason="NO_TICK";return false;}
   double sp=t.ask-t.bid;if(sp<=0){reason="BAD_SPREAD";return false;}
   double dyn=atr*InpMaxSpreadAtrFrac;
   double lim=MathMin(InpMaxSpreadPrice,MathMax(SymbolInfoDouble(InpSymbol,SYMBOL_POINT)*10,dyn));
   if(sp>lim){reason="SPREAD_SHOCK";return false;}
   return true;
}

string JsonString(string j,string key){
   string p="\""+key+"\":\"";int a=StringFind(j,p);if(a<0)return "";a+=StringLen(p);int b=StringFind(j,"\"",a);return b<0?"":StringSubstr(j,a,b-a);
}
long JsonLong(string j,string key){
   string p="\""+key+"\":";int a=StringFind(j,p);if(a<0)return 0;a+=StringLen(p);while(a<StringLen(j)&&StringGetCharacter(j,a)==32)a++;int b=a;while(b<StringLen(j)){ushort c=StringGetCharacter(j,b);if(c>=48&&c<=57)b++;else break;}return (long)StringToInteger(StringSubstr(j,a,b-a));
}
double JsonDouble(string j,string key){
   string p="\""+key+"\":";int a=StringFind(j,p);if(a<0)return 0;a+=StringLen(p);while(a<StringLen(j)&&StringGetCharacter(j,a)==32)a++;int b=a;while(b<StringLen(j)){ushort c=StringGetCharacter(j,b);if((c>=48&&c<=57)||c==45||c==46)b++;else break;}return StringToDouble(StringSubstr(j,a,b-a));
}

NewsView ExternalNews(){
   NewsView n;n.ok=false;n.block=false;n.riskMult=0.5;n.state="UNKNOWN";n.reason="EXTERNAL_NEWS_MISSING";n.blockUntil=0;n.ageSec=999999;
   int h=FileOpen(InpExternalNewsFile,FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE)return n;
   string j="";while(!FileIsEnding(h)){string x=FileReadString(h);if(j!="")j+=" ";j+=x;}FileClose(h);
   string st=U(JsonString(j,"state"));long updated=JsonLong(j,"updatedAtEpoch"),until=JsonLong(j,"blockUntilEpoch");
   datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();long age=updated>0?(long)now-updated:999999;
   n.ageSec=age;n.state=st!=""?st:"UNKNOWN";n.reason=JsonString(j,"reason");n.blockUntil=(datetime)until;
   if(age>InpNewsBlockStaleSec){n.block=true;n.riskMult=0;n.state="STALE_BLOCK";n.reason="EXTERNAL_NEWS_STALE";return n;}
   if(age>InpNewsCautionStaleSec){n.ok=true;n.block=false;n.riskMult=0.5;n.state="STALE_CAUTION";n.reason="EXTERNAL_NEWS_AGING";return n;}
   n.ok=true;
   if(st=="EMERGENCY"||st=="BLOCK_NEW"||(until>0&&now<(datetime)until)){n.block=true;n.riskMult=0;return n;}
   if(st=="CAUTION"||st=="DEGRADED"||st=="UNKNOWN"){n.riskMult=0.5;return n;}
   if(st=="NORMAL"){n.riskMult=1.0;return n;}
   n.riskMult=0.5;return n;
}

NewsView Mt5CalendarNews(){
   NewsView n;n.ok=true;n.block=false;n.riskMult=1.0;n.state="NORMAL";n.reason="MT5_CALENDAR_CLEAR";n.blockUntil=0;n.ageSec=0;
   if(!InpUseMt5EconomicCalendar)return n;
   datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();
   int before=MathMax(InpHighNewsBeforeMin,InpMediumNewsBeforeMin)*60;
   int after=MathMax(InpHighNewsAfterMin,InpMediumNewsAfterMin)*60;
   MqlCalendarValue vals[];ResetLastError();int total=CalendarValueHistory(vals,now-before,now+after,NULL,"USD");
   if(total<0){n.ok=false;n.riskMult=0.5;n.state="DEGRADED";n.reason="MT5_CALENDAR_UNAVAILABLE:"+IntegerToString(GetLastError());return n;}
   for(int i=0;i<total;i++){
      MqlCalendarEvent ev;if(!CalendarEventById(vals[i].event_id,ev))continue;
      long delta=(long)vals[i].time-(long)now;
      if(ev.importance==CALENDAR_IMPORTANCE_HIGH){
         if(delta<=InpHighNewsBeforeMin*60&&delta>=-InpHighNewsAfterMin*60){n.block=true;n.riskMult=0;n.state="BLOCK_NEW";n.reason="HIGH_USD_EVENT:"+ev.name;n.blockUntil=vals[i].time+InpHighNewsAfterMin*60;return n;}
      } else if(ev.importance==CALENDAR_IMPORTANCE_MODERATE){
         if(delta<=InpMediumNewsBeforeMin*60&&delta>=-InpMediumNewsAfterMin*60){n.riskMult=MathMin(n.riskMult,0.5);n.state="CAUTION";n.reason="MEDIUM_USD_EVENT:"+ev.name;}
      }
   }
   return n;
}

NewsView CombinedNews(){
   NewsView e=ExternalNews(),m=Mt5CalendarNews(),n;
   n.ok=e.ok&&m.ok;n.block=e.block||m.block;n.riskMult=MathMin(e.riskMult,m.riskMult);n.blockUntil=MathMax(e.blockUntil,m.blockUntil);n.ageSec=e.ageSec;
   if(n.block){n.state="BLOCK_NEW";n.reason=e.block?e.reason:m.reason;}
   else if(n.riskMult<0.75){n.state="CAUTION";n.reason=e.riskMult<=m.riskMult?e.reason:m.reason;}
   else {n.state="NORMAL";n.reason="NEWS_CLEAR";}
   return n;
}

double OpenRiskMoney(){
   double total=0;
   for(int i=0;i<PositionsTotal();i++){
      ulong tk=PositionGetTicket(i);if(tk==0||!PositionSelectByTicket(tk))continue;
      if((long)PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;
      if(PositionGetString(POSITION_SYMBOL)!=InpSymbol)continue;
      double sl=PositionGetDouble(POSITION_SL),op=PositionGetDouble(POSITION_PRICE_OPEN),vol=PositionGetDouble(POSITION_VOLUME);if(sl<=0||vol<=0)continue;
      ENUM_ORDER_TYPE typ=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL;double p=0;
      if(OrderCalcProfit(typ,InpSymbol,vol,op,sl,p)&&p<0)total+=-p;
   }
   return total;
}

int VolumeDigits(){double s=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(s>=1)return 0;if(s>=.1)return 1;if(s>=.01)return 2;if(s>=.001)return 3;return 4;}

double CalcVolume(int dir,double entry,double sl,double riskMoney){
   if(riskMoney<=0||entry<=0||sl<=0)return 0;
   double one=0;ENUM_ORDER_TYPE typ=dir>0?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   if(!OrderCalcProfit(typ,InpSymbol,1.0,entry,sl,one)||MathAbs(one)<1e-9)return 0;
   double raw=riskMoney/MathAbs(one),step=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP),mn=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX);
   if(step<=0||mn<=0)return 0;
   double v=MathFloor((raw+1e-12)/step)*step;
   if(v<mn)return 0;v=MathMin(v,mx);return NormalizeDouble(v,VolumeDigits());
}

bool MarginOk(int dir,double vol,double price,string &reason){
   double eq=AccountInfoDouble(ACCOUNT_EQUITY),fm=AccountInfoDouble(ACCOUNT_MARGIN_FREE),margin=AccountInfoDouble(ACCOUNT_MARGIN),need=0;
   ENUM_ORDER_TYPE typ=dir>0?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   if(eq<=0||fm<=0||!OrderCalcMargin(typ,InpSymbol,vol,price,need)){reason="MARGIN_CALC_FAILED";return false;}
   double projectedFree=fm-MathMax(0,need),projectedMargin=margin+MathMax(0,need),freePct=projectedFree/eq*100.0,ml=projectedMargin>0?eq/projectedMargin*100.0:99999;
   if(projectedFree<=0||freePct<InpMinFreeMarginPct){reason="FREE_MARGIN_LOW";return false;}
   if(ml<InpMinMarginLevelPct){reason="MARGIN_LEVEL_LOW";return false;}
   return true;
}

bool BuildStops(QuantView &q,int dir,double entry,double &sl,double &tp){
   MqlRates m5[];if(!LoadRates(InpSymbol,PERIOD_M5,30,m5))return false;
   double atr=q.atrM5;if(atr<=0)return false;
   double baseAtr=q.regime=="TREND"?InpTrendSlAtr:InpMeanSlAtr;
   double rr=q.regime=="TREND"?InpTrendRR:InpMeanRR;
   double swing;
   if(dir>0){swing=m5[1].low;for(int i=2;i<=6;i++)swing=MathMin(swing,m5[i].low);sl=MathMin(entry-baseAtr*atr,swing-0.15*atr);}
   else {swing=m5[1].high;for(int i=2;i<=6;i++)swing=MathMax(swing,m5[i].high);sl=MathMax(entry+baseAtr*atr,swing+0.15*atr);}
   double dist=MathAbs(entry-sl);if(dist<=0||dist>InpMaxSlAtr*atr)return false;
   tp=entry+dir*rr*dist;
   int dg=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);sl=NormalizeDouble(sl,dg);tp=NormalizeDouble(tp,dg);return true;
}

bool SendEntry(QuantView &q,NewsView &news){
   if(!InpAllowLiveTrading){LastState="REVIEW_ONLY";LastReason="LIVE_TRADING_DISABLED";return false;}
   if(q.direction==0)return false;
   if(news.block){LastState="NEWS_BLOCK";LastReason=news.reason;return false;}
   if(!TradeSessionOpen()){LastState="SESSION_BLOCK";LastReason="SYMBOL_NOT_TRADABLE_OR_STALE_TICK";return false;}
   string rs="";if(!SpreadOk(q.atrM5,rs)){LastState="SPREAD_BLOCK";LastReason=rs;return false;}

   bool usdOk=false;double usdEq=EquityUsd(usdOk),rawEq=AccountInfoDouble(ACCOUNT_EQUITY);if(!usdOk){LastState="CONFIG_BLOCK";LastReason="ACCOUNT_TO_USD_FACTOR_REQUIRED";return false;}
   double dd=DrawdownPct(),ddm=DrawdownRiskMult(dd);if(ddm<=0){LastState="DD_HALT";LastReason="HARD_DRAWDOWN_STOP";return false;}
   int streak=LossStreak();double lm=LossRiskMult(streak);
   double baseRisk=usdEq>=InpSafeThresholdUsd?InpSafeRiskPct:InpGrowthRiskPct;
   double effectiveRaw=EffectiveSizingEquityRaw(rawEq,usdEq);
   double riskPct=baseRisk*ddm*lm*news.riskMult;LastRiskPct=riskPct;
   if(riskPct<=0)return false;

   double aggregatePct=usdEq>=InpSafeThresholdUsd?InpSafeAggregateRiskPct:InpGrowthAggregateRiskPct;
   double openRisk=OpenRiskMoney(),capMoney=rawEq*aggregatePct/100.0,remaining=MathMax(0,capMoney-openRisk);
   double riskMoney=MathMin(effectiveRaw*riskPct/100.0,remaining);
   if(riskMoney<=0){LastState="PORTFOLIO_RISK_BLOCK";LastReason="AGGREGATE_RISK_CAP";return false;}

   MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return false;double entry=q.direction>0?t.ask:t.bid,sl=0,tp=0;
   if(!BuildStops(q,q.direction,entry,sl,tp)){LastState="STOP_BLOCK";LastReason="STRUCTURAL_SL_TOO_WIDE";return false;}
   double vol=CalcVolume(q.direction,entry,sl,riskMoney);if(vol<=0){LastState="SIZE_BLOCK";LastReason="VOLUME_BELOW_BROKER_MIN_OR_CALC_FAILED";return false;}
   if(!MarginOk(q.direction,vol,entry,rs)){LastState="MARGIN_BLOCK";LastReason=rs;return false;}

   Trade.SetExpertMagicNumber(InpMagic);Trade.SetDeviationInPoints(InpMaxSlippagePoints);Trade.SetTypeFillingBySymbol(InpSymbol);
   string comment="XAU_Q1_"+q.regime+"_"+(q.direction>0?"BUY":"SELL");
   bool ok=q.direction>0?Trade.Buy(vol,InpSymbol,0,sl,tp,comment):Trade.Sell(vol,InpSymbol,0,sl,tp,comment);
   if(ok){LastState="ORDER_SENT";LastReason=comment+" lot="+DoubleToString(vol,VolumeDigits());}
   else {LastState="ORDER_FAILED";LastReason=IntegerToString((int)Trade.ResultRetcode())+":"+Trade.ResultRetcodeDescription();}
   return ok;
}

void EvaluateNewBar(){
   QuantView q=BuildQuantView();LastRegime=q.regime;LastScore=q.score;
   if(!q.ok){LastState="DATA_BLOCK";LastReason="INSUFFICIENT_MARKET_DATA";return;}
   if(q.shock){LastState="SHOCK_BLOCK";LastReason="VOLATILITY_SHOCK";return;}
   bool qualified=(q.regime=="TREND"?MathAbs(q.score)>=InpTrendScoreThreshold:q.regime=="MEAN_REVERT"?MathAbs(q.score)>=InpMeanScoreThreshold:false);
   if(!qualified){LastState="NO_SIGNAL";LastReason=q.regime+" score="+DoubleToString(q.score,3);return;}
   NewsView n=CombinedNews();SendEntry(q,n);
}

void MaintainSafety(){
   UpdatePeak();
   // No forced daily trade cap. Existing trades keep broker-side SL/TP. New risk is halted by DD/news/spread/session gates.
   if(DrawdownPct()>=InpHardDrawdownStopPct){LastState="DD_HALT";LastReason="NEW_ENTRIES_HALTED";}
}

int OnInit(){
   if(!SymbolSelect(InpSymbol,true)){Print("XAU_Q1 init failed: symbol not found ",InpSymbol);return INIT_FAILED;}
   Trade.SetExpertMagicNumber(InpMagic);Trade.SetAsyncMode(false);
   PeakGV="XAU_Q1_PEAK_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN));
   if(GlobalVariableCheck(PeakGV))PeakEquityRaw=GlobalVariableGet(PeakGV);else {PeakEquityRaw=AccountInfoDouble(ACCOUNT_EQUITY);GlobalVariableSet(PeakGV,PeakEquityRaw);}
   if(InpTimerSeconds>0)EventSetTimer(InpTimerSeconds);
   bool usdOk=false;double usd=EquityUsd(usdOk);
   Print("XAU_Q1 INIT symbol=",InpSymbol," currency=",AccountInfoString(ACCOUNT_CURRENCY)," equityUsd=",usdOk?DoubleToString(usd,2):"UNRESOLVED"," mode=",usdOk?ModeName(usd):"CONFIG_BLOCK"," live=",InpAllowLiveTrading);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){EventKillTimer();}

void OnTimer(){
   MaintainSafety();
   MqlRates r[];ArraySetAsSeries(r,true);if(CopyRates(InpSymbol,PERIOD_M5,0,3,r)<3)return;
   datetime closed=r[1].time;if(closed<=0||closed==LastM5Bar)return;LastM5Bar=closed;
   EvaluateNewBar();
}

void OnTick(){MaintainSafety();}
