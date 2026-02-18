"""SQLite database for bot project storage."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    niche TEXT,
    pricelist_path TEXT,
    pricelist_text TEXT,
    competitors_path TEXT,
    competitors_text TEXT,
    addresses TEXT,
    managers TEXT,
    phone TEXT,
    company_info TEXT,
    title_info TEXT,
    ca_analysis TEXT,
    template_config TEXT,
    categories_config TEXT,
    output_path TEXT,
    state TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class ProjectDB:
    """Async SQLite storage for user projects."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Initialize database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(CREATE_TABLE)
        # Migrate: add title_info column if missing (for existing DBs)
        try:
            await self._db.execute("ALTER TABLE projects ADD COLUMN title_info TEXT")
        except Exception:
            pass  # Column already exists
        await self._db.commit()
        logger.info("Database initialized: %s", self.db_path)

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()

    async def create_project(self, user_id: int) -> int:
        """Create a new project for a user. Returns project id."""
        assert self._db is not None
        cursor = await self._db.execute(
            "INSERT INTO projects (user_id) VALUES (?)",
            (user_id,),
        )
        await self._db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_active_project(self, user_id: int) -> dict[str, Any] | None:
        """Get the latest project for a user."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def update_project(self, project_id: int, **fields: Any) -> None:
        """Update project fields."""
        assert self._db is not None
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [project_id]
        await self._db.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            values,
        )
        await self._db.commit()

    async def set_json_field(self, project_id: int, field: str, data: Any) -> None:
        """Store a JSON-serializable object in a text field."""
        await self.update_project(project_id, **{field: json.dumps(data, ensure_ascii=False)})

    async def get_json_field(self, project_id: int, field: str) -> Any | None:
        """Retrieve a JSON field from a project."""
        assert self._db is not None
        cursor = await self._db.execute(
            f"SELECT {field} FROM projects WHERE id = ?",
            (project_id,),
        )
        row = await cursor.fetchone()
        if row is None or row[0] is None:
            return None
        return json.loads(row[0])
