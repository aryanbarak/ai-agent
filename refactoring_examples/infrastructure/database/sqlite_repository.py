"""
Async SQLite repository implementation with connection pooling.
"""
from __future__ import annotations

import aiosqlite
from pathlib import Path
from typing import AsyncIterator
from contextlib import asynccontextmanager

from refactoring_examples.core.exceptions import (
    DatabaseConnectionError,
    DataIntegrityError,
)
from refactoring_examples.domain.protocols import FIAELog


class AsyncSQLiteRepository:
    """
    Async SQLite repository for FIAE logs.
    
    Features:
    - Async operations (non-blocking)
    - Proper error handling
    - Index support for performance
    - Safe parameterized queries
    """
    
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None
    
    async def initialize(self) -> None:
        """
        Initialize database and create tables.
        
        Should be called once during application startup.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with self._get_connection() as conn:
                # Create table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fiae_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        problem TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        topic TEXT,
                        language TEXT DEFAULT 'de'
                    );
                    """
                )
                
                # Create indexes for better query performance
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_created_at
                    ON fiae_logs(created_at DESC);
                    """
                )
                
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_topic
                    ON fiae_logs(topic);
                    """
                )
                
                await conn.commit()
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to initialize database: {e}")
    
    @asynccontextmanager
    async def _get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Context manager for database connections.
        
        Ensures connections are properly closed.
        """
        conn = None
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            yield conn
        except Exception as e:
            raise DatabaseConnectionError(f"Database connection failed: {e}")
        finally:
            if conn:
                await conn.close()
    
    async def save(
        self,
        problem: str,
        answer: str,
        topic: str | None = None,
        language: str = "de",
    ) -> FIAELog:
        """
        Save a new FIAE interaction.
        
        Args:
            problem: The user's problem/question
            answer: The AI's answer
            topic: Detected topic (e.g., "sorting", "arrays")
            language: Response language
        
        Returns:
            Created FIAELog with ID
        
        Raises:
            DataIntegrityError: If save fails
        """
        if not problem.strip() or not answer.strip():
            raise DataIntegrityError("Problem and answer cannot be empty")
        
        from datetime import datetime
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        
        try:
            async with self._get_connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO fiae_logs (created_at, problem, answer, topic, language)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (created_at, problem.strip(), answer.strip(), topic, language),
                )
                await conn.commit()
                
                log_id = cursor.lastrowid
                
                return FIAELog(
                    id=log_id,
                    created_at=created_at,
                    problem=problem.strip(),
                    answer=answer.strip(),
                )
        except Exception as e:
            raise DataIntegrityError(f"Failed to save FIAE log: {e}")
    
    async def get_recent(self, limit: int = 10) -> list[FIAELog]:
        """
        Retrieve recent FIAE logs.
        
        Args:
            limit: Maximum number of logs to return
        
        Returns:
            List of FIAELog ordered by creation time (newest first)
        """
        try:
            async with self._get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT id, created_at, problem, answer
                    FROM fiae_logs
                    ORDER BY id DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
                
                rows = await cursor.fetchall()
                
                return [
                    FIAELog(
                        id=row["id"],
                        created_at=row["created_at"],
                        problem=row["problem"],
                        answer=row["answer"],
                    )
                    for row in rows
                ]
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to fetch logs: {e}")
    
    async def count_by_topic(self) -> dict[str, int]:
        """
        Count interactions grouped by detected topic.
        
        Returns:
            Dictionary mapping topic to count
        """
        try:
            async with self._get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT topic, COUNT(*) as count
                    FROM fiae_logs
                    WHERE topic IS NOT NULL
                    GROUP BY topic
                    ORDER BY count DESC;
                    """
                )
                
                rows = await cursor.fetchall()
                
                return {row["topic"]: row["count"] for row in rows}
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to count by topic: {e}")
    
    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20,
    ) -> list[FIAELog]:
        """
        Search logs by keyword in problem or answer.
        
        Args:
            keyword: Search term
            limit: Maximum results
        
        Returns:
            Matching logs
        """
        try:
            async with self._get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT id, created_at, problem, answer
                    FROM fiae_logs
                    WHERE problem LIKE ? OR answer LIKE ?
                    ORDER BY id DESC
                    LIMIT ?;
                    """,
                    (f"%{keyword}%", f"%{keyword}%", limit),
                )
                
                rows = await cursor.fetchall()
                
                return [
                    FIAELog(
                        id=row["id"],
                        created_at=row["created_at"],
                        problem=row["problem"],
                        answer=row["answer"],
                    )
                    for row in rows
                ]
        except Exception as e:
            raise DatabaseConnectionError(f"Search failed: {e}")
