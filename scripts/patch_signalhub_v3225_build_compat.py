from pathlib import Path
p=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
s=p.read_text()
needle='''    public static WebSocket connectCryptoStream(WebSocketListener listener) {\n        String ws = BASE_URL.replace("https://","wss://").replace("http://","ws://") + "/v3/crypto/stream";\n        Request r = new Request.Builder().url(ws).header("Cache-Control","no-cache").header("User-Agent","SignalHub-Android/3.22.5").build();\n        return LIVE_CLIENT.newWebSocket(r, listener);\n    }\n'''
assert needle in s, 'crypto stream method marker missing'
if 'public static WebSocket connectForexStream(' not in s:
    compat='''\n    /** Legacy compile compatibility only; crypto-only UI never opens this stream. */\n    public static WebSocket connectForexStream(WebSocketListener listener) {\n        String ws = BASE_URL.replace("https://","wss://").replace("http://","ws://") + "/v3/forex/stream";\n        Request r = new Request.Builder().url(ws).header("Cache-Control","no-cache").header("User-Agent","SignalHub-Android/3.22.5").build();\n        return LIVE_CLIENT.newWebSocket(r, listener);\n    }\n'''
    s=s.replace(needle,needle+compat,1)
p.write_text(s)
assert 'public static WebSocket connectForexStream(' in s
print('V3.22.5 Android compile compatibility patched')
