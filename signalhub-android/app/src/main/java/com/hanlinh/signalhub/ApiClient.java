package com.hanlinh.signalhub;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import java.util.concurrent.TimeUnit;

public final class ApiClient {
    public static final String BASE_URL = "https://signalhub-forex.hanlinh227.workers.dev";

    private static final OkHttpClient LIVE_CLIENT = new OkHttpClient.Builder().pingInterval(10, TimeUnit.SECONDS).retryOnConnectionFailure(true).build();

    private ApiClient() {}

    public static WebSocket connectForexStream(WebSocketListener listener) {
        String ws = BASE_URL.replace("https://","wss://").replace("http://","ws://") + "/v3/forex/stream";
        Request r = new Request.Builder().url(ws).header("Cache-Control","no-cache").build();
        return LIVE_CLIENT.newWebSocket(r, listener);
    }

    public static String get(String path) throws Exception {
        return getInternal(path,7000,12000);
    }

    public static String getLive(String path) throws Exception {
        return getInternal(path,2500,3500);
    }

    private static String getInternal(String path,int connectTimeoutMs,int readTimeoutMs) throws Exception {
        URL url = new URL(path.startsWith("http") ? path : BASE_URL + path);
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(connectTimeoutMs);
        c.setReadTimeout(readTimeoutMs);
        c.setUseCaches(false);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("Cache-Control", "no-cache, no-store");
        c.setRequestProperty("Pragma", "no-cache");
        c.setRequestProperty("User-Agent", "SignalHub-Android/3.3.0-cyber-ui");
        int code = c.getResponseCode();
        BufferedReader br = new BufferedReader(new InputStreamReader(
                code >= 200 && code < 400 ? c.getInputStream() : c.getErrorStream(),
                StandardCharsets.UTF_8));
        StringBuilder out = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) out.append(line).append('\n');
        br.close();
        c.disconnect();
        if (code < 200 || code >= 300) throw new RuntimeException("HTTP " + code + ": " + out);
        return out.toString();
    }
}
