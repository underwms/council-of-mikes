"""Finite diagnostic catalog and private, bounded lifecycle events. No payload logging."""
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import sqlite3
import uuid

# Messages are constants, never derived from exception bodies or provider output.
CATALOG = {
    'FINAL_REVIEW_NON_TEXT_UNSUPPORTED': ('delivery', 'Non-text feature content requires a supported content-review path.'),
    'REQUIREMENTS_DRAFT_REJECTED': ('input', 'Requirements drafting exhausted its bounded attempts without satisfying source, identity or document limits.'),
    'DELIVERY_BOUNDARY_NOT_MET': ('delivery', 'Functional behavior does not satisfy the approved PR-readiness boundary; required quality evidence remains unresolved.'),
    'RECOVERY_REJECTED': ('recovery', 'Recovery evidence, action or checkpoint binding was rejected.'),
    'RECOVERY_EXHAUSTED': ('recovery', 'The bounded recovery allowance is exhausted.'),
    'RECOVERY_NO_PROGRESS': ('recovery', 'The proposed recovery retains the command that caused the recorded failure.'),
    'GOVERNANCE_CONTRACT_INVALID': ('plan_review', 'Architecture links or shared-contract changes need correction.'),
    'INTERNAL_ERROR': ('runtime', 'An unclassified operation failed; raw details are withheld.'),
    'PERMISSION_DENIED': ('runtime', 'A filesystem or execution boundary rejected access.'),
    'STORY_PATH_INVALID': ('input', 'Story paths must be relative to the selected workspace.'),
    'STORY_READ_FAILED': ('input', 'The development instruction file could not be read.'),
    'CLI_START_FAILED': ('transport', 'The native CLI could not start.'),
    'CLI_TIMEOUT': ('transport', 'The native CLI timed out.'),
    'CLI_INPUT_INVALID': ('input', 'Native CLI input could not be encoded.'),
    'CLI_INPUT_LIMIT': ('input', 'Native CLI input limit exceeded.'),
    'CLI_OUTPUT_LIMIT': ('transport', 'Native CLI output limit exceeded.'),
    'CLI_IO_FAILED': ('transport', 'Native CLI pipe failed.'),
    'CLI_UNAVAILABLE': ('configuration', 'CLI installation or login is unavailable.'),
    'PROVIDER_UNAVAILABLE': ('configuration', 'A selected model transport or its credentials are unavailable.'),
    'CLI_EXECUTION_FAILED': ('transport', 'Native CLI execution failed (execution_failed).'),
    'CLI_AUTH_REQUIRED': ('transport', 'Native CLI execution failed (authentication_required).'),
    'CLI_QUOTA_EXCEEDED': ('transport', 'Native CLI execution failed (quota_exceeded).'),
    'CLI_MODEL_UNSUPPORTED': ('transport', 'Native CLI execution failed (unsupported_model).'),
    'CLI_ARGUMENTS_INVALID': ('transport', 'Native CLI execution failed (invalid_arguments).'),
    'GEMINI_TOOL_DECLARATION_INVALID': ('transport', 'Gemini CLI execution failed (invalid_tool_declaration).'),
    'GEMINI_ISOLATION_FAILED': ('configuration', 'Gemini CLI isolation could not be verified.'),
    'GEMINI_ENVELOPE_JSON_INVALID': ('response_envelope', 'Invalid Gemini CLI response: envelope JSON rejected.'),
    'GEMINI_ENVELOPE_INVALID': ('response_envelope', 'Invalid Gemini CLI response: envelope structure rejected.'),
    'GEMINI_NATIVE_TOOLS_REJECTED': ('response_envelope', 'Invalid Gemini CLI response: native tool execution rejected.'),
    'GEMINI_RESPONSE_JSON_INVALID': ('response_json', 'Invalid Gemini CLI response: model JSON rejected.'),
    'GEMINI_TOOL_ENVELOPE_INVALID': ('tool_envelope', 'Invalid Gemini CLI response: tool envelope rejected.'),
    'GEMINI_TOOL_CALL_INVALID': ('tool_call', 'Invalid Gemini CLI response: tool call identity or structure rejected.'),
    'GEMINI_TOOL_NAME_UNOFFERED': ('tool_call', 'Invalid Gemini CLI response: an unoffered tool was requested.'),
    'GEMINI_TOOL_ARGUMENTS_INVALID': ('tool_call', 'Invalid Gemini CLI response: tool arguments do not match the offered parameter contract.'),
    'GEMINI_SCHEMA_INVALID': ('response_schema', 'Invalid Gemini CLI response: structured schema rejected.'),
    'CODEX_JSON_INVALID': ('response_json', 'Invalid or failed Codex CLI response: JSON rejected.'),
    'CODEX_RESPONSE_JSON_INVALID': ('response_json', 'Invalid Codex model response: JSON rejected.'),
    'CODEX_SCHEMA_INVALID': ('response_schema', 'Invalid Codex model response: structured schema rejected.'),
    'CODEX_TOOL_ENVELOPE_INVALID': ('tool_envelope', 'Invalid Codex model response: tool envelope rejected.'),
    'CODEX_TOOL_CALL_INVALID': ('tool_call', 'Invalid Codex model response: tool call identity or structure rejected.'),
    'CODEX_TOOL_NAME_UNOFFERED': ('tool_call', 'Invalid Codex model response: an unoffered tool was requested.'),
    'CODEX_TOOL_ARGUMENTS_INVALID': ('tool_call', 'Invalid Codex model response: tool arguments do not match the offered contract.'),
    'CODEX_EVENT_INVALID': ('native_event', 'Invalid or failed Codex CLI response: event contract rejected.'),
    'CODEX_TOOL_FAILED': ('native_event', 'A native MCP tool failed in a validated completed worker turn.'),
    'PROPOSAL_FORMAT_INVALID': ('response_schema', 'A model proposal did not satisfy its structured response contract.'),
    'CODEX_TURN_FAILED': ('native_event', 'Invalid or failed Codex CLI response: turn failed or was denied.'),
    'CODEX_TURN_INCOMPLETE': ('native_event', 'Invalid or failed Codex CLI response: turn incomplete.'),
    'NATIVE_INVENTORY_LIMIT': ('native_inventory', 'Native source change inventory exceeded its bounded budget.'),
    'NATIVE_INVENTORY_FAILED': ('native_inventory', 'Native source change inventory could not be completed.'),
    'TOOL_EXECUTION_FAILED': ('tool_execution', 'A workspace tool failed.'),
    'GRAPH_STEP_LIMIT': ('graph', 'Maximum graph steps exhausted.'),
    'GRAPH_STATE_INVALID': ('graph', 'A node attempted an unauthorized or inconsistent shared-state change.'),
    'GRAPH_CONTEXT_INVALID': ('graph', 'Required shared content is missing, stale, or inconsistent at a node boundary.'),
    'GRAPH_EVIDENCE_INVALID': ('verification', 'Required execution proof is absent, stale, or bound to a different contract.'),
    'APPROVAL_REJECTED': ('approval', 'The user did not approve the gate.'),
    'PLAN_REVIEW_INVALID': ('plan_review', 'The reviewer returned an invalid structured decision.'),
    'PLAN_REVIEW_FAILED': ('plan_review', 'Autonomous plan review could not complete.'),
    'PLAN_REVIEW_ESCALATED': ('plan_review', 'Plan review requires user input to resolve a blocker.'),
    'PLAN_REVIEW_EXHAUSTED': ('plan_review', 'Plan review exhausted its bounded revision budget.'),
    'REVISION_CONTRACT_EXHAUSTED': ('revision_contract', 'The latest revision could not be applied within the bounded correction budget.'),
    'PLAN_REVIEW_STALLED': ('plan_review', 'Plan review stopped after two revisions without verified progress.'),
    'PLAN_REVISION_INVALID': ('plan_review', 'The revised plan is invalid.'),
    'PLAN_ACCEPTANCE_INVALID': ('plan_review', 'The current plan does not match its recorded acceptance.'),
    'CODEX_REVIEW_TOOL_REJECTED': ('plan_review', 'The review-only native turn attempted a tool operation.'),
    'CODEX_REVIEW_ISOLATION_FAILED': ('configuration', 'A zero-tool native reasoning surface could not be established.'),
    'VERIFICATION_FAILED': ('verification', 'Declared verification failed and repair retries are exhausted.'),
    'READINESS_FAILED': ('readiness', 'Prerequisite verification failed after bounded setup repair; dependent implementation did not start.'),
    'READINESS_NOT_MET': ('readiness', 'Implementation cannot start before the accepted prerequisite tasks complete.'),
    'VERIFICATION_POLICY_OVERRIDE': ('verification', 'Verification cannot override PowerShell execution policy.'),
    'TDD_PHASE_INCOMPLETE': ('verification', 'Expected red tests lack an unchanged successful green transition.'),
    'WORKSPACE_VALIDATION_FAILED': ('verification', 'The workspace integrity audit failed.'),
    'PLAN_CATALOG_INVALID': ('plan_validation', 'The declared Council specialist catalog is unavailable or invalid.'),
    'PLAN_SPECIALIST_INVALID': ('plan_validation', 'A task must name a declared canonical Council specialist or its exact display call sign.'),
    'PLAN_SPECIALIST_UNAVAILABLE': ('plan_validation', 'A declared specialist package is missing, unreadable, or outside its protected boundary.'),
    'PLAN_VERIFICATION_INVALID': ('plan_validation', 'A task verification command or TDD phase contract is invalid.'),
    'PLAN_WORKING_DIRECTORY_INVALID': ('plan_validation', 'A task working directory violates workspace rules or is unavailable for native coding.'),
    'PLAN_TARGET_PATH_INVALID': ('plan_validation', 'A declared target path violates the selected workspace boundary.'),
    'DIAGNOSTICS_UNAVAILABLE': ('diagnostics', 'Private diagnostic persistence is unavailable.'),
}
_CATEGORY_CODES = {'authentication_required': 'CLI_AUTH_REQUIRED', 'quota_exceeded': 'CLI_QUOTA_EXCEEDED',
                   'unsupported_model': 'CLI_MODEL_UNSUPPORTED', 'invalid_arguments': 'CLI_ARGUMENTS_INVALID',
                   'invalid_tool_declaration': 'GEMINI_TOOL_DECLARATION_INVALID'}

