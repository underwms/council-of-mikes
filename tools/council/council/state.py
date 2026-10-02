"""State schema models for Council Autonomous Orchestrator.
Supports both Pydantic v2 and Python standard library fallback for zero-dep environments.
"""
import json
from typing import Literal, Optional, List, Dict, Any

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

if HAS_PYDANTIC:
    class TaskItem(BaseModel):
        id: str
        specialist: str
        description: str
        target_files: List[str] = Field(default_factory=list)
        acceptance_criteria: List[str] = Field(default_factory=list)
        status: Literal["pending", "in_progress", "completed", "failed"] = "pending"

    class MultiSpecialistPlan(BaseModel):
        title: str
        architecture_summary: str
        affected_services: List[str] = Field(default_factory=list)
        tasks: List[TaskItem] = Field(default_factory=list)

    class TestExecutionResult(BaseModel):
        command: str
        passed: bool
        exit_code: int
        tests_passed: int = 0
        tests_failed: int = 0
        compiler_errors: List[str] = Field(default_factory=list)
        failure_output: str = ""

    class CouncilState(BaseModel):
        run_id: str
        task_input: str
        auto_approve: bool = False
        model_name: str = "gemini"
        plan: Optional[MultiSpecialistPlan] = None
        current_task_index: int = 0
        active_specialist: str = "the-architect"
        modified_files: List[str] = Field(default_factory=list)
        test_result: Optional[TestExecutionResult] = None
        test_retry_count: int = 0
        max_test_retries: int = 3
        step_count: int = 0
        max_steps: int = 30
        last_error_hash: Optional[str] = None
        workspace_validator_passed: bool = False
        gatekeeper_summary: Dict[str, Any] = Field(default_factory=dict)
        messages: List[Any] = Field(default_factory=list)
        status: Literal[
            "START", "PLANNING", "PLAN_REVIEW", "EXECUTING", 
            "TESTING", "RETRYING", "PURIFYING", "GATEKEEPER_AUDIT", 
            "FINAL_REVIEW", "COMPLETED", "FAILED"
        ] = "START"

else:
    class _BaseModel:
        def model_dump(self) -> Dict[str, Any]:
            res = {}
            for k, v in self.__dict__.items():
                if isinstance(v, _BaseModel):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [item.model_dump() if isinstance(item, _BaseModel) else item for item in v]
                else:
                    res[k] = v
            return res

        def model_dump_json(self) -> str:
            return json.dumps(self.model_dump(), default=str)

        @classmethod
        def model_validate_json(cls, json_str: str):
            data = json.loads(json_str)
            return cls._from_dict(data)

        @classmethod
        def _from_dict(cls, data: Dict[str, Any]):
            return cls(**data)

    class TaskItem(_BaseModel):
        def __init__(
            self,
            id: str,
            specialist: str,
            description: str,
            target_files: Optional[List[str]] = None,
            acceptance_criteria: Optional[List[str]] = None,
            status: str = "pending"
        ):
            self.id = id
            self.specialist = specialist
            self.description = description
            self.target_files = target_files or []
            self.acceptance_criteria = acceptance_criteria or []
            self.status = status

    class MultiSpecialistPlan(_BaseModel):
        def __init__(
            self,
            title: str,
            architecture_summary: str,
            affected_services: Optional[List[str]] = None,
            tasks: Optional[List[Any]] = None
        ):
            self.title = title
            self.architecture_summary = architecture_summary
            self.affected_services = affected_services or []
            self.tasks = []
            if tasks:
                for t in tasks:
                    if isinstance(t, dict):
                        self.tasks.append(TaskItem._from_dict(t))
                    else:
                        self.tasks.append(t)

        @classmethod
        def _from_dict(cls, data: Dict[str, Any]):
            tasks_data = [TaskItem._from_dict(t) if isinstance(t, dict) else t for t in data.get("tasks", [])]
            return cls(
                title=data.get("title", ""),
                architecture_summary=data.get("architecture_summary", ""),
                affected_services=data.get("affected_services", []),
                tasks=tasks_data
            )

    class TestExecutionResult(_BaseModel):
        def __init__(
            self,
            command: str,
            passed: bool,
            exit_code: int,
            tests_passed: int = 0,
            tests_failed: int = 0,
            compiler_errors: Optional[List[str]] = None,
            failure_output: str = ""
        ):
            self.command = command
            self.passed = passed
            self.exit_code = exit_code
            self.tests_passed = tests_passed
            self.tests_failed = tests_failed
            self.compiler_errors = compiler_errors or []
            self.failure_output = failure_output

    class CouncilState(_BaseModel):
        def __init__(
            self,
            run_id: str,
            task_input: str,
            auto_approve: bool = False,
            model_name: str = "gemini",
            plan: Optional[Any] = None,
            current_task_index: int = 0,
            active_specialist: str = "the-architect",
            modified_files: Optional[List[str]] = None,
            test_result: Optional[Any] = None,
            test_retry_count: int = 0,
            max_test_retries: int = 3,
            step_count: int = 0,
            max_steps: int = 30,
            last_error_hash: Optional[str] = None,
            workspace_validator_passed: bool = False,
            gatekeeper_summary: Optional[Dict[str, Any]] = None,
            messages: Optional[List[Any]] = None,
            status: str = "START"
        ):
            self.run_id = run_id
            self.task_input = task_input
            self.auto_approve = auto_approve
            self.model_name = model_name
            if isinstance(plan, dict):
                self.plan = MultiSpecialistPlan._from_dict(plan)
            else:
                self.plan = plan
            self.current_task_index = current_task_index
            self.active_specialist = active_specialist
            self.modified_files = modified_files or []
            if isinstance(test_result, dict):
                self.test_result = TestExecutionResult(**test_result)
            else:
                self.test_result = test_result
            self.test_retry_count = test_retry_count
            self.max_test_retries = max_test_retries
            self.step_count = step_count
            self.max_steps = max_steps
            self.last_error_hash = last_error_hash
            self.workspace_validator_passed = workspace_validator_passed
            self.gatekeeper_summary = gatekeeper_summary or {}
            self.messages = messages or []
            self.status = status

        @classmethod
        def _from_dict(cls, data: Dict[str, Any]):
            plan_data = data.get("plan")
            if plan_data and isinstance(plan_data, dict):
                plan_data = MultiSpecialistPlan._from_dict(plan_data)
            test_res = data.get("test_result")
            if test_res and isinstance(test_res, dict):
                test_res = TestExecutionResult(**test_res)
            
            return cls(
                run_id=data.get("run_id", ""),
                task_input=data.get("task_input", ""),
                auto_approve=data.get("auto_approve", False),
                model_name=data.get("model_name", "gemini"),
                plan=plan_data,
                current_task_index=data.get("current_task_index", 0),
                active_specialist=data.get("active_specialist", "the-architect"),
                modified_files=data.get("modified_files", []),
                test_result=test_res,
                test_retry_count=data.get("test_retry_count", 0),
                max_test_retries=data.get("max_test_retries", 3),
                step_count=data.get("step_count", 0),
                max_steps=data.get("max_steps", 30),
                last_error_hash=data.get("last_error_hash", None),
                workspace_validator_passed=data.get("workspace_validator_passed", False),
                gatekeeper_summary=data.get("gatekeeper_summary", {}),
                messages=data.get("messages", []),
                status=data.get("status", "START")
            )
