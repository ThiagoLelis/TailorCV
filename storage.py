"""Persistência das vagas em SQLite."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models import JobPosting

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    company       TEXT,
    url           TEXT NOT NULL UNIQUE,
    ats_platform  TEXT NOT NULL,
    date_posted   TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    cv_path       TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""

STATUS_PENDING = "pending"
STATUS_CV_GENERATED = "cv_generated"
STATUS_FAILED = "failed"


def job_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, path: str | Path = "jobs.db"):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def get_status(self, url: str) -> str | None:
        row = self.conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id(url),)).fetchone()
        return row["status"] if row else None

    def save_pending(self, job: JobPosting) -> str:
        jid, now = job_id(job.url), _now()
        self.conn.execute(
            """INSERT INTO jobs (id, title, company, url, ats_platform, date_posted, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET title=excluded.title, company=excluded.company,
                   date_posted=excluded.date_posted, status=excluded.status, error=NULL,
                   updated_at=excluded.updated_at""",
            (jid, job.title, job.company, job.url, job.ats_platform,
             job.date_posted.isoformat() if job.date_posted else None, STATUS_PENDING, now, now),
        )
        self.conn.commit()
        return jid

    def update_status(self, jid: str, status: str, cv_path: str | None = None, error: str | None = None):
        self.conn.execute(
            "UPDATE jobs SET status = ?, cv_path = COALESCE(?, cv_path), error = ?, updated_at = ? WHERE id = ?",
            (status, cv_path, error, _now(), jid),
        )
        self.conn.commit()

    def all(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