# Finite native parser facts only. Never retain unknown provider strings.
NATIVE_EVENT_TYPES = frozenset({'thread.started', 'turn.started', 'turn.completed',
    'turn.failed', 'error', 'item.started', 'item.updated', 'item.completed'})
NATIVE_ITEM_TYPES = frozenset({'agent_message', 'reasoning', 'command_execution',
    'file_change', 'mcp_tool_call', 'web_search', 'todo_list', 'collab_tool_call',
    'dynamic_tool_call', 'image_view', 'error'})
NATIVE_REASONS = frozenset({'EMPTY_EVENT', 'INVALID_ENCODING', 'INVALID_JSON',
    'INVALID_EVENT', 'INVALID_THREAD', 'INVALID_TURN', 'INVALID_DIAGNOSTIC',
    'INVALID_ITEM', 'INVALID_ITEM_STATUS', 'INVALID_DECLINED_COMMAND', 'UNSUPPORTED_ITEM', 'INVALID_ITEM_LIFECYCLE',
    'DUPLICATE_ITEM_START', 'INVALID_FILE_CHANGES', 'INVALID_FILE_CHANGE',
    'INVALID_FILE_PATH', 'FILE_PATH_OUTSIDE_WORKSPACE', 'UNSUPPORTED_FAILED_ITEM', 'INVALID_FAILED_COMMAND',
    'INVALID_FINAL_MESSAGE', 'INVALID_COMPLETED_COMMAND',
    'INVALID_USAGE', 'UNSUPPORTED_EVENT', 'TURN_FAILED', 'TURN_INCOMPLETE',
    'REVIEW_TOOL_REJECTED', 'TOOL_FAILED', 'CONTRACT_INVALID'})
