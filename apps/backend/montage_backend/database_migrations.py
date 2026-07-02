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
    migrate_montage_plan_tables(sync_conn)
    migrate_clip_score_tables(sync_conn)
    migrate_clip_highlight_tables(sync_conn)
    migrate_music_sync_tables(sync_conn)
    migrate_plan_transition_tables(sync_conn)
    migrate_plan_pacing_tables(sync_conn)
    migrate_plan_effects_tables(sync_conn)
    migrate_plan_draft_tables(sync_conn)
    migrate_plan_timeline_tables(sync_conn)
    migrate_plan_feedback_tables(sync_conn)


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


def migrate_clip_score_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "clip_scores"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE clip_scores (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                montage_score REAL NOT NULL,
                confidence REAL,
                reasoning TEXT NOT NULL,
                breakdown_json TEXT NOT NULL DEFAULT '{}',
                scorer_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                source_fingerprint TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, scorer_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_scores_project ON clip_scores (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_scores_score ON clip_scores (montage_score)"),
    )


def migrate_clip_highlight_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "clip_highlights"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE clip_highlights (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                highlight_count INTEGER NOT NULL DEFAULT 0,
                detector_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                source_fingerprint TEXT,
                highlights_json TEXT NOT NULL DEFAULT '[]',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, detector_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_highlights_project ON clip_highlights (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_clip_highlights_count ON clip_highlights (highlight_count)"),
    )


def migrate_music_sync_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "music_sync_analyses"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE music_sync_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT NOT NULL,
                tempo_bpm REAL,
                confidence REAL,
                reasoning TEXT NOT NULL,
                sync_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                source_fingerprint TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE (media_id, sync_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_music_sync_project ON music_sync_analyses (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_music_sync_tempo ON music_sync_analyses (tempo_bpm)"),
    )


def migrate_plan_transition_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "plan_transition_analyses"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE plan_transition_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                junction_count INTEGER NOT NULL DEFAULT 0,
                random_seed INTEGER NOT NULL DEFAULT 0,
                confidence REAL,
                reasoning TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES montage_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, engine_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_transitions_project ON plan_transition_analyses (project_id)"),
    )


def migrate_plan_pacing_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "plan_pacing_analyses"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE plan_pacing_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                pacing_profile TEXT NOT NULL,
                target_duration_ms INTEGER,
                total_duration_ms INTEGER NOT NULL DEFAULT 0,
                clip_count INTEGER NOT NULL DEFAULT 0,
                random_seed INTEGER NOT NULL DEFAULT 0,
                confidence REAL,
                reasoning TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES montage_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, engine_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_pacing_project ON plan_pacing_analyses (project_id)"),
    )


def migrate_plan_effects_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "plan_effects_analyses"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE plan_effects_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                clip_count INTEGER NOT NULL DEFAULT 0,
                random_seed INTEGER NOT NULL DEFAULT 0,
                confidence REAL,
                reasoning TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES montage_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, engine_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_effects_project ON plan_effects_analyses (project_id)"),
    )


def migrate_plan_draft_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "plan_draft_analyses"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE plan_draft_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                clip_count INTEGER NOT NULL DEFAULT 0,
                random_seed INTEGER NOT NULL DEFAULT 0,
                confidence REAL,
                reasoning TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES montage_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, engine_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_draft_project ON plan_draft_analyses (project_id)"),
    )


def migrate_plan_timeline_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "plan_timeline_applications"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE plan_timeline_applications (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                timeline_id TEXT NOT NULL,
                plan_version INTEGER NOT NULL DEFAULT 1,
                clip_count INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                random_seed INTEGER NOT NULL DEFAULT 0,
                confidence REAL,
                reasoning TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES montage_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, engine_version)
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_timeline_project ON plan_timeline_applications (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_plan_timeline_timeline ON plan_timeline_applications (timeline_id)"),
    )


def migrate_plan_feedback_tables(sync_conn: Connection) -> None:
    if not _table_exists(sync_conn, "plan_quality_analyses"):
        sync_conn.execute(
            text(
                """
                CREATE TABLE plan_quality_analyses (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL REFERENCES montage_plans(id) ON DELETE CASCADE,
                    plan_version INTEGER NOT NULL DEFAULT 1,
                    overall_score REAL,
                    confidence REAL,
                    reasoning TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(plan_id, engine_version)
                )
                """,
            ),
        )
        sync_conn.execute(
            text("CREATE INDEX idx_plan_quality_project ON plan_quality_analyses (project_id)"),
        )

    if not _table_exists(sync_conn, "plan_feedback_events"):
        sync_conn.execute(
            text(
                """
                CREATE TABLE plan_feedback_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL REFERENCES montage_plans(id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    applied_changes_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """,
            ),
        )
        sync_conn.execute(
            text("CREATE INDEX idx_plan_feedback_events_plan ON plan_feedback_events (plan_id)"),
        )
        sync_conn.execute(
            text("CREATE INDEX idx_plan_feedback_events_project ON plan_feedback_events (project_id)"),
        )


def migrate_montage_plan_tables(sync_conn: Connection) -> None:
    if _table_exists(sync_conn, "montage_plans"):
        return

    sync_conn.execute(
        text(
            """
            CREATE TABLE montage_plans (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                version INTEGER NOT NULL DEFAULT 1,
                random_seed INTEGER NOT NULL DEFAULT 0,
                generator_id TEXT NOT NULL DEFAULT 'montage-plan-framework',
                generator_version TEXT NOT NULL DEFAULT '1.0.0',
                overall_confidence REAL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL DEFAULT '{}',
                applied_timeline_id TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_montage_plans_project ON montage_plans (project_id)"),
    )
    sync_conn.execute(
        text("CREATE INDEX idx_montage_plans_status ON montage_plans (status)"),
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
