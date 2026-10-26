#!/usr/bin/env python3
"""Macro news research input: RSS/Atom or offline JSON -> provenance-first JSON.

Advisory only. Headline classification is NOT a verified economic calendar,
directional trading signal, broker quote, or executable hard-news gate.
Python >= 3.10; standard library only; no keys or hosted inference.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET

ALLOWED_FEED_HOSTS = {
    "news.google.com", "www.federalreserve.gov", "federalreserve.gov",
    "www.ecb.europa.eu", "ecb.europa.eu", "www.eia.gov", "eia.gov",
}
MAX_INPUT_BYTES = 2_000_000
MAX_ITEMS_PER_SOURCE = 100
TOPICS = {
    "RATE_POLICY": r"\b(fomc|federal reserve|fed|interest rate|ecb|boe|boj|rate decision|central bank)\b",
    "INFLATION": r"\b(cpi|consumer price|pce|inflation|producer price|ppi)\b",
    "EMPLOYMENT": r"\b(nfp|nonfarm|payroll|unemployment|jobless claims|labor market)\b",
    "ENERGY_SUPPLY": r"\b(opec\+?|crude oil|oil inventory|oil inventories|petroleum|brent|wti|oil production|oil supply|refinery)\b",
    "GEO_RISK": r"\b(sanction|tariff|war|conflict|strait of hormuz|shipping disruption|ceasefire)\b",
}
GOLD = r"\b(gold|xauusd|xau\/usd|bullion)\b"
OIL = r"\b(oil|crude|wti|brent|opec|petroleum|eia|refinery)\b"
FX = r"\b(forex|fx|currency|currencies|usd|eur|gbp|jpy|chf|cad|aud|nzd|dollar|euro|yen|pound)\b"
HIGH = {"RATE_POLICY", "INFLATION", "EMPLOYMENT", "GEO_RISK"}
UTC = timezone.utc


def normalized(text: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))).strip()[:1200]


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value.strip())
        except (TypeError, ValueError, IndexError):
            return None
    if parsed.tzinfo is None:
        return None  # Never assume timezone for news.
    return parsed.astimezone(UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def childtext(node: ET.Element, *names: str) -> str:
    for item in node:
        if localname(item.tag).lower() in names and item.text:
            return item.text.strip()
    return ""


def parse_feed(content: bytes, source: str) -> list[dict]:
    root = ET.fromstring(content)
    nodes = [el for el in root.iter() if localname(el.tag).lower() in {"item", "entry"}]
    rows = []
    for node in nodes[:MAX_ITEMS_PER_SOURCE]:
        link = childtext(node, "link")
        if not link:
            for child in node:
                if localname(child.tag).lower() == "link":
                    link = child.attrib.get("href", "")
                    if link:
                        break
        rows.append({
            "title": childtext(node, "title"),
            "summary": childtext(node, "description", "summary", "content"),
            "url": link,
            "published": childtext(node, "pubdate", "published", "updated", "date"),
            "source": source,
        })
    return rows


class RejectRedirects(HTTPRedirectHandler):
    """Refuse redirects before a request could leave the approved host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("RSS redirects are disabled to enforce source allowlist")


def fetch_feed(url: str) -> list[dict]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_FEED_HOSTS or parsed.username or parsed.password:
        raise ValueError("feed host not in first-party/Google RSS allowlist")
    request = Request(url, headers={"User-Agent": "LinhAI-MacroNews-Research/1.0"})
    # A final-URL check is too late: a redirect could already reach an unsafe host.
    # Disable redirects entirely; feed sources must be explicit and preapproved.
    class NoRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(NoRedirects())
    with opener.open(request, timeout=7) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in ALLOWED_FEED_HOSTS:
            raise ValueError("feed redirected outside allowlist")
        data = response.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("RSS exceeds size budget")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML document type declarations and entities not permitted")
    return parse_feed(data, parsed.hostname or "unknown")


def markets_for(text: str, topics: list[str]) -> list[str]:
    markets = set()
    if re.search(GOLD, text, flags=re.I):
        markets.add("XAUUSD")
    if re.search(OIL, text, flags=re.I):
        markets.update(("WTI", "BRENT"))
    if re.search(FX, text, flags=re.I):
        markets.add("FOREX")
    if set(topics) & {"RATE_POLICY", "INFLATION", "EMPLOYMENT"}:
        markets.update(("FOREX", "XAUUSD"))
    if "GEO_RISK" in topics:
        markets.update(("FOREX", "XAUUSD", "WTI", "BRENT"))
    return sorted(markets)


