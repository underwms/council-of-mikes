"""Independent lifecycle integration: native LangGraph and durable SQLite only."""
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def test_graph_accepts_explicit_runtime_and_provider_boundary():
    from council.graph import build_council_graph

    parameters = inspect.signature(build_council_graph).parameters
    assert "context" in parameters, "Native graph must bind the validated workspace context"
    assert "llm_factory" in parameters, "Network provider boundary must be injectable"


class ScriptedProvider:
    """External provider double; all graph, tools, subprocesses and DB stay real."""

    def __init__(self, plan, contents=None):
        self.plan = plan
        self.contents = contents or {}
        self.attempts = {}

    def with_structured_output(self, schema):
        return SimpleNamespace(invoke=lambda messages: self.plan)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if isinstance(messages, str):
            return AIMessage(content="Inspect the actual subprocess exit code and repair its target.")
        if messages and isinstance(messages[-1], ToolMessage):
            return AIMessage(content="Task work finished; run the declared verification command.")
        text = " ".join(str(getattr(item, "content", item)) for item in messages)
        for task in self.plan.tasks:
            if task.description in text:
                attempt = self.attempts.get(task.id, 0)
                self.attempts[task.id] = attempt + 1
                versions = self.contents.get(task.id, ["valid"])
                content = versions[min(attempt, len(versions) - 1)]
                return AIMessage(content="", tool_calls=[{
                    "name": "write_workspace_file", "args": {
                        "rel_path": task.target_files[0], "content": content},
                    "id": f"{task.id}-{attempt}", "type": "tool_call"}])
        return AIMessage(content="No tools required.")


@pytest.fixture
def lifecycle(tmp_path):
    from council.runtime_context import RuntimeContext
    from council.state import CouncilState, MultiSpecialistPlan, TaskItem

    council_root = tmp_path / "installed council"
    workspace = tmp_path / "developer workspace"
    memory = council_root / "memory"
    workspace.mkdir()
    memory.mkdir(parents=True)
    (council_root / "manifest.json").write_text(json.dumps({"specialists": []}), encoding="utf-8")
    skill = council_root / "skills" / "the-coder"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: the-coder\ndescription: Coding\n---\n# [THE CODER]\nPerform declared task.\n", encoding="utf-8")
    context = RuntimeContext(council_root, workspace, memory)
    scripts = workspace / "scripts"
    scripts.mkdir()
    (scripts / "validate_workspace.py").write_text(
        "import argparse\nfrom pathlib import Path\n"
        "parser=argparse.ArgumentParser()\nparser.add_argument('workspace')\n"
        "args=parser.parse_args()\nassert Path(args.workspace).resolve() == Path.cwd().resolve()\n"
        "print('Fixture workspace audit passed')\n", encoding="utf-8")
    (workspace / "verify.py").write_text(
        "from pathlib import Path\nimport sys\n"
        "valid = Path(sys.argv[1]).read_text() == 'valid'\n"
        "print('Passed: 1 Failed: 0' if valid else 'Passed: 0 Failed: 1')\n"
        "sys.exit(0 if valid else 7)\n", encoding="utf-8")
    tasks = [TaskItem(id=f"task-{number}", specialist="the-coder",
        description=f"Implement unique integration target {number}",
        target_files=[f"target-{number}.txt"], acceptance_criteria=["Verification exits zero"],
        test_commands=[[sys.executable, "verify.py", f"target-{number}.txt"]],
        working_directory=".") for number in (1, 2)]
    plan = MultiSpecialistPlan(title="Integration lifecycle", architecture_summary="Two independent tasks", tasks=tasks)
    state = CouncilState(run_id="integration-run", task_input="Implement the two fixture targets",
                         thread_id="integration-run", max_steps=100,
                         workspace_root=str(workspace.resolve()), council_root=str(council_root.resolve()),
                         memory_root=str(memory.resolve()))
    return SimpleNamespace(context=context, workspace=workspace, plan=plan, state=state,
                           db=memory / "integration.sqlite", config={"configurable": {"thread_id": state.thread_id}, "recursion_limit": 100})


def open_graph(fixture, provider):
    from council.checkpoint import managed_sqlite_checkpointer
    return managed_sqlite_checkpointer(context=fixture.context, db_path=fixture.db)


def build(fixture, saver, provider):
    from council.graph import build_council_graph
    return build_council_graph(checkpointer=saver, context=fixture.context,
                               llm_factory=lambda role: provider)


