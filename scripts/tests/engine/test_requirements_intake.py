"""Human authority and observed baseline contracts, independent of model prose."""
import hashlib
import pytest
from council.state import CouncilState


def api():
    from council import requirements
    return requirements


def draft(text='Ship a local CLI'):
    from council.delivery_contracts import RequirementsDraft, RequirementEntry
    return RequirementsDraft(title='CLI', summary=text,
        requirements=[RequirementEntry(id='R1', statement=text, basis='user', source_refs=[])],
        baseline=[], proposals=[], questions=[])


def test_intake_requires_an_exact_explicit_human_approval():
    service = api()
    state = CouncilState(run_id='intake', task_input='Original business rationale', intake_enabled=True)
    service.revise(state, draft(), [])
    original = state.task_input
    with pytest.raises(ValueError):
        service.approve(state, {'approved': True})
    with pytest.raises(ValueError):
        service.approve(state, {'requirements_sha256': '0'*64})
    service.approve(state, {'requirements_sha256': state.requirements.document_sha256})
    assert service.effective_requirements(state) == state.requirements.markdown
    assert state.task_input == original
    assert state.requirements.approved_sha256 == state.requirements.document_sha256


def test_intake_read_miss_is_feedback_and_only_successful_reads_are_observations(current_autonomous_run):
    from council.requirements import observed_read_tools
    run=current_autonomous_run
    sources={}
    reader=observed_read_tools(run.fixture.context,sources)[0]
    missing=reader.invoke({'rel_path':'not-present.md'})
    assert missing['available'] is False and missing['reason']=='SOURCE_MISSING'
    assert sources=={}
    target=run.fixture.workspace/'observed.md'
    target.write_bytes(b'Observed source\nsecond line\n')
    assert reader.invoke({'rel_path':'observed.md','start_line':2,'end_line':2})=='second line'
    assert sources['observed.md'].sha256==hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.parametrize('failure',['permission','boundary','oversized'])
def test_intake_source_unavailability_does_not_mask_read_guards(current_autonomous_run,monkeypatch,failure):
    from council.requirements import observed_read_tools
    from council.tools import discovery
    from council.boundaries import WorkspaceBoundaryError
    sources={}
    if failure=='oversized':
        (current_autonomous_run.fixture.workspace/'large.md').write_bytes(b'x'*(discovery.MAX_FILE_BYTES+1))
        expected=ValueError
    else:
        error=PermissionError('private native detail') if failure=='permission' else WorkspaceBoundaryError('PATH_EXCLUDED')
        def rejected(*args,**kwargs):raise error
        monkeypatch.setattr(discovery,'validate_read_path',rejected)
        expected=type(error)
    reader=observed_read_tools(current_autonomous_run.fixture.context,sources)[0]
    with pytest.raises(expected):reader.invoke({'rel_path':'large.md'})
    assert sources=={}


@pytest.mark.parametrize('unavailable,reason',[('not-present.md','SOURCE_MISSING'),('.env','PATH_EXCLUDED'),('../PRIVATE_PATH_CANARY','PATH_PARENT_TRAVERSAL')])
def test_intake_read_miss_then_real_inspection_reaches_human_gate(current_autonomous_run,unavailable,reason):
    from langchain_core.messages import AIMessage,ToolMessage
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from council.delivery_contracts import BaselineEntry
    run=current_autonomous_run
    run.state['intake_enabled']=True
    (run.fixture.workspace/'observed.md').write_text('Existing local boundary',encoding='utf-8')
    inspected=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if getattr(self,'structured',False):
                value=draft()
                value.baseline=[BaselineEntry(id='B1',statement='Existing local boundary',basis='observed',source_refs=['observed.md'],consequence='Preserve integration')]
                return {'parsed':value,'raw':None,'parsing_error':None}
            feedback=[m.content for m in messages if isinstance(m,ToolMessage)]
            inspected.extend(feedback)
            path='observed.md' if feedback else unavailable
            return AIMessage(content='',tool_calls=[{'name':'read_workspace_file','args':{'rel_path':path},'id':'inspect-'+str(len(feedback))}])
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider())
        result=graph.invoke(run.state,run.fixture.config)
    assert '__interrupt__' in result,result.get('diagnostic')
    assert result['__interrupt__'][0].value['gate']=='requirements'
    assert any(reason in message for message in inspected)
    assert [source['path'] for source in result['requirements']['sources']]==['observed.md']
    assert result['planning_evidence']==[]
    assert 'PRIVATE_PATH_CANARY' not in str(result['tool_call_history'])
    assert result['requirements']['inspection_rounds']==2
    assert result['requirements']['approved_sha256'] is None and result['roadmap'] is None


