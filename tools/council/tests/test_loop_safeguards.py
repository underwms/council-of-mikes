import sys
import tempfile
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.state import CouncilState, MultiSpecialistPlan, TaskItem, TestExecutionResult
from council.graph import build_council_graph, evaluate_tests_edge
from council.tools.file_tools import FileTools

def test_hard_step_ceiling_aborts_infinite_loop():
    graph = build_council_graph()
    
    # State with max_steps = 5
    state = CouncilState(
        run_id="test-ceiling",
        task_input="Infinite loop test",
        max_steps=5,
        status="PLANNING"
    )
    
    completed = graph.run_until_complete(state)
    assert completed.step_count > 0
    # Should stop cleanly within max_steps limits
    assert completed.step_count <= 6

def test_consecutive_identical_error_fingerprint():
    task = TaskItem(id="1", specialist="the-coder", description="Task 1")
    plan = MultiSpecialistPlan(title="T", architecture_summary="A", tasks=[task])
    
    state = CouncilState(
        run_id="test-fingerprint",
        task_input="Test",
        plan=plan,
        test_retry_count=2,
        max_test_retries=3,
        last_error_hash=None,
        test_result=TestExecutionResult(
            command="dotnet test",
            passed=False,
            exit_code=1,
            compiler_errors=["CS0246: Missing type"]
        )
    )
    
    # First failure hashes the error
    route1 = evaluate_tests_edge(state)
    assert route1 == "retry"
    assert state.last_error_hash is not None
    
    # Second failure with exact same error triggers human_escalation
    state.test_retry_count = 2
    route2 = evaluate_tests_edge(state)
    assert route2 == "human_escalation", f"Expected human_escalation, got {route2}"

def test_repetitive_tool_call_circuit_breaker():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tools = FileTools(Path(tmp_dir))
        tools.write_file("file.txt", "content")
        
        # 2 identical reads succeed
        tools.read_file("file.txt")
        tools.read_file("file.txt")
        
        # 3rd identical consecutive read trips circuit breaker
        try:
            tools.read_file("file.txt")
            assert False, "Should have raised RuntimeError for repetitive tool calls"
        except RuntimeError as e:
            assert "Loop detected" in str(e)

if __name__ == "__main__":
    test_hard_step_ceiling_aborts_infinite_loop()
    test_consecutive_identical_error_fingerprint()
    test_repetitive_tool_call_circuit_breaker()
    print("[PASS] test_loop_safeguards passed successfully")