def assert_gate(result, name):
    interrupts = result.get("__interrupt__", ())
    assert interrupts, f"Expected durable {name} approval pause, got {result.get('status')}"
    assert interrupts[0].value["gate"] == name


def test_gate_one_denial_stops_before_any_workspace_write(lifecycle):
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        paused = graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(paused, "GATE_1_PLAN_APPROVAL")
        assert not list(lifecycle.workspace.glob("target-*.txt"))
        denied = graph.invoke(Command(resume={"approved": False}), lifecycle.config)
        assert denied["status"] == "FAILED"
        assert not list(lifecycle.workspace.glob("target-*.txt"))
        assert graph.get_state(lifecycle.config).next == ()


@pytest.mark.parametrize("approved", [True, False])
def test_sqlite_restart_multitask_gate_two_decision(lifecycle, approved):
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        paused = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(paused, "GATE_1_PLAN_APPROVAL")
    assert lifecycle.db.stat().st_size > 0
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        paused = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert_gate(paused, "GATE_2_PRE_SUBMIT_APPROVAL")
        assert all((lifecycle.workspace / file).read_text() == "valid" for file in ["target-1.txt", "target-2.txt"])
        assert [task["status"] for task in paused["plan"]["tasks"]] == ["completed", "completed"]
        assert paused["test_result"]["exit_code"] == 0
        assert paused["test_result"]["tests_passed"] == 1
        assert paused["workspace_root"] == str(lifecycle.workspace.resolve())
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        result = graph.invoke(Command(resume={"approved": approved}), lifecycle.config)
        assert result["status"] == ("COMPLETED" if approved else "FAILED")
        assert graph.get_state(lifecycle.config).next == ()


def test_real_subprocess_failure_is_repaired_before_gate_two(lifecycle):
    provider = ScriptedProvider(lifecycle.plan, {"task-1": ["broken", "valid"]})
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert_gate(result, "GATE_2_PRE_SUBMIT_APPROVAL")
        assert provider.attempts["task-1"] == 2
        assert (lifecycle.workspace / "target-1.txt").read_text() == "valid"
        evidence = [item for item in result["test_results"] if item["task_id"] == "task-1"]
        assert [item["exit_code"] for item in evidence] == [7, 0]
        assert [item["tests_failed"] for item in evidence] == [1, 0]


def test_repeat_subprocess_failure_exhausts_bounded_retries(lifecycle):
    lifecycle.state.max_test_retries = 2
    provider = ScriptedProvider(lifecycle.plan, {"task-1": ["broken"]})
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["test_result"]["exit_code"] == 7
        assert result["test_result"]["tests_failed"] == 1
        assert provider.attempts["task-1"] <= 3
        assert not (lifecycle.workspace / "target-2.txt").exists()
        assert graph.get_state(lifecycle.config).next == ()


def test_missing_provider_fails_without_fabricating_plan_or_success(lifecycle):
    from council.graph import build_council_graph
    def unavailable(role):
        raise RuntimeError("Missing provider credentials")
    with open_graph(lifecycle, None) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context, llm_factory=unavailable)
        result = graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["plan"] is None
        assert result["test_result"] is None
        assert not list(lifecycle.workspace.glob("target-*.txt"))


def test_missing_verification_command_cannot_reach_approval(lifecycle):
    lifecycle.plan.tasks[0].test_commands = []
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert result["status"] == "FAILED"
        assert not result.get("__interrupt__")
        assert not list(lifecycle.workspace.glob("target-*.txt"))


def test_workspace_validator_nonzero_prevents_final_approval(lifecycle):
    (lifecycle.workspace / "scripts" / "validate_workspace.py").write_text("import sys\nsys.exit(9)\n", encoding="utf-8")
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["workspace_validator_passed"] is False
        assert not result.get("__interrupt__")


def test_unavailable_tool_fails_without_fabricated_test_results(lifecycle):
    class UnknownToolProvider(ScriptedProvider):
        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[{"name": "nonexistent_tool", "args": {}, "id": "unknown", "type": "tool_call"}])
    provider = UnknownToolProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["test_result"] is None
        assert not list(lifecycle.workspace.glob("target-*.txt"))


