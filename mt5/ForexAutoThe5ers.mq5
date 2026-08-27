#property strict
#property version   "0.601"
#property description "FOREX AUTO The5ers PURE AI FAST - GPT + Claude own entry and position management; EA is transport/execution/safety only."

input string InpHubUrl="https://YOUR-WORKER.workers.dev";
input string InpBridgeToken="";
input bool InpAllowLiveTrading=false;
input int InpPulseSeconds=5;
input double InpMaxRiskPct=1.00;
input double InpMinFreeMarginPct=20.0;
input double InpMinMarginLevelPct=200.0;
input int InpMagic=560601;
input string InpSymbols="EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD";

string TerminalId;
ulong LastTradeOrder=0;
string LastTradeDetail="";

string Esc(string s){StringReplace(s,"\\","\\\\");StringReplace(s,"\"","\\\"");return s;}
string D(double v,int d=8){return DoubleToString(v,d);}
string JBool(bool x){return x?"true":"false";}
string Epoch(datetime t){return IntegerToString((long)t);}
bool IsCurrencyInSymbol(string symbol,string cur){return cur!=""&&StringFind(symbol,cur)>=0;}

bool NewsState(string symbol,bool &blocked){
 blocked=false;datetime now=TimeTradeServer();if(now<=0)now=TimeCurrent();
 MqlCalendarValue vals[];ResetLastError();int total=CalendarValueHistory(vals,now-180,now+180,NULL,NULL);if(total<0)return false;
 for(int i=0;i<total;i++){MqlCalendarEvent ev;if(!CalendarEventById(vals[i].event_id,ev)||ev.importance!=CALENDAR_IMPORTANCE_HIGH)continue;MqlCalendarCountry country;if(!CalendarCountryById(ev.country_id,country))continue;if(IsCurrencyInSymbol(symbol,country.currency)){blocked=true;return true;}}
 return true;
}