@pytest.mark.parametrize('rejection',['unobserved_source','requirement_id_loss','document_limit'])
def test_invalid_draft_receives_bounded_correction_before_human_gate(current_autonomous_run,rejection):
    from council.delivery_contracts import BaselineEntry,RequirementEntry
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from langchain_core.messages import AIMessage
    run=current_autonomous_run
    state=CouncilState.model_validate(run.state)
    state.intake_enabled=True
    api().revise(state,draft(),[])
    state.requirements.drafting_attempts=1
    old_hash=state.requirements.document_sha256
    requests=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if not getattr(self,'structured',False):return AIMessage(content='Inspection complete',tool_calls=[])
            requests.append(messages)
            value=draft()
            if len(requests)==1:
                if rejection=='unobserved_source':
                    value.baseline=[BaselineEntry(id='B1',statement='Unproven',basis='observed',source_refs=['PRIVATE_UNOBSERVED_CANARY'],consequence='Do not invent facts')]
                elif rejection=='requirement_id_loss':value.requirements=[RequirementEntry(id='R2',statement='Different identity',basis='user',source_refs=[])]
                else:value.requirements=[RequirementEntry(id='R'+str(i),statement='x'*3000,basis='user',source_refs=[]) for i in range(1,65)]
            return {'parsed':value,'raw':None,'parsing_error':None}
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider())
        result=graph.invoke(state.model_dump(mode='json'),run.fixture.config)
    assert '__interrupt__' in result,result.get('diagnostic')
    assert result['requirements']['draft_rejections']==[rejection]
    assert result['requirements']['drafting_attempts']==3
    assert len(result['requirements']['revisions'])==2
    assert result['requirements']['revisions'][0]['document_sha256']==old_hash
    assert result['requirements']['approved_sha256'] is None and result['roadmap'] is None
    assert len(requests)==2
    correction=str(requests[-1])
    assert rejection in correction and 'PRIVATE_UNOBSERVED_CANARY' not in correction


def test_invalid_drafts_exhaust_existing_cumulative_budget_without_replacing_valid_revision(current_autonomous_run):
    from council.delivery_contracts import BaselineEntry
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from langchain_core.messages import AIMessage
    run=current_autonomous_run
    state=CouncilState.model_validate(run.state);state.intake_enabled=True
    api().revise(state,draft(),[]);state.requirements.drafting_attempts=2
    old_hash=state.requirements.document_sha256
    calls=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if not getattr(self,'structured',False):return AIMessage(content='Inspection complete',tool_calls=[])
            calls.append(messages)
            value=draft();value.baseline=[BaselineEntry(id='B1',statement='Unproven',basis='observed',source_refs=['PRIVATE_CANARY'],consequence='Missing proof')]
            return {'parsed':value,'raw':None,'parsing_error':None}
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider()).invoke(state.model_dump(mode='json'),run.fixture.config)
    assert result['status']=='FAILED'
    assert result['diagnostic']['code']=='REQUIREMENTS_DRAFT_REJECTED'
    assert result['requirements']['drafting_attempts']==4 and len(calls)==2
    assert result['requirements']['draft_rejections']==['unobserved_source']*2
    assert result['requirements']['document_sha256']==old_hash
    assert len(result['requirements']['revisions'])==1 and result['requirements']['approved_sha256'] is None
    assert 'PRIVATE_CANARY' not in str(result['diagnostic'])


