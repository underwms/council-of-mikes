"""Baseline provenance survives restarts without promoting stale observations."""
import hashlib
import pytest
from council.state import CouncilState
from council.delivery_contracts import BaselineEntry, SourceObservation
from test_requirements_intake import draft
from council import requirements


def test_changed_observation_is_uncertain_but_user_workflow_remains_authoritative(tmp_path):
    from council import baseline
    path = tmp_path / 'auth.py'
    path.write_text('local auth')
    state = CouncilState(run_id='baseline', task_input='Reuse ReadPolicy', intake_enabled=True,
        council_root=str(tmp_path / 'private-council'))
    value = draft()
    value.baseline = [
        BaselineEntry(id='B1', statement='ReadPolicy exists', basis='observed',
            source_refs=['auth.py'], consequence='Reuse query filters'),
        BaselineEntry(id='B2', statement='Use local Compose identity', basis='user',
            source_refs=[], consequence='No production credentials needed')]
    requirements.revise(state, value, [SourceObservation(path='auth.py',
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
    requirements.approve(state, {'requirements_sha256':state.requirements.document_sha256})
    assert baseline.freshness(state, tmp_path) == {'B1':'current', 'B2':'user_confirmed'}
    path.write_text('new 403 defect')
    restored = CouncilState.model_validate_json(state.model_dump_json())
    assert baseline.freshness(restored, tmp_path) == {'B1':'stale', 'B2':'user_confirmed'}
    assert restored.requirements.approved_sha256 == state.requirements.approved_sha256


def test_challenge_requires_known_identity_and_evidence_and_retains_resolution(tmp_path):
    from council import baseline
    state = CouncilState(run_id='baseline', task_input='Read', intake_enabled=True)
    value = draft()
    value.baseline = [BaselineEntry(id='B1', statement='Reuse auth', basis='user',
        source_refs=[], consequence='Keep local identity')]
    requirements.revise(state, value, [])
    with pytest.raises(ValueError):
        baseline.challenge(state, baseline_id='B1', requirement_id='R1',
            reason='observed_failure', evidence_refs=['invented'], consequence='403')
    with pytest.raises(ValueError):
        baseline.challenge(state, baseline_id='B9', requirement_id='R1',
            reason='requirement_change', evidence_refs=['R1'], consequence='Change auth')
    item = baseline.challenge(state, baseline_id='B1', requirement_id='R1',
        reason='requirement_change', evidence_refs=['R1'], consequence='Change auth')
    assert item.route == 'human_requirements'
    baseline.resolve(state, item.id, 'Retain local identity; no scope change')
    restored = CouncilState.model_validate_json(state.model_dump_json())
    assert restored.requirements.challenges[0].resolution == 'Retain local identity; no scope change'
    with pytest.raises(ValueError):
        baseline.challenge(restored, baseline_id='B1', requirement_id='R1',
            reason='requirement_change', evidence_refs=['R1'], consequence='Change auth')


def test_effective_requirements_rejects_mutated_structured_document():
    state = CouncilState(run_id='baseline', task_input='Read', intake_enabled=True)
    requirements.revise(state, draft(), [])
    requirements.approve(state, {'requirements_sha256':state.requirements.document_sha256})
    state.requirements.draft.requirements[0].statement = 'Unauthorized replacement'
    with pytest.raises(ValueError):
        requirements.effective_requirements(state)


def test_intake_read_hash_is_bound_to_returned_bytes(graph_workspace):
    from council.requirements import observed_read_tools
    context = graph_workspace.context
    path = context.workspace_root / 'intake-source.txt'
    path.write_bytes(b'first\r\nsecond\r\n')
    sources = {}
    reader = observed_read_tools(context, sources)[0]
    assert reader.invoke({'rel_path':'intake-source.txt', 'start_line':2}) == 'second'
    assert sources['intake-source.txt'].sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_text('changed')
    assert sources['intake-source.txt'].sha256 != hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(Exception):
        reader.invoke({'rel_path':'../private.txt'})


def test_reviewed_plan_can_raise_a_typed_challenge_without_changing_human_scope(graph_workspace):
    from council import baseline
    state = CouncilState(run_id='challenge',task_input='Reuse auth',intake_enabled=True,plan=graph_workspace.plan)
    value = draft()
    value.baseline = [BaselineEntry(id='B1',statement='Reuse local identity',basis='user',
        source_refs=[],consequence='Keep development workflow')]
    requirements.revise(state,value,[])
    requirements.approve(state,{'requirements_sha256':state.requirements.document_sha256})
    from council.delivery_contracts import BaselineChallengeProposal
    state.plan.baseline_challenges = [BaselineChallengeProposal(baseline_id='B1',requirement_id='R1',
        reason='requirement_change',evidence_refs=['R1'],consequence='Proposed authorization scope change')]
    baseline.admit_plan_challenges(state)
    assert state.requirements.challenges[0].route=='human_requirements'
    requirements.reopen(state)
    assert state.requirements.approved_sha256 is None
    assert not state.requirements.feedback


@pytest.mark.parametrize('case',['valid','stale','user_rule'])
def test_independently_reviewed_fact_correction_preserves_human_approval(graph_workspace,case):
    from council import baseline
    from council.delivery_contracts import BaselineChallengeProposal
    fixture=graph_workspace
    path=fixture.workspace/'auth.py'
    path.write_text('Existing ReadPolicy query filter')
    state=CouncilState(run_id='facts',task_input='Reuse existing query auth',intake_enabled=True,
        workspace_root=str(fixture.workspace),council_root=str(fixture.context.council_root),
        memory_root=str(fixture.context.memory_root),plan=fixture.plan)
    value=draft()
    value.baseline=[BaselineEntry(id='B1',statement='ReadPolicy needs replacement',basis='user' if case=='user_rule' else 'observed',
        source_refs=['auth.py'],consequence='Use existing local identity')]
    observation=SourceObservation(path='auth.py',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    requirements.revise(state,value,[observation])
    requirements.approve(state,{'requirements_sha256':state.requirements.document_sha256})
    approved=state.requirements.approved_sha256
    state.plan.baseline_challenges=[BaselineChallengeProposal(baseline_id='B1',requirement_id='R1',
        reason='blocking_dependency',evidence_refs=['auth.py'],consequence='Avoid an invented auth prerequisite',
        replacement_statement='Reuse existing ReadPolicy query filters',replacement_source_refs=['auth.py'])]
    if case=='stale':path.write_text('Changed after source observation')
    if case!='valid':
        with pytest.raises(ValueError):
            baseline.admit_plan_challenges(state,context=fixture.context,review_sha256='a'*64)
        assert state.requirements.approved_sha256==approved
        assert not state.requirements.challenges and not state.requirements.baseline_amendments
        return
    baseline.admit_plan_challenges(state,context=fixture.context,review_sha256='a'*64)
    assert state.requirements.approved_sha256==approved
    assert requirements.effective_requirements(state)==state.requirements.markdown
    context=requirements.baseline_context(state)
    assert context['entries'][0]['statement']=='Reuse existing ReadPolicy query filters'
    assert context['entries'][0]['review_sha256']=='a'*64
    assert context['entries'][0]['consequence']=='Avoid an invented auth prerequisite'
    assert context['freshness']['B1']=='current'
    assert state.requirements.challenges[0].resolution


def test_graph_admits_fact_amendment_after_independent_plan_review(current_autonomous_run):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from council.delivery_contracts import RequirementsDraft,BaselineChallengeProposal
    run=current_autonomous_run
    (run.fixture.workspace/'auth.py').write_text('Existing query filter')
    run.state['intake_enabled']=True
    value=draft()
    value.baseline=[BaselineEntry(id='B1',statement='A replacement entitlement layer is needed',basis='observed',
        source_refs=['auth.py'],consequence='Reuse local identity')]
    run.fixture.plan.baseline_challenges=[BaselineChallengeProposal(baseline_id='B1',requirement_id='R1',
        reason='blocking_dependency',evidence_refs=['auth.py'],consequence='Avoid an invented prerequisite',
        replacement_statement='Existing query filters can be reused',replacement_source_refs=['auth.py'])]
    class Provider:
        def bind_tools(self,tools):
            calls=[]
            def inspect(messages):
                calls.append(1)
                return AIMessage(content='',tool_calls=[{'name':'read_workspace_file',
                    'args':{'rel_path':'auth.py'},'id':'auth-read'}]) if len(calls)==1 else AIMessage(content='Inspection complete')
            return SimpleNamespace(invoke=inspect)
        def with_structured_output(self,schema,**kwargs):
            if schema is RequirementsDraft:
                return SimpleNamespace(invoke=lambda messages:{'parsed':value,'raw':None,'parsing_error':None})
            return run.provider.with_structured_output(schema,**kwargs)
        def run_task(self,*args,**kwargs):return run.provider.run_task(*args,**kwargs)
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph=build_council_graph(checkpointer=saver,context=run.fixture.context,
            llm_factory=lambda role:run.reviewer if role=='reviewer' else Provider())
        first=graph.invoke(run.state,run.fixture.config)
        approved=first['requirements']['document_sha256']
        result=graph.invoke(Command(resume={'requirements_sha256':approved}),run.fixture.config)
    assert result['status']=='COMPLETED',result.get('diagnostic')
    assert result['requirements']['approved_sha256']==approved
    assert result['requirements']['baseline_amendments'][0]['statement']=='Existing query filters can be reused'
