"""Durable phase contracts and graph boundaries."""
import pytest
from test_engine_integration import lifecycle


def roadmap(**changes):
    from council.phase_contract import PhaseRoadmap

    data = {
        'title': 'Audit trail',
        'architecture_summary': 'Read persisted audit history before displaying it.',
        'phases': [
            {'id': 'data', 'goal': 'Read historical rows', 'affected_services': ['ShipRateAPI'],
             'required_inputs': ['Existing schema'], 'delivered_contracts': ['Audit query'],
             'acceptance_outcomes': ['PostgreSQL read passes'], 'depends_on': [],
             'final_acceptance': False},
            {'id': 'ui', 'goal': 'Display audit history', 'affected_services': ['ShipRateAdmin'],
             'required_inputs': ['Audit query'], 'delivered_contracts': ['Audit screen'],
             'acceptance_outcomes': ['End to end audit flow passes'], 'depends_on': ['data'],
             'final_acceptance': True},
        ],
    }
    data.update(changes)
    return PhaseRoadmap.model_validate(data)


def test_roadmap_accepts_ordered_phases():
    from council.phase_contract import validate_roadmap

    result = validate_roadmap(roadmap())
    assert [phase.id for phase in result.phases] == ['data', 'ui']


@pytest.mark.parametrize('phases', [
    [],
    [{'id': 'only', 'goal': 'Work', 'affected_services': ['a'], 'required_inputs': [],
      'delivered_contracts': ['contract'], 'acceptance_outcomes': ['passed'],
      'depends_on': ['missing'], 'final_acceptance': True}],
])
def test_roadmap_rejects_missing_or_unknown_phase(phases):
    from council.phase_contract import validate_roadmap

    with pytest.raises(ValueError):
        validate_roadmap(roadmap(phases=phases))


def test_roadmap_rejects_forward_dependency():
    from council.phase_contract import validate_roadmap

    value = roadmap()
    value.phases[0].depends_on = ['ui']
    with pytest.raises(ValueError, match='predecessor'):
        validate_roadmap(value)


def test_roadmap_requires_final_acceptance_on_last_phase():
    from council.phase_contract import validate_roadmap

    value = roadmap()
    value.phases[0].final_acceptance = True
    with pytest.raises(ValueError, match='final'):
        validate_roadmap(value)


@pytest.mark.parametrize('code', ['GEMINI_RESPONSE_JSON_INVALID', 'GEMINI_TOOL_NAME_UNOFFERED'])
def test_roadmap_inspection_has_the_same_bounded_format_recovery_as_planning(lifecycle, monkeypatch, code):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.diagnostics import DiagnosticValueError
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT])
    state['orchestration_policy_version'] = 2
    value = roadmap()
    value.phases = value.phases[:1]
    value.phases[0].final_acceptance = True
    inspections = []
    def inspect(messages):
        inspections.append(messages)
        if len(inspections) == 1:
            raise DiagnosticValueError(code)
        return AIMessage(content='Observed enough evidence')
    provider.bind_tools = lambda _: SimpleNamespace(invoke=inspect)
    provider.with_structured_output = lambda schema, **kwargs: SimpleNamespace(invoke=lambda messages:
        {'parsed': lifecycle.plan if schema is MultiSpecialistPlan else value,
         'raw': AIMessage(content=''), 'parsing_error': None})
    with open_graph(lifecycle, provider) as saver:
        result = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider).invoke(state, lifecycle.config)
    assert result['status'] == 'COMPLETED'
    assert [call['operation'] for call in result['model_calls']][:2] == [
        'roadmap_inspection', 'roadmap_format_retry']
    assert code in inspections[1][-1]['content']


def test_two_phases_checkpoint_verified_work_before_next_plan(lifecycle, monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT, ACCEPT])
    state['orchestration_policy_version'] = 2
    state['max_steps'] = 400
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:1]
    plans[1].tasks = plans[1].tasks[1:]
    checks = []

    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                index = len(checks)
                if index == 1:
                    assert (lifecycle.workspace / 'target-1.txt').read_text() == 'valid'
                checks.append(index)
                provider.plan = plans[index]
                value = plans[index]
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)
        saved = graph.get_state(lifecycle.config).values

    assert result['status'] == 'COMPLETED'
    assert len(checks) == 2
    assert [item['id'] for item in saved['completed_phases']] == ['data', 'ui']
    assert [item['verified_task_ids'] for item in saved['completed_phases']] == [['task-1'], ['task-2']]
    assert reviewer.calls == 3


