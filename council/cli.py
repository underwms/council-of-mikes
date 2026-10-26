"""CLI for native, durable Council runs and offline runtime diagnosis."""
import argparse
import json
import sys
import uuid
from pathlib import Path
from council.state import CouncilState
from council.graph import build_council_graph, the_architect_node
from council.checkpoint import managed_sqlite_checkpointer
from council.runtime_context import resolve_context
from council.config import resolve_model_configuration, RunModelConfiguration, preflight_credentials, PROVIDER_KEYS
from langgraph.types import Command
from council.diagnostics import DiagnosticSession, DiagnosticRuntimeError, describe, current_session
from council.plan_review import blocked_payload, validation_summary
from council.console_cue import show_status_cue
from council.viewer import launch_viewer
from council import recovery
from council.recovery_contracts import RecoveryPolicy
from council import requirements

REVIEW_PROTOCOL_VERSION = 2
READINESS_POLICY_VERSION = 3
ORCHESTRATION_POLICY_VERSION = 2
GRAPH_INTEGRITY_POLICY_VERSION = 2
GOVERNANCE_POLICY_VERSION = 2

def create_parser():
    parser = argparse.ArgumentParser(prog='council')
    parser.add_argument('prompt', nargs='?', default='')
    parser.add_argument('--story')
    parser.add_argument('--requirements-file', help='Workspace-relative Markdown analysis; draft and explicitly approve requirements before planning')
    parser.add_argument('--finalize', action='store_true', help='Require reviewed code/documentation polish and independent finished-content review for a new run (included in requirements intake)')
    parser.add_argument('--approve-requirements', help='Approve the exact current requirements document SHA256 on resume')
    parser.add_argument('--accept-limitation', action='append', default=[], help='Explicitly accept a bounded requirements question ID on approval')
    parser.add_argument('--workspace')
    parser.add_argument('--council-root')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--no-input', action='store_true', help='Pause at approval gates without prompting')
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument('--auto-approve', '-y', action='store_true', help='Explicitly bypass engine review')
    policy.add_argument('--approval-mode', choices=['autonomous', 'manual'], help='New runs default to autonomous Council review')
    parser.add_argument('--feedback-file', help='Workspace-relative UTF-8 feedback for a blocked planning run')
    parser.add_argument('--resume')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-viewer', action='store_true', help='Do not open the local run viewer')
    parser.add_argument('--recovery', choices=['enabled','disabled'], help='New autonomous runs enable bounded arbiter recovery; resume preserves recorded policy')
    parser.add_argument('--max-retries', type=int, choices=range(3), default=2, help='Repair retries after initial verification (0-2)')
    return parser

def emit(value):
    session = current_session()
    if session is not None and value.get('status') is not None:
        session.finish()
        value = {**value, 'run_id': session.run_id, **session.summary()}
    show_status_cue(value)
    print(json.dumps(value, ensure_ascii=True), flush=True)

def doctor(context):
    # Use an isolated in-memory DB: no private task/checkpoint mutation or API requests.
    with managed_sqlite_checkpointer(db_path=':memory:') as saver:
        graph = build_council_graph(checkpointer=saver, context=context)
        assert graph is not None
    configuration = resolve_model_configuration(autonomous=True)
    readiness = preflight_credentials(configuration)
    emit({'status':'ok', 'workspace_root':str(context.workspace_root), 'council_root':str(context.council_root),
          'native_graph':True, 'sqlite_checkpoint':True, 'provider_requests':0,
          'model_configuration': configuration.model_dump(mode='json'),
          'credential_presence': {provider: ready for provider, ready in readiness.items() if provider in PROVIDER_KEYS},
          'transport_readiness': readiness, 'live_provider_access':'unverified'})
    return 0


def credentials_available(configuration):
    readiness = preflight_credentials(configuration)
    missing = [PROVIDER_KEYS[provider] for provider, present in readiness.items() if not present and provider in PROVIDER_KEYS]
    unavailable = [provider for provider, present in readiness.items() if not present and provider not in PROVIDER_KEYS]
    if missing or unavailable:
        emit({'status': 'FAILED', 'error': 'Selected model transport is unavailable',
              'diagnostic': describe(DiagnosticRuntimeError('PROVIDER_UNAVAILABLE')),
              'missing_credentials': missing, 'unavailable_transports': unavailable,
              'remediation': 'Install the CLIs and sign in to Gemini CLI with Google and Codex with ChatGPT. API transports require their named keys.'})
    return not missing and not unavailable

