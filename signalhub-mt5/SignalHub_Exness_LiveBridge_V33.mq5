//+------------------------------------------------------------------+
//| SignalHub_Exness_LiveBridge_V33.mq5                              |
//| Windows VPS + MetaTrader 5 + Exness                              |
//| Purpose: Low-latency quote + heartbeat bridge to SignalHub V3.2  |
//| NOTE: This EA DOES NOT place, modify, or close trades.            |
//+------------------------------------------------------------------+
#property strict
#property version   "3.30"
#property description "SignalHub Exness low-latency data bridge"
#property description "Latest snapshot only, no stale quote queue"
#property description "Quote push + heartbeat for SignalHub V3.2"

input string InpSignalHubBaseUrl      = "https://signalhub-forex.hanlinh227.workers.dev";
input string InpBridgeToken           = ""; // Optional. If production uses MT5_BRIDGE_TOKEN, paste it here.
input string InpBridgeHeaderId        = "SIGNALHUB-EXNESS-BRIDGE-WINDOWS-V33";

input int    InpTimerResolutionMs     = 100;
input int    InpQuotePushIntervalMs   = 500;
input int    InpHeartbeatIntervalMs   = 2000;
input int    InpHttpTimeoutMs         = 800;
input int    InpRetryGapMs            = 250;
input bool   InpEnableVerboseLog      = true;

input string InpSymbolsCsv =
   "AUDCAD,AUDCHF,AUDJPY,AUDNZD,AUDUSD,"
   "CADCHF,CADJPY,CHFJPY,"
   "EURAUD,EURCAD,EURCHF,EURGBP,EURJPY,EURNZD,EURUSD,"
   "GBPAUD,GBPCAD,GBPCHF,GBPJPY,GBPNZD,GBPUSD,"
   "NZDCAD,NZDCHF,NZDJPY,NZDUSD,"
   "USDCAD,USDCHF,USDJPY,"
   "XAUUSD,XAGUSD,USOIL,UKOIL";

string g_requested[];
string g_broker[];
int    g_symbol_count = 0;

ulong  g_last_quote_attempt_ms = 0;
ulong  g_last_quote_success_ms = 0;
ulong  g_last_heartbeat_attempt_ms = 0;
ulong  g_last_heartbeat_success_ms = 0;
ulong  g_last_error_log_ms = 0;

int    g_quote_failures = 0;
int    g_heartbeat_failures = 0;
bool   g_busy = false;

string BRIDGE_VERSION = "SIGNALHUB-EXNESS-BRIDGE-WINDOWS-V33";

string TrimCopy(string s)
{
   StringTrimLeft(s);
   StringTrimRight(s);
   return s;
}

string UpperCopy(string s)
{
   StringToUpper(s);
   return s;
}

string JsonEscape(string s)
{
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\r", "\\r");
   StringReplace(s, "\n", "\\n");
   StringReplace(s, "\t", "\\t");
   return s;
}

string BoolJson(bool v)
{
   return v ? "true" : "false";
}

string BaseUrl()
{
   string s = TrimCopy(InpSignalHubBaseUrl);
   while(StringLen(s) > 0 && StringSubstr(s, StringLen(s)-1, 1) == "/")
      s = StringSubstr(s, 0, StringLen(s)-1);
   return s;
}

bool StartsWithNoCase(string value, string prefix)
{
   string a = UpperCopy(value);
   string b = UpperCopy(prefix);
   return StringFind(a, b, 0) == 0;
}

bool ResolveBrokerSymbol(string requested, string &resolved)
{
   requested = TrimCopy(requested);
   if(requested == "")
      return false;

   if(SymbolSelect(requested, true))
   {
      resolved = requested;
      return true;
   }

   int total = SymbolsTotal(false);
   int best_extra = 1000000;
   string best = "";

   for(int i = 0; i < total; i++)
   {
      string candidate = SymbolName(i, false);
      if(candidate == "")
         continue;
      if(!StartsWithNoCase(candidate, requested))
         continue;

      int extra = StringLen(candidate) - StringLen(requested);
      if(extra < 0)
         continue;
      if(extra < best_extra)
      {
         best = candidate;
         best_extra = extra;
         if(extra == 0)
            break;
      }
   }

   if(best == "")
      return false;
   if(!SymbolSelect(best, true))
      return false;

   resolved = best;
   return true;
}

int ResolveAllSymbols()
{
   ArrayResize(g_requested, 0);
   ArrayResize(g_broker, 0);

   string parts[];
   int n = StringSplit(InpSymbolsCsv, ',', parts);
   if(n <= 0)
      return 0;

   for(int i = 0; i < n; i++)
   {
      string requested = UpperCopy(TrimCopy(parts[i]));
      if(requested == "")
         continue;

      string broker = "";
      if(!ResolveBrokerSymbol(requested, broker))
      {
         if(InpEnableVerboseLog)
            Print("[SignalHub] Symbol not resolved: ", requested);
         continue;
      }

      int new_size = ArraySize(g_requested) + 1;
      ArrayResize(g_requested, new_size);
      ArrayResize(g_broker, new_size);
      g_requested[new_size - 1] = requested;
      g_broker[new_size - 1] = broker;

      if(InpEnableVerboseLog)
         Print("[SignalHub] Resolved ", requested, " -> ", broker);
   }

   g_symbol_count = ArraySize(g_requested);
   return g_symbol_count;
}