string BarsJson(string symbol,ENUM_TIMEFRAMES tf,int count){
 MqlRates r[];ArraySetAsSeries(r,true);int got=CopyRates(symbol,tf,0,count,r);if(got<12)return "[]";string out="[";
 for(int i=got-1;i>=0;i--){if(StringLen(out)>1)out+=",";out+="{\"time\":"+Epoch(r[i].time)+",\"open\":"+D(r[i].open)+",\"high\":"+D(r[i].high)+",\"low\":"+D(r[i].low)+",\"close\":"+D(r[i].close)+",\"volume\":"+IntegerToString((long)r[i].tick_volume)+"}";}
 return out+"]";
}
string SnapshotJson(string symbol){
 SymbolSelect(symbol,true);MqlTick t;if(!SymbolInfoTick(symbol,t))return "";bool newsBlocked=false,calendarOk=NewsState(symbol,newsBlocked);
 return "{\"symbol\":\""+Esc(symbol)+"\",\"bid\":"+D(t.bid)+",\"ask\":"+D(t.ask)+",\"last\":"+D(t.last)+",\"timestamp\":"+Epoch(t.time)+",\"newsBlocked\":"+JBool(newsBlocked)+",\"newsCalendarOk\":"+JBool(calendarOk)+",\"bars\":{\"M5\":"+BarsJson(symbol,PERIOD_M5,48)+",\"M15\":"+BarsJson(symbol,PERIOD_M15,40)+",\"H1\":"+BarsJson(symbol,PERIOD_H1,32)+",\"H4\":"+BarsJson(symbol,PERIOD_H4,24)+"}}";
}
string AccountJson(){
 double bal=AccountInfoDouble(ACCOUNT_BALANCE),eq=AccountInfoDouble(ACCOUNT_EQUITY),margin=AccountInfoDouble(ACCOUNT_MARGIN),freeMargin=AccountInfoDouble(ACCOUNT_MARGIN_FREE),marginLevel=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL),openRiskMoney=0;int count=0;
 for(int i=0;i<PositionsTotal();i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;count++;double sl=PositionGetDouble(POSITION_SL),op=PositionGetDouble(POSITION_PRICE_OPEN),vol=PositionGetDouble(POSITION_VOLUME);string sym=PositionGetString(POSITION_SYMBOL);if(sl<=0)continue;double v=0;ENUM_ORDER_TYPE typ=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(OrderCalcProfit(typ,sym,vol,op,sl,v))openRiskMoney+=MathMax(0,-v);}
 double riskPct=eq>0?openRiskMoney/eq*100.0:0;return "{\"balance\":"+D(bal,2)+",\"equity\":"+D(eq,2)+",\"margin\":"+D(margin,2)+",\"freeMargin\":"+D(freeMargin,2)+",\"marginLevelPct\":"+D(marginLevel,2)+",\"openRiskPct\":"+D(riskPct,3)+",\"openPositions\":"+IntegerToString(count)+"}";
}
string PositionsJson(){
 string out="[";for(int i=0;i<PositionsTotal();i++){ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;string sym=PositionGetString(POSITION_SYMBOL),side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL";if(StringLen(out)>1)out+=",";out+="{\"ticket\":\""+IntegerToString((long)ticket)+"\",\"symbol\":\""+Esc(sym)+"\",\"side\":\""+side+"\",\"entry\":"+D(PositionGetDouble(POSITION_PRICE_OPEN))+",\"sl\":"+D(PositionGetDouble(POSITION_SL))+",\"tp\":"+D(PositionGetDouble(POSITION_TP))+",\"volume\":"+D(PositionGetDouble(POSITION_VOLUME),3)+",\"profit\":"+D(PositionGetDouble(POSITION_PROFIT),2)+",\"openedAt\":"+Epoch((datetime)PositionGetInteger(POSITION_TIME))+"}";}return out+"]";
}

bool BridgeWrite(string name,string body){ResetLastError();FolderCreate("FOREX_BRIDGE");int h=FileOpen("FOREX_BRIDGE\\"+name,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);if(h==INVALID_HANDLE){Print("FOREX bridge write failed ",name," err=",GetLastError());return false;}FileWriteString(h,body);FileFlush(h);FileClose(h);return true;}
bool BridgeReadDecision(string &resp){resp="";ResetLastError();int h=FileOpen("FOREX_BRIDGE\\decision.json",FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);if(h==INVALID_HANDLE)return false;while(!FileIsEnding(h))resp+=FileReadString(h);FileClose(h);if(resp=="")return false;FileDelete("FOREX_BRIDGE\\decision.json");return true;}
bool HttpPost(string path,string body,string &resp){resp="";if(path=="/forex/mt5/pulse"){if(!BridgeWrite("pulse.json",body))return false;return BridgeReadDecision(resp);}if(path=="/forex/mt5/ack"){string name="ack_"+IntegerToString((long)TimeLocal())+"_"+IntegerToString((long)GetTickCount64())+".json";return BridgeWrite(name,body);}return false;}
string JsonString(string j,string k){string ptn="\""+k+"\":\"";int p=StringFind(j,ptn);if(p<0)return "";p+=StringLen(ptn);int e=StringFind(j,"\"",p);return e<0?"":StringSubstr(j,p,e-p);}
double JsonNumber(string j,string k){string ptn="\""+k+"\":";int p=StringFind(j,ptn);if(p<0)return 0;p+=StringLen(ptn);int e=p;while(e<StringLen(j)){ushort c=StringGetCharacter(j,e);if((c>=48&&c<=57)||c==45||c==43||c==46||c==101||c==69)e++;else break;}return StringToDouble(StringSubstr(j,p,e-p));}
int VolumeDigits(string s){double st=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);if(st>=1)return 0;if(st>=.1)return 1;if(st>=.01)return 2;return 3;}
ENUM_ORDER_TYPE_FILLING FillMode(string symbol){long filling=0;SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE,filling);if((filling&SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK)return ORDER_FILLING_FOK;if((filling&SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)return ORDER_FILLING_IOC;return ORDER_FILLING_RETURN;}
bool TradeRetcodeOk(uint rc){return rc==TRADE_RETCODE_DONE||rc==TRADE_RETCODE_PLACED||rc==TRADE_RETCODE_DONE_PARTIAL;}

double CalcVolume(string symbol,string side,double entry,double sl,double riskPct){double eq=AccountInfoDouble(ACCOUNT_EQUITY),riskMoney=eq*MathMin(riskPct,InpMaxRiskPct)/100.0,oneLot=0;if(riskMoney<=0)return 0;ENUM_ORDER_TYPE typ=side=="Buy"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcProfit(typ,symbol,1.0,entry,sl,oneLot)||MathAbs(oneLot)<.01)return 0;double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);if(step<=0)return 0;double vol=MathFloor((riskMoney/MathAbs(oneLot))/step)*step;vol=MathMax(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),MathMin(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX),vol));return NormalizeDouble(vol,VolumeDigits(symbol));}
bool MarginHeadroomOk(string symbol,string side,double volume,double price,string &reason){reason="";double eq=AccountInfoDouble(ACCOUNT_EQUITY),margin=AccountInfoDouble(ACCOUNT_MARGIN),freeMargin=AccountInfoDouble(ACCOUNT_MARGIN_FREE),need=0;if(eq<=0||freeMargin<0){reason="MARGIN_METRICS_INVALID";return false;}ENUM_ORDER_TYPE typ=side=="Buy"?ORDER_TYPE_BUY:ORDER_TYPE_SELL;if(!OrderCalcMargin(typ,symbol,volume,price,need)){reason="ORDER_MARGIN_CALC_FAILED";return false;}double projectedMargin=margin+MathMax(0,need),projectedFree=freeMargin-MathMax(0,need),freePct=projectedFree/eq*100.0,level=projectedMargin>0?eq/projectedMargin*100.0:99999;if(projectedFree<=0){reason="INSUFFICIENT_FREE_MARGIN";return false;}if(freePct<InpMinFreeMarginPct){reason="FREE_MARGIN_RESERVE_LOW";return false;}if(level<InpMinMarginLevelPct){reason="MARGIN_LEVEL_TOO_LOW";return false;}return true;}