def test_draft_correction_retains_real_observed_source_hashes(current_autonomous_run):
    from council.delivery_contracts import BaselineEntry
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['intake_enabled']=True
    target=run.fixture.workspace/'observed.md';target.write_bytes(b'Existing boundary')
    attempts=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if not getattr(self,'structured',False):
                if getattr(self,'inspected',False):return AIMessage(content='Done',tool_calls=[])
                self.inspected=True
                return AIMessage(content='',tool_calls=[{'name':'read_workspace_file','args':{'rel_path':'observed.md'},'id':'read-source'}])
            attempts.append(messages);value=draft()
            value.baseline=[BaselineEntry(id='B1',statement='Existing boundary',basis='observed',
                source_refs=['not-read.md' if len(attempts)==1 else 'observed.md'],consequence='Reuse boundary')]
            return {'parsed':value,'raw':None,'parsing_error':None}
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider()).invoke(run.state,run.fixture.config)
    assert '__interrupt__' in result,result.get('diagnostic')
    assert result['requirements']['sources']==[{'path':'observed.md','sha256':hashlib.sha256(target.read_bytes()).hexdigest()}]
    assert result['requirements']['draft']['baseline'][0]['source_refs']==['observed.md']
    assert result['requirements']['draft_rejections']==['unobserved_source']


def test_native_tool_rejection_does_not_become_a_requirements_correction_retry(current_autonomous_run):
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from council.diagnostics import DiagnosticValueError
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['intake_enabled']=True
    calls=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if not getattr(self,'structured',False):return AIMessage(content='Done',tool_calls=[])
            calls.append(messages);raise DiagnosticValueError('CODEX_REVIEW_TOOL_REJECTED')
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider()).invoke(run.state,run.fixture.config)
    assert result['diagnostic']['code']=='CODEX_REVIEW_TOOL_REJECTED' and len(calls)==1
    assert result['requirements']['draft_rejections']==[]
    assert result['requirements']['approved_sha256'] is None


def test_exhausted_draft_budget_stops_before_inspection_or_provider_dispatch(current_autonomous_run):
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    run=current_autonomous_run;run.state['intake_enabled']=True
    run.state['requirements']['drafting_attempts']=4
    def forbidden(role):raise AssertionError('Provider must not be constructed')
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=forbidden).invoke(run.state,run.fixture.config)
    assert result['diagnostic']['code']=='REQUIREMENTS_DRAFT_REJECTED'
    assert result['model_calls']==[] and result['requirements']['inspection_rounds']==0


def test_older_intake_state_defaults_rejection_history_without_inventing_events():
    state=CouncilState(run_id='old',task_input='Original analysis',intake_enabled=True).model_dump(mode='json')
    state['requirements'].pop('draft_rejections',None)
    assert CouncilState.model_validate(state).requirements.draft_rejections==[]


def test_rejection_reason_accepts_only_the_finite_contract():
    with pytest.raises(ValueError) as error:api().DraftRejected('PRIVATE_UNTRUSTED_REASON')
    assert 'PRIVATE_UNTRUSTED_REASON' not in str(error.value)


@pytest.mark.parametrize('shape',['bare_model','parsing_error'])
def test_draft_correction_preserves_provider_result_shapes_and_parse_failures(current_autonomous_run,shape):
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['intake_enabled']=True
    calls=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if not getattr(self,'structured',False):return AIMessage(content='Done',tool_calls=[])
            calls.append(messages)
            return draft() if shape=='bare_model' else {'parsed':None,'parsing_error':ValueError('PRIVATE_PARSE_CANARY')}
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider()).invoke(run.state,run.fixture.config)
    assert len(calls)==(1 if shape=='bare_model' else 2)
    assert result['requirements']['draft_rejections']==[]
    assert result['requirements']['approved_sha256'] is None
    if shape=='bare_model':assert '__interrupt__' in result
    else:
        assert result['status']=='FAILED' and result['requirements']['revisions']==[]
        assert result['diagnostic']['code']=='PROPOSAL_FORMAT_INVALID'
        assert 'PRIVATE_PARSE_CANARY' not in str(result['diagnostic'])
        assert 'PRIVATE_PARSE_CANARY' not in str(calls)


def test_feedback_preserves_unrelated_requirement_identity_and_history():
    service = api()
    state = CouncilState(run_id='intake', task_input='Business context', intake_enabled=True)
    service.revise(state, draft(), [])
    old = state.requirements.document_sha256
    service.approve(state, {'requirements_sha256': old})
    service.add_feedback(state, 'Support help output too')
    assert state.requirements.approved_sha256 is None
    replacement = draft('Support CLI and help output')
    service.revise(state, replacement, [])
    assert state.requirements.revisions[0].document_sha256 == old
    assert state.requirements.feedback == ['Support help output too']
    assert state.requirements.draft.requirements[0].id == 'R1'
    with pytest.raises(ValueError):
        service.approve(state, {'requirements_sha256': old})
    assert service.effective_requirements(CouncilState(run_id='legacy', task_input='legacy')) == 'legacy'


