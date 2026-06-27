from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from montage_backend.database_migrations import migrate_media_items_schema


@pytest.mark.asyncio
async def test_migrate_media_items_adds_missing_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE media_items (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    role TEXT NOT NULL,
                    import_status TEXT NOT NULL DEFAULT 'pending',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
            ),
        )
        await conn.run_sync(migrate_media_items_schema)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("PRAGMA table_info(media_items)"))).fetchall()

    columns = {row[1] for row in rows}
    assert "source_path" in columns
    assert "sha256_hash" in columns
    assert "proxy_status" in columns

    await engine.dispose()