def test_restart_refuses_changed_workspace_identity(lifecycle):
    from council.runtime_context import RuntimeContext
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
    original = lifecycle.workspace
    other = original.parent / "different workspace"
    other.mkdir()
    lifecycle.context = RuntimeContext(lifecycle.context.council_root, other, lifecycle.context.memory_root)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        with pytest.raises(ValueError, match="identity|workspace"):
            graph.invoke(Command(resume={"approved": True}), lifecycle.config)
    assert not list(original.glob("target-*.txt"))
    assert not list(other.iterdir())


@pytest.mark.parametrize("decision", [{}, {"approved": "true"}, {"approved": 1}, True])
def test_ambiguous_gate_decision_never_authorizes_writes(lifecycle, decision):
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume=decision), lifecycle.config)
        # Native LangGraph treats {} as an empty interrupt-ID resume map.
        # Its safe outcome is a retained pause, with no authorization delivered.
        assert result["status"] == ("PLAN_REVIEW" if decision == {} else "FAILED")
        if decision == {}:
            assert_gate(result, "GATE_1_PLAN_APPROVAL")
        assert not list(lifecycle.workspace.glob("target-*.txt"))


def test_file_tool_exception_cannot_report_success(lifecycle):
    class EscapingProvider(ScriptedProvider):
        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[{"name": "write_workspace_file",
                "args": {"rel_path": "../escaped.txt", "content": "unauthorized"},
                "id": "escape", "type": "tool_call"}])
    provider = EscapingProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["test_result"] is None
        assert not (lifecycle.workspace.parent / "escaped.txt").exists()
        assert result["tool_call_history"] == []


def test_graph_step_limit_terminates_before_worker(lifecycle):
    lifecycle.state.max_steps = 1
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        result = graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert result["status"] == "FAILED"
        assert not list(lifecycle.workspace.glob("target-*.txt"))
        assert graph.get_state(lifecycle.config).next == ()


def test_three_identical_verification_failures_stop_for_root_cause_reassessment(lifecycle):
    provider = ScriptedProvider(lifecycle.plan, {"task-1": ["broken"]})
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert provider.attempts["task-1"] <= 3, "Identical verification failure must trigger reassessment after three executions"


def test_later_successful_command_does_not_hide_first_verification_failure(lifecycle):
    lifecycle.state.max_test_retries = 0
    lifecycle.plan.tasks[0].test_commands.append([sys.executable, "-c", "print('Passed: 2 Failed: 0')"])
    provider = ScriptedProvider(lifecycle.plan, {"task-1": ["broken"]})
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert [item["exit_code"] for item in result["test_results"]] == [7, 0]
        assert result["test_result"]["exit_code"] == 7, "Diagnostic result must retain the failed command rather than the last successful command"
        assert result["test_result"]["tests_failed"] == 1


def test_provider_failure_never_persists_exception_secret(lifecycle):
    marker = "secret_marker_xyz"
    class FailingProvider(ScriptedProvider):
        def invoke(self, messages):
            raise RuntimeError(marker)
    provider = FailingProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert marker not in json.dumps(result)
        assert result["test_result"] is None
        for snapshot in graph.get_state_history(lifecycle.config):
            assert marker not in json.dumps(snapshot.values)
            assert marker not in repr(snapshot.tasks)
        assert not list(lifecycle.workspace.glob("target-*.txt"))
    assert marker.encode() not in lifecycle.db.read_bytes()


def test_preexisting_plan_is_validated_without_new_planner_request(lifecycle):
    lifecycle.state.plan = lifecycle.plan
    provider = ScriptedProvider(lifecycle.plan)
    provider.with_structured_output = lambda schema: pytest.fail("Existing plan must not be regenerated")
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(result, "GATE_1_PLAN_APPROVAL")
        assert result["plan"]["title"] == lifecycle.plan.title
        assert not list(lifecycle.workspace.glob("target-*.txt"))


@pytest.mark.parametrize("invalid", ["unknown-specialist", "empty-argv"])
def test_invalid_plan_is_rejected_before_work(lifecycle, invalid):
    if invalid == "unknown-specialist":
        lifecycle.plan.tasks[0].specialist = "nonexistent-specialist"
    else:
        lifecycle.plan.tasks[0].test_commands = [[""]]
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert result["status"] == "FAILED"
        assert not result.get("__interrupt__")
        assert not list(lifecycle.workspace.glob("target-*.txt"))