_NATIVE_CODES = frozenset({'CODEX_EVENT_INVALID', 'CODEX_JSON_INVALID',
    'CODEX_TURN_FAILED', 'CODEX_TURN_INCOMPLETE', 'CODEX_REVIEW_TOOL_REJECTED', 'CODEX_TOOL_FAILED'})
_CLI_CODES = frozenset({'CLI_EXECUTION_FAILED', 'CLI_AUTH_REQUIRED', 'CLI_QUOTA_EXCEEDED',
    'CLI_MODEL_UNSUPPORTED', 'CLI_ARGUMENTS_INVALID', 'GEMINI_TOOL_DECLARATION_INVALID',
    'CLI_TIMEOUT', 'CLI_IO_FAILED', 'CLI_OUTPUT_LIMIT', 'CLI_START_FAILED'})
_CLI_SIGNALS = frozenset({'connection_refused', 'network_unreachable', 'dns_failure',
    'tls_failure', 'proxy_failure', 'timeout', 'server_error', 'invalid_schema',
    'broken_pipe', 'panic', 'unclassified'})


def _cli_detail(value):
    if (type(value) is not dict or set(value) != {'provider', 'exit_code', 'stderr_bytes',
            'stdout_bytes', 'stderr_sha256', 'signals'}
            or type(value['provider']) is not str or value['provider'] not in {'codex-cli', 'gemini-cli'}
            or (value['exit_code'] is not None and (type(value['exit_code']) is not int
                or not -(2**31) <= value['exit_code'] < 2**32))
            or type(value['stderr_bytes']) is not int or not 0 <= value['stderr_bytes'] <= 4 * 1024 * 1024
            or type(value['stdout_bytes']) is not int or not 0 <= value['stdout_bytes'] <= 4 * 1024 * 1024
            or type(value['stderr_sha256']) is not str
            or not re.fullmatch(r'[0-9a-f]{64}', value['stderr_sha256'])
            or type(value['signals']) is not list or not 1 <= len(value['signals']) <= len(_CLI_SIGNALS)
            or any(type(signal) is not str or signal not in _CLI_SIGNALS for signal in value['signals'])
            or len(set(value['signals'])) != len(value['signals'])):
        return None
    return {**value, 'signals': list(value['signals'])}


