"""Validated engine schemas; checkpoints contain only JSON-compatible values."""
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator, model_serializer
from pydantic_core import PydanticCustomError
from council.phase_contract import PhaseRoadmap, CompletedPhase
from council.integrity_contracts import VerificationRecord, RepairAdvice
from council.governance_contracts import ContractChange, SharedContract, WorkPieceRecord
from council.recovery_contracts import RecoveryPolicy, RecoveryIncident, RecoveryEvent, WorkerObservation
from council.delivery_contracts import RequirementsState, ProofScope, FinalizationState, QualityGateSpec, BaselineChallengeProposal

class PlanReviewDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    decision: Literal['accept', 'revise', 'escalate']
    findings: list[str] = Field(max_length=12)

    @model_validator(mode='after')
    def validate_findings(self):
        if any(not item.strip() for item in self.findings):
            raise PydanticCustomError('review_finding_blank', 'Blank review finding')
        if any(len(item) > 1000 for item in self.findings):
            raise PydanticCustomError('review_finding_bounds', 'Review finding exceeds limit')
        if (self.decision == 'accept') != (not self.findings):
            raise PydanticCustomError('review_decision_findings', 'Acceptance requires no unresolved findings')
        return self

class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^F[1-9][0-9]{0,3}$')
    description: str = Field(min_length=1, max_length=1000)
    kind: Literal['technical', 'user_decision']

    @model_validator(mode='after')
    def nonblank_description(self):
        if not self.description.strip():
            raise PydanticCustomError('review_finding_blank', 'Blank finding')
        return self

class FindingLedgerEntry(ReviewFinding):
    status: Literal['unresolved', 'resolved']

