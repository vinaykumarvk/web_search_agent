"""Persistent logging utilities for metrics and query history."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default database path
# In production (Cloud Run), use /tmp for ephemeral storage
# For persistent storage, use Cloud SQL or mount a volume
DEFAULT_DB_PATH = Path(os.getenv("METRICS_DB_PATH", "/tmp/metrics.db"))

# Lazy-load sqlite3 to prevent import failures in test environments
_sqlite3 = None


def _get_sqlite3():
    """Lazy-load sqlite3 module."""
    global _sqlite3
    if _sqlite3 is None:
        try:
            import sqlite3
            _sqlite3 = sqlite3
        except ImportError as exc:
            logger.warning("sqlite3 module not available: %s", exc)
            raise ImportError("sqlite3 module not available. Persistent logging disabled.") from exc
    return _sqlite3


class PersistentLogger:
    """SQLite-based persistent logger for metrics and query history."""
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self._initialized = False
        # Don't initialize database on import - lazy initialization
    
    def _init_database(self) -> None:
        """Initialize database schema (lazy initialization)."""
        if self._initialized:
            return
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.warning("sqlite3 not available; persistent logging disabled")
            self._initialized = True  # Mark as initialized to prevent retries
            return
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL,
                extra TEXT,  -- JSON string
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Token usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                model TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Search queries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                depth TEXT,
                results_count INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Task status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_stage ON token_usage(stage)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_timestamp ON search_queries(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status_task_id ON task_status(task_id)")
        
        conn.commit()
        conn.close()
        self._initialized = True
    
    def log_metric(self, name: str, value: float, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log a metric to the database."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; skipping metric logging")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO metrics (name, value, extra) VALUES (?, ?, ?)",
                (name, value, json.dumps(extra) if extra else None)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.exception("Failed to log metric to database: %s", exc)
    
    def log_token_usage(
        self,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: Optional[str] = None,
    ) -> None:
        """Log token usage to the database."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; skipping token usage logging")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            total_tokens = prompt_tokens + completion_tokens
            cursor.execute(
                "INSERT INTO token_usage (stage, prompt_tokens, completion_tokens, total_tokens, model) VALUES (?, ?, ?, ?, ?)",
                (stage, prompt_tokens, completion_tokens, total_tokens, model)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.exception("Failed to log token usage to database: %s", exc)
    
    def log_search_query(self, query: str, depth: str, results_count: int) -> None:
        """Log a search query to the database."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; skipping search query logging")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO search_queries (query, depth, results_count) VALUES (?, ?, ?)",
                (query[:500], depth, results_count)  # Limit query length
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.exception("Failed to log search query to database: %s", exc)
    
    def log_task_status(self, task_id: str, status: str) -> None:
        """Log task status to the database."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; skipping task status logging")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO task_status (task_id, status) VALUES (?, ?)",
                (task_id, status)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.exception("Failed to log task status to database: %s", exc)
    
    def get_token_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get token usage summary for the last N days."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; returning empty summary")
            return {"summary": [], "days": days}
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    stage,
                    model,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as call_count
                FROM token_usage
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY stage, model
            """, (days,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "stage": row[0],
                    "model": row[1],
                    "total_prompt_tokens": row[2],
                    "total_completion_tokens": row[3],
                    "total_tokens": row[4],
                    "call_count": row[5],
                })
            
            conn.close()
            return {"summary": results, "days": days}
        except Exception as exc:
            logger.exception("Failed to get token usage summary: %s", exc)
            return {"summary": [], "days": days}
    
    def get_search_query_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent search query history."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; returning empty history")
            return []
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT query, depth, results_count, timestamp
                FROM search_queries
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "query": row[0],
                    "depth": row[1],
                    "results_count": row[2],
                    "timestamp": row[3],
                })
            
            conn.close()
            return results
        except Exception as exc:
            logger.exception("Failed to get search query history: %s", exc)
            return []
