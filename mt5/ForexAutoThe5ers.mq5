#property strict
#property version   "1.002"
#property description "FOREX PURE AI direct-Hub execution shell: MARKET/LIMIT/STOP, fail-closed red-news guard, pending auto-cancel, heartbeat watchdog."

input string InpHubUrl="https://trading-v77-scanner.hanlinh227.workers.dev";
input string InpBridgeToken="";
input bool InpAllowLiveTrading=false;
input int InpPulseMs=2000;
input int InpHttpTimeoutMs=8000;
input int InpHeartbeatSec=10;
input int InpWatchdogSec=15;
input int InpRedNewsGuardSec=180;
input double InpMaxRiskPct=1.00;
input double InpMinFreeMarginPct=20.0;
input double InpMinMarginLevelPct=200.0;
input double InpMaxEntryDriftAtr=0.10;
input int InpMaxSlippagePoints=15;
input int InpMagic=561001;
input string InpSymbols="EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD";

const int PROTOCOL_VERSION=1;
string TerminalId="";
string LastTradeDetail="";
ulong LastTradeOrder=0;

ulong PulseOkCount=0;
ulong PulseFailCount=0;
int ConsecutivePulseFails=0;
datetime LastPulseSuccessAt=0;
datetime LastHeartbeatAt=0;
int LastHttpCode=0;
long LastHttpLatencyMs=0;
string LastDecision="INIT";
string LastDecisionReason="";
string LastHttpState="INIT";

string Esc(string s){StringReplace(s,"\\","\\\\");StringReplace(s,"\"","\\\"");return s;}
string D(double v,int d=8){return DoubleToString(v,d);}
string JBool(bool x){return x?"true":"false";}
string Epoch(datetime t){return IntegerToString((long)t);}
string Upper(string s){StringToUpper(s);return s;}
bool IsCurrencyInSymbol(string symbol,string cur){return cur!=""&&StringFind(symbol,cur)>=0;}
bool IsPendingType(long t){return t==ORDER_TYPE_BUY_LIMIT||t==ORDER_TYPE_SELL_LIMIT||t==ORDER_TYPE_BUY_STOP||t==ORDER_TYPE_SELL_STOP;}

bool NewsState(string symbol,bool &blocked){
 blocked=false;datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();int guard=MathMax(120,InpRedNewsGuardSec);
 MqlCalendarValue vals[];ResetLastError();int total=CalendarValueHistory(vals,now-guard,now+guard,NULL,NULL);if(total<0)return false;
 for(int i=0;i<total;i++){MqlCalendarEvent ev;if(!CalendarEventById(vals[i].event_id,ev)||ev.importance!=CALENDAR_IMPORTANCE_HIGH)continue;MqlCalendarCountry c;if(!CalendarCountryById(ev.country_id,c))continue;if(IsCurrencyInSymbol(symbol,c.currency)){blocked=true;return true;}}
 return true;
}

