"""Audit repair invariants exercise real graph, files, and durable checkpoints."""
import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command
from test_engine_integration import lifecycle, ScriptedProvider, open_graph, build, assert_gate


def test_run_configuration_and_model_evidence_survive_restart(lifecycle, monkeypatch):
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_MODEL', 'gpt-original')
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(result, 'GATE_1_PLAN_APPROVAL')
        assert result['model_configuration']['roles']['orchestrator']['model'] == 'gpt-original'
        assert result['model_calls'][0]['role'] == 'orchestrator'
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_MODEL', 'gpt-changed')
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(Command(resume={'approved': True}), lifecycle.config)
        assert result['model_configuration']['roles']['orchestrator']['model'] == 'gpt-original'
        assert any(call['role'] == 'coder' for call in result['model_calls'])
        assert all(call['requested_model'] == result['model_configuration']['roles'][call['role']]['model']
                   for call in result['model_calls'])


def test_final_gate_contains_plan_tests_changes_and_unverified_phases(lifecycle):
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
        evidence = result['__interrupt__'][0].value
        assert evidence['plan']['title'] == lifecycle.plan.title
        assert len(evidence['test_results']) == 2
        assert evidence['modified_files'] == ['target-1.txt', 'target-2.txt']
        assert len(evidence['file_changes']) == 2
        assert evidence['model_calls']
        assert evidence['review_phases']['coverage_validation'] == 'unverified'
        assert evidence['review_phases']['pr_review_simulation'] == 'unverified'


def test_model_response_metadata_is_allowlisted_in_checkpoint(lifecycle):
    class EvidenceProvider(ScriptedProvider):
        def invoke(self, messages):
            response = super().invoke(messages)
            response.response_metadata = {'model_name': 'served-model', 'request_id': 'req-audit',
                                          'authorization': 'secret-marker', 'raw_payload': 'secret-marker'}
            response.usage_metadata = {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5}
            return response
    provider = EvidenceProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        calls = result['model_calls']
        assert any(call.get('returned_model') == 'served-model' for call in calls)
        assert any(call.get('request_id') == 'req-audit' for call in calls)
        assert 'secret-marker' not in repr(result)
    assert b'secret-marker' not in lifecycle.db.read_bytes()


def test_legacy_checkpoint_without_configuration_is_rejected(lifecycle):
    provider = ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        graph.update_state(lifecycle.config, {'model_configuration': {}})
        with pytest.raises(ValueError, match='configuration|legacy'):
            graph.invoke(Command(resume={'approved': True}), lifecycle.config)


def test_planner_reads_repository_before_structured_plan(lifecycle):
    (lifecycle.workspace / 'architecture.txt').write_text('repository-marker')
    observations = []
    class ExploringProvider(ScriptedProvider):
        def bind_tools(self, tools):
            self.planning_tools = {item.name for item in tools}
            return self

        def invoke(self, messages):
            from langchain_core.messages import ToolMessage
            if not getattr(self, 'explored', False):
                self.explored = True
                assert 'list_workspace_files' in self.planning_tools
                return AIMessage(content='', tool_calls=[{'name':'read_workspace_file',
                    'args':{'rel_path':'architecture.txt'},'id':'plan-read','type':'tool_call'}])
            if messages and isinstance(messages[-1], ToolMessage) and messages[-1].tool_call_id == 'plan-read':
                observations.append(messages[-1].content)
                return AIMessage(content='Ready to plan')
            return super().invoke(messages)
    provider = ExploringProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(result, 'GATE_1_PLAN_APPROVAL')
    assert observations == ['repository-marker']
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_planner_file_read_is_bounded(lifecycle):
    from council.tools.tool_registry import get_council_tools
    (lifecycle.workspace / 'large.txt').write_bytes(b'x' * 262_145)
    reader = next(tool for tool in get_council_tools(context=lifecycle.context, specialist='the-architect')
                  if tool.name == 'read_workspace_file')
    with pytest.raises(ValueError, match='limit'):
        reader.invoke({'rel_path':'large.txt'})


def test_missing_credentials_are_named_without_values(lifecycle, monkeypatch, capsys):
    from council.cli import main
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_PROVIDER', 'gpt')
    monkeypatch.setenv('COUNCIL_INVESTIGATOR_PROVIDER', 'gemini')
    code = main(['fixture', '--workspace',str(lifecycle.workspace), '--council-root',str(lifecycle.context.council_root)])
    assert code == 1
    result = json.loads(capsys.readouterr().out)
    assert set(result['missing_credentials']) == {'OPENAI_API_KEY','GEMINI_API_KEY'}


def test_failed_test_tool_result_can_be_observed_and_repaired(lifecycle, monkeypatch):
    from langchain_core.tools import tool
    from langchain_core.messages import ToolMessage
    import council.graph as graph_module
    original = graph_module.get_council_tools
    @tool
    def failing_test() -> dict:
        """Fixture failing verification whose result the worker must inspect."""
        return {'passed':False, 'exit_code':7, 'raw_output':'red-test-marker'}
    def tools(*args, **kwargs):
        result = original(*args, **kwargs)
        return result + [failing_test] if kwargs.get('specialist') == 'the-coder' else result
    monkeypatch.setattr(graph_module, 'get_council_tools', tools)
    observed = []
    class RepairProvider(ScriptedProvider):
        def invoke(self, messages):
            if not getattr(self, 'tested', False):
                self.tested = True
                return AIMessage(content='', tool_calls=[{'name':'failing_test','args':{},'id':'red-test','type':'tool_call'}])
            if messages and isinstance(messages[-1], ToolMessage) and messages[-1].tool_call_id == 'red-test':
                observed.append(messages[-1].content)
                # The fixture then performs a real file write and prover verification.
                return super().invoke(messages[:-1])
            return super().invoke(messages)
    provider = RepairProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert 'red-test-marker' in observed[0]


def test_tool_batch_limit_rejects_before_any_side_effect(lifecycle):
    class BatchProvider(ScriptedProvider):
        def invoke(self, messages):
            return AIMessage(content='', tool_calls=[{'name':'write_workspace_file',
                'args':{'rel_path':f'batch-{i}.txt','content':'fixture'},'id':f'call-{i}','type':'tool_call'} for i in range(17)])
    provider = BatchProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        result = graph.invoke(Command(resume={'approved':True}), lifecycle.config)
        assert result['status'] == 'FAILED'
    assert not list(lifecycle.workspace.glob('batch-*.txt'))