string MakeHeaders()
{
   string headers =
      "Content-Type: application/json\r\n"
      "Accept: application/json\r\n"
      "Cache-Control: no-cache\r\n";

   string token = TrimCopy(InpBridgeToken);
   if(token != "")
      headers += "Authorization: Bearer " + token + "\r\n";
   else
      headers += "X-SignalHub-Bridge: " + InpBridgeHeaderId + "\r\n";

   return headers;
}

bool HttpPostJson(string path, string body, int &http_code, string &response_text)
{
   string url = BaseUrl() + path;
   string headers = MakeHeaders();

   uchar payload_u[];
   char  payload[];
   char  result[];
   string result_headers = "";

   int copied = StringToCharArray(body, payload_u, 0, StringLen(body), CP_UTF8);
   if(copied <= 0)
   {
      http_code = -1;
      response_text = "";
      return false;
   }

   ArrayResize(payload, copied);
   for(int i = 0; i < copied; i++)
      payload[i] = (char)payload_u[i];

   ResetLastError();
   http_code = WebRequest(
      "POST",
      url,
      headers,
      MathMax(200, InpHttpTimeoutMs),
      payload,
      result,
      result_headers
   );

   int err = GetLastError();

   if(ArraySize(result) > 0)
   {
      uchar result_u[];
      int rn = ArraySize(result);
      ArrayResize(result_u, rn);
      for(int i = 0; i < rn; i++)
         result_u[i] = (uchar)result[i];
      response_text = CharArrayToString(result_u, 0, WHOLE_ARRAY, CP_UTF8);
   }
   else
      response_text = "";

   if(http_code >= 200 && http_code < 300)
      return true;

   ulong now = GetTickCount64();
   if(InpEnableVerboseLog && (now - g_last_error_log_ms >= 2000))
   {
      g_last_error_log_ms = now;
      Print("[SignalHub] POST failed path=", path,
            " http=", http_code,
            " mql_error=", err,
            " response=", response_text);
   }
   return false;
}