string BarsJson(string symbol,ENUM_TIMEFRAMES tf,int count){
 MqlRates r[];ArraySetAsSeries(r,true);int got=CopyRates(symbol,tf,0,count,r);if(got<12)return "[]";string out="[";
 for(int i=got-1;i>=0;i--){if(StringLen(out)>1)out+=",";out+="{\"t\":"+Epoch(r[i].time)+",\"o\":"+D(r[i].open)+",\"h\":"+D(r[i].high)+",\"l\":"+D(r[i].low)+",\"c\":"+D(r[i].close)+",\"v\":"+IntegerToString((long)r[i].tick_volume)+"}";}
 return out+"]";
}
string SnapshotJson(string symbol){
 SymbolSelect(symbol,true);MqlTick t;if(!SymbolInfoTick(symbol,t))return "";bool newsBlocked=false,calendarOk=NewsState(symbol,newsBlocked);
 return "{\"symbol\":\""+Esc(symbol)+"\",\"bid\":"+D(t.bid)+",\"ask\":"+D(t.ask)+",\"last\":"+D(t.last)+",\"timestamp\":"+Epoch(t.time)+",\"newsBlocked\":"+JBool(newsBlocked)+",\"newsCalendarOk\":"+JBool(calendarOk)+",\"bars\":{\"M5\":"+BarsJson(symbol,PERIOD_M5,36)+",\"M15\":"+BarsJson(symbol,PERIOD_M15,28)+",\"H1\":"+BarsJson(symbol,PERIOD_H1,24)+",\"H4\":"+BarsJson(symbol,PERIOD_H4,16)+"}}";
}
string AccountJson(){
 double bal=AccountInfoDouble(ACCOUNT_BALANCE),eq=AccountInfoDouble(ACCOUNT_EQUITY),margin=AccountInfoDouble(ACCOUNT_MARGIN),fm=AccountInfoDouble(ACCOUNT_MARGIN_FREE),ml=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL),openRiskMoney=0;int count=0;
 for(int i=0;i<PositionsTotal();i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;count++;double sl=PositionGetDouble(POSITION_SL),op=PositionGetDouble(POSITION_PRICE_OPEN),vol=PositionGetDouble(POSITION_VOLUME);string sym=PositionGetString(POSITION_SYMBOL);if(sl<=0)continue;double v=0;ENUM_ORDER_TYPE typ=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(OrderCalcProfit(typ,sym,vol,op,sl,v))openRiskMoney+=MathMax(0,-v);}
 double rp=eq>0?openRiskMoney/eq*100.0:0;return "{\"login\":\""+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"\",\"server\":\""+Esc(AccountInfoString(ACCOUNT_SERVER))+"\",\"balance\":"+D(bal,2)+",\"equity\":"+D(eq,2)+",\"margin\":"+D(margin,2)+",\"freeMargin\":"+D(fm,2)+",\"marginLevelPct\":"+D(ml,2)+",\"openRiskPct\":"+D(rp,3)+",\"openPositions\":"+IntegerToString(count)+",\"tradeAllowed\":"+JBool(TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)!=0)+"}";
}
string PositionsJson(){string out="[";for(int i=0;i<PositionsTotal();i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;string sym=PositionGetString(POSITION_SYMBOL),side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL";if(StringLen(out)>1)out+=",";out+="{\"ticket\":\""+IntegerToString((long)ticket)+"\",\"symbol\":\""+Esc(sym)+"\",\"side\":\""+side+"\",\"entry\":"+D(PositionGetDouble(POSITION_PRICE_OPEN))+",\"sl\":"+D(PositionGetDouble(POSITION_SL))+",\"tp\":"+D(PositionGetDouble(POSITION_TP))+",\"volume\":"+D(PositionGetDouble(POSITION_VOLUME),3)+",\"profit\":"+D(PositionGetDouble(POSITION_PROFIT),2)+",\"openedAt\":"+Epoch((datetime)PositionGetInteger(POSITION_TIME))+"}";}return out+"]";}

bool HttpPost(string path,string body,string &resp){
 resp="";uchar data[];uchar result[];string resultHeaders="";int n=StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);if(n>0)ArrayResize(data,n-1);
 string headers="Content-Type: application/json\r\nAccept: application/json\r\nX-Forex-Protocol: "+IntegerToString(PROTOCOL_VERSION)+"\r\n";
 if(InpBridgeToken!="")headers+="Authorization: Bearer "+InpBridgeToken+"\r\n";
 ulong started=GetTickCount64();ResetLastError();int code=WebRequest("POST",InpHubUrl+path,headers,MathMax(1000,InpHttpTimeoutMs),data,result,resultHeaders);LastHttpLatencyMs=(long)(GetTickCount64()-started);LastHttpCode=code;
 if(code<0){int err=GetLastError();LastHttpState="WEBREQUEST_FAILED:"+IntegerToString(err);Print("FOREX HUB WebRequest failed err=",err," latencyMs=",LastHttpLatencyMs," url=",InpHubUrl+path);return false;}
 resp=CharArrayToString(result,0,-1,CP_UTF8);
 if(code<200||code>=300){if(code==401||code==403)LastHttpState="AUTH_FAILED";else if(code==408||code==504)LastHttpState="HUB_TIMEOUT";else LastHttpState="HTTP_"+IntegerToString(code);Print("FOREX HUB HTTP ",code," latencyMs=",LastHttpLatencyMs," body=",StringSubstr(resp,0,300));return false;}
 LastHttpState="HTTP_OK";return true;
}
string JsonString(string j,string k){string ptn="\""+k+"\":\"";int p=StringFind(j,ptn);if(p<0)return "";p+=StringLen(ptn);int e=StringFind(j,"\"",p);return e<0?"":StringSubstr(j,p,e-p);}
double JsonNumber(string j,string k){string ptn="\""+k+"\":";int p=StringFind(j,ptn);if(p<0)return 0;p+=StringLen(ptn);while(p<StringLen(j)&&StringGetCharacter(j,p)==32)p++;int e=p;while(e<StringLen(j)){ushort c=StringGetCharacter(j,e);if((c>=48&&c<=57)||c==45||c==43||c==46||c==101||c==69)e++;else break;}return StringToDouble(StringSubstr(j,p,e-p));}
int VolumeDigits(string s){double st=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);if(st>=1)return 0;if(st>=.1)return 1;if(st>=.01)return 2;return 3;}
ENUM_ORDER_TYPE_FILLING FillMode(string symbol){long f=0;SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE,f);if((f&SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK)return ORDER_FILLING_FOK;if((f&SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)return ORDER_FILLING_IOC;return ORDER_FILLING_RETURN;}
bool TradeRetcodeOk(uint rc){return rc==TRADE_RETCODE_DONE||rc==TRADE_RETCODE_PLACED||rc==TRADE_RETCODE_DONE_PARTIAL;}

double FastAtr(string symbol){MqlRates r[];ArraySetAsSeries(r,true);int got=CopyRates(symbol,PERIOD_M5,0,16,r);if(got<15)return 0;double sum=0;for(int i=0;i<14;i++){double prev=r[i+1].close;double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-prev),MathAbs(r[i].low-prev)));sum+=tr;}return sum/14.0;}
string LastFilledEntrySide(){datetime to=TimeCurrent(),from=to-60*60*24*30;if(!HistorySelect(from,to))return "";for(int i=HistoryDealsTotal()-1;i>=0;i--){ulong d=HistoryDealGetTicket(i);if(d==0)continue;if(HistoryDealGetInteger(d,DEAL_MAGIC)!=InpMagic)continue;if(HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN)continue;long t=HistoryDealGetInteger(d,DEAL_TYPE);if(t==DEAL_TYPE_BUY)return "BUY";if(t==DEAL_TYPE_SELL)return "SELL";}return "";}
bool AlternationOk(string side){string prev=LastFilledEntrySide();string now=Upper(side);return prev==""||prev!=now;}
bool HasPendingSymbol(string symbol){for(int i=OrdersTotal()-1;i>=0;i--){ulong ticket=OrderGetTicket(i);if(ticket==0)continue;if(OrderGetInteger(ORDER_MAGIC)!=InpMagic)continue;if(OrderGetString(ORDER_SYMBOL)!=symbol)continue;if(IsPendingType(OrderGetInteger(ORDER_TYPE)))return true;}return false;}
double CalcVolume(string symbol,string side,double entry,double sl,double riskPct){double eq=AccountInfoDouble(ACCOUNT_EQUITY),riskMoney=eq*MathMin(riskPct,InpMaxRiskPct)/100.0,oneLot=0;if(riskMoney<=0)return 0;ENUM_ORDER_TYPE typ=Upper(side)=="BUY"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcProfit(typ,symbol,1.0,entry,sl,oneLot)||MathAbs(oneLot)<.01)return 0;double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);if(step<=0)return 0;double vol=MathFloor((riskMoney/MathAbs(oneLot))/step)*step;vol=MathMax(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),MathMin(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX),vol));return NormalizeDouble(vol,VolumeDigits(symbol));}
bool MarginHeadroomOk(string symbol,string side,double volume,double price,string &reason){reason="";double eq=AccountInfoDouble(ACCOUNT_EQUITY),margin=AccountInfoDouble(ACCOUNT_MARGIN),fm=AccountInfoDouble(ACCOUNT_MARGIN_FREE),need=0;if(eq<=0||fm<0){reason="MARGIN_METRICS_INVALID";return false;}ENUM_ORDER_TYPE typ=Upper(side)=="BUY"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcMargin(typ,symbol,volume,price,need)){reason="ORDER_MARGIN_CALC_FAILED";return false;}double pm=margin+MathMax(0,need),pf=fm-MathMax(0,need),fp=pf/eq*100.0,level=pm>0?eq/pm*100.0:99999;if(pf<=0){reason="INSUFFICIENT_FREE_MARGIN";return false;}if(fp<InpMinFreeMarginPct){reason="FREE_MARGIN_RESERVE_LOW";return false;}if(level<InpMinMarginLevelPct){reason="MARGIN_LEVEL_TOO_LOW";return false;}return true;}

