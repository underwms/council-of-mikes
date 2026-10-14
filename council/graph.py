"""Native LangGraph lifecycle with real evidence and explicit approval interrupts."""
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.errors import GraphBubbleUp
from council.state import CouncilState, MultiSpecialistPlan, TestExecutionResult
from council.config import get_llm_for_role
from council.specialists import SpecialistLoader
from council.tools.tool_registry import get_council_tools
from council.tools.validator_bridge import run_workspace_audit
from council.runner import SubprocessRunner
from council.tools.test_runner import parse_test_counts

def the_architect_node(state, llm_factory=None):
    if not isinstance(state, CouncilState):
        state = CouncilState.model_validate(state)
    if state.plan is None:
        provider = (llm_factory or get_llm_for_role)('orchestrator')
        response = provider.with_structured_output(MultiSpecialistPlan).invoke(
            'Create a scoped specialist plan. Include explicit argv test_commands and relative working_directory for every task. '
            'The user must approve these commands before execution. Requirement: ' + state.task_input)
        state.plan = MultiSpecialistPlan.model_validate(response)
    state.status = 'PLAN_REVIEW'
    return state

def build_council_graph(checkpointer=None, context=None, llm_factory=None):
    if checkpointer is None:
        raise ValueError('A managed durable checkpointer is required')
    if context is None:
        from council.runtime_context import resolve_context
        context = resolve_context()
    factory = llm_factory or get_llm_for_role
    transient_diagnostics = {}
    transient_test_output = {}
    fields = {name: object for name in CouncilState.model_fields}
    from typing import TypedDict
    Channels = TypedDict('CouncilChannels', fields, total=False)

    def wrap(operation):
        def node(raw):
            state = CouncilState.model_validate(raw)
            identity = (str(context.workspace_root), str(context.council_root), str(context.memory_root))
            recorded = (state.workspace_root, state.council_root, state.memory_root)
            if recorded != identity or not state.thread_id or state.thread_id != state.run_id:
                raise ValueError('Run identity or workspace context mismatch')
            if state.step_count >= state.max_steps:
                state.status, state.error = 'FAILED', 'Maximum graph steps exhausted'
                return state.model_dump(mode='json')
            state.step_count += 1
            try:
                operation(state)
            except GraphBubbleUp:
                raise
            except Exception as error:
                state.status = 'FAILED'
                state.error = f'{type(error).__name__}: execution failed (details withheld)'
            return state.model_dump(mode='json')
        return node

    def architect(state):
        the_architect_node(state, factory)
        for task in state.plan.tasks:
            if not task.test_commands or any(not command or any(not isinstance(arg, str) or not arg for arg in command) for command in task.test_commands):
                raise ValueError('Every task requires explicit verification argv')
            context.workspace_path(task.working_directory)
            for path in task.target_files:
                context.workspace_path(path)
            if SpecialistLoader(context=context).get_specialist(task.specialist) is None:
                raise ValueError('Unknown specialist')

    def gate(state, label):
        if not state.auto_approve:
            decision = interrupt({'gate': label, 'run_id': state.run_id,
                                  'plan': state.plan.model_dump(mode='json') if label == 'GATE_1_PLAN_APPROVAL' else None,
                                  'workspace_validator_passed': state.workspace_validator_passed})
            if not isinstance(decision, dict) or decision.get('approved') is not True:
                state.status, state.error = 'FAILED', 'Approval rejected'
                return
        state.status = 'EXECUTING' if label == 'GATE_1_PLAN_APPROVAL' else 'COMPLETED'

    def worker(state):
        task = state.plan.tasks[state.current_task_index]
        task.status = 'in_progress'
        state.active_specialist = task.specialist
        specialist = SpecialistLoader(context=context).get_specialist(task.specialist)
        if specialist is None:
            raise ValueError('Unknown specialist')
        tools = get_council_tools(specialist=task.specialist, context=context)
        provider = factory(state.active_role).bind_tools(tools)
        messages = [{'role':'system','content': specialist.instructions},
                    {'role':'user','content': task.description + '\nTarget files: ' + str(task.target_files) + '\nAcceptance criteria: ' + str(task.acceptance_criteria) + '\nPrior execution: ' + str(state.test_result.model_dump() if state.test_result else None)}]
        if state.run_id in transient_diagnostics:
            messages.append({'role':'user','content':transient_diagnostics.pop(state.run_id)})
        tool_map = {tool.name: tool for tool in tools}
        for iteration in range(12):
            response = provider.invoke(messages)
            calls = getattr(response, 'tool_calls', None) or []
            if not calls:
                state.status = 'TESTING'
                return
            messages.append(response)
            from langchain_core.messages import ToolMessage
            for call in calls:
                if not isinstance(call, dict) or not isinstance(call.get('id'), str) or not call['id'] or not isinstance(call.get('args'), dict):
                    raise ValueError('Invalid tool call envelope')
                name = call.get('name')
                if name not in tool_map:
                    raise ValueError('Unknown tool requested')
                result = tool_map[name].invoke(call.get('args', {}))
                if isinstance(result, dict) and (result.get('error') or result.get('passed') is False):
                    raise RuntimeError('Tool failed')
                state.tool_call_history.append({'tool': name, 'succeeded': True})
                messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))
        raise RuntimeError('Maximum tool rounds exhausted')

    def prover(state):
        task = state.plan.tasks[state.current_task_index]
        runner = SubprocessRunner(context=context)
        cwd = context.workspace_path(task.working_directory)
        # Recheck defensively if a persisted task/checkpoint changed after planning.
        if not task.test_commands:
            raise ValueError('No approved test commands')
        all_passed = True
        first_failure = None
        failure_output = ''
        for argv in task.test_commands:
            code, stdout, stderr = runner.run(argv, cwd=cwd)
            output = stdout + '\n' + stderr
            transient_test_output[state.run_id] = output[-4000:] if code else ''
            counts = parse_test_counts(output)
            known = counts[0] is not None and counts[1] is not None
            result = TestExecutionResult(command=argv[0], passed=code == 0, exit_code=code,
                                         tests_passed=counts[0], tests_failed=counts[1], counts_known=known,
                                         failure_output='' if code == 0 else f'Verification exited with code {code}')
            if not result.passed and first_failure is None:
                first_failure = result
                failure_output = output[-4000:]
            state.test_result = result
            state.test_results.append({'task_id':task.id, **result.model_dump()})
            all_passed = all_passed and result.passed
        if not all_passed:
            state.test_result = first_failure
            transient_test_output[state.run_id] = failure_output
            if state.test_retry_count >= min(state.max_test_retries, 2):
                state.status, state.error = 'FAILED', 'Test repair retries exhausted'
            else:
                state.status = 'RETRYING'
        else:
            task.status = 'completed'
            state.test_retry_count = 0
            state.active_role = 'orchestrator'
            state.current_task_index += 1
            state.status = 'EXECUTING' if state.current_task_index < len(state.plan.tasks) else 'GATEKEEPER_AUDIT'

    def investigate(state):
        response = factory('investigator').invoke('Investigate actual failed verification: ' + str(state.test_result.model_dump()) + '\nObserved bounded process output:\n' + transient_test_output.pop(state.run_id, ''))
        content = getattr(response, 'content', '')
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Investigator returned no diagnosis')
        transient_diagnostics[state.run_id] = content[:4000]
        state.investigation_report = 'Investigator consulted for recorded verification failure'
        state.test_retry_count += 1
        import os
        state.active_role = 'escalation' if state.test_retry_count >= 2 and os.environ.get('COUNCIL_ENABLE_ESCALATION','false').lower() in ('true','1','yes') else 'orchestrator'
        state.status = 'EXECUTING'

    def audit(state):
        passed, summary = run_workspace_audit(context=context)
        state.workspace_validator_passed = bool(passed)
        state.gatekeeper_summary = {'passed': bool(passed)}
        state.status = 'FINAL_REVIEW' if passed else 'FAILED'
        if not passed:
            state.error = 'Workspace validation failed'

    graph = StateGraph(Channels)
    for name, operation in [('architect',architect), ('plan_review',lambda state: gate(state,'GATE_1_PLAN_APPROVAL')),
                            ('worker',worker), ('prover',prover), ('investigation',investigate), ('gatekeeper',audit),
                            ('final_review',lambda state: gate(state,'GATE_2_PRE_SUBMIT_APPROVAL'))]:
        graph.add_node(name, wrap(operation))
    graph.add_edge(START, 'architect')
    def route(default):
        return lambda state: END if state.get('status') == 'FAILED' else default
    graph.add_conditional_edges('architect',route('plan_review'))
    graph.add_conditional_edges('plan_review',route('worker'))
    graph.add_conditional_edges('worker',route('prover'))
    graph.add_conditional_edges('prover',lambda state: END if state['status']=='FAILED' else 'investigation' if state['status']=='RETRYING' else 'worker' if state['status']=='EXECUTING' else 'gatekeeper')
    graph.add_conditional_edges('investigation',route('worker'))
    graph.add_conditional_edges('gatekeeper',route('final_review'))
    graph.add_edge('final_review',END)
    return graph.compile(checkpointer=checkpointer)