def run_council_task(prompt='', story=None, auto_approve=False, resume_id=None, dry_run=False, max_retries=2,
                     workspace_root=None, council_root=None, no_input=False, approval_mode=None, feedback_file=None,
                     viewer=False, recovery_mode=None, requirements_file=None, approve_requirements=None,
                     accepted_limitations=None, finalize=False):
    context = resolve_context(workspace_root, council_root)
    if finalize and resume_id:
        raise ValueError('Finalization policy is fixed at run creation')
    if requirements_file and (story or prompt or resume_id or dry_run):
        raise ValueError('Requirements submission is a separate new-run entry point')
    if (approve_requirements and (not resume_id or feedback_file)) or (accepted_limitations and not approve_requirements):
        raise ValueError('Requirements approval requires resume and cannot be combined with feedback')
    if requirements_file:
        with context.workspace_path(requirements_file).open('rb') as source:
            data = source.read(96001)
        if len(data) > 96000:
            raise ValueError('Requirements input exceeds 96000 bytes')
        prompt = data.decode('utf-8-sig')
    if recovery_mode not in (None,'enabled','disabled') or (resume_id and recovery_mode is not None):
        raise ValueError('Recovery selection applies only to new runs')
    if auto_approve and approval_mode is not None:
        raise ValueError('Conflicting approval policies')
    if approval_mode not in (None, 'autonomous', 'manual'):
        raise ValueError('Invalid approval policy')
    if feedback_file and not resume_id:
        raise ValueError('Feedback requires a blocked run ID')
    feedback = None
    if feedback_file:
        with context.workspace_path(feedback_file).open('rb') as source:
            data = source.read(48001)
        if len(data) > 48000:
            raise ValueError('Feedback exceeds limit')
        feedback = data.decode('utf-8').strip()
        if not feedback or len(feedback) > 12000:
            raise ValueError('Feedback must contain 1-12000 characters')
    session = current_session()
    if session is not None:
        session.attach(context.memory_root)
        session.event('run_started')
    if story:
        try:
            prompt = context.workspace_path(story).read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            if session is not None:
                code = 'STORY_PATH_INVALID' if isinstance(error, PermissionError) and Path(story).is_absolute() else 'STORY_READ_FAILED'
                raise DiagnosticRuntimeError(code) from None
            raise
    if not resume_id and not prompt.strip():
        raise ValueError('Task input is required')
    if dry_run:
        if resume_id:
            raise ValueError('Dry-run cannot resume an executing task')
        configuration = resolve_model_configuration()
        if not credentials_available(configuration):
            return 1
        state = the_architect_node(CouncilState(run_id=session.run_id if session else uuid.uuid4().hex, task_input=prompt,
                                               model_configuration=configuration.model_dump(mode='json')), context=context)
        emit({'status':'PLAN_ONLY','plan':state.plan.model_dump(mode='json'),
              'planning_inspection': state.planning_inspection.model_dump(mode='json') if state.planning_inspection else None,
              'model_configuration':state.model_configuration, 'model_calls':state.model_calls})
        return 0
    run_id = resume_id or (session.run_id if session else uuid.uuid4().hex)
    configuration = {'configurable':{'thread_id':run_id}, 'recursion_limit':1100}
    if session is not None:
        from council.narration_hooks import NodeNarrationCapture
        configuration['callbacks'] = [NodeNarrationCapture(context, session)]
    with managed_sqlite_checkpointer(context=context) as saver:
        graph = build_council_graph(checkpointer=saver, context=context)
        if resume_id:
            snapshot = graph.get_state(configuration)
            if not snapshot.values:
                raise ValueError('Checkpoint not found')
            recorded = CouncilState.model_validate(snapshot.values)
            if not recorded.model_configuration:
                raise ValueError('Legacy checkpoint lacks model configuration; start a new run')
            RunModelConfiguration.model_validate(recorded.model_configuration)
            if (recorded.workspace_root,recorded.council_root,recorded.memory_root) != (str(context.workspace_root),str(context.council_root),str(context.memory_root)):
                raise ValueError('Resume context mismatch')
            if approval_mode is not None or (recorded.approval_policy == 'autonomous' and auto_approve):
                raise ValueError('Resume preserves the recorded approval policy')
            autonomous = recorded.approval_policy == 'autonomous'
            waiting_requirements = recorded.intake_enabled and recorded.status == 'REQUIREMENTS_WAITING'
            if approve_requirements and not waiting_requirements:
                raise ValueError('Run is not waiting for requirements approval')
            if feedback is not None and not waiting_requirements and (not autonomous or recorded.status != 'PLAN_BLOCKED'):
                raise ValueError('Feedback requires an autonomous planning blocker')
            if not snapshot.tasks or not any(task.interrupts for task in snapshot.tasks):
                pending_recovery=(recovery.enabled(recorded) and snapshot.next and recorded.status!='COMPLETED'
                    and (recorded.recovery_incident is not None or set(snapshot.next)<=recovery.RECOVERY_NODES))
                if pending_recovery:
                    if not credentials_available(recorded.model_configuration):return 1
                    launch_viewer(context,run_id,interactive=viewer)
                    result=graph.invoke(None,configuration)
                else:
                    emit({'run_id':run_id,'status':recorded.status, 'error': recorded.error, 'diagnostic': recorded.diagnostic,
                          'planning_inspection': recorded.planning_inspection.model_dump(mode='json') if recorded.planning_inspection else None})
                    return 0 if recorded.status=='COMPLETED' else 1
            elif waiting_requirements:
                if feedback is None and approve_requirements is None:
                    emit({**requirements.approval_payload(recorded), 'resume_required':True})
                    return 2
                response = {'feedback':feedback} if feedback is not None else {
                    'requirements_sha256':approve_requirements, 'accepted_limitations':accepted_limitations or []}
                # Validate approval before consuming the checkpoint interrupt.
                if feedback is None:
                    requirements.approve(recorded.model_copy(deep=True), response)
                if not credentials_available(recorded.model_configuration):
                    return 1
                result = graph.invoke(Command(resume=response), configuration)
            elif autonomous:
                if feedback is None:
                    emit({**blocked_payload(recorded), 'resume_required': True})
                    return 2
                if not credentials_available(recorded.model_configuration):
                    return 1
                launch_viewer(context, run_id, interactive=viewer)
                result = graph.invoke(Command(resume={'feedback': feedback}), configuration)
            elif not auto_approve and (no_input or not sys.stdin.isatty()):
                emit({'run_id':run_id,'status':'PAUSED','resume_required':True,
                      'planning_inspection': recorded.planning_inspection.model_dump(mode='json') if recorded.planning_inspection else None})
                return 2
            else:
                if not auto_approve:
                    emit(next(interruption.value for task in snapshot.tasks for interruption in task.interrupts))
                if not credentials_available(recorded.model_configuration):
                    return 1
                approved = auto_approve or input('Approve paused gate? [y/N]: ').strip().lower() in ('y','yes')
                launch_viewer(context, run_id, interactive=viewer)
                result = graph.invoke(Command(resume={'approved':approved}), configuration)
        else:
            policy = 'bypass' if auto_approve else approval_mode or 'autonomous'
            if finalize and policy!='autonomous':
                raise ValueError('--finalize requires autonomous independent review; requirements intake still supports manual approval')
            selected = resolve_model_configuration(autonomous=policy == 'autonomous')
            if not credentials_available(selected):
                return 1
            state = CouncilState(run_id=run_id,thread_id=run_id,task_input=prompt,auto_approve=auto_approve,
                                 intake_enabled=bool(requirements_file),
                                 finalization_enabled=bool(requirements_file or finalize) and policy=='autonomous',
                                 approval_policy=policy,
                                 recovery_policy=RecoveryPolicy(version=1 if policy=='autonomous' and recovery_mode!='disabled' else 0),
                                 orchestration_policy_version=ORCHESTRATION_POLICY_VERSION if policy == 'autonomous' else 1,
                                 graph_integrity_policy_version=GRAPH_INTEGRITY_POLICY_VERSION if policy == 'autonomous' else 1,
                                 governance_policy_version=GOVERNANCE_POLICY_VERSION if policy == 'autonomous' else 1,
                                 review_protocol_version=REVIEW_PROTOCOL_VERSION if policy == 'autonomous' else 1,
                                 revision_evidence_policy_version=2 if policy == 'autonomous' else 1,
                                 readiness_policy_version=READINESS_POLICY_VERSION if policy == 'autonomous' else 1,
                                 max_test_retries=max_retries,max_steps=400 if policy == 'autonomous' else 100,
                                 workspace_root=str(context.workspace_root),
                                 council_root=str(context.council_root),memory_root=str(context.memory_root),
                                 model_configuration=selected.model_dump(mode='json'))
            launch_viewer(context, run_id, interactive=viewer)
            result = graph.invoke(state.model_dump(mode='json'), configuration)
        while result.get('__interrupt__'):
            if result['__interrupt__'][0].value.get('gate') == 'requirements':
                emit({**result['__interrupt__'][0].value, 'resume_required':True})
                return 2
            if result.get('approval_policy') == 'autonomous':
                emit({**result['__interrupt__'][0].value, 'resume_required': True})
                return 2
            if auto_approve:
                result = graph.invoke(Command(resume={'approved':True}), configuration)
                continue
            if no_input or not sys.stdin.isatty():
                emit({'run_id':run_id,'status':'PAUSED','gate':result['__interrupt__'][0].value['gate'],
                      'planning_inspection': result.get('planning_inspection')})
                return 2
            value = result['__interrupt__'][0].value
            emit(value)
            approved = input('Approve gate? [y/N]: ').strip().lower() in ('y','yes')
            result = graph.invoke(Command(resume={'approved':approved}), configuration)
        from council.readiness import summary as readiness_summary
        emit({'run_id':run_id,'status':result['status'],'error':result.get('error'),
              'orchestration_policy_version': result.get('orchestration_policy_version', 1),
              'roadmap': result.get('roadmap'),
              'current_phase_index': result.get('current_phase_index', 0),
              'completed_phases': result.get('completed_phases', []),
              'delivery_result': result.get('delivery_result', {}),
              'governance_policy_version': result.get('governance_policy_version', 1),
              'work_pieces': result.get('work_pieces', {}),
              'shared_contracts': result.get('shared_contracts', {}),
              'contract_history': result.get('contract_history', []),
              'roadmap_review_count': result.get('roadmap_review_count', 0),
              'total_inspection_rounds': result.get('total_inspection_rounds', 0),
              'readiness': readiness_summary(CouncilState.model_validate(result)),
              'diagnostic':result.get('diagnostic'),
              'recovery_policy':result.get('recovery_policy'),
              'recovery_incident':result.get('recovery_incident'),
              'recovery_history':result.get('recovery_history',[]),
              'planning_inspection':result.get('planning_inspection'),
              'workspace_validator_passed':result.get('workspace_validator_passed'), 'test_results':result.get('test_results',[]),
              'modified_files':result.get('modified_files',[]), 'file_changes':result.get('file_changes',[]),
              'model_calls':result.get('model_calls',[]), 'model_configuration':result.get('model_configuration'),
              'approval_policy': result.get('approval_policy'),
              'review_protocol_version': result.get('review_protocol_version', 1),
              'review_no_progress_count': result.get('review_no_progress_count', 0),
              'plan_preflight_failure_count': result.get('plan_preflight_failure_count', 0),
              'last_plan_validation': validation_summary(CouncilState.model_validate(result)),
              'red_phase_evidence': result.get('red_phase_evidence', []),
              'completed_red_phase_evidence': result.get('completed_red_phase_evidence', []),
              'evidence_available': result.get('planning_evidence_available', False),
              'evidence_truncated': result.get('planning_evidence_truncated', False),
              'plan_review_count': result.get('plan_review_count', 0),
              'plan_revision_count': result.get('plan_revision_count', 0),
              'plan_recovery_count': result.get('plan_recovery_count', 0),
              'accepted_plan_sha256': result.get('accepted_plan_sha256'),
              'review_phases':result.get('gatekeeper_summary',{}).get('review_phases',{})})
        return 0 if result['status']=='COMPLETED' else 1

