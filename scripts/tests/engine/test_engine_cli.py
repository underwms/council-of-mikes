import unittest
from unittest.mock import patch
from council.config import get_llm_for_role
from council.cli import create_parser

class NativeCliTests(unittest.TestCase):
    def test_offline_and_explicit_context_flags(self):
        args = create_parser().parse_args(['--doctor','--workspace','workspace','--council-root','council'])
        self.assertTrue(args.doctor)
        self.assertEqual(args.workspace,'workspace')

    def test_exact_role_model_is_forwarded(self):
        with patch.dict('os.environ', {'COUNCIL_ORCHESTRATOR_MODEL':'custom-deployment','COUNCIL_ORCHESTRATOR_PROVIDER':'gpt'}), patch('council.config.get_llm') as factory:
            get_llm_for_role('orchestrator')
            factory.assert_called_once_with('gpt',model='custom-deployment')

    def test_unknown_model_requires_provider(self):
        with patch.dict('os.environ', {'COUNCIL_ORCHESTRATOR_MODEL':'custom-deployment'},clear=True):
            with self.assertRaises(ValueError): get_llm_for_role('orchestrator')

if __name__=='__main__': unittest.main()

import json
import pytest
from test_engine_integration import lifecycle, ScriptedProvider
from council.cli import run_council_task, main

@pytest.fixture
def cli_runtime(lifecycle, monkeypatch):
    provider = ScriptedProvider(lifecycle.plan)
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda role: provider)
    monkeypatch.setattr('council.cli.uuid.uuid4', lambda: type('Id', (), {'hex':'cli-fixture'})())
    return lifecycle

def invoke_cli(fixture, **kwargs):
    return run_council_task(workspace_root=fixture.workspace, council_root=fixture.context.council_root, **kwargs)

def test_no_input_pauses_even_with_tty(cli_runtime, monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('No input flag must suppress prompts'))
    assert invoke_cli(cli_runtime,prompt='fixture',no_input=True)==2
    assert json.loads(capsys.readouterr().out)['status']=='PAUSED'

def test_resume_displays_plan_before_requesting_approval(cli_runtime, monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin.isatty',lambda:False)
    assert invoke_cli(cli_runtime,prompt='fixture')==2
    capsys.readouterr()
    monkeypatch.setattr('sys.stdin.isatty',lambda:True)
    def reject(prompt):
        output=capsys.readouterr().out
        assert 'GATE_1_PLAN_APPROVAL' in output
        assert cli_runtime.plan.title in output
        return 'n'
    monkeypatch.setattr('builtins.input',reject)
    assert invoke_cli(cli_runtime,resume_id='cli-fixture')==1

def test_cli_real_completed_run_and_repeated_resume(cli_runtime,capsys):
    assert invoke_cli(cli_runtime,prompt='fixture',auto_approve=True)==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='COMPLETED'
    assert len(result['test_results'])==2
    assert invoke_cli(cli_runtime,resume_id='cli-fixture')==0

def test_cli_paused_then_resume_noninteractive_then_autoapprove(cli_runtime,monkeypatch,capsys):
    monkeypatch.setattr('sys.stdin.isatty',lambda:False)
    assert invoke_cli(cli_runtime,prompt='fixture')==2
    assert invoke_cli(cli_runtime,resume_id='cli-fixture')==2
    assert invoke_cli(cli_runtime,resume_id='cli-fixture',auto_approve=True)==0
    assert 'COMPLETED' in capsys.readouterr().out

def test_cli_interactive_approvals_are_real(cli_runtime,monkeypatch,capsys):
    monkeypatch.setattr('sys.stdin.isatty',lambda:True)
    approvals=iter(['yes','yes'])
    monkeypatch.setattr('builtins.input',lambda message:next(approvals))
    assert invoke_cli(cli_runtime,prompt='fixture')==0
    assert 'GATE_2_PRE_SUBMIT_APPROVAL' in capsys.readouterr().out

def test_cli_interactive_rejection_is_terminal(cli_runtime,monkeypatch,capsys):
    monkeypatch.setattr('sys.stdin.isatty',lambda:True)
    monkeypatch.setattr('builtins.input',lambda message:'no')
    assert invoke_cli(cli_runtime,prompt='fixture')==1
    assert invoke_cli(cli_runtime,resume_id='cli-fixture')==1
    assert not list(cli_runtime.workspace.glob('target-*.txt'))

def test_cli_dryrun_story_and_boundaries(cli_runtime,capsys):
    (cli_runtime.workspace/'story.md').write_text('fixture requirement')
    assert invoke_cli(cli_runtime,story='story.md',dry_run=True)==0
    assert json.loads(capsys.readouterr().out)['status']=='PLAN_ONLY'
    assert not (cli_runtime.context.council_root/'memory'/'engine').exists()
    with pytest.raises(PermissionError):invoke_cli(cli_runtime,story='../outside.md')
    with pytest.raises(ValueError):invoke_cli(cli_runtime,prompt='')
    with pytest.raises(ValueError):invoke_cli(cli_runtime,resume_id='unknown')
    with pytest.raises(ValueError):invoke_cli(cli_runtime,resume_id='unknown',dry_run=True)

def test_cli_resume_refuses_other_workspace(cli_runtime,monkeypatch):
    monkeypatch.setattr('sys.stdin.isatty',lambda:False)
    assert invoke_cli(cli_runtime,prompt='fixture')==2
    other=cli_runtime.workspace.parent/'other';other.mkdir()
    with pytest.raises(ValueError,match='context mismatch'):
        run_council_task(resume_id='cli-fixture',workspace_root=other,council_root=cli_runtime.context.council_root)

def test_main_doctor_failed_config_help_and_noinput(cli_runtime,capsys):
    assert main(['--doctor','--workspace',str(cli_runtime.workspace),'--council-root',str(cli_runtime.context.council_root)])==0
    assert main(['--workspace',str(cli_runtime.workspace),'--council-root',str(cli_runtime.context.council_root)])==1
    assert main(['fixture','--no-input','--workspace',str(cli_runtime.workspace),'--council-root',str(cli_runtime.context.council_root)])==2
    with pytest.raises(SystemExit) as error: main(['--help'])
    assert error.value.code==0

def test_entrypoint_executes_main(cli_runtime,monkeypatch):
    import runpy
    monkeypatch.setattr('sys.argv',['council','--doctor','--workspace',str(cli_runtime.workspace),'--council-root',str(cli_runtime.context.council_root)])
    with pytest.raises(SystemExit) as error:runpy.run_module('council',run_name='__main__')
    assert error.value.code==0

def test_cli_module_entrypoint_executes_offline_doctor(cli_runtime,monkeypatch):
    import runpy
    import council.cli
    monkeypatch.setattr('sys.argv',['council','--doctor','--workspace',str(cli_runtime.workspace),'--council-root',str(cli_runtime.context.council_root)])
    with pytest.raises(SystemExit) as error: runpy.run_path(council.cli.__file__,run_name='__main__')
    assert error.value.code==0
