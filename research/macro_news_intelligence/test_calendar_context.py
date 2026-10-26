"""No-network, deterministic contract tests for official BLS ICS integration."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import calendar_context as cal
import news_skill as news

BLS_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BLS//Economic Release Calendar//EN
BEGIN:VEVENT
UID:employment-nov-2026
SUMMARY:Employment Situation
DTSTART;TZID=America/New_York:20261106T083000
END:VEVENT
BEGIN:VEVENT
UID:oct-2026-cpi
SUMMARY:Consumer Price Index
DTSTART:20261110T133000Z
END:VEVENT
BEGIN:VEVENT
UID:cancelled
SUMMARY:Producer Price Index
STATUS:CANCELLED
DTSTART:20261110T140000Z
END:VEVENT
BEGIN:VEVENT
UID:floating
SUMMARY:Payrolls unspecified timezone
DTSTART:20261112T083000
END:VEVENT
END:VCALENDAR
"""


class CalendarContextTests(unittest.TestCase):
    def test_verified_official_schedule_marks_near_event_but_never_clear(self):
        now = datetime(2026, 11, 6, 13, 0, tzinfo=timezone.utc)
        data = cal.calendar_context(BLS_ICS, now=now, source_verified=True)
        self.assertTrue(data["sourceVerified"])
        self.assertEqual(data["activeEventCount"], 1)
        self.assertEqual(data["advisoryRisk"], "OFFICIAL_SCHEDULED_EVENT_WINDOW")
        self.assertEqual(data["newsGate"], "NEWS_UNVERIFIED")
        self.assertEqual(len(data["events"]), 2)
        event = next(x for x in data["events"] if "Employment" in x["title"])
        self.assertEqual(event["scheduledAt"], "2026-11-06T13:30:00Z")
        self.assertIn("EMPLOYMENT", event["topics"])
        self.assertEqual(event["markets"], ["FOREX", "XAUUSD"])

    def test_user_supplied_calendar_cannot_claim_first_party(self):
        data = cal.calendar_context(
            BLS_ICS, now=datetime(2026, 11, 6, 13, 0, tzinfo=timezone.utc),
            source_verified=False)
        self.assertEqual(data["advisoryRisk"], "UNVERIFIED")
        self.assertFalse(data["sourceVerified"])
        self.assertTrue(all(not e["sourceVerified"] for e in data["events"]))
        self.assertTrue(all(e["sourceUrl"] is None for e in data["events"]))

    def test_unrelated_time_and_cancelled_events(self):
        data = cal.calendar_context(
            BLS_ICS, now=datetime(2026, 11, 8, 13, 0, tzinfo=timezone.utc),
            source_verified=True)
        self.assertEqual(data["activeEventCount"], 0)
        self.assertEqual(data["advisoryRisk"], "UNVERIFIED")
        self.assertEqual(data["skippedInvalid"], 2)

    def test_naive_unknown_timezone_or_incomplete_calendar_is_rejected(self):
        self.assertIsNone(cal.parse_ics_datetime("DTSTART:20261106T083000"))
        self.assertIsNone(cal.parse_ics_datetime("DTSTART;TZID=Etc/Unknown:20261106T083000"))
        self.assertIsNone(cal.parse_ics_datetime("DTSTART;VALUE=DATE:20261106"))
        for raw in (b"not a calendar", b"BEGIN:VCALENDAR\nBEGIN:VEVENT\n"):
            with self.assertRaises(ValueError):
                cal.parse_calendar(raw, source_verified=False, collected_at=datetime.now(timezone.utc))

    def test_cli_calendar_only_stays_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "calendar.ics"
            f.write_bytes(BLS_ICS)
            out = Path(tmp) / "report.json"
            exit_code = news.main([
                "--calendar-ics", str(f), "--now", "2026-11-06T13:00:00Z",
                "--output", str(out)])
            self.assertEqual(exit_code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["articleCount"], 0)
            self.assertEqual(data["hardNewsClearance"], "NEWS_UNVERIFIED")
            self.assertFalse(data["economicCalendarVerified"])
            self.assertFalse(data["executionAuthorized"])
            self.assertEqual(data["calendar"]["activeEventCount"], 1)
            self.assertFalse(data["calendar"]["sourceVerified"])

    def test_invalid_hosts_and_ports_blocked(self):
        for url in ("https://www.bls.gov:8080/feed/bls_latest.rss",
                    "https://www.bls.gov.evil.test/feed/rss",
                    "http://www.bls.gov/feed/rss"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                news.fetch_feed(url)


if __name__ == "__main__":
    unittest.main()