def main(argv=None):
    args = create_parser().parse_args(argv)
    if args.doctor:
        try:
            return doctor(resolve_context(args.workspace,args.council_root))
        except Exception as error:
            emit({'status': 'FAILED', 'diagnostic': describe(error)})
            return 1
    # Invalid resume identifiers cannot become filenames; correlate their failure
    # using a new local ID without echoing arbitrary user input.
    try:
        session = DiagnosticSession(args.resume or uuid.uuid4().hex)
    except ValueError:
        emit({'status': 'FAILED', 'run_id': uuid.uuid4().hex, 'diagnostic': describe(ValueError())})
        return 1
    with session:
        try:
            interactive_viewer = not args.no_viewer and not args.no_input and sys.stdin.isatty() and sys.stdout.isatty()
            return run_council_task(args.prompt,args.story,args.auto_approve,args.resume,args.dry_run,args.max_retries,args.workspace,args.council_root,args.no_input,args.approval_mode,args.feedback_file,viewer=interactive_viewer,recovery_mode=args.recovery,
                requirements_file=args.requirements_file, approve_requirements=args.approve_requirements,
                accepted_limitations=args.accept_limitation, finalize=args.finalize)
        except Exception as error:
            detail = describe(error)
            session.event('runtime_failed', diagnostic=error)
            emit({'status':'FAILED', 'error': detail['message'], 'diagnostic': detail})
            return 1

if __name__ == '__main__':
    raise SystemExit(main())
