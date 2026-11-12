"""Private full-content review inputs and exact-content final approval."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import os
from council.delivery_contracts import FinalReview
from council.native_inventory import snapshot
from council.tools.discovery import validate_read_path
from council.diagnostics import DiagnosticValueError

GATES = ('brainstorm', 'implement', 'purify', 'static_analysis', 'unit_tests',
    'coverage_validation', 'regression', 'diff_vs_behavior_review', 'integration_build',
    'pr_review_simulation', 'documentation_update')
POLISH_GUIDANCE = (
    'Perform actual scoped code polish and documentation inspection of the complete feature diff. '
    'Improve naming, flow, unnecessary indirection, duplication and non-obvious documentation where warranted. '
    'Preserve approved behavior, public contracts and unrelated inherited work. Inspect-no-edit is valid '
    'when warranted; report what was inspected and any remaining limitations. A behavior or scope change '
    'requires normal requirements/contract review. Run focused checks; independent verification follows.'
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _artifact(state, context):
    root = context.memory_root / 'finalization' / hashlib.sha256(state.run_id.encode()).hexdigest()
    current = root
    while current != context.memory_root:
        if current.is_symlink() or getattr(current, 'is_junction', lambda:False)():
            raise ValueError('Private finalization artifact cannot traverse links')
        current = current.parent
    root.mkdir(parents=True, exist_ok=True)
    return root / 'baseline.json'


def _read(path):
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or path.stat().st_size > 70 * 1024 * 1024:
        raise ValueError('Private baseline exceeds bounds')
    return json.loads(path.read_text(encoding='utf-8'))


def _repository(context, relative):
    root = context.workspace_path(relative)
    while root != context.workspace_root and not (root/'.git').exists():
        root = root.parent
    kind,head = ('git',None) if (root/'.git').exists() else ('unversioned_scope',None)
    if kind=='git':
        try:
            result = subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,
                timeout=5,check=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            value = result.stdout.decode('ascii',errors='replace').strip()
            if result.returncode==0 and re.fullmatch('[a-f0-9]{40,64}',value):
                head=value
        except (OSError,subprocess.TimeoutExpired):
            pass
    return {'root':root.relative_to(context.workspace_root).as_posix(),'kind':kind,'head':head}


def capture(state, context, relative):
    if not state.finalization_enabled or relative in state.finalization.captured_scopes:
        return
    artifact = _artifact(state, context)
    retained = _read(artifact) if artifact.exists() else {'files':{}, 'scopes':[], 'repositories':[]}
    if state.finalization.baseline_sha256 and _digest(retained) != state.finalization.baseline_sha256:
        raise ValueError('Finalization baseline identity mismatch')
    if relative not in retained['scopes']:
        inventory = snapshot(context, relative)
        for path, sha in inventory.items():
            if path in retained['files'] or any(Path(path).is_relative_to(Path(scope)) for scope in retained['scopes']):
                continue
            data = validate_read_path(context, path).read_bytes()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError('Source changed while capturing feature baseline')
            try:
                entry = {'sha256':sha, 'content':data.decode('utf-8')}
            except UnicodeDecodeError:
                entry = {'sha256':sha, 'representation':'non-text'}
            retained['files'][path] = entry
            if len(retained['files']) > 512:
                raise DiagnosticValueError('FINALIZATION_BASELINE_LIMIT')
        retained['scopes'].append(relative)
        identity = _repository(context,relative)
        if not any(r['root']==identity['root'] for r in retained['repositories']):
            retained['repositories'].append(identity)
        if len(retained['files']) > 512:
            raise DiagnosticValueError('FINALIZATION_BASELINE_LIMIT')
        serialized = json.dumps(retained,ensure_ascii=True).encode('utf-8')
        if len(serialized)>70*1024*1024:
            raise DiagnosticValueError('FINALIZATION_BASELINE_LIMIT')
        descriptor,temporary = tempfile.mkstemp(prefix='baseline-',suffix='.tmp',dir=artifact.parent)
        try:
            with os.fdopen(descriptor,'wb') as output:
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary,artifact)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    state.finalization.baseline_sha256 = _digest(retained)
    state.finalization.captured_scopes = list(retained['scopes'])


def review_packet(state, context):
    artifact = _artifact(state, context)
    baseline = _read(artifact)
    if _digest(baseline) != state.finalization.baseline_sha256:
        raise ValueError('Finalization baseline identity mismatch')
    current = {}
    for scope in state.finalization.captured_scopes:
        current.update(snapshot(context, scope))
    repositories = {r['root']:r for r in baseline.get('repositories',[])}
    for scope in state.finalization.captured_scopes:
        identity = _repository(context,scope)
        if repositories.get(identity['root']) != identity:
            raise ValueError('Repository identity changed during delivery')
    changes = {e['path']:e for e in state.file_changes}
    files = []
    for path in sorted(set(baseline['files']) | set(current)):
        old = baseline['files'].get(path)
        before = old['sha256'] if old else None
        after = current.get(path)
        if before == after:
            continue
        observed = changes.get(path)
        if (observed is None or not observed.get('before_known', True)
                or observed.get('before_sha256') != before or observed.get('after_sha256') != after):
            raise ValueError('Ambiguous concurrent change prevents complete feature review')
        data = validate_read_path(context, path).read_bytes() if after else None
        if data is not None and hashlib.sha256(data).hexdigest() != after:
            raise ValueError('Finished source changed while reading')
        if old and old.get('representation') == 'non-text':
            raise DiagnosticValueError('FINAL_REVIEW_NON_TEXT_UNSUPPORTED')
        try:
            text = data.decode('utf-8') if data is not None else None
        except UnicodeDecodeError:
            raise DiagnosticValueError('FINAL_REVIEW_NON_TEXT_UNSUPPORTED') from None
        files.append({'path':path, 'before_sha256':before, 'after_sha256':after,
            'before':old['content'] if old else None, 'after':text})
    evidence = [{'id':r.id, 'expectation_met':r.expectation_met, 'source_hashes':r.source_hashes,
        'plan_sha256':r.plan_sha256, 'contract_versions':r.contract_versions} for r in state.execution_records]
    content = {'files':files, 'evidence':evidence, 'requirements_sha256':state.requirements.approved_sha256,
        'repositories':list(repositories.values()),
        'baseline_sha256':state.finalization.baseline_sha256,
        'quality_gates':dict(state.finalization.quality_gates)}
    content['quality_evidence'] = state.finalization.quality_evidence
    if len(json.dumps(content).encode()) > 192000:
        raise ValueError('Complete final review exceeds input budget; approval unavailable')
    return {**content, 'content_sha256':_digest(content),
        'prior_findings':[f.model_dump(mode='json') for f in state.finalization.findings]}


def accept_review(state, packet, response):
    decision = FinalReview.model_validate(response)
    current = state.finalization
    if current.review_count >= 3 or decision.content_sha256 != packet['content_sha256']:
        raise ValueError('Final review identity or budget mismatch')
    ids = [f.id for f in decision.findings]
    if len(set(ids)) != len(ids) or (decision.decision == 'accept') != (not ids):
        raise ValueError('Final review finding/decision mismatch')
    old = {f.id:f for f in current.findings}
    resolved = set(decision.resolved_finding_ids)
    if (len(resolved) != len(decision.resolved_finding_ids) or not resolved <= old.keys()
            or resolved & set(ids) or not old.keys() <= set(ids) | resolved):
        raise ValueError('Final review must account for every retained finding')
    for finding in decision.findings:
        if finding.location not in {f['path'] for f in packet['files']}:
            raise ValueError('Finding location must name inspected feature content')
        if finding.id in old and finding != old[finding.id]:
            raise ValueError('Finding identity cannot change its meaning')
    current.review_count += 1
    current.reviews.append(decision)
    current.findings = decision.findings
    current.approved_content_sha256 = decision.content_sha256 if decision.decision == 'accept' else None


def review_current(state, context):
    try:
        return bool(state.finalization.approved_content_sha256 and
            state.finalization.approved_content_sha256 == review_packet(state, context)['content_sha256'])
    except (OSError, ValueError):
        return False


def delivery_result(state):
    gates = {name:state.finalization.quality_gates.get(name, 'unverified') for name in GATES}
    if state.finalization.approved_content_sha256:
        gates['diff_vs_behavior_review'] = gates['pr_review_simulation'] = 'passed'
        dimensions = state.finalization.reviews[-1].inspected_dimensions if state.finalization.reviews else []
        if state.finalization.polish_task_ids and 'polish' in dimensions:
            gates['purify'] = 'passed'
        if state.finalization.polish_task_ids and 'documentation' in dimensions:
            gates['documentation_update'] = 'passed'
    ready=bool(state.finalization.approved_content_sha256) and all(value in {'passed','out_of_scope'} for value in gates.values())
    boundary=state.requirements.draft.completion_boundary if state.intake_enabled and state.requirements.draft else 'functional'
    return {'functional_complete':bool(state.finalization.approved_content_sha256),
        'pr_ready':ready,'agreed_boundary':boundary,
        'completion_boundary_met':ready if boundary=='pr_ready' else bool(state.finalization.approved_content_sha256),
        'quality_gates':gates, 'final_review_sha256':state.finalization.approved_content_sha256,
        'quality_evidence':state.finalization.quality_evidence,
        'limitations':['Unverified quality phases do not establish PR readiness.']}


def enforce_boundary(state):
    if (state.intake_enabled and state.requirements.draft and state.requirements.draft.completion_boundary=='pr_ready'
            and state.delivery_result.get('pr_ready') is not True):
        from council.diagnostics import DiagnosticRuntimeError
        raise DiagnosticRuntimeError('DELIVERY_BOUNDARY_NOT_MET')


def qualify_gates(state, context):
    from council.delivery_contracts import QualityGateSpec
    from council.graph_integrity import matching_execution
    from council.plan_review import plan_digest
    gates, evidence = {}, {}
    if state.plan and state.accepted_plan_sha256==plan_digest(state.plan):
        gates['brainstorm']='passed'
        all_current = all(matching_execution(state,t,i,context) is not None
            for t in state.plan.tasks for i in range(1,len(t.test_commands)+1))
        gates['implement']='passed' if all_current and all(t.status=='completed' for t in state.plan.tasks) else 'unverified'
        seen = set()
        for raw in state.plan.quality_gates:
            spec = QualityGateSpec.model_validate(raw)
            if spec.phase in seen:
                raise ValueError('Duplicate quality gate')
            seen.add(spec.phase)
            if spec.out_of_scope_reason:
                gates[spec.phase]='out_of_scope'
                evidence[spec.phase]={'reason':spec.out_of_scope_reason,'execution_ids':[]}
                continue
            tasks = {t.id:t for t in state.plan.tasks}
            if not set(spec.task_ids)<=tasks.keys() or any(tasks[k].verification_phase!='green' for k in spec.task_ids):
                raise ValueError('Gate must bind existing green verification tasks')
            receipts = [matching_execution(state,tasks[k],i,context) for k in spec.task_ids
                for i in range(1,len(tasks[k].test_commands)+1)]
            gates[spec.phase]='passed' if receipts and all(receipts) else 'unverified'
            evidence[spec.phase]={'execution_ids':[r.id for r in receipts if r],
                'reason':'Accepted gate obligations; source/current-contract validity checked'}
    state.finalization.quality_gates,state.finalization.quality_evidence = gates,evidence


def piece_probe(state, index):
    from council.governor import _LOCAL_FIELDS
    record = state.work_pieces[state.roadmap.phases[index].id]
    raw = state.model_dump(mode='json')
    raw.update({k:v for k,v in record.checkpoint.items() if k in _LOCAL_FIELDS})
    raw['current_phase_index'] = index
    return type(state).model_validate(raw)


def first_stale_piece(state, context):
    from council.graph_integrity import matching_execution
    if not state.roadmap:
        return None
    for index,phase in enumerate(state.roadmap.phases):
        record = state.work_pieces.get(phase.id)
        if record is None or record.status!='completed':
            continue
        probe = piece_probe(state,index)
        if (probe.plan is None or any(matching_execution(probe,task,i,context) is None
                for task in probe.plan.tasks for i in range(1,len(task.test_commands)+1))):
            return index
    return None
