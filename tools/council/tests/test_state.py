import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.state import CouncilState, MultiSpecialistPlan, TaskItem, TestExecutionResult

def test_state_serialization():
    task = TaskItem(
        id="task-1",
        specialist="the-coder",
        description="Add DistanceUnit to RatesQueryRequest",
        target_files=["Application/Rates/RatesQueryRequest.cs"],
        acceptance_criteria=["Must compile cleanly"]
    )
    plan = MultiSpecialistPlan(
        title="ORDER-185",
        architecture_summary="Add distance unit to request",
        affected_services=["orderapi"],
        tasks=[task]
    )
    state = CouncilState(
        run_id="run-001",
        task_input="Implement ORDER-185",
        plan=plan
    )
    json_data = state.model_dump_json()
    restored = CouncilState.model_validate_json(json_data)
    
    assert restored.run_id == "run-001"
    assert restored.status == "START"
    assert restored.max_test_retries == 3
    assert restored.plan is not None
    assert len(restored.plan.tasks) == 1
    assert restored.plan.tasks[0].specialist == "the-coder"

def test_test_execution_result_serialization():
    res = TestExecutionResult(
        command="dotnet test",
        passed=True,
        exit_code=0,
        tests_passed=118,
        tests_failed=0,
        compiler_errors=[]
    )
    assert res.passed is True
    assert res.tests_passed == 118

if __name__ == "__main__":
    test_state_serialization()
    test_test_execution_result_serialization()
    print("[PASS] test_state passed successfully")