bool SendMarket(string symbol,string side,double volume,double sl,double tp){LastTradeOrder=0;LastTradeDetail="";MqlTick tick;if(!SymbolInfoTick(symbol,tick)){LastTradeDetail="NO_TICK";return false;}MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_DEAL;req.symbol=symbol;req.magic=InpMagic;req.volume=volume;req.deviation=InpMaxSlippagePoints;req.type_time=ORDER_TIME_GTC;req.type_filling=FillMode(symbol);req.comment="FOREX_AI_MARKET";string s=Upper(side);if(s=="BUY"){req.type=ORDER_TYPE_BUY;req.price=tick.ask;}else if(s=="SELL"){req.type=ORDER_TYPE_SELL;req.price=tick.bid;}else return false;req.sl=sl;req.tp=tp;bool sent=OrderSend(req,res);LastTradeOrder=res.order;LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool SendPending(string symbol,string side,string orderType,double volume,double entry,double sl,double tp){LastTradeOrder=0;LastTradeDetail="";MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_PENDING;req.symbol=symbol;req.magic=InpMagic;req.volume=volume;req.price=entry;req.sl=sl;req.tp=tp;req.type_time=ORDER_TIME_GTC;req.type_filling=ORDER_FILLING_RETURN;req.comment="FOREX_AI_"+orderType;string s=Upper(side),o=Upper(orderType);if(o=="LIMIT"&&s=="BUY")req.type=ORDER_TYPE_BUY_LIMIT;else if(o=="LIMIT"&&s=="SELL")req.type=ORDER_TYPE_SELL_LIMIT;else if(o=="STOP"&&s=="BUY")req.type=ORDER_TYPE_BUY_STOP;else if(o=="STOP"&&s=="SELL")req.type=ORDER_TYPE_SELL_STOP;else return false;bool sent=OrderSend(req,res);LastTradeOrder=res.order;LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool CancelPending(ulong ticket,string reason){if(ticket==0)return false;MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_REMOVE;req.order=ticket;bool sent=OrderSend(req,res);LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;if(sent&&TradeRetcodeOk(res.retcode)){Ack("CANCELLED",ticket,"",reason,"PENDING_CANCEL",0,"");return true;}return false;}
void CancelPendingForRedNews(){for(int i=OrdersTotal()-1;i>=0;i--){ulong ticket=OrderGetTicket(i);if(ticket==0)continue;if(OrderGetInteger(ORDER_MAGIC)!=InpMagic)continue;long type=OrderGetInteger(ORDER_TYPE);if(!IsPendingType(type))continue;string symbol=OrderGetString(ORDER_SYMBOL);bool blocked=false,calendarOk=NewsState(symbol,blocked);if(!calendarOk||blocked){string reason=!calendarOk?"NEWS_CALENDAR_FAIL_CLOSED":"RED_NEWS_PENDING_AUTO_CANCEL";if(CancelPending(ticket,reason))Print("FOREX pending cancelled ",ticket," ",symbol," reason=",reason);}}}
bool ModifyPosition(ulong ticket,double sl,double tp){if(ticket==0||!PositionSelectByTicket(ticket))return false;long type=PositionGetInteger(POSITION_TYPE);double oldSl=PositionGetDouble(POSITION_SL),entry=PositionGetDouble(POSITION_PRICE_OPEN);if(sl<=0)return false;if(type==POSITION_TYPE_BUY&&oldSl>0&&sl<oldSl)return false;if(type==POSITION_TYPE_SELL&&oldSl>0&&sl>oldSl)return false;if(type==POSITION_TYPE_BUY&&tp>0&&tp<=entry)return false;if(type==POSITION_TYPE_SELL&&tp>0&&tp>=entry)return false;MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_SLTP;req.position=ticket;req.symbol=PositionGetString(POSITION_SYMBOL);req.magic=InpMagic;req.sl=sl;req.tp=tp>0?tp:PositionGetDouble(POSITION_TP);bool sent=OrderSend(req,res);LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool ClosePosition(ulong ticket){if(ticket==0||!PositionSelectByTicket(ticket))return false;string symbol=PositionGetString(POSITION_SYMBOL);double vol=PositionGetDouble(POSITION_VOLUME);long type=PositionGetInteger(POSITION_TYPE);MqlTick tick;if(!SymbolInfoTick(symbol,tick))return false;MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_DEAL;req.position=ticket;req.symbol=symbol;req.magic=InpMagic;req.volume=vol;req.deviation=InpMaxSlippagePoints;req.type_filling=FillMode(symbol);req.type_time=ORDER_TIME_GTC;if(type==POSITION_TYPE_BUY){req.type=ORDER_TYPE_SELL;req.price=tick.bid;}else{req.type=ORDER_TYPE_BUY;req.price=tick.ask;}req.comment="PURE_AI_EXIT";bool sent=OrderSend(req,res);LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
void Ack(string status,ulong ticket,string symbol,string detail,string action="",double pnl=0,string side=""){string b="{\"protocolVersion\":"+IntegerToString(PROTOCOL_VERSION)+",\"terminalId\":\""+Esc(TerminalId)+"\",\"status\":\""+Esc(status)+"\",\"ticket\":"+IntegerToString((long)ticket)+",\"symbol\":\""+Esc(symbol)+"\",\"detail\":\""+Esc(detail)+"\",\"action\":\""+Esc(action)+"\",\"pnl\":"+D(pnl,2)+",\"side\":\""+Esc(side)+"\"}";string r;HttpPost("/forex/mt5/ack",b,r);}

void HandleManagement(string resp){string action=Upper(JsonString(resp,"manageAction"));if(action==""||action=="HOLD")return;ulong ticket=(ulong)JsonNumber(resp,"manageTicket");double sl=JsonNumber(resp,"manageSl"),tp=JsonNumber(resp,"manageTp");if(ticket==0)return;if(action=="CLOSE"){string sym="";double pnl=0;if(PositionSelectByTicket(ticket)){sym=PositionGetString(POSITION_SYMBOL);pnl=PositionGetDouble(POSITION_PROFIT);}if(ClosePosition(ticket))Ack("MANAGED",ticket,sym,"AI_CLOSE","AI_CLOSE",pnl);return;}if(action=="MODIFY_SLTP"&&ModifyPosition(ticket,sl,tp)){string sym=PositionSelectByTicket(ticket)?PositionGetString(POSITION_SYMBOL):"";Ack("MANAGED",ticket,sym,"AI_MODIFY_SLTP","AI_MODIFY_SLTP",0);}}
void HandleEntry(string resp){
 string action=Upper(JsonString(resp,"action"));if(action==""||action=="NO_TRADE"||action=="WAIT")return;string symbol=JsonString(resp,"symbol"),side=Upper(JsonString(resp,"side")),orderType=Upper(JsonString(resp,"orderType"));if(orderType=="")orderType="MARKET";double sl=JsonNumber(resp,"sl"),tp=JsonNumber(resp,"tp"),riskPct=JsonNumber(resp,"riskPct"),rr=JsonNumber(resp,"rr"),decisionEntry=JsonNumber(resp,"entry");
 if(action=="PAPER_TRADE"||!InpAllowLiveTrading){Print("FOREX PURE AI PAPER ",orderType," ",symbol," ",side," E=",decisionEntry," SL=",sl," TP=",tp," RR=",rr," risk%=",riskPct);return;}if(action!="TRADE"||symbol==""||sl<=0||tp<=0||riskPct<=0)return;
 if(!AlternationOk(side)){Ack("REJECTED",0,symbol,"ALTERNATION_HARD_LOCK","ENTRY",0,side);return;}if(PositionSelect(symbol)){Ack("REJECTED",0,symbol,"DUPLICATE_SYMBOL_POSITION","ENTRY",0,side);return;}if(HasPendingSymbol(symbol)){Ack("REJECTED",0,symbol,"DUPLICATE_SYMBOL_PENDING","ENTRY",0,side);return;}MqlTick tick;if(!SymbolSelect(symbol,true)||!SymbolInfoTick(symbol,tick))return;
 bool newsBlocked=false,calendarOk=NewsState(symbol,newsBlocked);if(!calendarOk){Ack("REJECTED",0,symbol,"NEWS_CALENDAR_FAIL_CLOSED","ENTRY",0,side);return;}if(newsBlocked){Ack("REJECTED",0,symbol,"HIGH_IMPACT_NEWS_WINDOW","ENTRY",0,side);return;}
 double liveEntry=side=="BUY"?tick.ask:tick.bid,entry=orderType=="MARKET"?liveEntry:decisionEntry;if(entry<=0)return;
 if(orderType=="LIMIT"&&side=="BUY"&&!(entry<tick.ask))return;if(orderType=="LIMIT"&&side=="SELL"&&!(entry>tick.bid))return;if(orderType=="STOP"&&side=="BUY"&&!(entry>tick.ask))return;if(orderType=="STOP"&&side=="SELL"&&!(entry<tick.bid))return;if(orderType!="MARKET"&&orderType!="LIMIT"&&orderType!="STOP")return;
 if(side=="BUY"&&!(sl<entry&&tp>entry))return;if(side=="SELL"&&!(sl>entry&&tp<entry))return;double atr=FastAtr(symbol);if(orderType=="MARKET"&&decisionEntry>0&&atr>0&&MathAbs(liveEntry-decisionEntry)>atr*InpMaxEntryDriftAtr){Ack("REJECTED",0,symbol,"PRICE_DRIFT_RETHINK","ENTRY",0,side);return;}
 double vol=CalcVolume(symbol,side,entry,sl,riskPct);if(vol<=0){Ack("REJECTED",0,symbol,"RISK_VOLUME_INVALID","ENTRY",0,side);return;}string reason;if(!MarginHeadroomOk(symbol,side,vol,entry,reason)){Ack("REJECTED",0,symbol,reason,"ENTRY",0,side);return;}bool sent=orderType=="MARKET"?SendMarket(symbol,side,vol,sl,tp):SendPending(symbol,side,orderType,vol,entry,sl,tp);if(sent)Print("FOREX PURE AI LIVE sent ",orderType," ",symbol," ",side," vol=",vol," entry=",entry);else Ack("REJECTED",0,symbol,LastTradeDetail,"ENTRY",0,side);
}

string BuildPulse(){string parts[];int count=StringSplit(InpSymbols,',',parts);string snaps="[";for(int i=0;i<count;i++){string s=parts[i];StringTrimLeft(s);StringTrimRight(s);string x=SnapshotJson(s);if(x=="")continue;if(StringLen(snaps)>1)snaps+=",";snaps+=x;}snaps+="]";return "{\"protocolVersion\":"+IntegerToString(PROTOCOL_VERSION)+",\"terminalId\":\""+Esc(TerminalId)+"\",\"mt5\":{\"connected\":"+JBool(TerminalInfoInteger(TERMINAL_CONNECTED)!=0)+",\"pureAiEa\":true,\"directHub\":true,\"eaVersion\":\"1.002\"},\"capabilities\":[\"MARKET_ENTRY\",\"LIMIT_ENTRY\",\"STOP_ENTRY\",\"RED_NEWS_FAIL_CLOSED\",\"PENDING_NEWS_AUTO_CANCEL\",\"HOLD\",\"CLOSE\",\"MODIFY_SLTP\",\"REPRICE\",\"ALTERNATION_LOCK\",\"HEARTBEAT_DIAGNOSTICS\"],\"account\":"+AccountJson()+",\"positions\":"+PositionsJson()+",\"snapshots\":"+snaps+"}";}

void PrintHeartbeat(bool force=false){datetime now=TimeCurrent();if(now<=0)now=TimeLocal();if(!force&&LastHeartbeatAt>0&&(now-LastHeartbeatAt)<MathMax(3,InpHeartbeatSec))return;LastHeartbeatAt=now;long age=LastPulseSuccessAt>0?(long)(now-LastPulseSuccessAt):-1;string watchdog=(LastPulseSuccessAt>0&&age>MathMax(5,InpWatchdogSec))?"STALE":"OK";Print("FOREX EA HEARTBEAT v1.002 connected=",TerminalInfoInteger(TERMINAL_CONNECTED)!=0," tradeAllowed=",TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)!=0," live=",InpAllowLiveTrading," pulseOk=",PulseOkCount," pulseFail=",PulseFailCount," failStreak=",ConsecutivePulseFails," lastHttp=",LastHttpCode," httpState=",LastHttpState," latencyMs=",LastHttpLatencyMs," lastDecision=",LastDecision," reason=",LastDecisionReason," lastPulseAgeSec=",age," watchdog=",watchdog," redNewsGuardSec=",MathMax(120,InpRedNewsGuardSec));}

void Pulse(){string resp;bool ok=HttpPost("/forex/mt5/pulse",BuildPulse(),resp);datetime now=TimeCurrent();if(now<=0)now=TimeLocal();if(!ok){PulseFailCount++;ConsecutivePulseFails++;LastDecision="PULSE_FAILED";LastDecisionReason=LastHttpState;PrintHeartbeat();return;}PulseOkCount++;ConsecutivePulseFails=0;LastPulseSuccessAt=now;string action=Upper(JsonString(resp,"action"));string reason=JsonString(resp,"reason");if(action=="")action="HTTP_OK_NO_ACTION";LastDecision=action;LastDecisionReason=reason;HandleManagement(resp);HandleEntry(resp);PrintHeartbeat();}

int OnInit(){TerminalId=IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"-"+IntegerToString((long)TerminalInfoInteger(TERMINAL_BUILD));if(StringLen(InpHubUrl)<8){Print("FOREX EA invalid Hub URL");return INIT_PARAMETERS_INCORRECT;}if(InpBridgeToken=="")Print("FOREX EA WARNING: InpBridgeToken is empty; Hub auth will likely fail.");int timerMs=MathMax(500,InpPulseMs);if(!EventSetMillisecondTimer(timerMs)){Print("FOREX EA timer setup failed err=",GetLastError());return INIT_FAILED;}Print("FOREX PURE AI EA 1.002 initialized terminal=",TerminalId," live=",InpAllowLiveTrading," pulseMs=",timerMs," httpTimeoutMs=",InpHttpTimeoutMs," protocol=",PROTOCOL_VERSION," orderTypes=MARKET/LIMIT/STOP redNewsGuard=ON");PrintHeartbeat(true);return INIT_SUCCEEDED;}
void OnDeinit(const int reason){EventKillTimer();Print("FOREX EA 1.002 deinitialized reason=",reason," pulseOk=",PulseOkCount," pulseFail=",PulseFailCount);}
void OnTimer(){CancelPendingForRedNews();Pulse();}
void OnTick(){}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result){if(trans.type!=TRADE_TRANSACTION_DEAL_ADD||trans.deal==0)return;if(!HistoryDealSelect(trans.deal))return;if(HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=InpMagic)return;long entryType=HistoryDealGetInteger(trans.deal,DEAL_ENTRY),dealType=HistoryDealGetInteger(trans.deal,DEAL_TYPE);ulong posId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);string symbol=HistoryDealGetString(trans.deal,DEAL_SYMBOL),side=dealType==DEAL_TYPE_BUY?"BUY":dealType==DEAL_TYPE_SELL?"SELL":"";double pnl=HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+HistoryDealGetDouble(trans.deal,DEAL_SWAP)+HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);if(entryType==DEAL_ENTRY_IN)Ack("FILLED",posId,symbol,"PURE_AI_ENTRY_FILLED","ENTRY",0,side);else if(entryType==DEAL_ENTRY_OUT||entryType==DEAL_ENTRY_OUT_BY)Ack("CLOSED",posId,symbol,"PURE_AI_OR_BROKER_EXIT","EXIT",pnl,side);}