def test_consequential_unknowns_need_explicit_bounded_acceptance():
    from council.delivery_contracts import IntakeQuestion
    service = api()
    state = CouncilState(run_id='intake', task_input='Build', intake_enabled=True)
    value = draft()
    value.questions = [IntakeQuestion(id='Q1', question='Which host?', consequence='Cannot select deployment',
        consequential=True, bounded_default='Local CLI only')]
    service.revise(state, value, [])
    with pytest.raises(ValueError):
        service.approve(state, {'requirements_sha256':state.requirements.document_sha256})
    service.approve(state, {'requirements_sha256':state.requirements.document_sha256,
        'accepted_limitations':['Q1']})
    assert state.requirements.accepted_limitations == ['Q1']


def test_baseline_observations_cannot_be_invented_or_promoted(tmp_path):
    from council.delivery_contracts import BaselineEntry, SourceObservation
    service = api()
    state = CouncilState(run_id='intake', task_input='Reuse existing auth', intake_enabled=True)
    value = draft()
    value.baseline = [BaselineEntry(id='B1', statement='Development auth exists', basis='observed',
        source_refs=['auth.py'], consequence='Reuse local identity')]
    with pytest.raises(ValueError):
        service.revise(state, value, [])
    observation = SourceObservation(path='auth.py', sha256=hashlib.sha256(b'local').hexdigest())
    service.revise(state, value, [observation])
    assert state.requirements.sources == [observation]
    value.baseline[0].basis = 'proposal'
    service.revise(state, value, [])
    assert state.requirements.draft.baseline[0].basis == 'proposal'


def test_intake_state_survives_json_and_cumulative_budgets():
    service = api()
    state = CouncilState(run_id='intake', task_input='CLI', intake_enabled=True)
    for _ in range(4):
        service.revise(state, draft(), [])
        state = CouncilState.model_validate_json(state.model_dump_json())
    with pytest.raises(ValueError):
        service.revise(state, draft(), [])
    assert len(state.requirements.revisions) == 4


def test_required_intake_api_is_available():
    # Clear behavioral failure before implementing the lifecycle.
    assert hasattr(api(), 'approve')


def test_draft_checkpoint_and_human_resume_precede_roadmap(current_autonomous_run):
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from council.checkpoint import managed_sqlite_checkpointer
    from council.graph import build_council_graph
    run = current_autonomous_run
    calls = []

    class IntakeProvider:
        def bind_tools(self, tools):
            assert all(t.name in {'read_workspace_file','list_workspace_files','search_workspace_text'} for t in tools)
            return self

        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            return self

        def invoke(self, messages):
            calls.append(messages)
            if getattr(self, 'schema', None):
                return {'parsed':draft(), 'raw':None, 'parsing_error':None}
            return AIMessage(content='Observed local fixture', tool_calls=[])

    run.state['intake_enabled'] = True
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph = build_council_graph(checkpointer=saver, context=run.fixture.context,
            llm_factory=lambda role:IntakeProvider())
        result = graph.invoke(run.state, run.fixture.config)
        assert '__interrupt__' in result
        assert result['__interrupt__'][0].value['gate'] == 'requirements'
        assert result['requirements']['draft']['requirements'][0]['id'] == 'R1'
        assert result['roadmap'] is None
        sha = result['requirements']['document_sha256']
    # A new checkpointer connection resumes the same exact human gate.
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph = build_council_graph(checkpointer=saver, context=run.fixture.context,
            llm_factory=lambda role:IntakeProvider())
        approved = graph.invoke(Command(resume={'requirements_sha256':sha}), run.fixture.config,
            interrupt_before=['roadmap'])
        assert approved['requirements']['approved_sha256'] == sha
        assert approved['task_input'] == run.state['task_input']
        assert len(approved['requirements']['revisions']) == 1
        assert graph.get_state(run.fixture.config).next == ('roadmap',)


