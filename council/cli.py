"""CLI for native, durable Council runs and offline runtime diagnosis."""
import argparse
import json
import sys
import uuid
from council.state import CouncilState
from council.graph import build_council_graph, the_architect_node
from council.checkpoint import managed_sqlite_checkpointer
from council.runtime_context import resolve_context
from langgraph.types import Command

def create_parser():
    parser = argparse.ArgumentParser(prog='council')
    parser.add_argument('prompt', nargs='?', default='')
    parser.add_argument('--story')
    parser.add_argument('--workspace')
    parser.add_argument('--council-root')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--no-input', action='store_true', help='Pause at approval gates without prompting')
    parser.add_argument('--auto-approve', '-y', action='store_true')
    parser.add_argument('--resume')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-retries', type=int, choices=range(3), default=2, help='Repair retries after initial verification (0-2)')
    return parser

def emit(value):
    print(json.dumps(value, ensure_ascii=True))

def doctor(context):
    # Use an isolated in-memory DB: no private task/checkpoint mutation or API requests.
    with managed_sqlite_checkpointer(db_path=':memory:') as saver:
        graph = build_council_graph(checkpointer=saver, context=context)
        assert graph is not None
    emit({'status':'ok', 'workspace_root':str(context.workspace_root), 'council_root':str(context.council_root),
          'native_graph':True, 'sqlite_checkpoint':True, 'provider_requests':0})
    return 0

def run_council_task(prompt='', story=None, auto_approve=False, resume_id=None, dry_run=False, max_retries=2,
                     workspace_root=None, council_root=None, no_input=False):
    context = resolve_context(workspace_root, council_root)
    if story:
        prompt = context.workspace_path(story).read_text(encoding='utf-8')
    if not resume_id and not prompt.strip():
        raise ValueError('Task input is required')
    if dry_run:
        if resume_id:
            raise ValueError('Dry-run cannot resume an executing task')
        state = the_architect_node(CouncilState(run_id=uuid.uuid4().hex, task_input=prompt))
        emit({'status':'PLAN_ONLY','plan':state.plan.model_dump(mode='json')})
        return 0
    run_id = resume_id or uuid.uuid4().hex
    configuration = {'configurable':{'thread_id':run_id}, 'recursion_limit':1100}
    with managed_sqlite_checkpointer(context=context) as saver:
        graph = build_council_graph(checkpointer=saver, context=context)
        if resume_id:
            snapshot = graph.get_state(configuration)
            if not snapshot.values:
                raise ValueError('Checkpoint not found')
            recorded = CouncilState.model_validate(snapshot.values)
            if (recorded.workspace_root,recorded.council_root,recorded.memory_root) != (str(context.workspace_root),str(context.council_root),str(context.memory_root)):
                raise ValueError('Resume context mismatch')
            if not snapshot.tasks or not any(task.interrupts for task in snapshot.tasks):
                emit({'run_id':run_id,'status':recorded.status})
                return 0 if recorded.status=='COMPLETED' else 1
            if not auto_approve and (no_input or not sys.stdin.isatty()):
                emit({'run_id':run_id,'status':'PAUSED','resume_required':True})
                return 2
            if not auto_approve:
                emit(next(interruption.value for task in snapshot.tasks for interruption in task.interrupts))
            approved = auto_approve or input('Approve paused gate? [y/N]: ').strip().lower() in ('y','yes')
            result = graph.invoke(Command(resume={'approved':approved}), configuration)
        else:
            state = CouncilState(run_id=run_id,thread_id=run_id,task_input=prompt,auto_approve=auto_approve,
                                 max_test_retries=max_retries,workspace_root=str(context.workspace_root),
                                 council_root=str(context.council_root),memory_root=str(context.memory_root))
            result = graph.invoke(state.model_dump(mode='json'), configuration)
        while result.get('__interrupt__'):
            if auto_approve:
                result = graph.invoke(Command(resume={'approved':True}), configuration)
                continue
            if no_input or not sys.stdin.isatty():
                emit({'run_id':run_id,'status':'PAUSED','gate':result['__interrupt__'][0].value['gate']})
                return 2
            value = result['__interrupt__'][0].value
            emit(value)
            approved = input('Approve gate? [y/N]: ').strip().lower() in ('y','yes')
            result = graph.invoke(Command(resume={'approved':approved}), configuration)
        emit({'run_id':run_id,'status':result['status'],'error':result.get('error'),
              'workspace_validator_passed':result.get('workspace_validator_passed'), 'test_results':result.get('test_results',[])})
        return 0 if result['status']=='COMPLETED' else 1

def main(argv=None):
    args = create_parser().parse_args(argv)
    try:
        if args.doctor:
            return doctor(resolve_context(args.workspace,args.council_root))
        return run_council_task(args.prompt,args.story,args.auto_approve,args.resume,args.dry_run,args.max_retries,args.workspace,args.council_root,args.no_input)
    except Exception as error:
        emit({'status':'FAILED','error':f'{type(error).__name__}: runtime failed; verify context, dependencies and provider configuration'})
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
