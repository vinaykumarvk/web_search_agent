"""Persistent task storage for research tasks."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.schemas import ResearchTaskStatus, TaskStatus

logger = logging.getLogger(__name__)

# Default database path
# In production (Cloud Run), use /tmp for ephemeral storage
# For persistent storage, use Cloud SQL or mount a volume
DEFAULT_DB_PATH = Path(os.getenv("TASK_DB_PATH", "/tmp/tasks.db"))

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
            raise ImportError("sqlite3 module not available. Task persistence disabled.") from exc
    return _sqlite3


class TaskStorage:
    """SQLite-based persistent task storage."""
    
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
            logger.warning("sqlite3 not available; task persistence disabled")
            self._initialized = True  # Mark as initialized to prevent retries
            return
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                envelope TEXT,  -- JSON string
                quality TEXT,   -- JSON string
                bibliography TEXT,
                source_map TEXT,  -- JSON string
                notes TEXT,      -- JSON string (array)
                findings TEXT,  -- JSON string (array)
                evidence TEXT,  -- JSON string (array)
                overall_confidence TEXT,
                error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
        
        conn.commit()
        conn.close()
        self._initialized = True
    
    def save_task(self, task: ResearchTaskStatus) -> None:
        """Save or update a task."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; skipping task persistence")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Serialize complex fields
            envelope_json = json.dumps(task.envelope.dict() if task.envelope else None) if task.envelope else None
            quality_json = json.dumps(task.quality.dict() if task.quality else None) if task.quality else None
            source_map_json = json.dumps(task.source_map) if task.source_map else None
            notes_json = json.dumps(task.notes) if task.notes else None
            findings_json = json.dumps(task.findings) if task.findings else None
            evidence_json = json.dumps(task.evidence) if task.evidence else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO tasks 
                (task_id, status, envelope, quality, bibliography, source_map, notes, findings, evidence, overall_confidence, error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                task.task_id,
                task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                envelope_json,
                quality_json,
                task.bibliography,
                source_map_json,
                notes_json,
                findings_json,
                evidence_json,
                task.overall_confidence,
                task.error,
            ))
            
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.exception("Failed to save task to database: %s", exc)
            raise
    
    def get_task(self, task_id: str) -> Optional[ResearchTaskStatus]:
        """Get a task by ID."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; task retrieval disabled")
            return None
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Deserialize task
            from app.schemas import ResponseEnvelope, QualityReport
            
            envelope = None
            if row[2]:  # envelope
                envelope_data = json.loads(row[2])
                if envelope_data:
                    envelope = ResponseEnvelope(**envelope_data)
            
            quality = None
            if row[3]:  # quality
                quality_data = json.loads(row[3])
                if quality_data:
                    quality = QualityReport(**quality_data)
            
            return ResearchTaskStatus(
                task_id=row[0],
                status=TaskStatus(row[1]),
                envelope=envelope,
                quality=quality,
                bibliography=row[4],
                source_map=json.loads(row[5]) if row[5] else None,
                notes=json.loads(row[6]) if row[6] else None,
                findings=json.loads(row[7]) if row[7] else None,
                evidence=json.loads(row[8]) if row[8] else None,
                overall_confidence=row[9],
                error=row[10],
            )
        except Exception as exc:
            logger.exception("Failed to get task from database: %s", exc)
            return None
    
    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 100) -> list[ResearchTaskStatus]:
        """List tasks, optionally filtered by status."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; task listing disabled")
            return []
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if status:
                cursor.execute("SELECT task_id FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status.value, limit))
            else:
                cursor.execute("SELECT task_id FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            
            task_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            tasks = []
            for task_id in task_ids:
                task = self.get_task(task_id)
                if task:
                    tasks.append(task)
            
            return tasks
        except Exception as exc:
            logger.exception("Failed to list tasks from database: %s", exc)
            return []
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if not self._initialized:
            self._init_database()
        
        try:
            sqlite3 = _get_sqlite3()
        except ImportError:
            logger.debug("sqlite3 not available; task deletion disabled")
            return False
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted
        except Exception as exc:
            logger.exception("Failed to delete task from database: %s", exc)
            return False
