import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.state import CouncilState, MultiSpecialistPlan, TaskItem, TestExecutionResult
from council.graph import (
    build_council_graph,
    the_architect_node,
    evaluate_tests_edge,
    retry_node,
    specialist_router_node
)

def test_the_architect_node_creates_plan():
    state = CouncilState(
        run_id="test-run-1",
        task_input="Implement ORDER-185: Add distance_unit to shipping rate query"
    )
    new_state = the_architect_node(state)
    assert new_state.plan is not None
    assert len(new_state.plan.tasks) > 0
    assert new_state.status == "PLAN_REVIEW"

def test_evaluate_tests_edge_routes_to_retry_on_failure():
    task = TaskItem(id="1", specialist="the-coder", description="Task 1")
    plan = MultiSpecialistPlan(title="T", architecture_summary="A", tasks=[task])
    
    state = CouncilState(
        run_id="test-run-2",
        task_input="Test",
        plan=plan,
        test_retry_count=0,
        max_test_retries=3,
        test_result=TestExecutionResult(
            command="dotnet test",
            passed=False,
            exit_code=1,
            compiler_errors=["error CS0246: The type or namespace 'XYZ' could not be found"]
        )
    )
    
    route = evaluate_tests_edge(state)
    assert route == "retry", f"Expected 'retry', got {route}"
    
    retried_state = retry_node(state)
    assert retried_state.test_retry_count == 1
    assert retried_state.status == "RETRYING"

def test_evaluate_tests_edge_escalates_after_max_retries():
    task = TaskItem(id="1", specialist="the-coder", description="Task 1")
    plan = MultiSpecialistPlan(title="T", architecture_summary="A", tasks=[task])
    
    state = CouncilState(
        run_id="test-run-3",
        task_input="Test",
        plan=plan,
        test_retry_count=3,
        max_test_retries=3,
        test_result=TestExecutionResult(
            command="dotnet test",
            passed=False,
            exit_code=1
        )
    )
    
    route = evaluate_tests_edge(state)
    assert route == "human_escalation", f"Expected 'human_escalation', got {route}"

def test_evaluate_tests_edge_advances_on_success():
    task1 = TaskItem(id="1", specialist="the-coder", description="Task 1")
    task2 = TaskItem(id="2", specialist="the-prover", description="Task 2")
    plan = MultiSpecialistPlan(title="T", architecture_summary="A", tasks=[task1, task2])
    
    state = CouncilState(
        run_id="test-run-4",
        task_input="Test",
        plan=plan,
        current_task_index=0,
        test_result=TestExecutionResult(command="dotnet test", passed=True, exit_code=0)
    )
    
    route = evaluate_tests_edge(state)
    assert route == "next_task", f"Expected 'next_task', got {route}"

def test_graph_compilation():
    graph = build_council_graph()
    assert graph is not None

if __name__ == "__main__":
    test_the_architect_node_creates_plan()
    test_evaluate_tests_edge_routes_to_retry_on_failure()
    test_evaluate_tests_edge_escalates_after_max_retries()
    test_evaluate_tests_edge_advances_on_success()
    test_graph_compilation()
    print("[PASS] test_graph passed successfully")