def classify(rows: list[dict], now: datetime, max_age_hours: int = 48) -> dict:
    if now.tzinfo is None:
        raise ValueError("now requires timezone")
    now = now.astimezone(UTC)
    dedup: dict[str, dict] = {}
    for item in rows[:1000]:
        title = normalized(item.get("title"))
        if not title:
            continue
        summary = normalized(item.get("summary"))
        headline = title.lower()
        topics = [name for name, pattern in TOPICS.items() if re.search(pattern, headline + " " + summary, flags=re.I)]
        markets = markets_for(headline + " " + summary, topics)
        if not topics and not markets:
            continue
        published = parse_time(item.get("published"))
        age = (now - published).total_seconds() / 3600 if published else None
        freshness = "UNKNOWN" if age is None or age < -0.25 else ("FRESH" if age <= max_age_hours else "STALE")
        key = hashlib.sha256(re.sub(r"\W+", "", title.casefold()).encode()).hexdigest()[:20]
        source = normalized(item.get("source"))[:100] or "unspecified"
        url = str(item.get("url") or "")
        if url and urlparse(url).scheme not in {"https", "http"}:
            url = ""
        impact = "HIGH_POTENTIAL" if set(topics) & HIGH else ("MEDIUM_POTENTIAL" if topics else "UNASSESSED")
        if key in dedup:
            original = dedup[key]
            if source not in original["sources"]:
                original["sources"].append(source)
            continue
        dedup[key] = {
            "id": key, "title": title, "summary": summary[:350], "url": url[:1000],
            "sources": [source], "publishedAt": iso(published) if published else None,
            "freshness": freshness, "topics": topics, "markets": markets,
            "potentialImpact": impact, "direction": "UNKNOWN",
            "verifiedScheduledEvent": False,
        }
    articles = sorted(dedup.values(), key=lambda x: (x["freshness"] != "FRESH", x["publishedAt"] or "", x["id"]), reverse=False)
    articles.sort(key=lambda x: ({"FRESH": 0, "UNKNOWN": 1, "STALE": 2}[x["freshness"]], -(parse_time(x["publishedAt"]).timestamp() if x["publishedAt"] else 0)))
    # Deterministic digest only: counts/links, not synthesized price direction.
    topic_counts = {topic: sum(topic in a["topics"] for a in articles) for topic in TOPICS}
    market_counts = {market: sum(market in a["markets"] for a in articles)
                     for market in ("FOREX", "XAUUSD", "WTI", "BRENT")}
    freshness_counts = {state: sum(a["freshness"] == state for a in articles)
                        for state in ("FRESH", "STALE", "UNKNOWN")}
    digest = {
        "byTopic": topic_counts, "byMarket": market_counts,
        "byFreshness": freshness_counts,
        "latestHeadlines": [
            {"title": a["title"], "url": a["url"],
             "publishedAt": a["publishedAt"], "markets": a["markets"]}
            for a in articles[:10]
        ],
        "riskInterpretation": "UNVERIFIED_MACRO_CONTEXT",
    }
    return {
        "schemaVersion": "1.0", "asOf": iso(now), "mode": "READ_ONLY_RESEARCH",
        "marketScope": ["FOREX", "XAUUSD", "WTI", "BRENT"],
        "hardNewsClearance": "NEWS_UNVERIFIED",
        "economicCalendarVerified": False, "executionAuthorized": False,
        "disclaimer": "RSS headlines are not verified scheduled events or direction/entry evidence.",
        "articleCount": len(articles), "summary": digest, "articles": articles,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-json", type=Path, help="offline JSON array of title/summary/url/published/source")
    ap.add_argument("--feed-url", action="append", default=[], help="approved HTTPS RSS/Atom feed; repeatable")
    ap.add_argument("--now", help="ISO 8601 timezone-aware timestamp for deterministic replay")
    ap.add_argument("--max-age-hours", type=int, default=48)
    ap.add_argument("--output", type=Path, help="optional output JSON path")
    args = ap.parse_args(argv)
    if not args.feed_url and args.input_json is None:
        ap.error("supply --input-json or --feed-url")
    if not (1 <= args.max_age_hours <= 168):
        ap.error("--max-age-hours must be 1..168")
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    if now is None:
        ap.error("--now needs an explicit timezone")
    rows, errors = [], []
    if args.input_json:
        data = args.input_json.read_bytes()
        if len(data) > MAX_INPUT_BYTES:
            ap.error("offline input too large")
        decoded = json.loads(data)
        if not isinstance(decoded, list) or not all(isinstance(x, dict) for x in decoded):
            ap.error("--input-json must be an array of objects")
        rows.extend(decoded[:1000])
    for feed in args.feed_url[:12]:
        try:
            rows.extend(fetch_feed(feed))
        except (ValueError, OSError, ET.ParseError) as ex:
            errors.append({"feed": urlparse(feed).hostname, "errorType": type(ex).__name__})
    result = classify(rows, now, args.max_age_hours)
    result["collection"] = {"feedCount": len(args.feed_url[:12]), "feedErrors": errors,
                            "inputRows": len(rows), "partial": bool(errors)}
    result["sourceCompleteness"] = "UNVERIFIED"  # Headline feeds never prove there are no events.
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