def _native_detail(value):
    if (type(value) is not dict or set(value) != {'reason', 'event_index', 'event_type', 'item_type'}
            or type(value['reason']) is not str or value['reason'] not in NATIVE_REASONS
            or type(value['event_index']) is not int or not 0 <= value['event_index'] <= 4194305
            or type(value['event_type']) is not str
            or value['event_type'] not in NATIVE_EVENT_TYPES | {'unknown', 'invalid', 'none', 'end_of_stream'}
            or type(value['item_type']) is not str
            or value['item_type'] not in NATIVE_ITEM_TYPES | {'unknown', 'invalid', 'none'}):
        return None
    return dict(value)


class DiagnosticValueError(ValueError):
    def __init__(self, code, *, task_index=None, field_index=None, verification=None, review_decision=None, response_json=None, response_schema=None):
        self.code = code if isinstance(code, str) and code in CATALOG else 'INTERNAL_ERROR'
        self.task_index = task_index if type(task_index) is int and 1 <= task_index <= 100000 else None
        # Field positions aid private plan correction; never retain field values here.
        self.field_index = field_index if type(field_index) is int and 1 <= field_index <= 100000 else None
        from council.verification_feedback import safe_detail
        self.verification = safe_detail(verification) if self.code == 'PLAN_VERIFICATION_INVALID' else None
        from council.review_feedback import safe_detail as safe_review_detail
        self.review_decision = safe_review_detail(review_decision) if self.code == 'PLAN_REVIEW_INVALID' else None
        from council.json_feedback import safe_detail as safe_json_detail
        self.response_json = safe_json_detail(response_json) if self.code in {'GEMINI_RESPONSE_JSON_INVALID', 'GEMINI_ENVELOPE_JSON_INVALID','CODEX_RESPONSE_JSON_INVALID'} else None
        from council.schema_feedback import safe_detail as safe_schema_detail
        self.response_schema = safe_schema_detail(response_schema) if self.code in {'GEMINI_SCHEMA_INVALID','CODEX_SCHEMA_INVALID','PROPOSAL_FORMAT_INVALID'} else None
        super().__init__(CATALOG[self.code][1])


class DiagnosticRuntimeError(RuntimeError):
    def __init__(self, code, *, tool_failure=None, cli_process=None, resource_cleanup=None):
        self.code = code if isinstance(code, str) and code in CATALOG else 'INTERNAL_ERROR'
        from council.tool_failures import safe_detail
        self.tool_failure = safe_detail(tool_failure)
        self.cli_process = _cli_detail(cli_process) if self.code in _CLI_CODES else None
        self.resource_cleanup = safe_resource_cleanup(resource_cleanup)
        super().__init__(CATALOG[self.code][1])