@pytest.mark.parametrize('tamper', [False, True])
def test_frozen_test_evidence_survives_phase_transition(lifecycle, monkeypatch, tamper):
    import hashlib
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT
    from test_engine_integration import open_graph

    frozen = lifecycle.workspace/'frozen.test.ts'
    frozen.write_bytes(b'accepted test source')
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT, ACCEPT])
    state.update(orchestration_policy_version=2, max_steps=400,
        red_phase_evidence=[dict(red_task_id='task-1', green_task_id='task-1', command_index=1,
            test_names=['accepted test'], source_hashes={'frozen.test.ts': digest}, closed=True)])
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:1]
    plans[1].tasks = plans[1].tasks[1:]
    generated = []
    def structured(schema, **kwargs):
        def invoke(messages):
            if schema is MultiSpecialistPlan:
                value = plans[len(generated)]
                generated.append(True)
                provider.plan = value
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)
    provider.with_structured_output = structured
    original_run = provider.run_task
    def run_task(task, guidance, **kwargs):
        response = original_run(task, guidance, **kwargs)
        if task.id == 'task-2' and tamper:
            frozen.write_bytes(b'weakened later')
        return response
    provider.run_task = run_task
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)
        saved = graph.get_state(lifecycle.config).values
    assert result['status'] == ('FAILED' if tamper else 'COMPLETED')
    assert saved['completed_red_phase_evidence'][0]['source_hashes'] == {'frozen.test.ts': digest}
    if tamper:
        assert result['diagnostic']['code'] == 'TDD_PHASE_INCOMPLETE'


def test_second_phase_block_preserves_first_phase_checkpoint_and_resume(lifecycle, monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT, ESCALATE
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT, ESCALATE, ACCEPT])
    state['orchestration_policy_version'] = 2
    state['max_steps'] = 400
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:1]
    plans[1].tasks = plans[1].tasks[1:]
    generated = 0

    def structured(schema, **kwargs):
        def invoke(messages):
            nonlocal generated
            if schema is MultiSpecialistPlan:
                index = min(generated, 1)
                generated += 1
                provider.plan = plans[index]
                value = plans[index]
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        blocked = graph.invoke(state, lifecycle.config)
        assert blocked['status'] == 'PLAN_BLOCKED'
        assert blocked['current_phase_index'] == 1
        assert [item['id'] for item in blocked['completed_phases']] == ['data']
        assert (lifecycle.workspace / 'target-1.txt').read_text() == 'valid'
        assert not (lifecycle.workspace / 'target-2.txt').exists()
        first_digest = blocked['completed_phases'][0]['accepted_plan_sha256']
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        resumed = graph.invoke(Command(resume={'feedback': 'The UI plan may use the completed audit query.'}), lifecycle.config)
        assert resumed['status'] == 'COMPLETED'
        assert resumed['completed_phases'][0]['accepted_plan_sha256'] == first_digest
        assert provider.attempts['task-1'] == 1


def test_roadmap_user_decision_blocks_before_phase_work(lifecycle, monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from test_autonomous_review import setup, ESCALATE
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [ESCALATE])
    state['orchestration_policy_version'] = 2
    provider.with_structured_output = lambda schema, **kwargs: SimpleNamespace(
        invoke=lambda messages: {'parsed': roadmap(), 'raw': AIMessage(content=''), 'parsing_error': None})
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)

    assert result['status'] == 'PLAN_BLOCKED'
    assert result['roadmap_review_findings'] == ESCALATE['findings']
    assert result['__interrupt__'][0].value['findings'] == ESCALATE['findings']
    assert result['current_phase_index'] == 0
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_new_cli_run_uses_phased_policy_by_default(lifecycle, monkeypatch, capsys):
    import json
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.cli import run_council_task
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT

    _, provider, reviewer = setup(lifecycle, monkeypatch, [
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
    ])
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:1]
    plans[1].tasks = plans[1].tasks[1:]
    generated = 0

    def structured(schema, **kwargs):
        def invoke(messages):
            nonlocal generated
            if schema is MultiSpecialistPlan:
                value = plans[generated]
                provider.plan = value
                generated += 1
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role, *args, **kwargs:
                        reviewer if role == 'reviewer' else provider)
    monkeypatch.setattr('council.cli.READINESS_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.GOVERNANCE_POLICY_VERSION', 1)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'codex-cli': True, 'gemini-cli': True})
    monkeypatch.setattr('council.cli.uuid.uuid4', lambda: SimpleNamespace(hex='phased-cli'))
    assert run_council_task(prompt='fixture', workspace_root=lifecycle.workspace,
                            council_root=lifecycle.context.council_root, no_input=True) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['orchestration_policy_version'] == 2
    assert [item['id'] for item in result['completed_phases']] == ['data', 'ui']
    assert result['status'] == 'COMPLETED'


