package com.hanlinh.signalhub;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

public final class ApiClient {
    public static final String BASE_URL = "https://signalhub-forex.hanlinh227.workers.dev";

    private static final ConnectionPool POOL = new ConnectionPool(8, 5, TimeUnit.MINUTES);

    private static final OkHttpClient API_CLIENT = new OkHttpClient.Builder()
            .connectionPool(POOL)
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .callTimeout(10, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();

    private static final OkHttpClient LIVE_CLIENT = new OkHttpClient.Builder()
            .connectionPool(POOL)
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(3, TimeUnit.SECONDS)
            .callTimeout(4, TimeUnit.SECONDS)
            .pingInterval(15, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();

    private ApiClient() {}

    public static WebSocket connectForexStream(WebSocketListener listener) {
        String ws = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/v3/forex/stream";
        Request r = new Request.Builder()
                .url(ws)
                .header("Cache-Control", "no-cache")
                .header("User-Agent", "SignalHub-Android/3.14.0-crypto-stability")
                .build();
        return LIVE_CLIENT.newWebSocket(r, listener);
    }

    public static String get(String path) throws Exception {
        return getInternal(path, API_CLIENT, 2);
    }

    public static String getLive(String path) throws Exception {
        return getInternal(path, LIVE_CLIENT, 2);
    }

    private static String getInternal(String path, OkHttpClient client, int attempts) throws Exception {
        String url = path.startsWith("http") ? path : BASE_URL + path;
        IOException lastIo = null;

        for (int attempt = 1; attempt <= Math.max(1, attempts); attempt++) {
            Request request = new Request.Builder()
                    .url(url)
                    .get()
                    .header("Accept", "application/json")
                    .header("Cache-Control", "no-cache, no-store")
                    .header("Pragma", "no-cache")
                    .header("User-Agent", "SignalHub-Android/3.14.0-crypto-stability")
                    .build();

            try (Response response = client.newCall(request).execute()) {
                ResponseBody body = response.body();
                String text = body == null ? "" : body.string();
                if (!response.isSuccessful()) {
                    throw new RuntimeException("HTTP " + response.code() + ": " + text);
                }
                return text;
            } catch (IOException e) {
                lastIo = e;
                if (attempt < attempts) {
                    try { Thread.sleep(120L * attempt); }
                    catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        throw interrupted;
                    }
                }
            }
        }

        throw lastIo != null ? lastIo : new IOException("SignalHub request failed");
    }
}