def execution_error(category, *, cli_process=None):
    return DiagnosticRuntimeError(_CATEGORY_CODES.get(category, 'CLI_EXECUTION_FAILED'), cli_process=cli_process)


def describe(error):
    # Do not trust arbitrary diagnostic attributes on third-party exceptions.
    code = error.code if type(error) in (DiagnosticValueError, DiagnosticRuntimeError) else (
        'PERMISSION_DENIED' if isinstance(error, PermissionError) else 'INTERNAL_ERROR')
    if not isinstance(code, str) or code not in CATALOG:
        code = 'INTERNAL_ERROR'
    stage, message = CATALOG[code]
    result = {'code': code, 'stage': stage, 'message': message}
    if type(error) is DiagnosticRuntimeError:
        from council.tool_failures import safe_detail
        detail = safe_detail(error.tool_failure)
        if detail is not None:
            result['tool_failure'] = detail
        if code in _CLI_CODES and (detail := _cli_detail(error.cli_process)) is not None:
            result['cli_process'] = detail
        if (detail := safe_resource_cleanup(error.resource_cleanup)) is not None:
            result['resource_cleanup']=detail
    if type(error) is DiagnosticValueError and type(error.task_index) is int and 1 <= error.task_index <= 100000:
        result['task_index'] = error.task_index
    if type(error) is DiagnosticValueError and code == 'PLAN_VERIFICATION_INVALID':
        from council.verification_feedback import safe_detail
        detail = safe_detail(getattr(error, 'verification', None))
        if detail is not None:
            result['verification'] = detail
    if type(error) is DiagnosticValueError and code in _NATIVE_CODES:
        detail = _native_detail(getattr(error, 'native_event', None))
        if detail is not None:
            result['native_event'] = detail
    if type(error) is DiagnosticValueError and code == 'PLAN_REVIEW_INVALID':
        from council.review_feedback import safe_detail as safe_review_detail
        detail = safe_review_detail(getattr(error, 'review_decision', None))
        if detail is not None:
            result['review_decision'] = detail
    if type(error) is DiagnosticValueError and code in {'GEMINI_RESPONSE_JSON_INVALID', 'GEMINI_ENVELOPE_JSON_INVALID','CODEX_RESPONSE_JSON_INVALID'}:
        from council.json_feedback import safe_detail as safe_json_detail
        detail = safe_json_detail(getattr(error, 'response_json', None))
        if detail is not None:
            result['response_json'] = detail
    if type(error) is DiagnosticValueError and code in {'GEMINI_SCHEMA_INVALID','CODEX_SCHEMA_INVALID','PROPOSAL_FORMAT_INVALID'}:
        from council.schema_feedback import safe_detail as safe_schema_detail
        detail = safe_schema_detail(getattr(error, 'response_schema', None))
        if detail is not None:
            result['response_schema'] = detail
    return result


def safe_error_type(error):
    return next((name for cls, name in (
        (PermissionError, 'PermissionError'), (ValueError, 'ValueError'), (TypeError, 'TypeError'),
        (RuntimeError, 'RuntimeError'), (OSError, 'OSError')) if isinstance(error, cls)), 'Error')


MAX_BYTES = 1024 * 1024
MAX_FILES = 200
_RUN_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
_EVENTS = {'run_started', 'run_finished', 'call_started', 'call_succeeded', 'call_failed', 'cli_attempt_failed',
           'node_started', 'node_finished', 'node_failed', 'approval_waiting', 'runtime_failed',
           'inspection_round_started', 'inspection_budget_reached', 'planning_blocked', 'plan_preflight_rejected',
           'plan_review_rejected', 'verification_rejected', 'inspection_read_rejected', 'tool_failed'}
