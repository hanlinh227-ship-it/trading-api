package com.hanlinh.signalhub;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class ApiClient {
    public static final String BASE_URL = "https://signalhub-forex.hanlinh227.workers.dev";

    private ApiClient() {}

    public static String get(String path) throws Exception {
        URL url = new URL(path.startsWith("http") ? path : BASE_URL + path);
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(7000);
        c.setReadTimeout(12000);
        c.setUseCaches(false);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("Cache-Control", "no-cache, no-store");
        c.setRequestProperty("Pragma", "no-cache");
        c.setRequestProperty("User-Agent", "SignalHub-Android/3.2.0");
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
