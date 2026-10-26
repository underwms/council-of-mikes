"""Policy override tests never execute a real PowerShell override."""
import json
import subprocess
from types import SimpleNamespace

import pytest
from council.plan_validation import validate_plan,plan_contract
from council.diagnostics import DiagnosticValueError,DiagnosticRuntimeError,describe
from council.runner import SubprocessRunner
from test_engine_integration import lifecycle,open_graph
from test_autonomous_review import setup,graph_for,ACCEPT
from council.plan_review import plan_digest


BLOCKED = [
    ['powershell','-ExecutionPolicy','Bypass','-File','check.ps1'],
    ['PowerShell.EXE','-NoProfile','-ep','Bypass','-File','check.ps1'],
    ['pwsh','-executionpolicy:Bypass','-File','check.ps1'],
    ['C:/Program Files/PowerShell/7/pwsh.exe','-ExecutionPolicy=Unrestricted','-File','check.ps1'],
    ['powershell','-ex','Bypass','-File','check.ps1'],
    ['pwsh','/ExecutionPolicy','Bypass','-File','check.ps1'],
    ['pwsh','-e','Bypass','-File','check.ps1'],
    ['pwsh','-ExecutionPolicy','RemoteSigned','-File','check.ps1'],
]


@pytest.mark.parametrize('argv',BLOCKED,ids=[f'override-{n}' for n in range(len(BLOCKED))])
def test_plan_rejects_policy_override_with_finite_feedback(lifecycle,argv):
    plan=lifecycle.plan.model_copy(deep=True);plan.tasks[0].test_commands=[argv]
    with pytest.raises(DiagnosticValueError) as caught:validate_plan(plan,lifecycle.context,native_coding=True)
    detail=describe(caught.value)
    assert detail['code']=='PLAN_VERIFICATION_INVALID'
    assert detail['verification']['reason']=='EXECUTION_POLICY_OVERRIDE'
    assert detail['verification']['command_index']==1
    assert 'Bypass' not in json.dumps(detail)


@pytest.mark.parametrize('argv',BLOCKED,ids=[f'override-{n}' for n in range(len(BLOCKED))])
def test_runtime_rejects_override_before_process_creation(lifecycle,monkeypatch,argv):
    calls=[]
    def execute(*args,**kwargs):
        calls.append(args);return subprocess.CompletedProcess(args[0],0,'','')
    monkeypatch.setattr('council.runner.subprocess.Popen',execute)
    with pytest.raises(DiagnosticRuntimeError) as caught:SubprocessRunner(context=lifecycle.context).run(argv)
    assert describe(caught.value)['code']=='VERIFICATION_POLICY_OVERRIDE'
    assert calls==[]


@pytest.mark.parametrize('argv', [
    ['powershell','-NoProfile','-File','check.ps1'],
    ['pwsh','-File','check.ps1','-ExecutionPolicy','Bypass'],
    ['pwsh','-f','check.ps1','-ep','literal'],
    ['deno','test','tests/example.test.ts'],
    ['python','check.py','-ExecutionPolicy','literal'],
])
def test_normal_commands_and_script_arguments_remain_literal(lifecycle,monkeypatch,argv):
    calls=[]
    def execute(command,**kwargs):
        calls.append((command,kwargs));return SimpleNamespace(returncode=0, communicate=lambda **kw: ('ok',''))
    monkeypatch.setattr('council.runner.subprocess.Popen',execute)
    assert SubprocessRunner(context=lifecycle.context).run(argv)==(0,'ok','')
    assert calls[0][0]==argv and calls[0][1]['shell'] is False
    plan=lifecycle.plan.model_copy(deep=True);plan.tasks[0].test_commands=[argv]
    assert validate_plan(plan,lifecycle.context,native_coding=True).tasks[0].test_commands==[argv]


def test_old_accepted_plan_cannot_dispatch_override_to_worker(lifecycle,monkeypatch):
    plan=lifecycle.plan.model_copy(deep=True);plan.tasks[0].test_commands=[BLOCKED[0]]
    state,provider,reviewer=setup(lifecycle,monkeypatch,[ACCEPT])
    state.update(plan=plan.model_dump(),status='EXECUTING',accepted_plan_sha256=plan_digest(plan))
    # Even the pre-change red test cannot execute a real override.
    monkeypatch.setattr('council.graph.SubprocessRunner.run',lambda *args,**kwargs:(0,'',''))
    with open_graph(lifecycle,provider) as saver:
        graph=graph_for(lifecycle,saver,provider,reviewer)
        graph.update_state(lifecycle.config,state,as_node='plan_review')
        result=graph.invoke(None,lifecycle.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['verification']['reason']=='EXECUTION_POLICY_OVERRIDE'
    assert provider.attempts=={}
    assert result['accepted_plan_sha256']==plan_digest(plan)
    assert result['modified_files']==[]


def test_planner_contract_explicitly_preserves_native_policy(lifecycle):
    assert 'execution-policy' in plan_contract(lifecycle.context)['test_commands'].lower()


@pytest.mark.parametrize('command', [None,[],[None],['pwsh',None],['pwsh','-NoProfile'],['pwsh','check.ps1'],
    ['pwsh','--','literal'],['C:/Windows/System32/cmd.exe','/c','echo','literal']])
def test_detector_handles_nonmatches_without_executing_anything(command):
    from council.command_policy import has_policy_override
    assert has_policy_override(command) is False


def test_rejected_revision_gets_fixed_correction_without_argv(lifecycle):
    from council.plan_review import record_preflight_failure,revision_request
    state=lifecycle.state;state.plan=lifecycle.plan
    plan=lifecycle.plan.model_copy(deep=True)
    plan.tasks[0].test_commands.append(['powershell','-ExecutionPolicy','Bypass','-File','PRIVATE_SCRIPT.ps1'])
    with pytest.raises(DiagnosticValueError) as caught:validate_plan(plan,lifecycle.context,native_coding=True)
    assert record_preflight_failure(state,plan,caught.value)
    request=revision_request(state,lifecycle.context)
    assert request['verification_correction']['reason']=='EXECUTION_POLICY_OVERRIDE'
    assert request['verification_correction']['command_index']==2
    assert 'PRIVATE_SCRIPT' not in json.dumps(request)
    assert state.plan.model_dump()==lifecycle.plan.model_dump()
