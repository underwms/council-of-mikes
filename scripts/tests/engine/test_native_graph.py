import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from council.runtime_context import RuntimeContext
from council.cli import run_council_task, doctor
from council.checkpoint import managed_sqlite_checkpointer
from council.graph import build_council_graph
from council.state import CouncilState, MultiSpecialistPlan, TaskItem

class NativeRuntimeTests(unittest.TestCase):
    def test_offline_doctor_uses_no_provider_and_no_disk_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); council=root/'council'; workspace=root/'workspace'
            council.mkdir(); workspace.mkdir(); (council/'manifest.json').write_text('{}')
            context=RuntimeContext(council,workspace,council/'memory')
            with patch('council.graph.get_llm_for_role',side_effect=AssertionError('no API')), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(doctor(context),0)
            self.assertFalse(context.memory_root.exists())
            self.assertIn('"native_graph": true',output.getvalue())

    def test_database_connection_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            with managed_sqlite_checkpointer(db_path=Path(temp)/'checkpoint.sqlite') as saver:
                connection=saver.conn
                connection.execute('SELECT 1')
            import sqlite3
            with self.assertRaises(sqlite3.ProgrammingError): connection.execute('SELECT 1')


    def test_default_checkpoint_path_stays_in_private_fixture_context(self):
        from council.checkpoint import get_checkpoint_db_path
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);council=root/'council';workspace=root/'workspace'
            council.mkdir();workspace.mkdir();(council/'manifest.json').write_text('{}')
            context=RuntimeContext(council,workspace,council/'memory')
            self.assertEqual(get_checkpoint_db_path(context),(council/'memory'/'council_checkpoints.db').resolve())
            with patch('council.runtime_context.resolve_context',return_value=context):
                self.assertEqual(get_checkpoint_db_path(),get_checkpoint_db_path(context))

import pytest
from test_engine_integration import lifecycle,ScriptedProvider,open_graph,build,assert_gate
from langgraph.types import Command
from langchain_core.messages import AIMessage

def test_architect_accepts_plain_dict_and_presupplied_plan(lifecycle):
    from council.graph import the_architect_node
    provider=ScriptedProvider(lifecycle.plan)
    result=the_architect_node(lifecycle.state.model_dump(mode='json'),lambda role:provider)
    assert result.plan==lifecycle.plan
    assert the_architect_node(result,lambda role:pytest.fail('Do not regenerate supplied plan')).plan==lifecycle.plan

def test_native_builder_requires_managed_checkpoint_and_resolves_context(lifecycle,monkeypatch):
    with pytest.raises(ValueError,match='durable'):
        build_council_graph(context=lifecycle.context)
    monkeypatch.setattr('council.runtime_context.resolve_context',lambda:lifecycle.context)
    with open_graph(lifecycle,ScriptedProvider(lifecycle.plan)) as saver:
        assert build_council_graph(checkpointer=saver).get_graph() is not None

def test_specialist_removed_after_approval_fails_closed(lifecycle):
    provider=ScriptedProvider(lifecycle.plan)
    with open_graph(lifecycle,provider) as saver:
        graph=build(lifecycle,saver,provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(),lifecycle.config),'GATE_1_PLAN_APPROVAL')
        (lifecycle.context.council_root/'skills'/'the-coder'/'SKILL.md').unlink()
        result=graph.invoke(Command(resume={'approved':True}),lifecycle.config)
        assert result['status']=='FAILED'
        assert not list(lifecycle.workspace.glob('target-*.txt'))

def test_continuous_tool_requests_stop_at_round_limit(lifecycle):
    class EndlessProvider(ScriptedProvider):
        def invoke(self,messages):
            return AIMessage(content='',tool_calls=[{'name':'read_workspace_file','args':{'rel_path':'verify.py','start_line':len(messages)},'id':'read','type':'tool_call'}])
    provider=EndlessProvider(lifecycle.plan)
    with open_graph(lifecycle,provider) as saver:
        graph=build(lifecycle,saver,provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(),lifecycle.config),'GATE_1_PLAN_APPROVAL')
        result=graph.invoke(Command(resume={'approved':True}),lifecycle.config)
        assert result['status']=='FAILED'
        assert len(result['tool_call_history'])==12
        assert result['test_results']==[]

@pytest.mark.parametrize('content',['Error: this is literal source text','Failed: recorded historical log'])
def test_reading_error_named_content_is_not_tool_failure(lifecycle,content):
    from langchain_core.messages import ToolMessage
    (lifecycle.workspace/'diagnostic.txt').write_text(content,encoding='utf-8')
    class ReadingProvider(ScriptedProvider):
        def invoke(self,messages):
            if not any(isinstance(item,ToolMessage) for item in messages):
                return AIMessage(content='',tool_calls=[{'name':'read_workspace_file','args':{'rel_path':'diagnostic.txt'},'id':'read-diagnostic','type':'tool_call'}])
            return super().invoke(messages)
    for number in (1,2):(lifecycle.workspace/f'target-{number}.txt').write_text('valid',encoding='utf-8')
    provider=ReadingProvider(lifecycle.plan)
    with open_graph(lifecycle,provider) as saver:
        graph=build(lifecycle,saver,provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(),lifecycle.config),'GATE_1_PLAN_APPROVAL')
        result=graph.invoke(Command(resume={'approved':True}),lifecycle.config)
        assert_gate(result,'GATE_2_PRE_SUBMIT_APPROVAL')
        assert all(item['succeeded'] for item in result['tool_call_history'])
