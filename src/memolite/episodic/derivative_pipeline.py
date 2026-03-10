"""Derivative generation pipeline for episodic memory."""

from __future__ import annotations

import json
import re
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from memolite.storage.episode_store import EpisodeRecord
from memolite.storage.graph_store import GraphEdgeRecord, KuzuGraphStore
from memolite.storage.sqlite_vec import SqliteVecIndex

EmbedderFn = Callable[[str], Awaitable[list[float]]]

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")


@dataclass(slots=True)
class DerivativeRecord:
    """Derived chunk built from a source episode."""

    uid: str
    episode_uid: str
    session_id: str
    content: str
    content_type: str
    sequence_num: int
    metadata_json: str
    embedding: list[float]


class DerivativePipeline:
    """Create derivative nodes and vectors from episodic records."""

    def __init__(
        self,
        *,
        graph_store: KuzuGraphStore,
        derivative_index: SqliteVecIndex,
        embedder: EmbedderFn,
    ) -> None:
        self._graph_store = graph_store
        self._derivative_index = derivative_index
        self._embedder = embedder

    def chunk_text(self, content: str) -> list[str]:
        """Split an episode into sentence-level chunks."""
        normalized = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(content)]
        chunks = [part for part in normalized if part]
        return chunks or [content.strip()]

    def build_derivative_metadata(
        self,
        *,
        episode: EpisodeRecord,
        chunk_index: int,
        chunk_count: int,
    ) -> dict[str, object]:
        """Map source episode fields into derivative metadata."""
        source_metadata = _parse_metadata_json(episode.metadata_json)
        return {
            "episode_uid": episode.uid,
            "session_id": episode.session_id,
            "producer_id": episode.producer_id,
            "producer_role": episode.producer_role,
            "episode_type": episode.episode_type,
            "content_type": episode.content_type,
            "sequence_num": episode.sequence_num,
            "chunk_index": chunk_index,
            "chunk_count": chunk_count,
            "source_metadata": source_metadata,
        }

    async def create_derivatives(
        self,
        episode: EpisodeRecord,
    ) -> list[DerivativeRecord]:
        """Create and persist derivatives for a single episode."""
        # SQLite episode rows remain the source of truth. This pipeline only
        # materializes search-friendly projections into Kùzu and sqlite-vec.
        chunks = self.chunk_text(episode.content)
        derivative_records: list[DerivativeRecord] = []
        await self._graph_store.add_nodes(
            node_table="Episode",
            nodes=[
                {
                    "uid": episode.uid,
                    "session_id": episode.session_id,
                    "content": episode.content,
                    "content_type": episode.content_type,
                    "created_at": episode.created_at,
                    "metadata_json": episode.metadata_json or "{}",
                }
            ],
        )

        for index, chunk in enumerate(chunks, start=1):
            # Every derivative keeps enough lineage metadata to trace a vector
            # hit back to the original episode without another SQL join table.
            metadata = self.build_derivative_metadata(
                episode=episode,
                chunk_index=index,
                chunk_count=len(chunks),
            )
            embedding = await self._embedder(chunk)
            record = DerivativeRecord(
                uid=f"{episode.uid}:d:{index}",
                episode_uid=episode.uid,
                session_id=episode.session_id,
                content=chunk,
                content_type=episode.content_type,
                sequence_num=index,
                metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                embedding=embedding,
            )
            derivative_records.append(record)

        await self._graph_store.add_nodes(
            node_table="Derivative",
            nodes=[
                {
                    "uid": record.uid,
                    "episode_uid": record.episode_uid,
                    "session_id": record.session_id,
                    "content": record.content,
                    "content_type": record.content_type,
                    "sequence_num": record.sequence_num,
                    "metadata_json": record.metadata_json,
                }
                for record in derivative_records
            ],
        )
        await self._graph_store.add_edges(
            relation_table="DERIVED_FROM",
            from_table="Derivative",
            to_table="Episode",
            edges=[
                GraphEdgeRecord(
                    from_table="Derivative",
                    from_uid=record.uid,
                    to_table="Episode",
                    to_uid=record.episode_uid,
                    relation_table="DERIVED_FROM",
                    relation_type="derived_from_episode",
                )
                for record in derivative_records
            ],
        )
        # The vector index stores the same derivative uid through a stable
        # integer mapping, so graph hits and vector hits can be merged.
        await self._derivative_index.initialize()
        await self._derivative_index.batch_upsert(
            [(vector_item_id(record.uid), record.embedding) for record in derivative_records]
        )
        return derivative_records


def _parse_metadata_json(metadata_json: str | None) -> dict[str, object]:
    if metadata_json is None:
        return {}
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def vector_item_id(uid: str) -> int:
    return zlib.crc32(uid.encode("utf-8")) & 0x7FFFFFFF
