#property strict
#property version   "0.10"
#property description "FOREX AUTO The5ers - MT5 execution bridge. AI decides; EA enforces risk/protection."
#include <Trade/Trade.mqh>
CTrade trade;

input string InpHubUrl="https://YOUR-WORKER.workers.dev";
input string InpBridgeToken="";
input bool   InpAllowLiveTrading=false;
input int    InpPulseSeconds=60;
input double InpMaxRiskPct=0.50;
input int    InpMagic=560501;
input string InpSymbols="EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD";

string TerminalId;
datetime LastPulse=0;

string Esc(string s){StringReplace(s,"\\","\\\\");StringReplace(s,"\"","\\\"");return s;}
string D(double v,int d=8){return DoubleToString(v,d);}
string JBool(bool x){return x?"true":"false";}

bool IsCurrencyInSymbol(string symbol,string cur){return StringFind(symbol,cur)>=0;}
bool HasHighImpactNews(string symbol){
   datetime now=TimeTradeServer(); if(now<=0) now=TimeCurrent();
   MqlCalendarValue vals[]; int n=CalendarValueHistory(vals,now-180,now+180,NULL,NULL);
   if(n<=0) return false;
   for(int i=0;i<n;i++){
      MqlCalendarEvent ev; if(!CalendarEventById(vals[i].event_id,ev)) continue;
      if(ev.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry country; if(!CalendarCountryById(ev.country_id,country)) continue;
      if(IsCurrencyInSymbol(symbol,country.currency)) return true;
   }
   return false;
}

string BarsJson(string symbol,ENUM_TIMEFRAMES tf,int count){
   MqlRates r[]; ArraySetAsSeries(r,true); int got=CopyRates(symbol,tf,0,count,r); if(got<30) return "[]";
   string out="["; for(int i=got-1;i>=0;i--){ if(StringLen(out)>1) out+=","; out+="{\"time\":"+(string)r[i].time+",\"open\":"+D(r[i].open)+",\"high\":"+D(r[i].high)+",\"low\":"+D(r[i].low)+",\"close\":"+D(r[i].close)+",\"volume\":"+(string)r[i].tick_volume+"}";} return out+"]";
}

string SnapshotJson(string symbol){
   SymbolSelect(symbol,true); MqlTick t; if(!SymbolInfoTick(symbol,t)) return "";
   bool news=HasHighImpactNews(symbol);
   return "{\"symbol\":\""+Esc(symbol)+"\",\"bid\":"+D(t.bid)+",\"ask\":"+D(t.ask)+",\"last\":"+D(t.last)+",\"timestamp\":"+(string)(GetTickCount64())+",\"newsBlocked\":"+JBool(news)+",\"bars\":{\"M5\":"+BarsJson(symbol,PERIOD_M5,45)+",\"M15\":"+BarsJson(symbol,PERIOD_M15,45)+",\"H1\":"+BarsJson(symbol,PERIOD_H1,60)+"}}";
}

string AccountJson(){
   double bal=AccountInfoDouble(ACCOUNT_BALANCE),eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int positions=PositionsTotal(); double openRiskMoney=0;
   for(int i=0;i<positions;i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;double sl=PositionGetDouble(POSITION_SL),open=PositionGetDouble(POSITION_PRICE_OPEN),vol=PositionGetDouble(POSITION_VOLUME);string sym=PositionGetString(POSITION_SYMBOL);if(sl<=0)continue;double profit=0;if(OrderCalcProfit(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL,sym,vol,open,sl,profit))openRiskMoney+=MathAbs(profit);}
   double openRiskPct=eq>0?openRiskMoney/eq*100.0:0;
   // Day-start and initial balance are supplied conservatively as current balance until broker-history bootstrap is added.
   return "{\"balance\":"+D(bal,2)+",\"equity\":"+D(eq,2)+",\"initialBalance\":"+D(bal,2)+",\"dayStartBalance\":"+D(bal,2)+",\"openRiskPct\":"+D(openRiskPct,3)+",\"openPositions\":"+(string)positions+",\"lossStreak\":0}";
}

bool HttpPost(string path,string body,string &resp){
   char data[],result[];StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);string headers="Content-Type: application/json\r\nAuthorization: Bearer "+InpBridgeToken+"\r\n";string rh="";int code=WebRequest("POST",InpHubUrl+path,headers,15000,data,result,rh);resp=CharArrayToString(result,0,-1,CP_UTF8);if(code<200||code>=300){Print("FOREX hub HTTP ",code," ",resp);return false;}return true;
}

