from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Opportunity
from .policy import PolicyDecision
from .scoring import ScoreResult


class StackHubRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sources (
                name TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS opportunities (
                source TEXT NOT NULL,
                id TEXT NOT NULL,
                url TEXT NOT NULL,
                category TEXT NOT NULL,
                reward_amount TEXT NOT NULL,
                reward_asset TEXT NOT NULL,
                reward_network TEXT,
                deadline TEXT,
                requirements_json TEXT NOT NULL,
                acceptance_criteria_json TEXT NOT NULL,
                competition_model TEXT NOT NULL,
                agent_allowed INTEGER,
                estimated_effort_minutes INTEGER,
                policy_allowed INTEGER NOT NULL,
                policy_reasons_json TEXT NOT NULL,
                expected_net_value_usd TEXT,
                score_usd_per_minute TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, id)
            );
            CREATE TABLE IF NOT EXISTS claims (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, opportunity_id TEXT);
            CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, status TEXT);
            CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, opportunity_id TEXT, reference TEXT);
            CREATE TABLE IF NOT EXISTS verification_events (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, opportunity_id TEXT, event TEXT, observed_at TEXT);
            CREATE TABLE IF NOT EXISTS payouts (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, opportunity_id TEXT, asset TEXT, amount TEXT, txid TEXT);
            CREATE TABLE IF NOT EXISTS wallet_public_addresses (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, asset TEXT, network TEXT, address TEXT);
            CREATE TABLE IF NOT EXISTS costs (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, opportunity_id TEXT, kind TEXT, amount_usd TEXT);
            CREATE TABLE IF NOT EXISTS source_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                ok INTEGER NOT NULL,
                status_code INTEGER,
                error_code TEXT,
                observed_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def upsert_opportunity(self, opportunity: Opportunity, policy: PolicyDecision, score: ScoreResult | None) -> None:
        self.conn.execute(
            """
            INSERT INTO opportunities (
                source,id,url,category,reward_amount,reward_asset,reward_network,deadline,
                requirements_json,acceptance_criteria_json,competition_model,agent_allowed,
                estimated_effort_minutes,policy_allowed,policy_reasons_json,
                expected_net_value_usd,score_usd_per_minute,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(source,id) DO UPDATE SET
                url=excluded.url, category=excluded.category,
                reward_amount=excluded.reward_amount, reward_asset=excluded.reward_asset,
                reward_network=excluded.reward_network, deadline=excluded.deadline,
                requirements_json=excluded.requirements_json,
                acceptance_criteria_json=excluded.acceptance_criteria_json,
                competition_model=excluded.competition_model,
                agent_allowed=excluded.agent_allowed,
                estimated_effort_minutes=excluded.estimated_effort_minutes,
                policy_allowed=excluded.policy_allowed,
                policy_reasons_json=excluded.policy_reasons_json,
                expected_net_value_usd=excluded.expected_net_value_usd,
                score_usd_per_minute=excluded.score_usd_per_minute,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                opportunity.source, opportunity.id, opportunity.url, opportunity.category,
                str(opportunity.reward.amount), opportunity.reward.asset, opportunity.reward.network,
                opportunity.deadline.isoformat() if opportunity.deadline else None,
                json.dumps(opportunity.requirements), json.dumps(opportunity.acceptance_criteria),
                opportunity.competition_model,
                None if opportunity.agent_allowed is None else int(opportunity.agent_allowed),
                opportunity.estimated_effort_minutes,
                int(policy.allowed), json.dumps(policy.reasons),
                None if score is None else str(score.expected_net_value_usd),
                None if score is None else str(score.score_usd_per_minute),
            ),
        )
        self.conn.commit()

    def list_ranked_opportunities(self, limit: int = 50) -> list[dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT * FROM opportunities
            ORDER BY CAST(COALESCE(score_usd_per_minute, '-999999') AS REAL) DESC,
                     CAST(COALESCE(expected_net_value_usd, '-999999') AS REAL) DESC,
                     source ASC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def record_source_health(self, source: str, ok: bool, status_code: int | None, error_code: str | None, observed_at: datetime) -> None:
        self.conn.execute(
            "INSERT INTO source_health(source,ok,status_code,error_code,observed_at) VALUES(?,?,?,?,?)",
            (source, int(ok), status_code, error_code, observed_at.isoformat()),
        )
        self.conn.commit()

    def get_source_health(self, source: str) -> dict[str, object] | None:
        row = self.conn.execute(
            "SELECT * FROM source_health WHERE source=? ORDER BY observed_at DESC, id DESC LIMIT 1",
            (source,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["ok"] = bool(d["ok"])
        return d

    def count_source_health(self, source: str) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM source_health WHERE source=?", (source,)).fetchone()[0])

    def close(self) -> None:
        self.conn.close()