_STAGES = {'runtime', 'model', 'roadmap', 'roadmap_review', 'governor', 'architect', 'plan_review', 'plan_revision', 'strategy_reset', 'plan_blocked', 'worker', 'prover', 'phase_complete', 'investigation', 'gatekeeper', 'final_review'}
_STAGES |= {'arbiter', 'recovery_admit', 'recovery_dispatch', 'recovery_result', 'recovery'}
_STAGES |= {'intake_draft', 'requirements_gate'}
_STAGES.add('finished_change_review')
_STAGES |= {'requirements_reopen','proof_refresh'}
_EVENTS |= {'verification_started','verification_finished','delivery_state'}
_EVENTS.add('human_input_received')
_EVENTS |= {'recovery_'+name for name in ('opened','admitted','dispatched','resolved','failed','stopped','human_input','rejected')}
_EVENTS.add('resource_cleanup_observed')
_ROLES = {'orchestrator', 'coder', 'investigator', 'reviewer'}
from council.call_policy import READ_ONLY_OPERATIONS
_OPERATIONS = (set(READ_ONLY_OPERATIONS) | {name + '_transport_retry' for name in READ_ONLY_OPERATIONS}
               | {'worker', 'implementation', 'repair', 'arbiter',
                  'intake_format_retry','arbiter_format_retry','investigation_format_retry',
                  'roadmap_review_format_retry','plan_review_format_retry','finished_change_review_format_retry'})
_CURRENT = ContextVar('council_diagnostic_session', default=None)

_RECOVERY_MESSAGES = {
    'verify_partial':'Verifying retained worker files before requesting more coding.',
    'refresh_proofs':'Refreshing affected verification against current sources.',
    'replan':'Correcting the affected plan through independent review.',
    'repair_task':'Repairing the diagnosed task before verification.',
    'stop':'Recovery stopped with its original evidence preserved.',
    'ask_user':'A recorded user decision is required to continue.',
}


def safe_resource_cleanup(value):
    if (type(value) is not dict or set(value)!={'owned_process_exit_confirmed','detached_resources'}
            or type(value['owned_process_exit_confirmed']) not in (bool,type(None))
            or type(value['detached_resources']) is not str
            or value['detached_resources'] not in {'unobserved','none','owned_cleanup_confirmed','cleanup_required'}):
        return None
    return dict(value)


def failure_reference(value):
    """Retain one finite cause reference, never arbitrary diagnostic payloads."""
    if type(value) is not dict:
        return None
    code, stage = value.get('code'), value.get('graph_stage')
    if type(code) is not str or code not in CATALOG or type(stage) is not str or stage not in _STAGES:
        return None
    return {'code': code, 'graph_stage': stage}


def safe_recovery(value):
    if type(value) is not dict or set(value)!={'incident_id','category','action','outcome','elapsed_seconds','execution_ids',
            'reason','run_budget_remaining','incident_budget_remaining'}:
        return None
    if (not isinstance(value['incident_id'],str) or not re.fullmatch('[a-f0-9]{64}',value['incident_id'])
            or not isinstance(value['category'],str) or type(value['action']) not in (str,type(None))
            or not isinstance(value['outcome'],str) or not isinstance(value['reason'],str)
            or value['category'] not in {'timeout','tool_failure','verification','command_contract','prerequisite','stale_proof','transport','planning','unknown'}
            or value['action'] not in {*_RECOVERY_MESSAGES,None}
            or value['outcome'] not in {'opened','admitted','dispatched','resolved','failed','stopped','human_input','rejected'}
            or type(value['elapsed_seconds']) not in (float,int) or not 0<=value['elapsed_seconds']<=10**9
            or not isinstance(value['execution_ids'],list) or len(value['execution_ids'])>32
            or any(not isinstance(x,str) or not re.fullmatch('[a-f0-9]{64}',x) for x in value['execution_ids'])
            or type(value['run_budget_remaining']) is not int or not 0<=value['run_budget_remaining']<=32
            or type(value['incident_budget_remaining']) is not int or not 0<=value['incident_budget_remaining']<=2):
        return None
    from council.recovery_contracts import Reason
    if value['reason'] not in Reason.__args__:return None
    return {**value,'message':_RECOVERY_MESSAGES.get(value['action'],'Inspecting a recorded recovery incident.')}


def current_session():
    return _CURRENT.get()


def event(name, **fields):
    session = current_session()
    if session is not None:
        session.event(name, **fields)


def _regular(path):
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400


@contextmanager
def _locked_file(path, mode='a+b'):
    """Nonblocking process lock; contention disables diagnostics, never execution."""
    if path.is_symlink() or (path.exists() and not _regular(path)):
        raise OSError('Unsafe diagnostic file')
    stream = path.open(mode, buffering=0)
    locked = False
    try:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield stream
    finally:
        if locked:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


