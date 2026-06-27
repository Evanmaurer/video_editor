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
    "metadata_status": "TEXT NOT NULL DEFAULT 'pending'",
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


def _table_exists(sync_conn: Connection, table_name: str) -> bool:
    row = sync_conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def migrate_metadata_features_table(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "media_metadata_features"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE media_metadata_features (
                id TEXT PRIMARY KEY,
                media_id TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payload_json TEXT NOT NULL DEFAULT '{}',
                confidence REAL,
                reasoning TEXT,
                source_fingerprint TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, feature_key)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_media_metadata_media ON media_metadata_features (media_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_media_metadata_status ON media_metadata_features (status)"),
    )


def migrate_analysis_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "analysis_module_cache"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE analysis_module_cache (
                id TEXT PRIMARY KEY,
                media_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                analyzer_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payload_json TEXT NOT NULL DEFAULT '{}',
                confidence REAL,
                reasoning TEXT,
                source_fingerprint TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, module_id)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_cache_media ON analysis_module_cache (media_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_cache_module ON analysis_module_cache (module_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_cache_status ON analysis_module_cache (status)"),
    )

    sync_conn.execute(
        text(
            """
            CREATE TABLE analysis_jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress REAL NOT NULL DEFAULT 0.0,
                message TEXT,
                error_message TEXT,
                cache_id TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_jobs_media ON analysis_jobs (media_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_jobs_status ON analysis_jobs (status)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_jobs_module ON analysis_jobs (module_id)"),
    )


ANALYSIS_JOB_COLUMN_DDL: dict[str, str] = {
    "retry_count": "INTEGER NOT NULL DEFAULT 0",
    "max_retries": "INTEGER NOT NULL DEFAULT 2",
}


def migrate_analysis_jobs_schema(sync_conn: Connection) -> None:
    if not _table_exists(sync_conn, "analysis_jobs"):
        return
    rows = sync_conn.execute(text("PRAGMA table_info(analysis_jobs)")).fetchall()
    existing = {row[1] for row in rows}
    for column, ddl in ANALYSIS_JOB_COLUMN_DDL.items():
        if column in existing:
            continue
        sync_conn.execute(text(f"ALTER TABLE analysis_jobs ADD COLUMN {column} {ddl}"))


def migrate_project_db_schema(sync_conn: Connection) -> None:
    """Add columns and tables introduced after initial M2 releases."""
    migrate_media_items_schema(sync_conn)
    migrate_metadata_features_table(sync_conn)
    migrate_analysis_tables(sync_conn)
    migrate_analysis_jobs_schema(sync_conn)
    migrate_embedding_tables(sync_conn)
    migrate_clip_analysis_tables(sync_conn)


def migrate_clip_analysis_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "clip_analysis_snapshots"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE clip_analysis_snapshots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                overall_status TEXT NOT NULL DEFAULT 'pending',
                readiness REAL NOT NULL DEFAULT 0.0,
                source_fingerprint TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_analysis_project ON clip_analysis_snapshots (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_analysis_status ON clip_analysis_snapshots (overall_status)"),
    )


def migrate_embedding_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "analysis_embeddings"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE analysis_embeddings (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                timestamp_ms INTEGER,
                start_ms INTEGER,
                end_ms INTEGER,
                source_fingerprint TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, scope_type, scope_id, model_id)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_embeddings_project ON analysis_embeddings (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_embeddings_media ON analysis_embeddings (media_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_embeddings_scope ON analysis_embeddings (scope_type)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_analysis_embeddings_model ON analysis_embeddings (model_id)"),
    )
