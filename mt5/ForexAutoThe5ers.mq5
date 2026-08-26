#property strict
#property version   "0.400"
#property description "FOREX AUTO The5ers - independent 3AI bridge with hard risk and visible protection."

input string InpHubUrl="https://YOUR-WORKER.workers.dev";
input string InpBridgeToken="";
input bool InpAllowLiveTrading=false;
input int InpPulseSeconds=60;
input double InpMaxRiskPct=1.00;
input int InpMagic=560501;
input string InpSymbols="EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD";
input double InpBreakEvenR=1.00;
input double InpProfitLockR=1.35;
input double InpTrailR=1.60;

string TerminalId;
ulong LastTradeOrder=0;
string LastTradeDetail="";

string Esc(string s){StringReplace(s,"\\","\\\\");StringReplace(s,"\"","\\\"");return s;}
string D(double v,int d=8){return DoubleToString(v,d);}
string JBool(bool x){return x?"true":"false";}
bool IsCurrencyInSymbol(string symbol,string cur){return cur!=""&&StringFind(symbol,cur)>=0;}

bool NewsState(string symbol,bool &blocked){
  blocked=false;datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();
  MqlCalendarValue vals[];ResetLastError();int total=CalendarValueHistory(vals,now-180,now+180,NULL,NULL);
  if(total<0)return false;
  for(int i=0;i<total;i++){
    MqlCalendarEvent ev;if(!CalendarEventById(vals[i].event_id,ev)||ev.importance!=CALENDAR_IMPORTANCE_HIGH)continue;
    MqlCalendarCountry country;if(!CalendarCountryById(ev.country_id,country))continue;
    if(IsCurrencyInSymbol(symbol,country.currency)){blocked=true;return true;}
  }
  return true;
}

string BarsJson(string symbol,ENUM_TIMEFRAMES tf,int count){
  MqlRates r[];ArraySetAsSeries(r,true);int got=CopyRates(symbol,tf,0,count,r);if(got<30)return "[]";
  string out="[";for(int i=got-1;i>=0;i--){if(StringLen(out)>1)out+=",";out+="{\"time\":"+(string)r[i].time+",\"open\":"+D(r[i].open)+",\"high\":"+D(r[i].high)+",\"low\":"+D(r[i].low)+",\"close\":"+D(r[i].close)+",\"volume\":"+(string)r[i].tick_volume+"}";}return out+"]";
}

string SnapshotJson(string symbol){
  SymbolSelect(symbol,true);MqlTick t;if(!SymbolInfoTick(symbol,t))return "";bool newsBlocked=false,calendarOk=NewsState(symbol,newsBlocked);
  return "{\"symbol\":\""+Esc(symbol)+"\",\"bid\":"+D(t.bid)+",\"ask\":"+D(t.ask)+",\"last\":"+D(t.last)+",\"timestamp\":"+(string)t.time+",\"newsBlocked\":"+JBool(newsBlocked)+",\"newsCalendarOk\":"+JBool(calendarOk)+",\"bars\":{\"M5\":"+BarsJson(symbol,PERIOD_M5,45)+",\"M15\":"+BarsJson(symbol,PERIOD_M15,45)+",\"H1\":"+BarsJson(symbol,PERIOD_H1,60)+",\"H4\":"+BarsJson(symbol,PERIOD_H4,60)+"}}";
}

string AccountJson(){
  double bal=AccountInfoDouble(ACCOUNT_BALANCE),eq=AccountInfoDouble(ACCOUNT_EQUITY),openRiskMoney=0;int count=0;
  for(int i=0;i<PositionsTotal();i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;count++;double sl=PositionGetDouble(POSITION_SL),op=PositionGetDouble(POSITION_PRICE_OPEN),vol=PositionGetDouble(POSITION_VOLUME);string sym=PositionGetString(POSITION_SYMBOL);if(sl<=0)continue;double v=0;ENUM_ORDER_TYPE typ=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(OrderCalcProfit(typ,sym,vol,op,sl,v))openRiskMoney+=MathMax(0,-v);}
  double riskPct=eq>0?openRiskMoney/eq*100.0:0;return "{\"balance\":"+D(bal,2)+",\"equity\":"+D(eq,2)+",\"openRiskPct\":"+D(riskPct,3)+",\"openPositions\":"+(string)count+"}";
}

