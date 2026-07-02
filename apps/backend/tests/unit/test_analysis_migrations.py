from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from montage_backend.database_migrations import migrate_project_db_schema


def test_migrate_project_db_creates_analysis_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "project.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        conn.execute(
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
        migrate_project_db_schema(conn)

    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"),
        )
        names = {row[0] for row in tables.fetchall()}
        columns = conn.execute(text("PRAGMA table_info(analysis_jobs)")).fetchall()
        column_names = {row[1] for row in columns}

    assert "analysis_module_cache" in names
    assert "analysis_jobs" in names
    assert "analysis_embeddings" in names
    assert "clip_analysis_snapshots" in names
    assert "montage_plans" in names
    assert "clip_scores" in names
    assert "clip_highlights" in names
    assert "music_sync_analyses" in names
    assert "plan_transition_analyses" in names
    assert "plan_pacing_analyses" in names
    assert "plan_effects_analyses" in names
    assert "plan_draft_analyses" in names
    assert "plan_timeline_applications" in names
    assert "plan_quality_analyses" in names
    assert "plan_feedback_events" in names
    assert "media_metadata_features" in names
    assert "retry_count" in column_names
    assert "max_retries" in column_names
    engine.dispose()