def test_cli_declares_explicit_requirements_mode_and_exact_approval():
    from council.cli import create_parser
    parsed = create_parser().parse_args(['--requirements-file','idea.md'])
    assert parsed.requirements_file == 'idea.md'
    parsed = create_parser().parse_args(['--resume','run1','--approve-requirements','a'*64,
        '--accept-limitation','Q1'])
    assert parsed.approve_requirements == 'a'*64
    assert create_parser().parse_args(['CLI','--finalize']).finalize is True


@pytest.mark.parametrize('auto,mode',[(True,None),(False,'manual'),(False,'autonomous')])
def test_no_input_cli_cannot_bypass_human_requirements_gate(current_autonomous_run,monkeypatch,auto,mode):
    from council import cli
    from council.graph import build_council_graph
    from council.config import RunModelConfiguration
    from langchain_core.messages import AIMessage
    run=current_autonomous_run
    original=b'CLI analysis and business rationale'
    idea=run.fixture.workspace/'analysis.md'
    idea.write_bytes(original)
    emitted=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):
            self.structured=True
            return self
        def invoke(self,messages):
            return {'parsed':draft(),'raw':None,'parsing_error':None} if getattr(self,'structured',False) else AIMessage(content='Read-only inspection complete')
    monkeypatch.setattr(cli,'resolve_context',lambda *args,**kwargs:run.fixture.context)
    monkeypatch.setattr(cli,'resolve_model_configuration',lambda **kwargs:RunModelConfiguration.model_validate(run.state['model_configuration']))
    monkeypatch.setattr(cli,'credentials_available',lambda configuration:True)
    monkeypatch.setattr(cli,'build_council_graph',lambda **kwargs:build_council_graph(**kwargs,llm_factory=lambda role:Provider()))
    monkeypatch.setattr(cli,'emit',emitted.append)
    code=cli.run_council_task(requirements_file='analysis.md',auto_approve=auto,
        approval_mode=mode,no_input=True,viewer=False)
    assert code==2
    assert emitted[-1]['gate']=='requirements' and emitted[-1]['status']=='REQUIREMENTS_WAITING'
    assert emitted[-1]['requirements_sha256']
    assert idea.read_bytes()==original


def test_canonical_template_and_render_keep_domain_lifecycle_and_delivery_sections():
    service = api()
    text = service.render(draft(), 'CLI business rationale')
    for heading in ['Purpose and desired outcome', 'Scope and ownership',
                    'Existing patterns and integration context', 'Required behavior and business rules',
                    'Data, relationships and lifecycle', 'Acceptance examples',
                    'Verification and delivery constraints', 'Questions, decisions and approval']:
        assert heading in service.template()
        assert heading in text
    assert 'CLI business rationale' in text
    assert [text.index(f'## {i}.') for i in range(1,9)] == sorted(text.index(f'## {i}.') for i in range(1,9))


def test_feedback_checkpoint_reconnect_revises_before_fresh_approval(current_autonomous_run):
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from council.checkpoint import managed_sqlite_checkpointer
    from council.graph import build_council_graph
    run = current_autonomous_run
    run.state['intake_enabled'] = True
    class Provider:
        def bind_tools(self, tools):
            return self
        def with_structured_output(self, schema, **kwargs):
            self.structured = True
            return self
        def invoke(self, messages):
            if getattr(self, 'structured', False):
                revised = any('Support help' in str(m) for m in messages)
                return {'parsed':draft('Support help' if revised else 'CLI'), 'raw':None, 'parsing_error':None}
            return AIMessage(content='No additional source needed', tool_calls=[])
    def build(saver):
        return build_council_graph(checkpointer=saver, context=run.fixture.context,
            llm_factory=lambda role:Provider())
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph = build(saver)
        first = graph.invoke(run.state, run.fixture.config)
        sha = first['requirements']['document_sha256']
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        graph = build(saver)
        revised = graph.invoke(Command(resume={'feedback':'Support help'}), run.fixture.config)
        assert revised['__interrupt__'][0].value['gate'] == 'requirements'
        assert revised['requirements']['feedback'] == ['Support help']
        assert len(revised['requirements']['revisions']) == 2
        assert revised['requirements']['approved_sha256'] is None
        assert revised['requirements']['document_sha256'] != sha
        assert revised['roadmap'] is None
        assert revised['requirements']['inspection_rounds'] == 2