bool SendMarket(string symbol,string side,double volume,double sl,double tp){LastTradeOrder=0;LastTradeDetail="";MqlTick tick;if(!SymbolInfoTick(symbol,tick)){LastTradeDetail="NO_TICK";return false;}MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_DEAL;req.symbol=symbol;req.magic=InpMagic;req.volume=volume;req.deviation=20;req.type_time=ORDER_TIME_GTC;req.type_filling=FillMode(symbol);req.comment="FOREX_PURE_AI_2AI";req.sl=sl;req.tp=tp;if(side=="Buy"){req.type=ORDER_TYPE_BUY;req.price=tick.ask;}else if(side=="Sell"){req.type=ORDER_TYPE_SELL;req.price=tick.bid;}else return false;bool sent=OrderSend(req,res);LastTradeOrder=res.order;LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool ModifyPosition(ulong ticket,double sl,double tp){if(ticket==0||!PositionSelectByTicket(ticket))return false;long type=PositionGetInteger(POSITION_TYPE);double oldSl=PositionGetDouble(POSITION_SL),entry=PositionGetDouble(POSITION_PRICE_OPEN);if(sl<=0)return false;if(type==POSITION_TYPE_BUY&&oldSl>0&&sl<oldSl)return false;if(type==POSITION_TYPE_SELL&&oldSl>0&&sl>oldSl)return false;if(type==POSITION_TYPE_BUY&&tp>0&&tp<=entry)return false;if(type==POSITION_TYPE_SELL&&tp>0&&tp>=entry)return false;MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_SLTP;req.position=ticket;req.symbol=PositionGetString(POSITION_SYMBOL);req.magic=InpMagic;req.sl=sl;req.tp=tp>0?tp:PositionGetDouble(POSITION_TP);bool sent=OrderSend(req,res);LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
bool ClosePosition(ulong ticket){if(ticket==0||!PositionSelectByTicket(ticket))return false;string symbol=PositionGetString(POSITION_SYMBOL);double vol=PositionGetDouble(POSITION_VOLUME);long type=PositionGetInteger(POSITION_TYPE);MqlTick tick;if(!SymbolInfoTick(symbol,tick))return false;MqlTradeRequest req={};MqlTradeResult res={};req.action=TRADE_ACTION_DEAL;req.position=ticket;req.symbol=symbol;req.magic=InpMagic;req.volume=vol;req.deviation=20;req.type_filling=FillMode(symbol);req.type_time=ORDER_TIME_GTC;if(type==POSITION_TYPE_BUY){req.type=ORDER_TYPE_SELL;req.price=tick.bid;}else{req.type=ORDER_TYPE_BUY;req.price=tick.ask;}req.comment="PURE_AI_EXIT";bool sent=OrderSend(req,res);LastTradeDetail=IntegerToString((long)res.retcode)+":"+res.comment;return sent&&TradeRetcodeOk(res.retcode);}
void Ack(string status,ulong ticket,string symbol,string detail,string action="",double pnl=0,string side=""){string b="{\"terminalId\":\""+Esc(TerminalId)+"\",\"status\":\""+Esc(status)+"\",\"ticket\":"+IntegerToString((long)ticket)+",\"symbol\":\""+Esc(symbol)+"\",\"detail\":\""+Esc(detail)+"\",\"action\":\""+Esc(action)+"\",\"pnl\":"+D(pnl,2)+",\"side\":\""+Esc(side)+"\"}";string r;HttpPost("/forex/mt5/ack",b,r);}

void HandleManagement(string resp){string action=JsonString(resp,"manageAction");if(action==""||action=="HOLD")return;ulong ticket=(ulong)JsonNumber(resp,"manageTicket");double sl=JsonNumber(resp,"manageSl"),tp=JsonNumber(resp,"manageTp");if(ticket==0)return;if(action=="CLOSE"){string sym="";double pnl=0;if(PositionSelectByTicket(ticket)){sym=PositionGetString(POSITION_SYMBOL);pnl=PositionGetDouble(POSITION_PROFIT);}if(ClosePosition(ticket))Ack("MANAGED",ticket,sym,"AI_CLOSE","AI_CLOSE",pnl);return;}if(action=="MODIFY_SLTP"&&ModifyPosition(ticket,sl,tp)){string sym=PositionSelectByTicket(ticket)?PositionGetString(POSITION_SYMBOL):"";Ack("MANAGED",ticket,sym,"AI_MODIFY_SLTP","AI_MODIFY_SLTP",0);}}
void HandleEntry(string resp){string action=JsonString(resp,"action");if(action==""||action=="NO_TRADE")return;string symbol=JsonString(resp,"symbol"),side=JsonString(resp,"side");double sl=JsonNumber(resp,"sl"),tp=JsonNumber(resp,"tp"),riskPct=JsonNumber(resp,"riskPct"),rr=JsonNumber(resp,"rr");if(action=="PAPER_TRADE"||!InpAllowLiveTrading){Print("FOREX PURE AI PAPER ",symbol," ",side," SL=",sl," TP=",tp," RR=",rr," risk%=",riskPct);return;}if(action!="TRADE"||symbol==""||sl<=0||tp<=0||riskPct<=0)return;if(PositionSelect(symbol)){Ack("REJECTED",0,symbol,"DUPLICATE_SYMBOL_POSITION","ENTRY",0,side);return;}MqlTick tick;if(!SymbolSelect(symbol,true)||!SymbolInfoTick(symbol,tick))return;double liveEntry=side=="Buy"?tick.ask:tick.bid;if(side=="Buy"&&!(sl<liveEntry&&tp>liveEntry))return;if(side=="Sell"&&!(sl>liveEntry&&tp<liveEntry))return;double vol=CalcVolume(symbol,side,liveEntry,sl,riskPct);if(vol<=0){Ack("REJECTED",0,symbol,"RISK_VOLUME_INVALID","ENTRY",0,side);return;}string marginReason;if(!MarginHeadroomOk(symbol,side,vol,liveEntry,marginReason)){Ack("REJECTED",0,symbol,marginReason,"ENTRY",0,side);return;}if(SendMarket(symbol,side,vol,sl,tp))Print("FOREX PURE AI LIVE sent ",symbol," ",side," vol=",vol);else Ack("REJECTED",0,symbol,LastTradeDetail,"ENTRY",0,side);}

string BuildPulse(){string parts[];int count=StringSplit(InpSymbols,',',parts);string snaps="[";for(int i=0;i<count;i++){string s=parts[i];StringTrimLeft(s);StringTrimRight(s);string x=SnapshotJson(s);if(x=="")continue;if(StringLen(snaps)>1)snaps+=",";snaps+=x;}snaps+="]";return "{\"terminalId\":\""+Esc(TerminalId)+"\",\"mt5\":{\"connected\":true,\"pureAiEa\":true,\"fastLoop\":true,\"version\":\"0.601\"},\"account\":"+AccountJson()+",\"positions\":"+PositionsJson()+",\"snapshots\":"+snaps+"}";}
void Pulse(){string resp;if(!HttpPost("/forex/mt5/pulse",BuildPulse(),resp))return;HandleManagement(resp);HandleEntry(resp);}

int OnInit(){TerminalId=IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"-"+IntegerToString((long)TerminalInfoInteger(TERMINAL_BUILD));EventSetTimer(MathMax(2,InpPulseSeconds));Print("FOREX PURE AI FAST 0.601 initialized terminal=",TerminalId," live=",InpAllowLiveTrading," pulse=",InpPulseSeconds);return INIT_SUCCEEDED;}
void OnDeinit(const int reason){EventKillTimer();}
void OnTimer(){Pulse();}
void OnTick(){}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result){if(trans.type!=TRADE_TRANSACTION_DEAL_ADD||trans.deal==0)return;if(!HistoryDealSelect(trans.deal))return;long magic=HistoryDealGetInteger(trans.deal,DEAL_MAGIC);if(magic!=InpMagic)return;long entryType=HistoryDealGetInteger(trans.deal,DEAL_ENTRY),dealType=HistoryDealGetInteger(trans.deal,DEAL_TYPE);ulong posId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);string symbol=HistoryDealGetString(trans.deal,DEAL_SYMBOL),side=dealType==DEAL_TYPE_BUY?"BUY":dealType==DEAL_TYPE_SELL?"SELL":"";double pnl=HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+HistoryDealGetDouble(trans.deal,DEAL_SWAP)+HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);if(entryType==DEAL_ENTRY_IN)Ack("FILLED",posId,symbol,"PURE_AI_ENTRY_FILLED","ENTRY",0,side);else if(entryType==DEAL_ENTRY_OUT||entryType==DEAL_ENTRY_OUT_BY)Ack("CLOSED",posId,symbol,"PURE_AI_OR_BROKER_EXIT","EXIT",pnl,side);}
