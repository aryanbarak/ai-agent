from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Path to the SQLite database file (same folder as this script)
DB_PATH = Path(__file__).with_name("db.sqlite")


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the SQLite database and create tables if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fiae_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                problem TEXT NOT NULL,
                answer  TEXT NOT NULL
            );
            """
        )
        conn.commit()


def log_fiae_interaction(problem: str, answer: str) -> None:
    """Store a single FIAE interaction (problem + answer) in the database."""
    if not problem.strip() or not answer.strip():
        return

    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO fiae_logs (created_at, problem, answer)
            VALUES (?, ?, ?);
            """,
            (created_at, problem.strip(), answer.strip()),
        )
        conn.commit()


def get_recent_fiae_logs(limit: int = 10) -> List[Tuple[str, str, str]]:
    """Return the most recent FIAE interactions.

    Returns a list of tuples: (created_at, problem, answer)
    """
    with _get_connection() as conn:
        cur = conn.execute(
            """
            SELECT created_at, problem, answer
            FROM fiae_logs
            ORDER BY id DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()

    result: List[Tuple[str, str, str]] = []
    for row in rows:
        result.append(
            (
                str(row["created_at"]),
                str(row["problem"]),
                str(row["answer"]),
            )
        )
    return result