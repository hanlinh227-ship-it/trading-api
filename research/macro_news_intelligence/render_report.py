#!/usr/bin/env python3
"""Deterministic Markdown brief from macro-news JSON; no model or trade advice."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

MARKETS = ("FOREX", "XAUUSD", "WTI", "BRENT")
MARKET_NAMES = {"FOREX": "Forex (8 đồng tiền chính)", "XAUUSD": "Vàng / XAUUSD",
                "WTI": "Dầu WTI", "BRENT": "Dầu Brent"}
LIMIT = 2_000_000


def safe_text(value: object, limit: int = 220) -> str:
    result = " ".join(str(value or "").split())[:limit]
    return (result.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            .replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
            .replace("*", "\\*").replace(chr(96), "'"))


def safe_link(value: object) -> str | None:
    url = str(value or "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or len(url) > 800:
        return None
    if any(c in url for c in "()<>\r\n\t "):
        return None
    return url


def safe_list(value: object, limit: int) -> list:
    return value[:limit] if isinstance(value, list) else []


def create_brief(report: dict, *, market: str | None = None, limit_per_market: int = 5) -> str:
    if report.get("mode") != "READ_ONLY_RESEARCH" or report.get("executionAuthorized") is not False:
        raise ValueError("source is not explicit read-only research")
    if report.get("hardNewsClearance") != "NEWS_UNVERIFIED":
        raise ValueError("unsafe news-clearance claim")
    if market is not None and market not in MARKETS:
        raise ValueError("unsupported market")
    if not 1 <= limit_per_market <= 20:
        raise ValueError("invalid per-market limit")
    asof = safe_text(report.get("asOf") or "UNKNOWN")
    markets = (market,) if market else MARKETS
    lines = [
        "# Macro Brief — Forex / Vàng / Dầu", "",
        f"- Thời điểm tổng hợp (UTC): **{asof}**",
        "- Trạng thái: **NGHIÊN CỨU CHỈ ĐỌC — NEWS_UNVERIFIED**",
        "- Không phải tín hiệu BUY/SELL hoặc bằng chứng được phép đặt lệnh.", "",
    ]
    articles = report.get("articles", [])
    if not isinstance(articles, list):
        raise ValueError("articles must be an array")
    for name in markets:
        relevant = [x for x in articles if isinstance(x, dict) and name in safe_list(x.get("markets"), 20)]
        lines.extend([f"## {MARKET_NAMES[name]} ({len(relevant)} tin phù hợp)", ""])
        for item in relevant[:limit_per_market]:
            title = safe_text(item.get("title"))
            link = safe_link(item.get("url"))
            headline = f"[{title}]({link})" if link else title
            topics = ", ".join(safe_text(x, 40) for x in safe_list(item.get("topics"), 5) if isinstance(x, str))
            currencies = ", ".join(safe_text(x, 10) for x in safe_list(item.get("currencies"), 8) if isinstance(x, str))
            when = safe_text(item.get("publishedAt") or "không rõ giờ", 55)
            freshness = safe_text(item.get("freshness") or "UNKNOWN", 20)
            sources = ", ".join(safe_text(x, 40) for x in safe_list(item.get("sources"), 3) if isinstance(x, str))
            lines.append(f"- {headline} — {when}, **{freshness}**, chủ đề: {topics or 'UNKNOWN'}; tiền tệ: {currencies or 'chưa xác định'}; nguồn: {sources or 'UNKNOWN'}")
        if not relevant:
            lines.append("- Chưa có tin được phân loại; không đồng nghĩa thị trường không có sự kiện.")
        lines.append("")
    calendar = report.get("calendar")
    if isinstance(calendar, dict):
        lines.extend(["## Lịch kinh tế BLS (Mỹ) — tham khảo", ""])
        verified = calendar.get("sourceVerified") is True
        lines.append(f"- Nguồn lịch: **{'đã lấy trực tiếp từ BLS' if verified else 'CHƯA XÁC MINH / OFFLINE'}**; chỉ bao phủ một phần sự kiện USD.")
        matches = [x for x in safe_list(calendar.get("events"), 400) if isinstance(x, dict) and (not market or market in safe_list(x.get("markets"), 20))]
        for event in matches[:20]:
            label = safe_text(event.get("title"))
            when = safe_text(event.get("scheduledAt"), 40)
            near = " — GẦN GIỜ CÔNG BỐ" if event.get("inEventWindow") else ""
            lines.append(f"- {when}: {label}{near}")
        if not matches:
            lines.append("- Không tìm thấy sự kiện phù hợp trong lịch có sẵn; không chứng minh an toàn giao dịch.")
        lines.append("")
    collection = report.get("collection")
    errors = collection.get("feedErrors", []) if isinstance(collection, dict) else []
    if errors:
        lines.extend(["## Nguồn gặp lỗi", ""])
        for err in safe_list(errors, 12):
            if isinstance(err, dict):
                lines.append(f"- {safe_text(err.get('feed'))}: {safe_text(err.get('errorType'))}")
        lines.append("")
    lines.extend([
        "## Giới hạn diễn giải", "",
        "HIGH_POTENTIAL chỉ là độ liên quan theo từ khóa, không xác nhận mức tác động, hướng giá, giờ công bố hoặc sự xác nhận độc lập. Đánh giá lệnh phải kiểm chứng lịch kinh tế, giá/chi phí/venue hiện tại và chính sách rủi ro riêng.", ""
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--market", choices=MARKETS)
    parser.add_argument("--limit-per-market", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    with args.input.open("rb") as source:
        blob = source.read(LIMIT + 1)
    if len(blob) > LIMIT:
        parser.error("input too large")
    report = json.loads(blob)
    if not isinstance(report, dict):
        parser.error("input must be JSON object")
    brief = create_brief(report, market=args.market, limit_per_market=args.limit_per_market)
    if args.output:
        args.output.write_text(brief + "\n", encoding="utf-8")
    else:
        print(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
