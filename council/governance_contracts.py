"""Bounded architecture decisions and durable per-piece delivery records."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class GovernanceModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Executable(GovernanceModel):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_-]*$')
    kind: str = Field(min_length=1, max_length=64, description='API, console, UI, database, library, or other system boundary')
    repository: str = Field(min_length=1, max_length=256)
    depends_on: list[str] = Field(default_factory=list, max_length=32)


class SharedContract(GovernanceModel):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_-]*$')
    producer_piece: str = Field(min_length=1, max_length=64)
    consumer_pieces: list[str] = Field(default_factory=list, max_length=8)
    version: int = Field(default=1, ge=1, le=33)
    definition: str = Field(min_length=1, max_length=6000,
        description='Workable initial communication/data contract grounded in existing code; routine details belong to engineers')


class OpenQuestion(GovernanceModel):
    id: str = Field(min_length=1, max_length=64)
    owner_piece: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    assumption: str = Field(min_length=1, max_length=1000,
        description='Working assumption or localized decision to resolve in this piece; uncertainty does not block unrelated work')


class SolutionArchitecture(GovernanceModel):
    executables: list[Executable] = Field(min_length=1, max_length=32)
    contracts: list[SharedContract] = Field(default_factory=list, max_length=32)
    open_questions: list[OpenQuestion] = Field(default_factory=list, max_length=32)
    integration_strategy: str = Field(min_length=1, max_length=4000)


class ContractChange(GovernanceModel):
    id: str = Field(min_length=1, max_length=64)
    base_version: int = Field(ge=1, le=32)
    definition: str = Field(min_length=1, max_length=6000)
    reason: str = Field(min_length=1, max_length=1000)


class WorkPieceRecord(GovernanceModel):
    id: str = Field(min_length=1, max_length=64)
    status: Literal['pending', 'planning', 'reviewing', 'executing', 'blocked', 'completed', 'needs_revision'] = 'pending'
    contract_versions: dict[str, int] = Field(default_factory=dict, max_length=32)
    verified_contract_versions: dict[str, int] = Field(default_factory=dict, max_length=32)
    plan_versions: list[dict[str, Any]] = Field(default_factory=list, max_length=128)
    review_history: list[dict[str, Any]] = Field(default_factory=list, max_length=128)
    checkpoint: dict[str, Any] = Field(default_factory=dict, max_length=64)
    execution_record_ids: list[str] = Field(default_factory=list, max_length=8192)
    completion_history: list[dict[str, Any]] = Field(default_factory=list, max_length=64)
