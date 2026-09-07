package com.hanlinh.signalhub;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Iterator;

public final class SignalFormatter {
    private SignalFormatter() {}

    public static JSONObject unwrap(String raw) throws Exception {
        JSONObject root = new JSONObject(raw);
        for (String key : new String[]{"snapshot", "scan", "result"}) {
            JSONObject nested = root.optJSONObject(key);
            if (nested != null) return nested;
        }
        return root;
    }

    private static JSONArray candidates(JSONObject o) {
        JSONArray a = o.optJSONArray("analyses");
        if (a == null) a = o.optJSONArray("top");
        if (a == null) a = o.optJSONArray("setups");
        return a;
    }

    public static String formatScan(String group, String raw) {
        try {
            JSONObject o = unwrap(raw);
            String state = o.optString("status", "OK");
            String scanId = o.optString("scanId", "—");
            String scannedAt = o.optString("scannedAt", "—");
            StringBuilder b = new StringBuilder();
            b.append(group.toUpperCase()).append("  •  ").append(state).append('\n');
            b.append("SCAN ").append(scanId).append("\n");
            b.append("TIME ").append(scannedAt).append("\n\n");

            if ("SOURCE_UNAVAILABLE".equalsIgnoreCase(state)) {
                b.append("Nguồn dữ liệu đang lỗi. Không phát lại tín hiệu cũ.");
                return b.toString();
            }
            if ("MARKET_CLOSED_OR_NO_DATA".equalsIgnoreCase(state)) {
                b.append("Thị trường đang đóng hoặc nguồn chưa có dữ liệu mới. Không phát tín hiệu.");
                return b.toString();
            }
            if ("BUSY".equalsIgnoreCase(state) || "RATE_BUDGET_WAIT".equalsIgnoreCase(state)) {
                b.append("Không dùng dữ liệu cũ. ").append(o.optString("reason", "Worker đang bận/quota đang hồi."));
                return b.toString();
            }

            JSONArray a = candidates(o);
            if (a == null || a.length() == 0) {
                b.append("Chưa có setup đạt chuẩn trong lượt quét mới này.");
                return b.toString();
            }
            int n = Math.min(5, a.length());
            for (int i = 0; i < n; i++) {
                JSONObject x = a.optJSONObject(i);
                if (x == null) continue;
                JSONObject p = x.optJSONObject("planned"); if (p == null) p = x;
                JSONObject q = x.optJSONObject("analysisQuote"); if (q == null) q = x.optJSONObject("quote");
                String status = x.optString("status", "WATCH");
                b.append(i + 1).append(". ").append(x.optString("symbol", "—")).append("  ")
                        .append(x.optString("side", "WAIT")).append("\n");
                b.append("   ").append(status).append("  • SCORE ").append(x.optInt("score", 0)).append("/100");
                double rr = p.optDouble("targetRR", p.optDouble("rr", 0));
                if (rr > 0) b.append("  • RR ").append(String.format("%.2f", rr));
                b.append('\n');
                appendLevel(b, "ENTRY", p, "entry"); appendLevel(b, "SL", p, "sl");
                double tp = p.optDouble("tp2", p.optDouble("tp1", p.optDouble("tp", Double.NaN)));
                if (!Double.isNaN(tp) && tp != 0) b.append("   TP    ").append(trim(tp)).append('\n');
                if (q != null) {
                    b.append("   SRC   ").append(q.optString("source", x.optString("source", "—")));
                    if (q.has("quoteAgeSec")) b.append(" • ").append(Math.round(q.optDouble("quoteAgeSec", 0))).append("s");
                    if (q.has("fresh")) b.append(q.optBoolean("fresh") ? " • LIVE" : " • STALE");
                    b.append('\n');
                }
                b.append('\n');
            }
            b.append("Chỉ MARKET_SIGNAL mới tạo thông báo. WATCH chỉ để theo dõi.");
            return b.toString();
        } catch (Exception e) {
            return "Không đọc được payload: " + e.getMessage();
        }
    }

    private static void appendLevel(StringBuilder b, String label, JSONObject p, String key) {
        if (!p.has(key)) return;
        double v = p.optDouble(key, Double.NaN);
        if (!Double.isNaN(v) && v != 0) b.append("   ").append(String.format("%-5s", label)).append(' ').append(trim(v)).append('\n');
    }

    private static String trim(double v) {
        if (Math.abs(v) >= 1000) return String.format("%.2f", v);
        if (Math.abs(v) >= 10) return String.format("%.4f", v);
        return String.format("%.5f", v);
    }

    public static Hit bestHit(String group, String raw) {
        try {
            JSONObject o = unwrap(raw);
            if (!"OK".equalsIgnoreCase(o.optString("status", "OK"))) return null;
            JSONArray a = candidates(o); if (a == null) return null;
            Hit best = null;
            for (int i = 0; i < a.length(); i++) {
                JSONObject x = a.optJSONObject(i); if (x == null) continue;
                int score = x.optInt("score", 0);
                String status = x.optString("status", "WATCH");
                if (!"MARKET_SIGNAL".equalsIgnoreCase(status) || score < 82) continue;
                JSONObject p = x.optJSONObject("planned"); if (p == null) p = x;
                Hit h = new Hit();
                h.group = group; h.scanId = o.optString("scanId", "scan");
                h.symbol = x.optString("symbol", "—"); h.side = x.optString("side", "WAIT");
                h.status = status; h.score = score;
                h.entry = p.optDouble("entry", 0); h.sl = p.optDouble("sl", 0);
                h.tp = p.optDouble("tp2", p.optDouble("tp1", p.optDouble("tp", 0)));
                if (best == null || h.score > best.score) best = h;
            }
            return best;
        } catch (Exception ignore) { return null; }
    }

    public static String formatStatus(String raw) {
        try {
            JSONObject o = new JSONObject(raw);
            StringBuilder b = new StringBuilder("SIGNALHUB LIVE CORE\n\n");
            String[] preferred = {"version","service","ok","dataSource","independentFromBybit","staleFallback","generatedAt"};
            for (String k : preferred) if (o.has(k)) b.append(k.toUpperCase()).append("  ").append(String.valueOf(o.opt(k))).append('\n');
            b.append("\nHEALTH FIELDS\n");
            Iterator<String> it = o.keys(); int count = 0;
            while (it.hasNext() && count < 20) {
                String k = it.next(); boolean known = false;
                for (String p : preferred) if (p.equals(k)) known = true;
                if (known) continue;
                Object v = o.opt(k); if (v instanceof JSONObject || v instanceof JSONArray) continue;
                b.append(k).append(" = ").append(String.valueOf(v)).append('\n'); count++;
            }
            return b.toString();
        } catch (Exception e) { return raw; }
    }

    public static final class Hit {
        public String group, scanId, symbol, side, status;
        public int score; public double entry, sl, tp;
        // Stable key prevents repeating the same live signal every scan cycle.
        public String key() { return group + ":" + symbol + ":" + side + ":" + status; }
        public String title() { return symbol + " • " + side + " • " + score + "/100"; }
        public String text() {
            StringBuilder b = new StringBuilder(status);
            if (entry != 0) b.append(" | E ").append(trim(entry));
            if (sl != 0) b.append(" | SL ").append(trim(sl));
            if (tp != 0) b.append(" | TP ").append(trim(tp));
            return b.toString();
        }
    }
}