class PlanReviewDecisionV2(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    decision: Literal['accept', 'revise', 'escalate']
    findings: list[ReviewFinding] = Field(max_length=12)
    resolved_finding_ids: list[str] = Field(max_length=12)

    @model_validator(mode='after')
    def consistent_decision(self):
        ids = [item.id for item in self.findings]
        if len(set(ids)) != len(ids):
            raise PydanticCustomError('review_duplicate_finding', 'Duplicate finding identity')
        if len(set(self.resolved_finding_ids)) != len(self.resolved_finding_ids):
            raise PydanticCustomError('review_duplicate_resolved', 'Duplicate closure identity')
        if (self.decision == 'accept') != (not self.findings):
            raise PydanticCustomError('review_decision_findings', 'Acceptance requires no unresolved findings')
        needs_user = any(item.kind == 'user_decision' for item in self.findings)
        if (self.decision == 'escalate') != needs_user:
            raise PydanticCustomError('review_escalation_kind', 'Escalation requires a user decision')
        return self

class PlanValidationFeedback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: Literal['PLAN_TARGET_PATH_INVALID', 'PLAN_WORKING_DIRECTORY_INVALID',
                  'PLAN_VERIFICATION_INVALID', 'PLAN_SPECIALIST_INVALID']
    task_index: int = Field(ge=1, le=100000)
    task_id: str = Field(max_length=256)
    task_description: str = Field(max_length=512)
    field: Literal['target_files', 'working_directory', 'test_commands', 'specialist',
                   'id', 'red_verification', 'verification_phase', 'kind', 'readiness_for', 'status', 'delivery_stage']
    field_index: int | None = Field(default=None, ge=1, le=100000)
    rejected_value: str = Field(max_length=2048)
    value_truncated: bool
    verification: dict[str, Any] | None = None

    @model_validator(mode='after')
    def bounded_utf8(self):
        if self.verification is not None:
            from council.verification_feedback import safe_detail
            detail = safe_detail(self.verification)
            if (self.code != 'PLAN_VERIFICATION_INVALID' or detail is None or self.field != detail['field']):
                raise ValueError('Invalid verification feedback')
        if any(len(getattr(self, field).encode('utf-8')) > limit for field, limit in
               [('task_id', 256), ('task_description', 512), ('rejected_value', 2048)]):
            raise ValueError('Plan validation feedback exceeds limit')
        return self

class ExpectedRedFailure(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    command_index: int = Field(ge=1, le=16)
    test_name: str = Field(min_length=1, max_length=256)
    assertion_message: str = Field(min_length=16, max_length=200, pattern=r'^TDD_RED: .+')

class RedVerificationContract(BaseModel):
    model_config = ConfigDict(extra='forbid')
    implementation_task_id: str = Field(min_length=1, max_length=256)
    expected_failures: list[ExpectedRedFailure] = Field(min_length=1, max_length=64)

class RedPhaseEvidence(BaseModel):
    red_task_id: str
    green_task_id: str
    command_index: int = Field(ge=1, le=16)
    test_names: list[str] = Field(min_length=1, max_length=256)
    source_hashes: dict[str, str] = Field(min_length=1, max_length=32)
    closed: bool = False
    piece_id: str | None = None
    plan_sha256: str | None = None
    contract_versions: dict[str, int] = Field(default_factory=dict, max_length=32)

class TaskItem(BaseModel):
    id: str
    kind: Literal['implementation', 'readiness'] = 'implementation'
    readiness_for: list[str] = Field(default_factory=list, max_length=256,
        description='For readiness tasks: later implementation task IDs in this same plan, never roadmap phase IDs. Empty for every task in an all-readiness phase plan.')
    specialist: str = Field(description="Canonical Council specialist package identifier, for example 'the-coder'. Use a declared identifier, not a bracketed display call sign.")
    description: str
    target_files: list[str] = Field(default_factory=list, description='Paths relative to the workspace root, including the project prefix; never absolute or parent-traversing.')
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_commands: list[list[str]] = Field(default_factory=list)
    working_directory: str = Field(default='.', description='Workspace-relative directory; must already exist and be safe for native coding.')
    verification_phase: Literal['green', 'red'] = Field(default='green', description='Green requires exit zero. Red requires a strict named assertion-failure contract and a later green implementation task.')
    red_verification: RedVerificationContract | None = None
    proof_scope: ProofScope | None = Field(default=None,
        description='Optional observed project dependency scope. Keep runtime_mutable true for services, databases, fixtures or unknown runtime inputs. Use only supported metadata; unsupported discovery falls back conservatively.')
    delivery_stage: Literal['implementation', 'finalize'] = Field(default='implementation',
        description='Finalize is a real scoped code/documentation polish assignment with normal independent verification; use last in the final acceptance phase.')
    status: Literal['pending','in_progress','completed','failed'] = 'pending'

class MultiSpecialistPlan(BaseModel):
    title: str
    architecture_summary: str
    affected_services: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list, min_length=1)
    contract_changes: list[ContractChange] = Field(default_factory=list, max_length=16)
    quality_gates: list[QualityGateSpec] = Field(default_factory=list,max_length=5,
        description='Final delivery: map applicable SOP checks to actual verification tasks, or give a concrete out-of-scope reason. Missing checks remain unverified; no readiness is inferred from command names.')
    baseline_challenges: list[BaselineChallengeProposal] = Field(default_factory=list,max_length=8,
        description='Evidence-backed challenges to a retained B/R identity. Independent review admits fact challenges; requirement changes return to the exact human approval boundary.')

class TestExecutionResult(BaseModel):
    command: str
    passed: bool
    exit_code: int
    tests_passed: int | None = None
    tests_failed: int | None = None
    counts_known: bool = False
    compiler_errors: list[str] = Field(default_factory=list)
    failure_output: str = ''
    verification_phase: Literal['green', 'red'] = 'green'
    expectation_met: bool | None = None
    verification_reason: str = ''
    command_index: int | None = None
    verification_detail: dict[str, Any] | None = None

    @field_validator('command_index', mode='before')
    @classmethod
    def bounded_command_index(cls, value):
        from council.red_feedback import command_index
        return command_index(value)

    @field_validator('verification_detail', mode='before')
    @classmethod
    def safe_verification_detail(cls, value):
        from council.red_feedback import safe_detail
        return safe_detail(value)

    @model_serializer(mode='wrap')
    def sanitized_output(self, handler):
        from council.red_feedback import sanitize_result
        return sanitize_result(handler(self))

class PlanningInspectionSummary(BaseModel):
    rounds_used: int = Field(default=0, ge=0, le=12)
    round_limit: int = Field(default=12, ge=0, le=12)
    limit_reached: bool = False

class CouncilState(BaseModel):
    run_id: str
    task_input: str
    intake_enabled: bool = False
    finalization_enabled: bool = False
    finalization: FinalizationState = Field(default_factory=FinalizationState)
    delivery_result: dict[str, Any] = Field(default_factory=dict)
    proof_refresh_piece: int | None = Field(default=None,ge=0,le=7)
    proof_refresh_reason: Literal['stale','review'] | None = None
    requirements: RequirementsState = Field(default_factory=RequirementsState)
    thread_id: str | None = None
    workspace_root: str = ''
    council_root: str = ''
    memory_root: str = ''
    auto_approve: bool = False
    approval_policy: Literal['autonomous', 'manual', 'bypass'] | None = None
    approval_policy_version: Literal[1] = 1
    review_protocol_version: Literal[1, 2] = 1
    revision_evidence_policy_version: Literal[1, 2] = 1
    readiness_policy_version: Literal[1, 2, 3] = 1
    orchestration_policy_version: Literal[1, 2] = 1
    graph_integrity_policy_version: Literal[1, 2] = 1
    governance_policy_version: Literal[1, 2] = 1
    recovery_policy: RecoveryPolicy = Field(default_factory=RecoveryPolicy)
    recovery_incident: RecoveryIncident | None = None
    recovery_history: list[RecoveryEvent] = Field(default_factory=list, max_length=512)
    worker_observation: WorkerObservation | None = None
    shared_contracts: dict[str, SharedContract] = Field(default_factory=dict, max_length=32)
    work_pieces: dict[str, WorkPieceRecord] = Field(default_factory=dict, max_length=8)
    contract_history: list[dict[str, Any]] = Field(default_factory=list, max_length=32)
    governance_feedback: dict[str, str] | None = None
    roadmap_finding_ledger: list[FindingLedgerEntry] = Field(default_factory=list, max_length=72)
    document_revision_feedback: dict[str, Any] | None = None
    last_document_revision: dict[str, Any] | None = None
    roadmap_no_progress_count: int = Field(default=0, ge=0)
    last_reviewed_roadmap_sha256: str | None = None
    requirement_sha256: str = ''
    run_identity_sha256: str = ''
    context_receipts: list[dict[str, Any]] = Field(default_factory=list, max_length=4096)
    integrity_events: list[dict[str, Any]] = Field(default_factory=list, max_length=1024)
    execution_records: list[VerificationRecord] = Field(default_factory=list, max_length=8192)
    repair_advice: RepairAdvice | None = None
    roadmap: 'PhaseRoadmap | None' = None
    accepted_roadmap_sha256: str | None = None
    roadmap_review_count: int = Field(default=0, ge=0, le=6)
    roadmap_revision_count: int = Field(default=0, ge=0, le=5)
    roadmap_review_findings: list[str] = Field(default_factory=list, max_length=12)
    roadmap_inspection_evidence: list[str] = Field(default_factory=list, max_length=64)
    roadmap_inspection_available: bool = False
    roadmap_inspection_truncated: bool = False
    current_phase_index: int = Field(default=0, ge=0, le=8)
    completed_phases: list['CompletedPhase'] = Field(default_factory=list, max_length=64)
    total_inspection_rounds: int = Field(default=0, ge=0, le=32)
    phase_start_test_result_index: int = Field(default=0, ge=0)
    phase_start_file_hashes: dict[str, str | None] = Field(default_factory=dict)
    review_finding_ledger: list[FindingLedgerEntry] = Field(default_factory=list, max_length=72)
    review_no_progress_count: int = Field(default=0, ge=0)
    last_reviewed_plan_sha256: str | None = None
    plan_review_count: int = Field(default=0, ge=0)
    plan_revision_count: int = Field(default=0, ge=0)
    plan_preflight_failure_count: int = Field(default=0, ge=0)
    plan_validation_feedback: PlanValidationFeedback | None = None
    plan_recovery_count: int = Field(default=0, ge=0)
    strategy_reset_count: int = Field(default=0, ge=0, le=1)
    recovery_review_baseline: int = Field(default=0, ge=0)
    recovery_revision_baseline: int = Field(default=0, ge=0)
    plan_review_findings: list[str] = Field(default_factory=list, max_length=12)
    accepted_plan_sha256: str | None = None
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    active_role: Literal['orchestrator','investigator','coder'] = 'orchestrator'
    investigation_report: str | None = None
    plan: MultiSpecialistPlan | None = None
    planning_inspection: PlanningInspectionSummary | None = None
    planning_evidence: list[str] = Field(default_factory=list, max_length=64)
    planning_evidence_available: bool = False
    planning_evidence_truncated: bool = False
    current_task_index: int = 0
    active_specialist: str = 'the-architect'
    modified_files: list[str] = Field(default_factory=list)
    file_changes: list[dict[str, Any]] = Field(default_factory=list)
    test_result: TestExecutionResult | None = None
    test_results: list[dict[str, Any]] = Field(default_factory=list)
    red_phase_evidence: list[RedPhaseEvidence] = Field(default_factory=list, max_length=64)
    completed_red_phase_evidence: list[RedPhaseEvidence] = Field(default_factory=list, max_length=512)
    test_retry_count: int = 0
    max_test_retries: int = Field(default=2, ge=0, le=2)
    step_count: int = 0
    max_steps: int = Field(default=100, ge=1, le=1000)
    last_error_hash: str | None = None
    workspace_validator_passed: bool = False
    gatekeeper_summary: dict[str, Any] = Field(default_factory=dict)
    human_feedback: str | None = None
    tool_call_history: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    error: str | None = None
    diagnostic: dict[str, Any] | None = None
    status: str = 'START'

    @field_validator('readiness_policy_version', mode='before')
    @classmethod
    def strict_readiness_policy(cls, value):
        if type(value) is not int or value not in (1, 2, 3):
            raise ValueError('Readiness policy must be version 1, 2 or 3')
        return value

    @field_validator('revision_evidence_policy_version', 'graph_integrity_policy_version', 'governance_policy_version', mode='before')
    @classmethod
    def strict_revision_policy(cls, value):
        if type(value) is not int or value not in (1, 2):
            raise ValueError('Policy must be version 1 or 2')
        return value

    @field_validator('test_results')
    @classmethod
    def sanitized_test_results(cls, values):
        from council.red_feedback import sanitize_result
        return [sanitize_result(value) for value in values]

    @model_serializer(mode='wrap')
    def sanitized_output(self, handler):
        from council.red_feedback import sanitize_result
        result = handler(self)
        if 'test_results' in result:
            result['test_results'] = [sanitize_result(value) for value in result['test_results']]
        return result

    @model_validator(mode='after')
    def bounded_planning_evidence(self):
        sizes = [len(item.encode('utf-8')) for item in self.planning_evidence]
        if any(size > 16384 for size in sizes) or sum(sizes) > 131072:
            raise ValueError('Planning evidence exceeds limit')
        from council.review_feedback import sanitize_diagnostic
        self.diagnostic = sanitize_diagnostic(self.diagnostic)
        return self
