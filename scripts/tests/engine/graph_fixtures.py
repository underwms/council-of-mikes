"""Explicit policy fixtures over shared, policy-neutral graph resources."""

import json
import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from council.phase_contract import Phase, PhaseRoadmap
from council.runtime_context import RuntimeContext
from council.state import CouncilState, MultiSpecialistPlan, TaskItem


# These are declared test contracts, not values derived from production defaults.
# test_fixture_policies compares the current contract with actual CLI startup.
CURRENT_AUTONOMOUS_POLICIES = {
    'review_protocol_version': 2,
    'revision_evidence_policy_version': 2,
    'readiness_policy_version': 3,
    'orchestration_policy_version': 2,
    'graph_integrity_policy_version': 2,
    'governance_policy_version': 2,
}
LEGACY_POLICIES = {field: 1 for field in CURRENT_AUTONOMOUS_POLICIES}
MONOLITHIC_INTEGRITY_POLICIES = {
    **LEGACY_POLICIES, 'review_protocol_version': 2, 'graph_integrity_policy_version': 2,
}


@pytest.fixture
def graph_workspace(tmp_path):
    """Real files, verifier, context and SQLite location; no policy selected."""
    council_root = tmp_path / 'installed council'
    workspace = tmp_path / 'developer workspace'
    memory = council_root / 'memory'
    workspace.mkdir()
    memory.mkdir(parents=True)
    (council_root / 'manifest.json').write_text(json.dumps({'specialists': ['the-coder']}), encoding='utf-8')
    skill = council_root / 'skills' / 'the-coder'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text(
        '---\nname: the-coder\ndescription: Coding\n---\n# [THE CODER]\nPerform declared task.\n', encoding='utf-8')
    context = RuntimeContext(council_root, workspace, memory)
    scripts = workspace / 'scripts'
    scripts.mkdir()
    (scripts / 'validate_workspace.py').write_text(
        'import argparse\nfrom pathlib import Path\n'
        "parser=argparse.ArgumentParser()\nparser.add_argument('workspace')\n"
        'args=parser.parse_args()\nassert Path(args.workspace).resolve() == Path.cwd().resolve()\n'
        "print('Fixture workspace audit passed')\n", encoding='utf-8')
    (workspace / 'verify.py').write_text(
        'from pathlib import Path\nimport sys\n'
        "valid = Path(sys.argv[1]).read_text() == 'valid'\n"
        "print('Passed: 1 Failed: 0' if valid else 'Passed: 0 Failed: 1')\n"
        'sys.exit(0 if valid else 7)\n', encoding='utf-8')
    tasks = [TaskItem(id=f'task-{number}', specialist='the-coder',
        description=f'Implement unique integration target {number}',
        target_files=[f'target-{number}.txt'], acceptance_criteria=['Verification exits zero'],
        test_commands=[[sys.executable, 'verify.py', f'target-{number}.txt']],
        working_directory='.') for number in (1, 2)]
    plan = MultiSpecialistPlan(title='Integration lifecycle', architecture_summary='Two independent tasks', tasks=tasks)
    return SimpleNamespace(context=context, workspace=workspace, plan=plan,
        db=memory / 'integration.sqlite')


def with_policy(workspace, policies, *, approval_policy=None, max_steps=100):
    state = CouncilState(run_id='integration-run', task_input='Implement the two fixture targets',
        thread_id='integration-run', max_steps=max_steps, approval_policy=approval_policy,
        workspace_root=str(workspace.workspace.resolve()),
        council_root=str(workspace.context.council_root.resolve()),
        memory_root=str(workspace.context.memory_root.resolve()), **policies)
    return SimpleNamespace(**vars(workspace), state=state,
        config={'configurable': {'thread_id': state.thread_id}, 'recursion_limit': max_steps + 100})


@pytest.fixture
def legacy_lifecycle(graph_workspace):
    """Version-one compatibility state, including the supported manual flow."""
    fixture = with_policy(graph_workspace, LEGACY_POLICIES)
    fixture.config['recursion_limit'] = 100  # Preserve historical fixture behavior.
    return fixture


@pytest.fixture
def lifecycle(legacy_lifecycle):
    """Compatibility alias: always legacy_policy, never current acceptance."""
    return legacy_lifecycle


@dataclass
class GraphRun:
    fixture: SimpleNamespace
    state: dict
    provider: object
    reviewer: object

    def build(self, saver):
        from council.graph import build_council_graph
        return build_council_graph(checkpointer=saver, context=self.fixture.context,
            llm_factory=lambda role: self.reviewer if role == 'reviewer' else self.provider)


def autonomous_run(fixture, *, phased):
    # Import existing provider-boundary doubles after test collection. Neither
    # the graph implementation, verifier subprocess nor checkpoint is mocked.
    from council.config import resolve_model_configuration
    from test_autonomous_review import Reviewer
    from test_engine_integration import ScriptedProvider

    class Provider(ScriptedProvider):
        def with_structured_output(self, schema, **kwargs):
            if schema is PhaseRoadmap:
                value = PhaseRoadmap(title='Current-policy fixture',
                    architecture_summary='Verify declared fixture targets', phases=[
                        Phase(id='fixture', goal='Implement and verify fixture targets',
                            affected_services=['fixture'], executable_ids=['fixture'], delivered_contracts=['Verified targets'],
                            acceptance_outcomes=['Actual subprocess checks pass'], final_acceptance=True)],
                    solution_architecture={'executables': [{'id': 'fixture', 'kind': 'console', 'repository': '.', 'depends_on': []}],
                        'contracts': [], 'open_questions': [], 'integration_strategy': 'Verify fixture targets through actual subprocesses'})
                return SimpleNamespace(invoke=lambda messages:
                    {'parsed': value, 'raw': AIMessage(content=''), 'parsing_error': None})
            return super().with_structured_output(schema, **kwargs)

        def run_task(self, task, guidance, **kwargs):
            self.attempts[task.id] = self.attempts.get(task.id, 0) + 1
            (fixture.workspace / task.target_files[0]).write_text('valid', encoding='utf-8')
            return AIMessage(content='Fixture task completed.')

    fixture.state.model_configuration = resolve_model_configuration(autonomous=True).model_dump(mode='json')
    accept = {'decision': 'accept', 'findings': [], 'resolved_finding_ids': []}
    return GraphRun(fixture=fixture, state=fixture.state.model_dump(mode='json'),
        provider=Provider(fixture.plan), reviewer=Reviewer([accept] * (2 if phased else 1)))


@pytest.fixture
def current_autonomous_run(graph_workspace):
    """All fresh autonomous policies enabled, with a real readiness prefix."""
    graph_workspace.plan.tasks.insert(0, TaskItem(id='setup', specialist='the-coder',
        description='Prepare real prerequisite', kind='readiness',
        readiness_for=[task.id for task in graph_workspace.plan.tasks],
        target_files=['prerequisite.txt'], acceptance_criteria=['Real prerequisite is readable'],
        test_commands=[[sys.executable, 'verify.py', 'prerequisite.txt']]))
    fixture = with_policy(graph_workspace, CURRENT_AUTONOMOUS_POLICIES,
        approval_policy='autonomous', max_steps=400)
    return autonomous_run(fixture, phased=True)


@pytest.fixture
def legacy_monolithic_run(graph_workspace):
    """Monolithic compatibility with review/integrity v2 and other policies v1."""
    fixture = with_policy(graph_workspace, MONOLITHIC_INTEGRITY_POLICIES,
        approval_policy='autonomous', max_steps=400)
    return autonomous_run(fixture, phased=False)