string JsonString(string j,string key){string pat="\""+key+"\":\"";int p=StringFind(j,pat);if(p<0)return "";p+=StringLen(pat);int e=StringFind(j,"\"",p);if(e<0)return "";return StringSubstr(j,p,e-p);}
double JsonNumber(string j,string key){string pat="\""+key+\":";int p=StringFind(j,pat);if(p<0)return 0;p+=StringLen(pat);int e=p;while(e<StringLen(j)){ushort c=StringGetCharacter(j,e);if((c>='0'&&c<='9')||c=='-'||c=='+'||c=='.'||c=='e'||c=='E')e++;else break;}return StringToDouble(StringSubstr(j,p,e-p));}

int VolumeDigits(string symbol){double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);if(step>=1)return 0;if(step>=.1)return 1;if(step>=.01)return 2;return 3;}
double CalcVolume(string symbol,string side,double entry,double sl,double riskPct){
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);double riskMoney=eq*MathMin(riskPct,InpMaxRiskPct)/100.0;if(riskMoney<=0)return 0;double oneLot=0;ENUM_ORDER_TYPE type=side=="Buy"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcProfit(type,symbol,1.0,entry,sl,oneLot)||MathAbs(oneLot)<.01)return 0;double vol=riskMoney/MathAbs(oneLot);double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),maxv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);vol=MathFloor(vol/step)*step;vol=MathMax(minv,MathMin(maxv,vol));return NormalizeDouble(vol,VolumeDigits(symbol));
}

void Ack(string status,ulong ticket,string symbol,string detail){string body="{\"terminalId\":\""+Esc(TerminalId)+"\",\"status\":\""+Esc(status)+"\",\"ticket\":"+(string)ticket+",\"symbol\":\""+Esc(symbol)+"\",\"detail\":\""+Esc(detail)+"\"}";string r;HttpPost("/forex/mt5/ack",body,r);}

void HandleDecision(string resp){
   string action=JsonString(resp,"action");if(action==""||action=="NO_TRADE")return;
   string symbol=JsonString(resp,"symbol"),side=JsonString(resp,"side");double entry=JsonNumber(resp,"entry"),sl=JsonNumber(resp,"sl"),tp=JsonNumber(resp,"tp"),riskPct=JsonNumber(resp,"riskPct"),rr=JsonNumber(resp,"rr");
   if(action=="PAPER_TRADE"||!InpAllowLiveTrading){Print("FOREX PAPER ",symbol," ",side," SL=",sl," TP=",tp," RR=",rr," risk%=",riskPct);return;}
   if(action!="TRADE"||symbol==""||sl<=0||tp<=0||riskPct<=0)return;
   if(PositionSelect(symbol)){Print("FOREX duplicate blocked ",symbol);return;}
   SymbolSelect(symbol,true);MqlTick tick;if(!SymbolInfoTick(symbol,tick))return;double liveEntry=side=="Buy"?tick.ask:tick.bid;double vol=CalcVolume(symbol,side,liveEntry,sl,riskPct);if(vol<=0){Ack("REJECTED",0,symbol,"VOLUME_CALC_FAILED");return;}
   trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(20);bool ok=side=="Buy"?trade.Buy(vol,symbol,0,sl,tp,"FOREX_AUTO_3AI"):trade.Sell(vol,symbol,0,sl,tp,"FOREX_AUTO_3AI");ulong ticket=(ulong)trade.ResultOrder();if(ok)Ack("FILLED",ticket,symbol,"SL_TP_ATTACHED");else Ack("REJECTED",ticket,symbol,trade.ResultRetcodeDescription());
}

void Pulse(){
   if(InpBridgeToken==""||StringFind(InpHubUrl,"YOUR-WORKER")>=0){Print("Configure InpHubUrl and InpBridgeToken");return;}
   string syms[];int cnt=StringSplit(InpSymbols,',',syms);string snaps="[";for(int i=0;i<cnt;i++){string s=syms[i];StringTrimLeft(s);StringTrimRight(s);string x=SnapshotJson(s);if(x=="")continue;if(StringLen(snaps)>1)snaps+=",";snaps+=x;}snaps+="]";
   string body="{\"terminalId\":\""+Esc(TerminalId)+"\",\"mt5\":{\"build\":"+(string)TerminalInfoInteger(TERMINAL_BUILD)+",\"connected\":"+JBool((bool)TerminalInfoInteger(TERMINAL_CONNECTED))+"},\"account\":"+AccountJson()+",\"snapshots\":"+snaps+"}";
   string resp;if(HttpPost("/forex/mt5/pulse",body,resp))HandleDecision(resp);
}

int OnInit(){TerminalId=StringFormat("%I64d-%s",AccountInfoInteger(ACCOUNT_LOGIN),AccountInfoString(ACCOUNT_SERVER));EventSetTimer(MathMax(30,InpPulseSeconds));Print("FOREX AUTO bridge ready: ",TerminalId," LIVE=",InpAllowLiveTrading);return INIT_SUCCEEDED;}
void OnDeinit(const int reason){EventKillTimer();}
void OnTimer(){Pulse();}
