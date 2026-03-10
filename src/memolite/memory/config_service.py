"""Memory configuration service for episodic, short-term and long-term behavior."""

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class EpisodicMemoryConfig:
    top_k: int = 5
    min_score: float = 0.0001
    context_window: int = 1
    rerank_enabled: bool = True


@dataclass(slots=True)
class ShortTermMemoryConfig:
    message_capacity: int = 4096
    summary_enabled: bool = True


@dataclass(slots=True)
class LongTermMemoryConfig:
    semantic_enabled: bool = True
    episodic_enabled: bool = True


class MemoryConfigService:
    """Manage mutable runtime configuration for memory subsystems."""

    def __init__(self) -> None:
        self._episodic = EpisodicMemoryConfig()
        self._short_term = ShortTermMemoryConfig()
        self._long_term = LongTermMemoryConfig()

    def get_episodic(self) -> EpisodicMemoryConfig:
        return self._episodic

    def update_episodic(self, **fields: object) -> EpisodicMemoryConfig:
        self._episodic = EpisodicMemoryConfig(
            **{**asdict(self._episodic), **{k: v for k, v in fields.items() if v is not None}}
        )
        return self._episodic

    def get_short_term(self) -> ShortTermMemoryConfig:
        return self._short_term

    def update_short_term(self, **fields: object) -> ShortTermMemoryConfig:
        self._short_term = ShortTermMemoryConfig(
            **{**asdict(self._short_term), **{k: v for k, v in fields.items() if v is not None}}
        )
        return self._short_term

    def get_long_term(self) -> LongTermMemoryConfig:
        return self._long_term

    def update_long_term(self, **fields: object) -> LongTermMemoryConfig:
        self._long_term = LongTermMemoryConfig(
            **{**asdict(self._long_term), **{k: v for k, v in fields.items() if v is not None}}
        )
        return self._long_term