class DiagnosticSession:
    def __init__(self, run_id, memory_root=None):
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise ValueError('Invalid diagnostic run ID')
        self.run_id, self.memory_root = run_id, memory_root
        self.started = time.monotonic()
        self.status, self.path, self._token = 'unavailable', None, None
        self._lock = threading.Lock()
        self._warned = False
        self.finished = False
        self._lease, self._file = None, None
        self.observations = None
        self.observations_status = 'unavailable'
        self.session_id = uuid.uuid4().hex
        self.source_seq = 0
        self._narration_observer = None
        self._narrator = None

    def attach(self, memory_root):
        self.memory_root = Path(memory_root)
        try:
            root = self.memory_root/'diagnostics'
            # Reject reparse points on every existing ancestor; never follow one
            # for writing or retention deletion.
            for path in (root, *root.parents):
                if path.exists() or path.is_symlink():
                    info = path.lstat()
                    if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                        raise OSError('Unsafe diagnostic path')
            root.mkdir(parents=True, exist_ok=True)
            target = root/(self.run_id + '.jsonl')
            with _locked_file(root/'.writer.lock'):
                files = [p for p in root.iterdir() if p.suffix == '.jsonl' and _RUN_ID.fullmatch(p.stem) and _regular(p)]
                if target.is_symlink() or (target.exists() and not _regular(target)):
                    raise OSError('Unsafe diagnostic file')
                if not target.exists():
                    for candidate in sorted(files, key=lambda p: p.stat().st_mtime):
                        if len(files) < MAX_FILES:
                            break
                        # Both the terminal marker and a free process lock are
                        # required: another session may have resumed this run.
                        try:
                            with _locked_file(candidate, 'r+b') as stream:
                                stream.seek(max(0, candidate.stat().st_size - 2048))
                                tail = stream.read(2048).splitlines()
                                completed = bool(tail) and json.loads(tail[-1]).get('event') == 'run_finished'
                            if completed and _regular(candidate):
                                candidate.unlink()
                                files.remove(candidate)
                        except (OSError, ValueError, AttributeError, TypeError):
                            continue
                    if len(files) >= MAX_FILES:
                        raise OSError('Diagnostic retention capacity reached')
                self._lease = _locked_file(target)
                self._file = self._lease.__enter__()
            self.path, self.status = target, 'available'
            try:
                from council.observability import ObservationStore
                self.observations = ObservationStore(self.memory_root/'observability.sqlite')
                self.observations.open_session(self.run_id,self.session_id)
                self.observations_status = 'available'
            except (OSError, ValueError, sqlite3.Error):
                self.observations_status = 'unavailable'
                self._warning()
        except OSError:
            self.status = 'unavailable'
            self._warning()

    def _console(self, record):
        try:
            print(json.dumps(record, ensure_ascii=True), file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass

    def _warning(self):
        if not self._warned:
            self._warned = True
            self._console({'run_id': self.run_id, **describe(DiagnosticRuntimeError('DIAGNOSTICS_UNAVAILABLE'))})

    def event(self, name, *, stage='runtime', role=None, operation=None, call=None, diagnostic=None,
              inspection_round=None, remaining_rounds=None, task_index=None, command_index=None, verification_detail=None,
              boundary_reason=None, recovery_detail=None, resource_cleanup=None, accounting=None,
              measurement=None, run_status=None, functional_complete=None, pr_ready=None, comparison=None):
        if self.finished or not isinstance(name, str) or name not in _EVENTS:
            return
        record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'run_id': self.run_id, 'event': name,
                  'stage': stage if isinstance(stage, str) and stage in _STAGES else 'runtime',
                  'elapsed_seconds': round(max(0, time.monotonic() - self.started), 3)}
        from council.observability import accounting as safe_accounting, measurement as safe_measurement, STATUSES
        if accounting is not None:
            record['accounting'] = safe_accounting(accounting)
        if measurement is not None:
            record['measurement'] = safe_measurement(measurement)
        if comparison is not None:
            from council.observability import safe_comparison
            record['comparison']=safe_comparison(comparison)
        if isinstance(run_status,str) and run_status in STATUSES:
            record['run_status'] = run_status
        for key,value in (('functional_complete',functional_complete),('pr_ready',pr_ready)):
            if type(value) is bool:
                record[key] = value
        recovery=safe_recovery(recovery_detail)
        if recovery is not None:record['recovery']=recovery
        cleanup=safe_resource_cleanup(resource_cleanup)
        if cleanup is not None:record['resource_cleanup']=cleanup
        if isinstance(role, str) and role in _ROLES:
            record['role'] = role
        if isinstance(operation, str) and operation in _OPERATIONS:
            record['operation'] = operation
        if type(call) is int and 0 < call <= 100000:
            record['call'] = call
        if type(inspection_round) is int and 1 <= inspection_round <= 12:
            record['inspection_round'] = inspection_round
        if type(remaining_rounds) is int and 0 <= remaining_rounds <= 11:
            record['remaining_rounds'] = remaining_rounds
        if type(task_index) is int and 1 <= task_index <= 100000:
            record['task_index'] = task_index
        if type(command_index) is int and 1 <= command_index <= 100000:
            record['command_index'] = command_index
        from council.boundaries import REASONS as BOUNDARY_REASONS
        if type(boundary_reason) is str and boundary_reason in BOUNDARY_REASONS:
            record['boundary_reason'] = boundary_reason
        from council.red_feedback import safe_detail as safe_red_detail
        red_detail = safe_red_detail(verification_detail)
        if red_detail is not None:
            record['verification_detail'] = red_detail
        if diagnostic is not None:
            detail = describe(diagnostic)
            record.update(code=detail['code'], failure_stage=detail['stage'], message=detail['message'])
            if 'task_index' in detail:
                record['task_index'] = detail['task_index']
            if 'native_event' in detail:
                record['native_event'] = detail['native_event']
            if 'verification' in detail:
                record['verification'] = detail['verification']
            if 'review_decision' in detail:
                record['review_decision'] = detail['review_decision']
            if 'tool_failure' in detail:
                record['tool_failure'] = detail['tool_failure']
            if 'cli_process' in detail:
                record['cli_process'] = detail['cli_process']
            if 'response_json' in detail:
                record['response_json'] = detail['response_json']
            if 'response_schema' in detail:
                record['response_schema'] = detail['response_schema']
        self._console(record)
        with self._lock:
            if self.observations is not None and self.observations_status=='available':
                try:
                    self.source_seq += 1
                    self.observations.append(self.run_id,self.session_id,self.source_seq,record)
                    if self._narration_observer is not None:
                        try:
                            self._narration_observer(name, record, self.source_seq)
                        except Exception:
                            pass  # Narration is best-effort and cannot change execution.
                except (OSError,ValueError,sqlite3.Error):
                    self.observations_status='incomplete'
                    self._warning()
            if self.path is None or self.status == 'unavailable':
                return
            try:
                data = (json.dumps(record, ensure_ascii=True) + '\n').encode('utf-8')
                if self.path.is_symlink() or (self.path.exists() and not _regular(self.path)):
                    raise OSError('Unsafe diagnostic file')
                size = self._file.seek(0, os.SEEK_END)
                limit = MAX_BYTES if name == 'run_finished' else MAX_BYTES - 512
                if size + len(data) > limit:
                    self.status = 'capped'
                    return
                if self._file.write(data) != len(data):
                    raise OSError('Incomplete diagnostic write')
            except OSError:
                self.status = 'unavailable'
                self._warning()

    def summary(self):
        result = {'diagnostics_status': self.status, 'observations_status':self.observations_status}
        if self.path is not None:
            result['diagnostics_file'] = 'diagnostics/' + self.run_id + '.jsonl'
        return result

    def __enter__(self):
        self._token = _CURRENT.set(self)
        if self.memory_root is not None:
            self.attach(self.memory_root)
            self.event('run_started')
        return self

    def finish(self):
        if not self.finished:
            try:
                self.event('run_finished')
            finally:
                self.finished = True
                if self._narrator is not None and self._narrator.stdin is not None:
                    try:
                        self._narrator.stdin.close()
                    except OSError:
                        pass
                if self._file is not None:
                    try:
                        self._lease.__exit__(None, None, None)
                    except OSError:
                        self.status = 'unavailable'
                        self._warning()
                    finally:
                        self._file = None
                if self.observations is not None:
                    self.observations.__exit__(None,None,None)
                    self.observations = None

    def __exit__(self, exc_type, error, traceback):
        try:
            if error is not None:
                self.event('runtime_failed', diagnostic=error)
            self.finish()
        finally:
            _CURRENT.reset(self._token)
