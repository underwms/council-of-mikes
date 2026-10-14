"""Validated engine schemas; checkpoints contain only JSON-compatible values."""
from typing import Any, Literal
from pydantic import BaseModel, Field

class TaskItem(BaseModel):
    id: str
    specialist: str
    description: str
    target_files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_commands: list[list[str]] = Field(default_factory=list)
    working_directory: str = '.'
    status: Literal['pending','in_progress','completed','failed'] = 'pending'

class MultiSpecialistPlan(BaseModel):
    title: str
    architecture_summary: str
    affected_services: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list, min_length=1)

class TestExecutionResult(BaseModel):
    command: str
    passed: bool
    exit_code: int
    tests_passed: int | None = None
    tests_failed: int | None = None
    counts_known: bool = False
    compiler_errors: list[str] = Field(default_factory=list)
    failure_output: str = ''

class CouncilState(BaseModel):
    run_id: str
    task_input: str
    thread_id: str | None = None
    workspace_root: str = ''
    council_root: str = ''
    memory_root: str = ''
    auto_approve: bool = False
    model_name: str = ''
    active_role: Literal['orchestrator','investigator','escalation'] = 'orchestrator'
    investigation_report: str | None = None
    plan: MultiSpecialistPlan | None = None
    current_task_index: int = 0
    active_specialist: str = 'the-architect'
    modified_files: list[str] = Field(default_factory=list)
    test_result: TestExecutionResult | None = None
    test_results: list[dict[str, Any]] = Field(default_factory=list)
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
    status: str = 'START'
