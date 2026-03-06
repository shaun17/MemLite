"""Abstract storage contracts for MemLite."""

from abc import ABC, abstractmethod
from typing import Any


class ProjectStore(ABC):
    """Store projects and project metadata."""

    @abstractmethod
    async def create_project(self, org_id: str, project_id: str, **kwargs: Any) -> None:
        raise NotImplementedError


class SessionStore(ABC):
    """Store session metadata and summaries."""

    @abstractmethod
    async def get_session(self, session_key: str) -> dict[str, Any] | None:
        raise NotImplementedError


class EpisodeStore(ABC):
    """Store raw episodic records."""

    @abstractmethod
    async def add_episode(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class SemanticStorage(ABC):
    """Store semantic features and citations."""

    @abstractmethod
    async def get_feature(self, feature_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class SemanticConfigStore(ABC):
    """Store semantic configuration such as categories and tags."""

    @abstractmethod
    async def get_set_config(self, set_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class GraphStore(ABC):
    """Store graph relations for episodic memory."""

    @abstractmethod
    async def get_node(self, uid: str) -> dict[str, Any] | None:
        raise NotImplementedError


class VectorIndex(ABC):
    """Store and search vectors."""

    @abstractmethod
    async def search(self, query_vector: list[float], limit: int) -> list[str]:
        raise NotImplementedError
