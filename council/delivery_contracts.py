"""Versioned intake records; disabled defaults preserve existing checkpoints."""
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class SourceObservation(Record):
    path: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class ProofScope(Record):
    version: Literal[1] = 1
    project: str = Field(min_length=1, max_length=1024)
    generated_inputs: list[str] = Field(default_factory=list, max_length=32)
    runtime_mutable: bool = True


class FinalFinding(Record):
    id: str = Field(pattern=r'^F[1-9][0-9]{0,3}$')
    location: str = Field(min_length=1, max_length=1024)
    concern: str = Field(min_length=1, max_length=2000)
    consequence: str = Field(min_length=1, max_length=2000)
    kind: Literal['correctness', 'maintainability', 'requirements', 'scope_change']


class FinalReview(Record):
    content_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['accept', 'revise']
    findings: list[FinalFinding] = Field(max_length=16)
    resolved_finding_ids: list[str] = Field(max_length=16)
    inspected_dimensions: list[Literal['polish','documentation']] = Field(default_factory=list,max_length=2)


class QualityGateSpec(Record):
    phase: Literal['static_analysis','unit_tests','coverage_validation','regression','integration_build']
    task_ids: list[str] = Field(default_factory=list,max_length=12)
    out_of_scope_reason: str | None = Field(default=None,min_length=1,max_length=2000)

    @model_validator(mode='after')
    def evidence_or_scope(self):
        if bool(self.task_ids)==bool(self.out_of_scope_reason) or len(set(self.task_ids))!=len(self.task_ids):
            raise ValueError('Gate requires task obligations or an explicit scope reason')
        return self


class FinalizationState(Record):
    captured_scopes: list[str] = Field(default_factory=list, max_length=32)
    baseline_sha256: str | None = None
    polish_task_ids: list[str] = Field(default_factory=list, max_length=32)
    review_count: int = Field(default=0, ge=0, le=3)
    reviews: list[FinalReview] = Field(default_factory=list, max_length=3)
    approved_content_sha256: str | None = None
    findings: list[FinalFinding] = Field(default_factory=list, max_length=16)
    quality_gates: dict[str, str] = Field(default_factory=dict, max_length=11)
    proof_epoch: int = Field(default=0, ge=0, le=4)
    quality_evidence: dict[str, dict[str, Any]] = Field(default_factory=dict,max_length=11)


class RequirementEntry(Record):
    id: str = Field(pattern=r'^R[1-9][0-9]{0,3}$')
    statement: str = Field(min_length=1, max_length=3000)
    basis: Literal['user', 'observed', 'proposal']
    source_refs: list[str] = Field(max_length=16)


class BaselineEntry(Record):
    id: str = Field(pattern=r'^B[1-9][0-9]{0,3}$')
    statement: str = Field(min_length=1, max_length=3000)
    basis: Literal['user', 'observed', 'proposal', 'unknown']
    source_refs: list[str] = Field(max_length=16)
    consequence: str = Field(min_length=1, max_length=2000)


class IntakeQuestion(Record):
    id: str = Field(pattern=r'^Q[1-9][0-9]{0,3}$')
    question: str = Field(min_length=1, max_length=2000)
    consequence: str = Field(min_length=1, max_length=2000)
    consequential: bool
    bounded_default: str | None = Field(default=None, min_length=1, max_length=2000)


class RequirementsDraft(Record):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    requirements: list[RequirementEntry] = Field(min_length=1, max_length=64)
    baseline: list[BaselineEntry] = Field(max_length=64)
    proposals: list[str] = Field(max_length=32)
    questions: list[IntakeQuestion] = Field(max_length=32)
    scope_exclusions: list[str] = Field(default_factory=list, max_length=32)
    acceptance: list[str] = Field(default_factory=list, max_length=64)
    retired_requirement_ids: list[str] = Field(default_factory=list, max_length=64)
    scope_and_ownership: str = Field(default='Not established; no additional ownership or dependencies inferred.', max_length=6000)
    data_and_lifecycle: str = Field(default='Not established; mark not applicable with a reason when irrelevant.', max_length=6000)
    delivery_constraints: str = Field(default='Not established; executable commands belong to planning.', max_length=6000)
    decisions: str = Field(default='No additional consequential decisions recorded.', max_length=4000)
    completion_boundary: Literal['functional','pr_ready'] = Field(default='functional',
        description='Human-approved acceptance boundary shown in the document. Use pr_ready when complete reviewable quality is required; never silently reduce that requirement to functional behavior.')

    @model_validator(mode='after')
    def unique_ids(self):
        for entries in (self.requirements, self.baseline, self.questions):
            ids = [entry.id for entry in entries]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate document identity')
        if set(self.retired_requirement_ids) & {item.id for item in self.requirements}:
            raise ValueError('Active requirement cannot be retired')
        if any(len(item) > 3000 or not item.strip() for item in
               [*self.proposals, *self.scope_exclusions, *self.acceptance]):
            raise ValueError('Document entry exceeds bounds')
        return self


class RequirementsRevision(Record):
    revision: int = Field(ge=1, le=4)
    document_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    markdown: str = Field(min_length=1, max_length=96000)
    feedback_count: int = Field(ge=0, le=4)


class BaselineChallengeProposal(Record):
    baseline_id: str
    requirement_id: str
    reason: Literal['requirement_change', 'observed_failure', 'introduced_defect', 'blocking_dependency']
    evidence_refs: list[str] = Field(min_length=1, max_length=16)
    consequence: str = Field(min_length=1, max_length=2000)
    replacement_statement: str | None = Field(default=None,min_length=1,max_length=3000)
    replacement_source_refs: list[str] = Field(default_factory=list,max_length=16)


class BaselineChallenge(BaselineChallengeProposal):
    id: str = Field(pattern=r'^C[1-9][0-9]*$')
    document_sha256: str
    route: Literal['human_requirements', 'existing_review']
    resolution: str | None = Field(default=None, min_length=1, max_length=2000)


class BaselineAmendment(Record):
    baseline_id: str
    requirements_sha256: str
    challenge_id: str
    statement: str = Field(min_length=1,max_length=3000)
    consequence: str = Field(min_length=1,max_length=2000)
    sources: list[SourceObservation] = Field(min_length=1,max_length=16)
    review_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class RequirementsState(Record):
    version: Literal[1] = 1
    draft: RequirementsDraft | None = None
    markdown: str = Field(default='', max_length=96000)
    document_sha256: str | None = None
    approved_sha256: str | None = None
    accepted_limitations: list[str] = Field(default_factory=list, max_length=32)
    feedback: list[str] = Field(default_factory=list, max_length=4)
    revisions: list[RequirementsRevision] = Field(default_factory=list, max_length=4)
    sources: list[SourceObservation] = Field(default_factory=list, max_length=128)
    inspection_rounds: int = Field(default=0, ge=0, le=8)
    drafting_attempts: int = Field(default=0, ge=0, le=4)
    draft_rejections: list[Literal['unobserved_source','requirement_id_loss','document_limit']] = Field(default_factory=list,max_length=4)
    challenges: list[BaselineChallenge] = Field(default_factory=list, max_length=32)
    reopening: bool = False
    previous_approval: str | None = None
    proposed_change: str = Field(default='', max_length=12000)
    superseded_deliveries: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    baseline_amendments: list[BaselineAmendment] = Field(default_factory=list,max_length=32)