string BuildQuotesJson(int &valid_quotes)
{
   valid_quotes = 0;

   string server = JsonEscape(AccountInfoString(ACCOUNT_SERVER));
   string body =
      "{"
      "\"bridgeVersion\":\"" + JsonEscape(BRIDGE_VERSION) + "\","
      "\"server\":\"" + server + "\","
      "\"quotes\":[";

   bool first = true;

   for(int i = 0; i < g_symbol_count; i++)
   {
      string canonical = g_requested[i];
      string broker = g_broker[i];

      MqlTick tick;
      ResetLastError();

      if(!SymbolInfoTick(broker, tick))
         continue;
      if(!(tick.bid > 0.0) || !(tick.ask > 0.0) || tick.ask < tick.bid)
         continue;

      int digits = (int)SymbolInfoInteger(broker, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(broker, SYMBOL_POINT);
      double spread_points = 0.0;
      if(point > 0.0)
         spread_points = (tick.ask - tick.bid) / point;

      string row =
         "{"
         "\"symbol\":\"" + JsonEscape(canonical) + "\","
         "\"brokerSymbol\":\"" + JsonEscape(broker) + "\","
         "\"bid\":" + DoubleToString(tick.bid, digits) + ","
         "\"ask\":" + DoubleToString(tick.ask, digits) + ","
         "\"last\":" + (tick.last > 0.0 ? DoubleToString(tick.last, digits) : "null") + ","
         "\"spreadPoints\":" + DoubleToString(spread_points, 2) + ","
         "\"tickTimeMsc\":" + IntegerToString((long)tick.time_msc) +
         "}";

      if(!first)
         body += ",";
      body += row;
      first = false;
      valid_quotes++;
   }

   body += "]}";
   return body;
}

string BuildHeartbeatJson()
{
   bool terminal_connected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   bool terminal_trade_allowed = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   bool account_trade_allowed = (bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED);

   string server = JsonEscape(AccountInfoString(ACCOUNT_SERVER));
   string company = JsonEscape(AccountInfoString(ACCOUNT_COMPANY));

   string body =
      "{"
      "\"bridgeVersion\":\"" + JsonEscape(BRIDGE_VERSION) + "\","
      "\"status\":\"RUNNING\","
      "\"server\":\"" + server + "\","
      "\"company\":\"" + company + "\","
      "\"terminalConnected\":" + BoolJson(terminal_connected) + ","
      "\"tradeAllowed\":" + BoolJson(terminal_trade_allowed && account_trade_allowed) + ","
      "\"resolvedSymbols\":" + IntegerToString(g_symbol_count) + ","
      "\"positions\":" + IntegerToString(PositionsTotal()) + ","
      "\"orders\":" + IntegerToString(OrdersTotal()) + ","
      "\"queuedEvents\":0"
      "}";

   return body;
}

void PushQuotes()
{
   int valid_quotes = 0;
   string body = BuildQuotesJson(valid_quotes);

   if(valid_quotes <= 0)
   {
      g_quote_failures++;
      return;
   }

   int code = -1;
   string response = "";
   bool ok = HttpPostJson("/v3/mt5/prices", body, code, response);

   if(ok)
   {
      g_quote_failures = 0;
      g_last_quote_success_ms = GetTickCount64();
   }
   else
      g_quote_failures++;
}

void PushHeartbeat()
{
   string body = BuildHeartbeatJson();
   int code = -1;
   string response = "";
   bool ok = HttpPostJson("/v3/mt5/heartbeat", body, code, response);

   if(ok)
   {
      g_heartbeat_failures = 0;
      g_last_heartbeat_success_ms = GetTickCount64();
   }
   else
      g_heartbeat_failures++;
}

void UpdateChartStatus()
{
   ulong now = GetTickCount64();

   long quote_age =
      (g_last_quote_success_ms > 0 && now >= g_last_quote_success_ms)
      ? (long)(now - g_last_quote_success_ms)
      : -1;

   long hb_age =
      (g_last_heartbeat_success_ms > 0 && now >= g_last_heartbeat_success_ms)
      ? (long)(now - g_last_heartbeat_success_ms)
      : -1;

   string state;
   if(!(bool)TerminalInfoInteger(TERMINAL_CONNECTED))
      state = "MT5 OFFLINE";
   else if(quote_age >= 0 && quote_age <= 3000)
      state = "LIVE";
   else if(quote_age >= 0 && quote_age <= 8000)
      state = "DEGRADED";
   else
      state = "NO FRESH PUSH";

   string text =
      "SignalHub Exness Bridge V3.3\n"
      "State: " + state + "\n"
      "Resolved: " + IntegerToString(g_symbol_count) + "\n"
      "Quote push age: " + (quote_age >= 0 ? IntegerToString(quote_age) + " ms" : "N/A") + "\n"
      "Heartbeat age: " + (hb_age >= 0 ? IntegerToString(hb_age) + " ms" : "N/A") + "\n"
      "Quote failures: " + IntegerToString(g_quote_failures) + "\n"
      "Heartbeat failures: " + IntegerToString(g_heartbeat_failures);

   Comment(text);
}

int OnInit()
{
   if(StringLen(BaseUrl()) < 8)
   {
      Print("[SignalHub] Invalid base URL.");
      return INIT_PARAMETERS_INCORRECT;
   }

   int resolved = ResolveAllSymbols();
   if(resolved <= 0)
   {
      Print("[SignalHub] No symbols resolved. Check Market Watch / Exness symbol names.");
      return INIT_FAILED;
   }

   int timer_ms = InpTimerResolutionMs;
   if(timer_ms < 50)
      timer_ms = 50;
   if(timer_ms > 1000)
      timer_ms = 1000;

   ResetLastError();
   if(!EventSetMillisecondTimer(timer_ms))
   {
      Print("[SignalHub] EventSetMillisecondTimer failed. Error=", GetLastError());
      return INIT_FAILED;
   }

   g_last_quote_attempt_ms = 0;
   g_last_heartbeat_attempt_ms = 0;
   g_last_quote_success_ms = 0;
   g_last_heartbeat_success_ms = 0;

   Print("[SignalHub] Bridge started. Resolved symbols=", resolved,
         " quote_interval_ms=", InpQuotePushIntervalMs,
         " heartbeat_ms=", InpHeartbeatIntervalMs,
         " http_timeout_ms=", InpHttpTimeoutMs);

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
   Print("[SignalHub] Bridge stopped. reason=", reason);
}

void OnTick()
{
   // Intentionally empty: bridge timing does not depend on the chart symbol's ticks.
}

void OnTimer()
{
   if(g_busy)
      return;

   g_busy = true;
   ulong now = GetTickCount64();

   int quote_interval = MathMax(250, InpQuotePushIntervalMs);
   int retry_gap = MathMax(100, InpRetryGapMs);
   int heartbeat_interval = MathMax(1000, InpHeartbeatIntervalMs);

   bool quote_due = false;
   if(g_last_quote_attempt_ms == 0)
      quote_due = true;
   else if(g_quote_failures > 0)
      quote_due = (now - g_last_quote_attempt_ms >= (ulong)retry_gap);
   else
      quote_due = (now - g_last_quote_attempt_ms >= (ulong)quote_interval);

   if(quote_due)
   {
      g_last_quote_attempt_ms = now;
      PushQuotes();
   }

   now = GetTickCount64();
   if(g_last_heartbeat_attempt_ms == 0 ||
      now - g_last_heartbeat_attempt_ms >= (ulong)heartbeat_interval)
   {
      g_last_heartbeat_attempt_ms = now;
      PushHeartbeat();
   }

   UpdateChartStatus();
   g_busy = false;
}
//+------------------------------------------------------------------+
