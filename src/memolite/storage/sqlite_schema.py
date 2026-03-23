"""SQLite schema bootstrap helpers for MemLite."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

BOOTSTRAP_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS projects (
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        description TEXT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (org_id, project_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_key TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        user_id TEXT NULL,
        agent_id TEXT NULL,
        group_id TEXT NULL,
        summary TEXT NOT NULL DEFAULT '',
        summary_updated_at TEXT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS episodes (
        uid TEXT PRIMARY KEY,
        session_key TEXT NOT NULL,
        session_id TEXT NOT NULL,
        producer_id TEXT NOT NULL,
        producer_role TEXT NOT NULL,
        produced_for_id TEXT NULL,
        sequence_num INTEGER NOT NULL DEFAULT 0,
        content TEXT NOT NULL,
        content_type TEXT NOT NULL,
        episode_type TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        metadata_json TEXT NULL,
        filterable_metadata_json TEXT NULL,
        deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(session_key) REFERENCES sessions(session_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_set_type (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        org_level_set INTEGER NOT NULL DEFAULT 0,
        metadata_tags_sig TEXT NOT NULL,
        name TEXT NULL,
        description TEXT NULL,
        UNIQUE (org_id, org_level_set, metadata_tags_sig)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_set_id_resources (
        set_id TEXT PRIMARY KEY,
        set_name TEXT NULL,
        set_description TEXT NULL,
        embedder_name TEXT NULL,
        language_model_name TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_set_id_set_type (
        set_id TEXT PRIMARY KEY,
        set_type_id INTEGER NOT NULL,
        FOREIGN KEY(set_type_id) REFERENCES semantic_config_set_type(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_category (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id TEXT NULL,
        set_type_id INTEGER NULL,
        name TEXT NOT NULL,
        prompt TEXT NOT NULL,
        description TEXT NULL,
        FOREIGN KEY(set_type_id) REFERENCES semantic_config_set_type(id) ON DELETE CASCADE,
        UNIQUE (set_id, name),
        UNIQUE (set_type_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_category_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_type_id INTEGER NULL,
        name TEXT NOT NULL,
        category_name TEXT NOT NULL,
        prompt TEXT NOT NULL,
        description TEXT NULL,
        FOREIGN KEY(set_type_id) REFERENCES semantic_config_set_type(id) ON DELETE CASCADE,
        UNIQUE (set_type_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_tag (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        FOREIGN KEY(category_id) REFERENCES semantic_config_category(id) ON DELETE CASCADE,
        UNIQUE (category_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_config_disabled_category (
        set_id TEXT NOT NULL,
        disabled_category TEXT NOT NULL,
        PRIMARY KEY (set_id, disabled_category)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id TEXT NOT NULL,
        category TEXT NOT NULL,
        tag TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        value TEXT NOT NULL,
        metadata_json TEXT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        deleted INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_feature_vectors (
        feature_id INTEGER PRIMARY KEY,
        embedding BLOB NOT NULL,
        FOREIGN KEY(feature_id) REFERENCES semantic_features(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_org_project ON sessions (org_id, project_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_group_id ON sessions (group_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_session_deleted_sequence ON episodes (session_key, deleted, sequence_num)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_session_id_deleted ON episodes (session_id, deleted)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_role_type_deleted ON episodes (producer_role, episode_type, deleted)",
    "CREATE INDEX IF NOT EXISTS idx_semantic_features_lookup ON semantic_features (set_id, category, tag, feature_name, deleted)",
    "CREATE INDEX IF NOT EXISTS idx_semantic_features_prefix_set_id ON semantic_features (set_id)",
)


async def initialize_sqlite_schema(engine: AsyncEngine) -> None:
    """Create the bootstrap schema required by the first MemLite milestones."""
    async with engine.begin() as conn:
        for statement in BOOTSTRAP_STATEMENTS:
            await conn.execute(text(statement))



BOOTSTRAP_STATEMENTS = BOOTSTRAP_STATEMENTS + (
    """
    CREATE TABLE IF NOT EXISTS semantic_citations (
        feature_id INTEGER NOT NULL,
        episode_id TEXT NOT NULL,
        PRIMARY KEY (feature_id, episode_id),
        FOREIGN KEY(feature_id) REFERENCES semantic_features(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_set_ingested_history (
        set_id TEXT NOT NULL,
        history_id TEXT NOT NULL,
        ingested INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        PRIMARY KEY (set_id, history_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_semantic_citations_episode_id ON semantic_citations (episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_semantic_history_pending ON semantic_set_ingested_history (ingested, set_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_semantic_history_set_created ON semantic_set_ingested_history (set_id, created_at)",
)
