"""Specific red-phase failures remain strict and survive the existing repair path."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from council.verification import evaluate_deno_red
from council.state import TestExecutionResult as ExecutionResult, CouncilState
from council.diagnostics import DiagnosticSession
from test_tdd_phases import junit, RED, GREEN, contract, make_plan
from test_engine_integration import lifecycle, open_graph
from test_autonomous_review import setup, graph_for, ACCEPT


def expected(count=1):
    return [dict(command_index=2,test_name=f'expected-{n}',assertion_message=f'TDD_RED: required behavior {n} missing') for n in range(1,count+1)]


def report_for(items, passed=()):
    return junit(*[(item['test_name'],'AssertionError: '+item['assertion_message']) for item in items],
                 *[(name,None) for name in passed])


def detail_of(result):
    return result.model_dump().get('verification_detail') or {}


def test_observed_incomplete_red_report_explains_eight_missing_cases():
    items = expected(10)
    result = evaluate_deno_red(1,report_for(items[4:6],['baseline-one','baseline-two']),'',items)
    detail = detail_of(result)
    assert detail.get('reason') == 'MISSING_EXPECTED_CASE'
    assert detail['missing_expected'] == [1,2,3,4,7,8,9,10]
    assert detail['expected_count'] == 10 and detail['observed_count'] == 4
    assert result.tests_failed == 2 and result.tests_passed == 2
    assert not result.passed and not result.expectation_met


@pytest.mark.parametrize('kind,reason', [
    ('report','REPORT_INVALID'), ('exit','EXIT_CODE'), ('empty','EXPECTATIONS_EMPTY'),
    ('duplicate','EXPECTATIONS_DUPLICATE'), ('passed','EXPECTED_CASE_PASSED'),
    ('extra','UNEXPECTED_FAILURE'), ('type','ASSERTION_TYPE'),
    ('header','ASSERTION_HEADER'), ('body','ASSERTION_BODY'),
])
def test_existing_red_rejections_have_specific_safe_reasons(kind,reason):
    items = expected()
    code,report,stderr = 1,report_for(items),''
    if kind=='report': report='PRIVATE_RAW_OUTPUT'
    if kind=='exit': code=0
    if kind=='empty': items=[]
    if kind=='duplicate': items*=2
    if kind=='passed': report=report_for([],['expected-1'])
    if kind=='extra': report=report_for(items+[dict(test_name='PRIVATE_UNEXPECTED_NAME',assertion_message='PRIVATE_ASSERTION')])
    if kind=='type': report=report.replace('<failure ','<failure type="TypeError" ')
    if kind=='header': report=report.replace('message="Uncaught AssertionError:','message="PRIVATE_HEADER ')
    if kind=='body': report=report.replace('>AssertionError:', '>PRIVATE_BODY:')
    result=evaluate_deno_red(code,report,stderr,items)
    detail=detail_of(result)
    assert detail.get('reason') == reason
    assert not result.expectation_met
    assert 'PRIVATE_' not in json.dumps(detail)
    if kind=='passed': assert detail['passed_expected']==[1]
    if kind=='extra': assert detail['unexpected_failure_count']==1
    if kind in ('type','header','body'): assert detail['assertion_index']==1


def valid_detail():
    return dict(reason='MISSING_EXPECTED_CASE',expected_count=2,observed_count=1,
        missing_expected=[2],passed_expected=[],unexpected_failure_count=0,assertion_index=None)


@pytest.mark.parametrize('update', [
    {'reason':'PRIVATE_REASON'}, {'expected_count':True}, {'observed_count':257},
    {'expected_count':65}, {'unexpected_failure_count':-1}, {'missing_expected':[0]},
    {'missing_expected':[3]}, {'missing_expected':[2,2]}, {'passed_expected':[True]},
    {'assertion_index':3}, {'PRIVATE_FIELD':'PRIVATE_VALUE'},
])
def test_malformed_detail_is_ignored(update):
    from council.red_feedback import safe_detail
    assert safe_detail({**valid_detail(),**update}) is None


def test_result_revalidates_detail_and_command_at_loading_and_output(lifecycle):
    from council.red_feedback import sanitize_result
    data=dict(command='deno',passed=False,exit_code=1,verification_phase='red',command_index=2,verification_detail=valid_detail())
    result=ExecutionResult.model_validate(data)
    assert result.model_dump()['verification_detail']==valid_detail()
    result.verification_detail={'PRIVATE_FIELD':'PRIVATE_VALUE'}
    assert 'PRIVATE_' not in json.dumps(result.model_dump())
    result.command_index=True
    assert 'command_index' not in result.model_dump()
    malformed={**data,'verification_detail':{'PRIVATE_FIELD':'PRIVATE_VALUE'},'command_index':-1}
    assert 'verification_detail' not in ExecutionResult.model_validate(malformed).model_dump()
    state=CouncilState(run_id='fixture',task_input='fixture',test_results=[malformed])
    assert 'PRIVATE_' not in json.dumps(state.test_results)
    state.test_results=[malformed]
    assert 'PRIVATE_' not in json.dumps(state.model_dump()['test_results'])
    assert 'verification_detail' not in sanitize_result({**data,'verification_phase':'green'})


def test_legacy_result_defaults_do_not_invent_feedback():
    data=dict(command='deno',passed=False,exit_code=1,verification_reason='RED_EXPECTATION_NOT_MET')
    result=ExecutionResult.model_validate(data).model_dump()
    assert 'command_index' not in result and 'verification_detail' not in result


def test_private_correction_resolves_only_accepted_contract_indices(lifecycle):
    from council.red_feedback import correction
    task=make_plan(lifecycle).tasks[0]
    task.red_verification.expected_failures=[type(task.red_verification.expected_failures[0])(**item) for item in expected(2)]
    data=dict(command='deno',passed=False,exit_code=1,verification_phase='red',command_index=2,verification_detail=valid_detail())
    # A missing command must not resolve against another command's expectations.
    assert correction(task,data) is None
    task.test_commands*=2
    value=correction(task,data)
    assert value['command_index']==2
    assert value['required_expectations'][0]['test_name']=='expected-2'
    assert 'omit' in value['guidance'] and 'later green' in value['guidance']
    assert correction(task,{**data,'command_index':1}) is None


def test_multicommand_feedback_reaches_investigator_and_repairs_without_partial_freeze(lifecycle,monkeypatch,capsys):
    from council.state import ExpectedRedFailure
    plan=make_plan(lifecycle)
    red=plan.tasks[0]
    red.target_files.append('tests/behavior.test.ts')
    red.test_commands.append(['deno','test','--reporter=junit','tests/behavior.test.ts'])
    plan.tasks[1].test_commands=list(red.test_commands)
    red.red_verification.expected_failures += [ExpectedRedFailure(**item) for item in expected(10)]
    state,provider,reviewer=setup(lifecycle,monkeypatch,[ACCEPT])
    provider.plan=plan
    prior_results=[];prompts=[]
    def work(task,guidance,**kwargs):
        assert task.id=='task-1'
        prior_results.append(kwargs.get('prior_result'))
        for target in task.target_files:
            path=lifecycle.workspace/target;path.parent.mkdir(exist_ok=True);path.write_text('Deno.test("fixture",()=>{});')
        return AIMessage(content='Fixture test work')
    provider.run_task=work
    original=provider.invoke
    def investigate(messages):
        if isinstance(messages,str):
            prompts.append(messages)
            return AIMessage(content='Repair the missing accepted tests using the required harness.')
        return original(messages)
    provider.invoke=investigate
    monkeypatch.setattr('council.graph.SubprocessRunner.run',lambda self,argv,**kw:
        (1,RED,'') if argv[-1]=='tests/rules.test.ts' else (1,report_for(expected(10)[4:6],['baseline-one','baseline-two']),''))
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        with open_graph(lifecycle,provider) as saver:
            graph=graph_for(lifecycle,saver,provider,reviewer)
            result=graph.invoke(state,lifecycle.config)
        path=session.path
    assert result['status']=='FAILED' and result['test_retry_count']==2
    assert result['current_task_index']==0 and result['red_phase_evidence']==[]
    assert [x.get('command_index') for x in result['test_results']]==[1,2,1,2,1,2]
    assert all(x['expectation_met'] for x in result['test_results'][::2])
    assert len(prior_results)==3 and len(prompts)==2
    assert prior_results[1]['verification_detail']['missing_expected']==[1,2,3,4,7,8,9,10]
    assert all('MISSING_EXPECTED_CASE' in text and 'expected-10' in text for text in prompts)
    with open_graph(lifecycle,provider) as saver:
        saved=graph_for(lifecycle,saver,provider,reviewer).get_state(lifecycle.config).values
        assert saved['test_result']==result['test_result']
    events=[json.loads(line) for line in path.read_text().splitlines()]
    rejections=[e for e in events if e['event']=='verification_rejected']
    assert len(rejections)==3
    assert all(e['task_index']==1 and e['command_index']==2 for e in rejections)
    assert rejections[0]['verification_detail']==result['test_result']['verification_detail']
    assert 'expected-' not in path.read_text()
    assert 'verification_rejected' in capsys.readouterr().err


def test_native_worker_receives_the_same_private_correction(lifecycle,monkeypatch):
    from council.codex_cli import CodexCLIWorker
    from test_codex_cli import completed
    from council.state import ExpectedRedFailure
    task=make_plan(lifecycle).tasks[0]
    task.test_commands*=2
    task.red_verification.expected_failures=[ExpectedRedFailure(**item) for item in expected(2)]
    settings=dict(executable='C:/trusted/codex.exe',cli_version='0.163.0',timeout_seconds=600)
    captured=[]
    monkeypatch.setattr('council.codex_cli.cli_ready',lambda settings:True)
    def run(argv,payload,**kwargs):
        captured.append(json.loads(payload))
        return 0,'\n'.join(json.dumps(e) for e in completed()).encode(),b''
    monkeypatch.setattr('council.codex_cli.run_process',run)
    prior=dict(command='deno',passed=False,exit_code=1,verification_phase='red',command_index=2,verification_detail=valid_detail())
    CodexCLIWorker('fixture-model',settings,lifecycle.context).run_task(task,'fixture-guidance',prior_result=prior)
    assert captured[0].get('red_verification_correction',{}).get('command_index')==2
    assert captured[0]['red_verification_correction']['required_expectations'][0]['test_name']=='expected-2'
    assert 'meaningful assertions' in captured[0]['instruction']
    prior['verification_detail']={'PRIVATE_FIELD':'PRIVATE_VALUE'}
    CodexCLIWorker('fixture-model',settings,lifecycle.context).run_task(task,'fixture-guidance',prior_result=prior)
    assert 'PRIVATE_' not in json.dumps(captured[1])


def test_valid_red_preserves_actual_failure_and_has_no_rejection_detail():
    result=evaluate_deno_red(1,RED,'',contract()['expected_failures'])
    assert result.expectation_met and not result.passed and result.exit_code==1
    assert 'verification_detail' not in result.model_dump()


def test_state_serialization_preserves_requested_field_exclusion():
    state=CouncilState(run_id='fixture',task_input='fixture')
    assert 'test_results' not in state.model_dump(exclude={'test_results'})


@pytest.mark.parametrize('value', [None,[],{},'PRIVATE_VALUE'])
def test_optional_detail_wrong_shapes_are_ignored(value):
    from council.red_feedback import safe_detail
    assert safe_detail(value) is None


@pytest.mark.parametrize('update', [
    {'reason':[]}, {'missing_expected':'PRIVATE_VALUE'}, {'missing_expected':list(range(1,66))},
    {'expected_count':None}, {'assertion_index':True}, {'passed_expected':[1,1]},
])
def test_detail_shape_and_index_guards(update):
    from council.red_feedback import safe_detail
    assert safe_detail({**valid_detail(),**update}) is None


def test_sanitizer_copies_optional_lists_and_accepts_unknown_report_counts():
    from council.red_feedback import safe_detail,detail,sanitize_result
    value=valid_detail();copied=safe_detail(value)
    value['missing_expected'].clear()
    assert copied['missing_expected']==[2]
    assert detail('REPORT_INVALID',[])['observed_count'] is None
    assert sanitize_result(None) is None


def test_correction_handles_legacy_and_unrelated_results(lifecycle):
    from council.red_feedback import correction
    task=make_plan(lifecycle).tasks[0]
    assert correction(task,None) is None
    assert correction(task,[]) is None
    assert correction(task,dict(command='deno',passed=False,exit_code=1)) is None
    # No accepted red contract is present on the green task.
    assert correction(make_plan(lifecycle).tasks[1],{}) is None


def test_assertion_correction_identifies_the_accepted_expectation(lifecycle):
    from council.red_feedback import correction,detail
    task=make_plan(lifecycle).tasks[0]
    data=dict(command='deno',passed=False,exit_code=1,verification_phase='red',command_index=1,
        verification_detail=detail('ASSERTION_HEADER',contract()['expected_failures'],assertion_index=1))
    value=correction(task,data)
    assert value['required_expectations']==contract()['expected_failures']
    result=ExecutionResult.model_validate(data)
    assert correction(task,result)==value


def test_invalid_event_details_never_enter_timeline(lifecycle,capsys):
    with DiagnosticSession(lifecycle.state.run_id,lifecycle.context.memory_root) as session:
        session.event('verification_rejected',stage='prover',task_index=0,command_index=True,
            verification_detail={'PRIVATE_FIELD':'PRIVATE_VALUE'})
        path=session.path
    record=next(json.loads(line) for line in path.read_text().splitlines() if json.loads(line)['event']=='verification_rejected')
    assert 'task_index' not in record and 'command_index' not in record and 'verification_detail' not in record
    assert 'PRIVATE_' not in path.read_text()+capsys.readouterr().err


def test_unstable_test_source_gets_specific_feedback(lifecycle,monkeypatch):
    from test_tdd_phases import lifecycle_run
    result,_,_=lifecycle_run(lifecycle,monkeypatch,missing_source=True)
    assert result['test_result'].get('verification_detail',{}).get('reason')=='FROZEN_SOURCE_CHANGED'
    assert not result['red_phase_evidence']


def test_prior_frozen_source_change_overrides_red_comparison_detail(lifecycle,monkeypatch):
    from test_tdd_phases import lifecycle_run
    monkeypatch.setattr('council.graph.frozen_tests_unchanged',lambda *args:False)
    result,_,_=lifecycle_run(lifecycle,monkeypatch)
    assert result['test_result']['verification_reason']=='FROZEN_TEST_CHANGED'
    assert result['test_result'].get('verification_detail',{}).get('reason')=='FROZEN_SOURCE_CHANGED'


def test_tool_worker_gets_specific_correction(lifecycle,monkeypatch):
    from council.state import ExpectedRedFailure
    plan=make_plan(lifecycle)
    items=[{**item,'command_index':1} for item in expected(2)]
    plan.tasks[0].red_verification.expected_failures=[ExpectedRedFailure(**item) for item in items]
    state,provider,reviewer=setup(lifecycle,monkeypatch,[ACCEPT])
    state.update(plan=plan.model_dump(),max_test_retries=0,test_result=dict(command='deno',passed=False,exit_code=1,
        verification_phase='red',command_index=1,verification_detail=valid_detail()))
    provider.plan=plan
    provider.run_task=None
    (lifecycle.workspace/'tests').mkdir()
    seen=[];original=provider.invoke
    def invoke(messages):
        seen.append(str(messages))
        return original(messages)
    provider.invoke=invoke
    monkeypatch.setattr('council.graph.SubprocessRunner.run',lambda *args,**kwargs:(1,report_for(items[:1]),''))
    with open_graph(lifecycle,provider) as saver:
        result=graph_for(lifecycle,saver,provider,reviewer).invoke(state,lifecycle.config)
    assert result['status']=='FAILED'
    assert any('Red verification correction:' in text and 'expected-2' in text for text in seen)
