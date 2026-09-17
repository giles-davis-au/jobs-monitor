import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from jobsmonitor.models import Job, LocationConfidence

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    company TEXT NOT NULL,
    job_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT NOT NULL,
    location_confidence TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (company, job_id)
);

CREATE TABLE IF NOT EXISTS run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    run_at TEXT NOT NULL,
    status TEXT NOT NULL,       -- 'ok' | 'degraded' | 'error'
    jobs_fetched INTEGER,       -- total jobs returned by the connector, NULL on hard error
    new_matches INTEGER,        -- new keyword+location matches this run
    error TEXT                  -- error message, if any
);

CREATE INDEX IF NOT EXISTS idx_run_history_company ON run_history (company, id DESC);
"""


class Store:
    """SQLite-backed dedup + run-history store. One file, no server."""

    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def is_new(self, company: str, job_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM seen_jobs WHERE company = ? AND job_id = ?",
            (company, job_id),
        )
        return cur.fetchone() is None

    def mark_seen(self, job: Job, location_confidence: LocationConfidence) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO seen_jobs
                (company, job_id, title, url, location, location_confidence, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.company,
                job.job_id,
                job.title,
                job.url,
                job.location,
                location_confidence.value,
                datetime.now(UTC).isoformat(),
            ),
        )
        self.conn.commit()

    def record_run(
        self,
        company: str,
        status: str,
        jobs_fetched: int | None,
        new_matches: int,
        error: str | None = None,
    ) -> None:
        assert status in ("ok", "degraded", "error")
        self.conn.execute(
            """
            INSERT INTO run_history (company, run_at, status, jobs_fetched, new_matches, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (company, datetime.now(UTC).isoformat(), status, jobs_fetched, new_matches, error),
        )
        self.conn.commit()

    def last_ok_jobs_fetched(self, company: str) -> int | None:
        """Jobs-fetched count from this company's most recent successful run.

        Used to detect a connector going from "returns N jobs" to "returns 0"
        without raising — the classic silent-scraper-breakage case.
        """
        cur = self.conn.execute(
            """
            SELECT jobs_fetched FROM run_history
            WHERE company = ? AND status = 'ok'
            ORDER BY id DESC LIMIT 1
            """,
            (company,),
        )
        row = cur.fetchone()
        return row["jobs_fetched"] if row else None

    def recent_runs(self, company: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
        if company:
            cur = self.conn.execute(
                "SELECT * FROM run_history WHERE company = ? ORDER BY id DESC LIMIT ?",
                (company, limit),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM run_history ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Self":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
