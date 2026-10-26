"""Finite checkpoint records for shared context, actual verification, and repair."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VerificationRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(max_length=64)
    run_id: str = Field(max_length=256)
    phase_index: int = Field(ge=0, le=8)
    task_id: str = Field(max_length=256)
    graph_step: int = Field(ge=0, le=1000)
    attempt: int = Field(ge=0, le=3)
    plan_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    contract_versions: dict[str, int] = Field(default_factory=dict, max_length=32)
    command_index: int = Field(ge=1, le=16)
    command_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    source_hashes: dict[str, str | None] = Field(max_length=512)
    source_scope: Literal['declared_targets_and_command_files', 'project_dependencies_v1', 'readiness_observation_v1'] = 'declared_targets_and_command_files'
    validity_boundary: str | None = Field(default=None, max_length=64)
    requirements_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    started_utc: str | None = Field(default=None,max_length=40)
    ended_utc: str | None = Field(default=None,max_length=40)
    duration_seconds: float | None = Field(default=None,ge=0,le=10**9)
    exit_code: int
    expectation_met: bool


class RepairAdvice(BaseModel):
    """No arbitrary prose/output: every retained action and limitation is finite."""
    model_config = ConfigDict(extra='forbid', strict=True)
    failure_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    category: Literal['implementation', 'test_harness', 'command_contract', 'prerequisite', 'unknown']
    action: Literal['inspect_declared_targets', 'repair_implementation', 'repair_test_harness',
                    'report_command_contract', 'resolve_prerequisite', 'recheck_failure']
    target_files: list[str] = Field(max_length=32,
        description='Only exact declared task target paths. Do not copy output or other source text.')
    limitations: list[Literal['output_unavailable', 'cause_unproven', 'needs_source_inspection']] = Field(max_length=3)