def test_final_gate_refuses_missing_completed_phase_evidence(lifecycle, monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan
    from test_autonomous_review import setup, ACCEPT
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [ACCEPT, ACCEPT, ACCEPT])
    state['orchestration_policy_version'] = 2
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:1]
    plans[1].tasks = plans[1].tasks[1:]
    generated = 0

    def structured(schema, **kwargs):
        def invoke(messages):
            nonlocal generated
            if schema is MultiSpecialistPlan:
                value = plans[generated]
                provider.plan = value
                generated += 1
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        paused = graph.invoke(state, lifecycle.config, interrupt_before=['gatekeeper'])
        assert len(paused['completed_phases']) == 2
        graph.update_state(lifecycle.config, {'completed_phases': paused['completed_phases'][:1]})
        result = graph.invoke(None, lifecycle.config)

    assert result['status'] == 'FAILED'
    assert result['diagnostic']['code'] == 'PLAN_ACCEPTANCE_INVALID'


def test_oversized_phase_plan_returns_for_revision(lifecycle):
    from council.graph import the_architect_node
    from council.phase_contract import roadmap_digest
    from test_engine_integration import ScriptedProvider

    state = lifecycle.state.model_copy(deep=True)
    state.orchestration_policy_version = 2
    state.roadmap = roadmap()
    state.accepted_roadmap_sha256 = roadmap_digest(state.roadmap)
    plan = lifecycle.plan.model_copy(deep=True)
    plan.tasks = [plan.tasks[0].model_copy(deep=True, update={'id': f'task-{index}'}) for index in range(13)]
    result = the_architect_node(state, lambda role: ScriptedProvider(plan))
    assert result.status == 'PLAN_REVISION'
    assert result.plan_review_findings == ['Current phase plan exceeds 12 tasks.']


def test_two_phases_with_real_readiness_prefixes(lifecycle, monkeypatch):
    import sys
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from council.state import MultiSpecialistPlan, TaskItem
    from test_graph_readiness import prepared
    from test_engine_integration import open_graph

    state, provider, reviewer = prepared(lifecycle, monkeypatch)
    state['orchestration_policy_version'] = 2
    state['review_protocol_version'] = 2
    reviewer.decisions = iter([
        {'decision': 'accept', 'findings': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
        {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []},
    ])
    plans = [lifecycle.plan.model_copy(deep=True), lifecycle.plan.model_copy(deep=True)]
    plans[0].tasks = plans[0].tasks[:2]
    plans[0].tasks[0].readiness_for = ['task-1']
    setup_two = TaskItem(id='setup-two', specialist='the-coder', description='Prepare UI prerequisite',
        kind='readiness', readiness_for=['task-2'], target_files=['prerequisite2.txt'],
        acceptance_criteria=['UI prerequisite is readable'],
        test_commands=[[sys.executable, 'verify.py', 'prerequisite2.txt']])
    plans[1].tasks = [setup_two, plans[1].tasks[2]]
    generated = 0

    def structured(schema, **kwargs):
        def invoke(messages):
            nonlocal generated
            if schema is MultiSpecialistPlan:
                value = plans[generated]
                provider.plan = value
                generated += 1
            else:
                value = roadmap()
            return {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None}
        return SimpleNamespace(invoke=invoke)

    provider.with_structured_output = structured
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)

    assert result['status'] == 'COMPLETED'
    assert [item['task_id'] for item in result['test_results']] == [
        'setup', 'task-1', 'setup-two', 'task-2']
    assert [item['id'] for item in result['completed_phases']] == ['data', 'ui']


def test_roadmap_review_budget_blocks_without_workers(lifecycle, monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from council.graph import build_council_graph
    from test_autonomous_review import setup, REVISE
    from test_engine_integration import open_graph

    state, provider, reviewer = setup(lifecycle, monkeypatch, [REVISE] * 4)
    state['orchestration_policy_version'] = 2
    provider.with_structured_output = lambda schema, **kwargs: SimpleNamespace(
        invoke=lambda messages: {'parsed': roadmap(), 'raw': AIMessage(content=''), 'parsing_error': None})
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context,
            llm_factory=lambda role: reviewer if role == 'reviewer' else provider)
        result = graph.invoke(state, lifecycle.config)

    assert result['status'] == 'PLAN_BLOCKED'
    assert result['roadmap_review_count'] == 4
    assert result['roadmap_revision_count'] == 3
    assert provider.attempts == {}


def test_phase_review_limits_are_per_phase():
    from council.plan_review import review_limits
    from council.state import CouncilState

    state = CouncilState(run_id='phased-limits', task_input='feature',
                         orchestration_policy_version=2, review_protocol_version=2)
    assert review_limits(state) == (4, 3)
    state.strategy_reset_count = 1
    assert review_limits(state) == (6, 4)