def test_failed_patch_tool_cannot_be_recorded_as_success(lifecycle):
    for number in (1, 2):
        (lifecycle.workspace / f"target-{number}.txt").write_text("valid", encoding="utf-8")
    class FailedPatchProvider(ScriptedProvider):
        def invoke(self, messages):
            if messages and isinstance(messages[-1], ToolMessage):
                return AIMessage(content="Finished")
            return AIMessage(content="", tool_calls=[{"name": "patch_workspace_file",
                "args": {"rel_path": "target-1.txt", "old_string": "absent-match", "new_string": "replacement"},
                "id": "patch", "type": "tool_call"}])
    provider = FailedPatchProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED", "A patch with no matching text is a failed operation"
        assert result["tool_call_history"] == []
        assert result["test_result"] is None


def test_provider_receives_correlated_real_tool_result(lifecycle):
    receipts = []
    class ReceiptProvider(ScriptedProvider):
        def invoke(self, messages):
            if messages and isinstance(messages[-1], ToolMessage):
                receipts.append(messages[-1])
            return super().invoke(messages)
    provider = ReceiptProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert_gate(result, "GATE_2_PRE_SUBMIT_APPROVAL")
        assert [message.tool_call_id for message in receipts] == ["task-1-0", "task-2-0"]
        assert all("Successfully wrote" in message.content for message in receipts)


def test_twelve_tool_round_limit_stops_real_read_loop(lifecycle):
    for index in range(12):
        (lifecycle.workspace / f"read-{index}.txt").write_text("fixture", encoding="utf-8")
    class ReadLoopProvider(ScriptedProvider):
        rounds = 0
        def invoke(self, messages):
            index = self.rounds
            self.rounds += 1
            return AIMessage(content="", tool_calls=[{"name": "read_workspace_file",
                "args": {"rel_path": f"read-{index}.txt"}, "id": f"read-{index}", "type": "tool_call"}])
    provider = ReadLoopProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert provider.rounds == 12
        assert len(result["tool_call_history"]) == 12
        assert result["test_result"] is None


def test_missing_investigator_diagnosis_stops_repair(lifecycle):
    class EmptyDiagnosisProvider(ScriptedProvider):
        def invoke(self, messages):
            if isinstance(messages, str):
                return AIMessage(content="")
            return super().invoke(messages)
    provider = EmptyDiagnosisProvider(lifecycle.plan, {"task-1": ["broken", "valid"]})
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert result["test_result"]["exit_code"] == 7
        assert provider.attempts["task-1"] == 1


def test_escalation_provider_is_selected_only_after_second_failure(lifecycle, monkeypatch):
    from council.graph import build_council_graph
    monkeypatch.setenv("COUNCIL_ENABLE_ESCALATION", "true")
    provider = ScriptedProvider(lifecycle.plan, {"task-1": ["broken", "broken", "valid"]})
    roles = []
    def factory(role):
        roles.append(role)
        return provider
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context, llm_factory=factory)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert_gate(result, "GATE_2_PRE_SUBMIT_APPROVAL")
        assert roles == ["orchestrator", "orchestrator", "investigator", "orchestrator", "investigator", "escalation", "orchestrator"]
        assert [entry["exit_code"] for entry in result["test_results"]] == [7, 7, 0, 0]


def test_unknown_test_counts_remain_unknown(lifecycle):
    for task in lifecycle.plan.tasks:
        task.test_commands = [[sys.executable, "-c", "print('Uncounted verification succeeded')"]]
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert_gate(result, "GATE_2_PRE_SUBMIT_APPROVAL")
        assert result["test_result"]["counts_known"] is False
        assert result["test_result"]["tests_passed"] is None
        assert result["test_result"]["tests_failed"] is None


def test_uncorrelatable_provider_tool_call_is_rejected_before_write(lifecycle):
    class MissingCallIdProvider(ScriptedProvider):
        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[{"name": "write_workspace_file",
                "args": {"rel_path": "target-1.txt", "content": "valid"},
                "id": None, "type": "tool_call"}])
    provider = MissingCallIdProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), "GATE_1_PLAN_APPROVAL")
        result = graph.invoke(Command(resume={"approved": True}), lifecycle.config)
        assert result["status"] == "FAILED"
        assert not (lifecycle.workspace / "target-1.txt").exists(), "Invalid tool call IDs must be rejected before tool side effects"
        assert result["tool_call_history"] == []
