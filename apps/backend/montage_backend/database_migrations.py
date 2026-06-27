from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


MEDIA_ITEM_COLUMN_DDL: dict[str, str] = {
    "source_path": "TEXT",
    "storage_mode": "TEXT NOT NULL DEFAULT 'copy'",
    "sha256_hash": "TEXT",
    "proxy_status": "TEXT NOT NULL DEFAULT 'pending'",
    "waveform_status": "TEXT NOT NULL DEFAULT 'pending'",
    "scene_status": "TEXT NOT NULL DEFAULT 'pending'",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "is_favorite": "INTEGER NOT NULL DEFAULT 0",
}


def migrate_media_items_schema(sync_conn: Connection) -> None:
    """Add columns introduced after initial M2 releases (SQLite create_all is not additive)."""
    rows = sync_conn.execute(text("PRAGMA table_info(media_items)")).fetchall()
    if not rows:
        return

    existing = {row[1] for row in rows}
    for column, ddl in MEDIA_ITEM_COLUMN_DDL.items():
        if column in existing:
            continue
        sync_conn.execute(text(f"ALTER TABLE media_items ADD COLUMN {column} {ddl}"))
