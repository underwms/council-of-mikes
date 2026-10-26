"""Finite recovery records; no executable commands or provider prose."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Action = Literal['verify_partial', 'refresh_proofs', 'repair_task', 'replan', 'ask_user', 'stop']
Category = Literal['timeout', 'tool_failure', 'verification', 'command_contract', 'prerequisite', 'stale_proof', 'transport', 'planning', 'unknown']
Reason = Literal['retained_sources_match','command_correction_required','prerequisite_scope_review',
    'stale_bound_proof','repair_existing_task','safe_retry_exhausted','cause_unproven',
    'user_decision_required','resources_unresolved','technical_plan_correction','repair_budget_exhausted']


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('resource_cleanup',mode='before',check_fields=False)
    @classmethod
    def finite_cleanup(cls,value):
        from council.diagnostics import safe_resource_cleanup
        cleaned=safe_resource_cleanup(value)
        if cleaned is None:raise ValueError('Finite resource cleanup evidence required')
        return cleaned


class RecoveryPolicy(StrictRecord):
    version: Literal[0, 1] = 0
    max_strategies_per_incident: int = Field(default=2, ge=1, le=2)
    max_strategies_per_run: int = Field(default=32, ge=1, le=32)

    @field_validator('version',mode='before')
    @classmethod
    def strict_version(cls,value):
        if type(value) is not int:raise ValueError('Integer recovery policy version required')
        return value


class WorkerObservation(StrictRecord):
    run_id: str
    phase_index: int
    task_id: str
    plan_sha256: str
    call: int
    source_hashes: dict[str, str | None] = Field(max_length=512)


class RecoveryDecision(StrictRecord):
    incident_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    action: Action
    reason: Reason = 'cause_unproven'
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    limitations: list[Literal['cause_unproven', 'output_unavailable', 'needs_source_inspection']] = Field(default_factory=list, max_length=3)


class RecoveryIncident(StrictRecord):
    id: str
    lineage: str
    category: Category
    origin: str
    code: str
    run_id: str
    phase_index: int
    task_id: str | None
    plan_sha256: str | None
    contract_versions: dict[str, int]
    source_hashes: dict[str, str | None]
    evidence_ids: list[str] = Field(max_length=32)
    cursor: int
    phase: Literal['proposed', 'admitted', 'dispatched'] = 'proposed'
    decision: RecoveryDecision | None = None
    queue: list[int] = Field(default_factory=list, max_length=64)
    source_tasks: list[int] = Field(default_factory=list, max_length=64)
    repairing: bool = False
    review_baseline: int = 0
    revision_baseline: int = 0
    resume_status: str = 'FAILED'
    opened_utc: str
    execution_cursor: int = Field(ge=0)
    resource_cleanup: dict = Field(default_factory=lambda:{'owned_process_exit_confirmed':None,'detached_resources':'unobserved'})
    failure_commands: list[str] = Field(default_factory=list,max_length=16)


class RecoveryEvent(StrictRecord):
    incident_id: str
    lineage: str
    outcome: Literal['opened', 'admitted', 'dispatched', 'resolved', 'failed', 'stopped', 'human_input', 'rejected']
    action: Action | None = None
    step: int
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    execution_ids: list[str] = Field(default_factory=list, max_length=32)
    elapsed_seconds: float = Field(default=0.0,ge=0)
    category: Category = 'unknown'
    reason: Reason = 'cause_unproven'
    run_budget_remaining: int = Field(default=0,ge=0)
    incident_budget_remaining: int = Field(default=0,ge=0)
    resource_cleanup: dict = Field(default_factory=lambda:{'owned_process_exit_confirmed':None,'detached_resources':'unobserved'})
    diagnostic_code: str | None = None
    incident: RecoveryIncident | None = None
