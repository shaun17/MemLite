"""SQLite-backed semantic configuration store."""

from dataclasses import dataclass

from sqlalchemy import text

from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class SetTypeRecord:
    id: int
    org_id: str
    org_level_set: int
    metadata_tags_sig: str
    name: str | None
    description: str | None


@dataclass(slots=True)
class CategoryRecord:
    id: int
    set_id: str | None
    set_type_id: int | None
    name: str
    prompt: str
    description: str | None
    inherited: bool = False


@dataclass(slots=True)
class TagRecord:
    id: int
    category_id: int
    name: str
    description: str


@dataclass(slots=True)
class SetConfigRecord:
    set_id: str
    set_name: str | None
    set_description: str | None
    embedder_name: str | None
    language_model_name: str | None


class SqliteSemanticConfigStore:
    """Store semantic categories, tags, set types, and set-level config."""

    def __init__(self, engine_factory: SqliteEngineFactory) -> None:
        self._engine_factory = engine_factory

    async def create_set_type(
        self,
        *,
        org_id: str,
        metadata_tags_sig: str,
        org_level_set: bool = False,
        name: str | None = None,
        description: str | None = None,
    ) -> int:
        async def _create(session):
            result = await session.execute(
                text(
                    """
                    INSERT INTO semantic_config_set_type (
                        org_id, org_level_set, metadata_tags_sig, name, description
                    ) VALUES (
                        :org_id, :org_level_set, :metadata_tags_sig, :name, :description
                    )
                    RETURNING id
                    """
                ),
                {
                    "org_id": org_id,
                    "org_level_set": int(org_level_set),
                    "metadata_tags_sig": metadata_tags_sig,
                    "name": name,
                    "description": description,
                },
            )
            return int(result.scalar_one())

        return await run_in_transaction(self._engine_factory.create_session_factory(), _create)

    async def list_set_types(self, org_id: str | None = None) -> list[SetTypeRecord]:
        query = "SELECT id, org_id, org_level_set, metadata_tags_sig, name, description FROM semantic_config_set_type"
        params: dict[str, object] = {}
        if org_id is not None:
            query += " WHERE org_id = :org_id"
            params["org_id"] = org_id
        query += " ORDER BY id"

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()
        return [SetTypeRecord(**row) for row in rows]

    async def delete_set_type(self, set_type_id: int) -> None:
        async def _delete(session):
            await session.execute(
                text("DELETE FROM semantic_config_set_type WHERE id = :set_type_id"),
                {"set_type_id": set_type_id},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def set_setid_config(
        self,
        *,
        set_id: str,
        set_name: str | None = None,
        set_description: str | None = None,
        embedder_name: str | None = None,
        language_model_name: str | None = None,
    ) -> None:
        async def _upsert(session):
            await session.execute(
                text(
                    """
                    INSERT INTO semantic_config_set_id_resources (
                        set_id, set_name, set_description, embedder_name, language_model_name
                    ) VALUES (
                        :set_id, :set_name, :set_description, :embedder_name, :language_model_name
                    )
                    ON CONFLICT(set_id)
                    DO UPDATE SET
                        set_name = excluded.set_name,
                        set_description = excluded.set_description,
                        embedder_name = excluded.embedder_name,
                        language_model_name = excluded.language_model_name
                    """
                ),
                {
                    "set_id": set_id,
                    "set_name": set_name,
                    "set_description": set_description,
                    "embedder_name": embedder_name,
                    "language_model_name": language_model_name,
                },
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _upsert)

    async def get_setid_config(self, set_id: str) -> SetConfigRecord | None:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT set_id, set_name, set_description, embedder_name, language_model_name
                        FROM semantic_config_set_id_resources
                        WHERE set_id = :set_id
                        """
                    ),
                    {"set_id": set_id},
                )
            ).mappings().first()
        return None if row is None else SetConfigRecord(**row)

    async def register_set_id_set_type(self, *, set_id: str, set_type_id: int) -> None:
        async def _register(session):
            await session.execute(
                text(
                    """
                    INSERT INTO semantic_config_set_id_set_type (set_id, set_type_id)
                    VALUES (:set_id, :set_type_id)
                    ON CONFLICT(set_id)
                    DO NOTHING
                    """
                ),
                {"set_id": set_id, "set_type_id": set_type_id},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _register)

    async def create_category(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        set_id: str | None = None,
        set_type_id: int | None = None,
    ) -> int:
        async def _create(session):
            result = await session.execute(
                text(
                    """
                    INSERT INTO semantic_config_category (
                        set_id, set_type_id, name, prompt, description
                    ) VALUES (
                        :set_id, :set_type_id, :name, :prompt, :description
                    )
                    RETURNING id
                    """
                ),
                {
                    "set_id": set_id,
                    "set_type_id": set_type_id,
                    "name": name,
                    "prompt": prompt,
                    "description": description,
                },
            )
            return int(result.scalar_one())

        return await run_in_transaction(self._engine_factory.create_session_factory(), _create)

    async def get_category(self, category_id: int) -> CategoryRecord | None:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, set_id, set_type_id, name, prompt, description
                        FROM semantic_config_category
                        WHERE id = :category_id
                        """
                    ),
                    {"category_id": category_id},
                )
            ).mappings().first()
        return None if row is None else CategoryRecord(**row)

    async def list_categories_for_set(self, set_id: str) -> list[CategoryRecord]:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            local_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT id, set_id, set_type_id, name, prompt, description
                        FROM semantic_config_category
                        WHERE set_id = :set_id
                        ORDER BY id
                        """
                    ),
                    {"set_id": set_id},
                )
            ).mappings().all()

            set_type_id = (
                await conn.execute(
                    text(
                        "SELECT set_type_id FROM semantic_config_set_id_set_type WHERE set_id = :set_id"
                    ),
                    {"set_id": set_id},
                )
            ).scalar_one_or_none()

            inherited_rows = []
            if set_type_id is not None:
                inherited_rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT id, set_id, set_type_id, name, prompt, description
                            FROM semantic_config_category
                            WHERE set_type_id = :set_type_id
                            ORDER BY id
                            """
                        ),
                        {"set_type_id": set_type_id},
                    )
                ).mappings().all()

        local = [CategoryRecord(**row, inherited=False) for row in local_rows]
        local_names = {entry.name for entry in local}
        inherited = [
            CategoryRecord(**row, inherited=True)
            for row in inherited_rows
            if row["name"] not in local_names
        ]
        return local + inherited

    async def delete_category(self, category_id: int) -> None:
        async def _delete(session):
            await session.execute(
                text("DELETE FROM semantic_config_tag WHERE category_id = :category_id"),
                {"category_id": category_id},
            )
            await session.execute(
                text("DELETE FROM semantic_config_category WHERE id = :category_id"),
                {"category_id": category_id},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def create_tag(self, *, category_id: int, name: str, description: str) -> int:
        async def _create(session):
            result = await session.execute(
                text(
                    """
                    INSERT INTO semantic_config_tag (category_id, name, description)
                    VALUES (:category_id, :name, :description)
                    RETURNING id
                    """
                ),
                {
                    "category_id": category_id,
                    "name": name,
                    "description": description,
                },
            )
            return int(result.scalar_one())

        return await run_in_transaction(self._engine_factory.create_session_factory(), _create)

    async def list_tags(self, category_id: int) -> list[TagRecord]:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, category_id, name, description FROM semantic_config_tag WHERE category_id = :category_id ORDER BY id"
                    ),
                    {"category_id": category_id},
                )
            ).mappings().all()
        return [TagRecord(**row) for row in rows]

    async def delete_tag(self, tag_id: int) -> None:
        async def _delete(session):
            await session.execute(
                text("DELETE FROM semantic_config_tag WHERE id = :tag_id"),
                {"tag_id": tag_id},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def add_disabled_category_to_setid(self, *, set_id: str, category_name: str) -> None:
        async def _insert(session):
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO semantic_config_disabled_category (set_id, disabled_category) VALUES (:set_id, :category_name)"
                ),
                {"set_id": set_id, "category_name": category_name},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _insert)

    async def remove_disabled_category_from_setid(
        self, *, set_id: str, category_name: str
    ) -> None:
        async def _delete(session):
            await session.execute(
                text(
                    "DELETE FROM semantic_config_disabled_category WHERE set_id = :set_id AND disabled_category = :category_name"
                ),
                {"set_id": set_id, "category_name": category_name},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def get_disabled_categories(self, set_id: str) -> list[str]:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT disabled_category FROM semantic_config_disabled_category WHERE set_id = :set_id ORDER BY disabled_category"
                    ),
                    {"set_id": set_id},
                )
            ).all()
        return [str(row[0]) for row in rows]
