#!/usr/bin/env python3
"""Auditable BLS calendar (iCalendar) research adapter. Never grants NEWS_CLEAR.

Only an actual HTTPS fetch of the *exact* official BLS calendar URL may set
sourceVerified=true. Offline ICS is untrusted replay, even with valid event times.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from news_skill import (
    MAX_INPUT_BYTES, RejectRedirects, iso, markets_for, normalized, TOPICS,
)

OFFICIAL_BLS_ICS = "https://www.bls.gov/schedule/news_release/bls.ics"
UTC = timezone.utc
MAX_EVENTS = 400
MAX_CALENDAR_BYTES = 1_000_000


def fetch_official_calendar() -> bytes:
    """Strict allowlisted request: no redirects, custom endpoints or credentials."""
    request = Request(OFFICIAL_BLS_ICS, headers={
        "User-Agent": "LinhAI-MacroNews-Research/1.0",
        "Accept": "text/calendar",
    })
    with build_opener(RejectRedirects()).open(request, timeout=7) as response:
        if response.geturl() != OFFICIAL_BLS_ICS:
            raise ValueError("unexpected final calendar source")
        content = response.read(MAX_CALENDAR_BYTES + 1)
    if len(content) > MAX_CALENDAR_BYTES:
        raise ValueError("calendar exceeds 1 MB budget")
    return content


def unfold_ics(blob: bytes) -> list[str]:
    if len(blob) > MAX_CALENDAR_BYTES:
        raise ValueError("calendar exceeds 1 MB budget")
    text = blob.decode("utf-8-sig", errors="strict")
    if "BEGIN:VCALENDAR" not in text or "END:VCALENDAR" not in text:
        raise ValueError("not a complete iCalendar document")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        elif line:
            out.append(line)
    return out


def parse_ics_datetime(line: str) -> datetime | None:
    """Reject floating/all-day/ambiguous timezone formats rather than guessing."""
    if ":" not in line:
        return None
    header, value = line.split(":", 1)
    if not header.upper().startswith("DTSTART"):
        return None
    value = value.strip()
    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if not re.fullmatch(r"\d{8}T\d{6}", value):
        return None
    tzid = re.search(r"(?:^|;)TZID=([^;:]+)", header, flags=re.I)
    if not tzid:
        return None
    zone_name = tzid.group(1).strip('"')
    # Narrow TZID allowlist: BLS uses US Eastern for releases.
    if zone_name not in {"America/New_York", "US/Eastern"}:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(
            tzinfo=ZoneInfo(zone_name)
        ).astimezone(UTC)
    except ZoneInfoNotFoundError:
        return None


def parse_calendar(blob: bytes, *, source_verified: bool, collected_at: datetime) -> dict:
    """Parse calendar event times. source_verified is assigned by trusted caller only."""
    if collected_at.tzinfo is None:
        raise ValueError("collection instant must include timezone")
    lines = unfold_ics(blob)
    entries: list[dict] = []
    skipped = 0
    event: dict | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            event = {}
            continue
        if line == "END:VEVENT":
            if event is not None:
                if event.get("status") != "CANCELLED" and event.get("when") and event.get("title"):
                    entries.append(event)
                else:
                    skipped += 1
            event = None
            if len(entries) >= MAX_EVENTS:
                break
            continue
        if event is None or ":" not in line:
            continue
        prop, value = line.split(":", 1)
        key = prop.split(";", 1)[0].upper()
        if key == "DTSTART":
            event["when"] = parse_ics_datetime(line)
        elif key == "SUMMARY":
            event["title"] = normalized(value.replace(r"\,", ",").replace(r"\;", ";").replace(r"\n", " "))
        elif key == "STATUS":
            event["status"] = value.strip().upper()
        elif key == "UID":
            event["uid"] = value.strip()[:250]
    dedup = {}
    for item in entries:
        title = item["title"][:250]
        date = iso(item["when"])
        key = hashlib.sha256((title.lower() + "/" + date).encode()).hexdigest()[:20]
        import re as _re
        topics = [name for name, pattern in TOPICS.items() if _re.search(pattern, title, flags=_re.I)]
        markets = markets_for(title, topics)
        if not markets:
            continue
        dedup[key] = {
            "id": key, "title": title, "scheduledAt": date,
            "topics": topics, "markets": markets,
            "publisher": "U.S. Bureau of Labor Statistics" if source_verified else "UNVERIFIED_OFFLINE_ICS",
            "sourceUrl": OFFICIAL_BLS_ICS if source_verified else None,
            "sourceVerified": source_verified,
            "impactVerified": False,
            "direction": "UNKNOWN",
        }
    items = sorted(dedup.values(), key=lambda x: (x["scheduledAt"], x["id"]))
    return {
        "source": "BLS_OFFICIAL_ICS" if source_verified else "OFFLINE_ICS_UNVERIFIED",
        "sourceVerified": source_verified,
        "checkedAt": iso(collected_at.astimezone(UTC)),
        "totalParsed": len(entries),
        "skippedInvalid": skipped,
        "events": items,
    }


def calendar_context(blob: bytes, *, now: datetime, source_verified: bool,
                     pre_minutes: int = 60, post_minutes: int = 30) -> dict:
    if not (0 <= pre_minutes <= 1440 and 0 <= post_minutes <= 1440):
        raise ValueError("invalid event window")
    parsed = parse_calendar(blob, source_verified=source_verified, collected_at=now)
    now_utc = now.astimezone(UTC)
    events = []
    for event in parsed["events"]:
        at = datetime.fromisoformat(event["scheduledAt"].replace("Z", "+00:00"))
        minutes = round((at - now_utc).total_seconds() / 60, 1)
        event = {**event, "minutesToEvent": minutes,
                 "inEventWindow": -post_minutes <= minutes <= pre_minutes}
        events.append(event)
    parsed["events"] = events
    parsed["activeEventCount"] = sum(x["inEventWindow"] for x in events)
    # Even a fresh calendar does not prove coverage of all relevant global events.
    parsed["newsGate"] = "NEWS_UNVERIFIED"
    parsed["advisoryRisk"] = (
        "OFFICIAL_SCHEDULED_EVENT_WINDOW" if source_verified and parsed["activeEventCount"]
        else "UNVERIFIED"
    )
    parsed["sourceCompleteness"] = "PARTIAL_BLS_ONLY"
    return parsed