def test_material_planning_question_returns_to_exact_requirements_approval(current_autonomous_run):
    from council.checkpoint import managed_sqlite_checkpointer
    from council.delivery_contracts import RequirementsDraft
    from council.graph import build_council_graph
    from langchain_core.messages import AIMessage
    from langgraph.types import Command
    from types import SimpleNamespace
    from test_autonomous_review import Reviewer
    run = current_autonomous_run
    run.state['intake_enabled'] = True
    drafts = []
    base = run.provider
    class Provider:
        def bind_tools(self, tools):
            return SimpleNamespace(invoke=lambda messages:AIMessage(content='Read-only inspection complete'))
        def with_structured_output(self, schema, **kwargs):
            if schema is RequirementsDraft:
                def produce(messages):
                    drafts.append(messages)
                    return {'parsed':draft('Revised CLI scope' if len(drafts)>1 else 'CLI scope'),'raw':None,'parsing_error':None}
                return SimpleNamespace(invoke=produce)
            return base.with_structured_output(schema,**kwargs)
        def run_task(self,*args,**kwargs):
            return base.run_task(*args,**kwargs)
    accept = {'decision':'accept','findings':[],'resolved_finding_ids':[]}
    reviewer = Reviewer([accept,{'decision':'escalate','findings':[
        {'id':'F1','description':'R1 requires a human scope decision','kind':'user_decision'}],
        'resolved_finding_ids':[]},accept,accept])
    def build(saver):
        return build_council_graph(checkpointer=saver,context=run.fixture.context,
            llm_factory=lambda role:reviewer if role=='reviewer' else Provider())
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        graph = build(saver)
        first = graph.invoke(run.state,run.fixture.config)
        sha = first['requirements']['document_sha256']
        reopened = graph.invoke(Command(resume={'requirements_sha256':sha}),run.fixture.config)
        assert reopened['__interrupt__'][0].value['gate']=='requirements'
        assert len(reopened['requirements']['revisions'])==2
        assert reopened['requirements']['approved_sha256'] is None
        assert not base.attempts
        assert reopened['requirements']['feedback']==[], 'Model findings must not impersonate human feedback'
        revised_sha = reopened['requirements']['document_sha256']
    with managed_sqlite_checkpointer(db_path=run.fixture.db) as saver:
        completed = build(saver).invoke(Command(resume={'requirements_sha256':revised_sha}),run.fixture.config)
    assert completed['status']=='COMPLETED',completed.get('diagnostic')
    assert completed['requirements']['approved_sha256']==revised_sha
    assert completed['requirements']['superseded_deliveries'][0]['requirements_sha256']==sha


@pytest.mark.parametrize('used',[0,6,8])
def test_repeated_boundary_rejections_keep_intake_inspection_budget(current_autonomous_run,used):
    from council.graph import build_council_graph
    from council.checkpoint import managed_sqlite_checkpointer
    from langchain_core.messages import AIMessage
    run=current_autonomous_run;run.state['intake_enabled']=True
    run.state['requirements']['inspection_rounds']=used
    inspections=[]
    class Provider:
        def bind_tools(self,tools):return self
        def with_structured_output(self,schema,**kwargs):self.structured=True;return self
        def invoke(self,messages):
            if getattr(self,'structured',False):return {'parsed':draft(),'raw':None,'parsing_error':None}
            inspections.append(True)
            return AIMessage(content='',tool_calls=[{'name':'read_workspace_file','args':{'rel_path':'.env'},'id':'denied'}])
    with managed_sqlite_checkpointer(context=run.fixture.context) as saver:
        result=build_council_graph(checkpointer=saver,context=run.fixture.context,llm_factory=lambda role:Provider()).invoke(run.state,run.fixture.config)
    assert '__interrupt__' in result,result.get('diagnostic')
    expected=min(2,8-used)
    assert len(inspections)==expected
    assert result['requirements']['inspection_rounds']==used+expected
    assert result['requirements']['drafting_attempts']==1
    assert result['requirements']['sources']==[]
    assert result['modified_files']==[] and result['planning_evidence']==[]
    assert result['requirements']['approved_sha256'] is None
