from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from montage_backend.analysis.embedding_analysis import (
    EmbeddingMatch,
    EmbeddingScopeType,
    cosine_similarity,
)
from montage_backend.database_migrations import migrate_project_db_schema


def test_embedding_table_schema(tmp_path: Path) -> None:
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
        columns = conn.execute(text("PRAGMA table_info(analysis_embeddings)")).fetchall()
        column_names = {row[1] for row in columns}

    assert "embedding_json" in column_names
    assert "scope_type" in column_names
    assert "model_id" in column_names
    engine.dispose()


def test_duplicate_filtering_logic():
    vector_a = [1.0, 0.0, 0.0]
    candidates = [
        ("m2", [0.99, 0.1, 0.0]),
        ("m3", [0.0, 1.0, 0.0]),
    ]
    matches = [
        EmbeddingMatch(
            embedding_id=f"emb-{media_id}",
            media_id=media_id,
            scope_type=EmbeddingScopeType.CLIP,
            scope_id=media_id,
            similarity=cosine_similarity(vector_a, vector),
        )
        for media_id, vector in candidates
    ]
    duplicates = [match for match in matches if match.similarity >= 0.9]
    assert len(duplicates) == 1
    assert duplicates[0].media_id == "m2"