bool BridgeWrite(string name,string body){ResetLastError();FolderCreate("FOREX_BRIDGE");int h=FileOpen("FOREX_BRIDGE\\"+name,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);if(h==INVALID_HANDLE){Print("FOREX local bridge write failed ",name," err=",GetLastError());return false;}FileWriteString(h,body);FileFlush(h);FileClose(h);return true;}
bool BridgeReadDecision(string &resp){resp="";ResetLastError();int h=FileOpen("FOREX_BRIDGE\\decision.json",FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);if(h==INVALID_HANDLE)return false;while(!FileIsEnding(h))resp+=FileReadString(h);FileClose(h);if(resp=="")return false;FileDelete("FOREX_BRIDGE\\decision.json");return true;}
bool HttpPost(string path,string body,string &resp){resp="";if(path=="/forex/mt5/pulse"){if(!BridgeWrite("pulse.json",body))return false;return BridgeReadDecision(resp);}if(path=="/forex/mt5/ack"){string name="ack_"+(string)TimeLocal()+"_"+(string)GetTickCount64()+".json";return BridgeWrite(name,body);}Print("FOREX local bridge rejected path ",path);return false;}
string JsonString(string j,string k){string ptn="\""+k+"\":\"";int p=StringFind(j,ptn);if(p<0)return "";p+=StringLen(ptn);int e=StringFind(j,"\"",p);return e<0?"":StringSubstr(j,p,e-p);}
double JsonNumber(string j,string k){string ptn="\""+k+"\":";int p=StringFind(j,ptn);if(p<0)return 0;p+=StringLen(ptn);int e=p;while(e<StringLen(j)){ushort c=StringGetCharacter(j,e);if((c>=48&&c<=57)||c==45||c==43||c==46||c==101||c==69)e++;else break;}return StringToDouble(StringSubstr(j,p,e-p));}
int VolumeDigits(string s){double st=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);if(st>=1)return 0;if(st>=.1)return 1;if(st>=.01)return 2;return 3;}
double CalcVolume(string symbol,string side,double entry,double sl,double riskPct){double eq=AccountInfoDouble(ACCOUNT_EQUITY),riskMoney=eq*MathMin(riskPct,InpMaxRiskPct)/100.0,oneLot=0;if(riskMoney<=0)return 0;ENUM_ORDER_TYPE typ=side=="Buy"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcProfit(typ,symbol,1.0,entry,sl,oneLot)||MathAbs(oneLot)<.01)return 0;double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);if(step<=0)return 0;double vol=MathFloor((riskMoney/MathAbs(oneLot))/step)*step;vol=MathMax(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),MathMin(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX),vol));return NormalizeDouble(vol,VolumeDigits(symbol));}
ENUM_ORDER_TYPE_FILLING FillMode(string symbol){long filling=0;SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE,filling);if((filling & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK)return ORDER_FILLING_FOK;if((filling & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)return ORDER_FILLING_IOC;return ORDER_FILLING_RETURN;}
bool TradeRetcodeOk(uint rc){return rc==TRADE_RETCODE_DONE||rc==TRADE_RETCODE_PLACED||rc==TRADE_RETCODE_DONE_PARTIAL;}
bool SendMarket(string symbol,string side,double volume,double sl,double tp){LastTradeOrder=0;LastTradeDetail="";MqlTick tick;if(!SymbolInfoTick(symbol,tick)){LastTradeDetail="NO_TICK";return false;}MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_DEAL;req.symbol=symbol;req.magic=InpMagic;req.volume=volume;req.deviation=20;req.type_time=ORDER_TIME_GTC;req.type_filling=FillMode(symbol);req.comment="FOREX_AUTO_3AI";req.sl=sl;req.tp=tp;if(side=="Buy"){req.type=ORDER_TYPE_BUY;req.price=tick.ask;}else if(side=="Sell"){req.type=ORDER_TYPE_SELL;req.price=tick.bid;}else{LastTradeDetail="INVALID_SIDE";return false;}bool sent=OrderSend(req,res);LastTradeOrder=res.order;LastTradeDetail=(string)res.retcode+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool ModifyPositionStops(string symbol,double sl,double tp){LastTradeDetail="";if(!PositionSelect(symbol)){LastTradeDetail="POSITION_NOT_FOUND";return false;}MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_SLTP;req.symbol=symbol;req.position=(ulong)PositionGetInteger(POSITION_TICKET);req.magic=InpMagic;req.sl=sl;req.tp=tp;bool sent=OrderSend(req,res);LastTradeOrder=res.order;LastTradeDetail=(string)res.retcode+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
void Ack(string status,ulong ticket,string symbol,string detail,string action="",double pnl=0,string side="",double mfeR=0,double maeR=0){string b="{\"terminalId\":\""+Esc(TerminalId)+"\",\"status\":\""+Esc(status)+"\",\"ticket\":"+(string)ticket+",\"symbol\":\""+Esc(symbol)+"\",\"detail\":\""+Esc(detail)+"\",\"action\":\""+Esc(action)+"\",\"pnl\":"+D(pnl,2)+",\"side\":\""+Esc(side)+"\",\"mfeR\":"+D(mfeR,3)+",\"maeR\":"+D(maeR,3)+"}";string r;HttpPost("/forex/mt5/ack",b,r);}
string RiskKey(ulong ticket){return "FOREX_RISK_"+(string)ticket;}
string MfeKey(ulong ticket){return "FOREX_MFE_"+(string)ticket;}
string MaeKey(ulong ticket){return "FOREX_MAE_"+(string)ticket;}
double AtrM5(string symbol){MqlRates r[];ArraySetAsSeries(r,true);if(CopyRates(symbol,PERIOD_M5,0,16,r)<15)return 0;double sum=0;for(int i=0;i<14;i++){double pc=r[i+1].close;sum+=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-pc),MathAbs(r[i].low-pc)));}return sum/14.0;}
void ManagePositions(){for(int i=PositionsTotal()-1;i>=0;i--){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket)||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;string sym=PositionGetString(POSITION_SYMBOL);long type=PositionGetInteger(POSITION_TYPE);double entry=PositionGetDouble(POSITION_PRICE_OPEN),sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP),pnl=PositionGetDouble(POSITION_PROFIT);MqlTick t;if(!SymbolInfoTick(sym,t))continue;double mark=type==POSITION_TYPE_BUY?t.bid:t.ask,keyRisk=GlobalVariableCheck(RiskKey(ticket))?GlobalVariableGet(RiskKey(ticket)):MathAbs(entry-sl);if(keyRisk<=0)continue;double favorable=type==POSITION_TYPE_BUY?mark-entry:entry-mark,R=favorable/keyRisk,mfe=GlobalVariableCheck(MfeKey(ticket))?GlobalVariableGet(MfeKey(ticket)):0,mae=GlobalVariableCheck(MaeKey(ticket))?GlobalVariableGet(MaeKey(ticket)):0;if(R>mfe)GlobalVariableSet(MfeKey(ticket),R);if(R<mae)GlobalVariableSet(MaeKey(ticket),R);double newSl=sl;string phase="";if(R>=InpTrailR){double atr=AtrM5(sym);double tr=type==POSITION_TYPE_BUY?mark-MathMax(atr,keyRisk*.55):mark+MathMax(atr,keyRisk*.55);newSl=type==POSITION_TYPE_BUY?MathMax(sl,tr):((sl<=0)?tr:MathMin(sl,tr));phase="TRAIL";}else if(R>=InpProfitLockR){double lock=type==POSITION_TYPE_BUY?entry+keyRisk*.25:entry-keyRisk*.25;newSl=type==POSITION_TYPE_BUY?MathMax(sl,lock):((sl<=0)?lock:MathMin(sl,lock));phase="PROFIT_LOCK";}else if(R>=InpBreakEvenR){newSl=type==POSITION_TYPE_BUY?MathMax(sl,entry):((sl<=0)?entry:MathMin(sl,entry));phase="BREAKEVEN";}double point=SymbolInfoDouble(sym,SYMBOL_POINT);bool improve=type==POSITION_TYPE_BUY?newSl>sl+point*3:(sl<=0||newSl<sl-point*3);if(phase!=""&&improve&&ModifyPositionStops(sym,newSl,tp))Ack("MANAGED",ticket,sym,phase,phase,pnl);}}
void HandleDecision(string resp){string action=JsonString(resp,"action");if(action==""||action=="NO_TRADE")return;string symbol=JsonString(resp,"symbol"),side=JsonString(resp,"side");double sl=JsonNumber(resp,"sl"),tp=JsonNumber(resp,"tp"),riskPct=JsonNumber(resp,"riskPct"),rr=JsonNumber(resp,"rr");if(action=="PAPER_TRADE"||!InpAllowLiveTrading){Print("FOREX PAPER ",symbol," ",side," SL=",sl," TP=",tp," RR=",rr," risk%=",riskPct);return;}if(action!="TRADE"||symbol==""||sl<=0||tp<=0||riskPct<=0)return;if(PositionSelect(symbol)){Ack("REJECTED",0,symbol,"DUPLICATE_SYMBOL_POSITION","ENTRY",0,side);return;}MqlTick tick;if(!SymbolSelect(symbol,true)||!SymbolInfoTick(symbol,tick))return;double liveEntry=side=="Buy"?tick.ask:tick.bid,vol=CalcVolume(symbol,side,liveEntry,sl,riskPct);if(vol<=0){Ack("REJECTED",0,symbol,"VOLUME_CALC_FAILED","ENTRY",0,side);return;}bool ok=SendMarket(symbol,side,vol,sl,tp);if(ok&&PositionSelect(symbol)){ulong pt=(ulong)PositionGetInteger(POSITION_TICKET);double psl=PositionGetDouble(POSITION_SL),ptp=PositionGetDouble(POSITION_TP);if(psl<=0||ptp<=0){Ack("REJECTED",pt,symbol,"BROKER_PROTECTION_NOT_VISIBLE","ENTRY",0,side);return;}GlobalVariableSet(RiskKey(pt),MathAbs(PositionGetDouble(POSITION_PRICE_OPEN)-psl));GlobalVariableSet(MfeKey(pt),0);GlobalVariableSet(MaeKey(pt),0);Ack("FILLED",pt,symbol,"VISIBLE_SL_TP_ATTACHED","ENTRY",0,side);}else Ack("REJECTED",LastTradeOrder,symbol,LastTradeDetail,"ENTRY",0,side);}
void Pulse(){if(InpBridgeToken==""||StringFind(InpHubUrl,"YOUR-WORKER")>=0){Print("Configure InpHubUrl and InpBridgeToken");return;}string syms[];int cnt=StringSplit(InpSymbols,',',syms),valid=0;string snaps="[";for(int i=0;i<cnt;i++){string s=syms[i];StringTrimLeft(s);StringTrimRight(s);string x=SnapshotJson(s);if(x=="")continue;if(valid++>0)snaps+=",";snaps+=x;}snaps+="]";string body="{\"terminalId\":\""+Esc(TerminalId)+"\",\"mt5\":{\"build\":"+(string)TerminalInfoInteger(TERMINAL_BUILD)+",\"connected\":"+JBool((bool)TerminalInfoInteger(TERMINAL_CONNECTED))+",\"tradeAllowed\":"+JBool((bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))+"},\"account\":"+AccountJson()+",\"snapshots\":"+snaps+"}";string resp;if(HttpPost("/forex/mt5/pulse",body,resp))HandleDecision(resp);}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result){if(trans.type!=TRADE_TRANSACTION_DEAL_ADD||trans.deal==0)return;if(!HistoryDealSelect(trans.deal))return;if((long)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=InpMagic)return;long entry=(long)HistoryDealGetInteger(trans.deal,DEAL_ENTRY);if(entry!=DEAL_ENTRY_OUT&&entry!=DEAL_ENTRY_OUT_BY)return;ulong pos=(ulong)trans.position;string sym=HistoryDealGetString(trans.deal,DEAL_SYMBOL);double pnl=HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+HistoryDealGetDouble(trans.deal,DEAL_SWAP)+HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);long reason=(long)HistoryDealGetInteger(trans.deal,DEAL_REASON);string detail=reason==DEAL_REASON_TP?"TP":reason==DEAL_REASON_SL?"SL":reason==DEAL_REASON_SO?"STOP_OUT":"EXIT";double mfe=GlobalVariableCheck(MfeKey(pos))?GlobalVariableGet(MfeKey(pos)):0,mae=GlobalVariableCheck(MaeKey(pos))?GlobalVariableGet(MaeKey(pos)):0;Ack("CLOSED",pos,sym,detail,"EXIT",pnl,"",mfe,mae);GlobalVariableDel(RiskKey(pos));GlobalVariableDel(MfeKey(pos));GlobalVariableDel(MaeKey(pos));}
int OnInit(){TerminalId=StringFormat("%I64d-%s",AccountInfoInteger(ACCOUNT_LOGIN),AccountInfoString(ACCOUNT_SERVER));EventSetTimer(MathMax(10,InpPulseSeconds));Print("FOREX AUTO 0.400 independent local-bridge ready: ",TerminalId," LIVE=",InpAllowLiveTrading);return INIT_SUCCEEDED;}
void OnDeinit(const int reason){EventKillTimer();}
void OnTimer(){ManagePositions();Pulse();}