import sqlite3

from memolite.app.resources import ResourceManager, _resolve_embedder_provider_name
from memolite.common.config import Settings


def test_resource_manager_uses_hash_embedder_provider_by_default(tmp_path):
    settings = Settings(
        sqlite_path=tmp_path / "memolite.sqlite3",
        kuzu_path=tmp_path / "graph.kuzu",
        embedder_provider="hash",
    )

    resources = ResourceManager.create(settings)

    derivative_embedder = resources.derivative_pipeline._embedder  # type: ignore[attr-defined]
    episodic_embedder = resources.episodic_search._embedder  # type: ignore[attr-defined]
    semantic_embedder = resources.semantic_service._embedder  # type: ignore[attr-defined]

    assert derivative_embedder is episodic_embedder
    assert episodic_embedder is semantic_embedder
    assert derivative_embedder.__self__.name == "hash"
    assert resources.embedder_provider_name == "hash"


def test_resolve_embedder_provider_name_reads_single_persisted_value(tmp_path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE semantic_config_set_id_resources (
                set_id TEXT PRIMARY KEY,
                set_name TEXT NULL,
                set_description TEXT NULL,
                embedder_name TEXT NULL,
                language_model_name TEXT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO semantic_config_set_id_resources (set_id, embedder_name) VALUES (?, ?)",
            ("set-a", "hash"),
        )
        conn.commit()

    settings = Settings(sqlite_path=sqlite_path, embedder_provider="hash")

    assert _resolve_embedder_provider_name(settings) == "hash"


def test_resolve_embedder_provider_name_falls_back_on_multiple_values(tmp_path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE semantic_config_set_id_resources (
                set_id TEXT PRIMARY KEY,
                set_name TEXT NULL,
                set_description TEXT NULL,
                embedder_name TEXT NULL,
                language_model_name TEXT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO semantic_config_set_id_resources (set_id, embedder_name) VALUES (?, ?)",
            [("set-a", "hash"), ("set-b", "custom-provider")],
        )
        conn.commit()

    settings = Settings(sqlite_path=sqlite_path, embedder_provider="hash")

    assert _resolve_embedder_provider_name(settings) == "hash"


def test_resource_manager_uses_persisted_embedder_provider_override(tmp_path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE semantic_config_set_id_resources (
                set_id TEXT PRIMARY KEY,
                set_name TEXT NULL,
                set_description TEXT NULL,
                embedder_name TEXT NULL,
                language_model_name TEXT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO semantic_config_set_id_resources (set_id, embedder_name) VALUES (?, ?)",
            ("set-a", "sentence_transformer"),
        )
        conn.commit()

    settings = Settings(
        sqlite_path=sqlite_path,
        kuzu_path=tmp_path / "graph.kuzu",
        embedder_provider="hash",
        embedder_model="sentence-transformers/all-MiniLM-L6-v2",
    )

    resources = ResourceManager.create(settings)

    assert resources.embedder_provider_name == "sentence_transformer"
    assert resources.derivative_pipeline._embedder.__self__.name == "sentence_transformer"  # type: ignore[attr-defined]
