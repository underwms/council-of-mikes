"""Human requirements admission and a single evidence-backed project baseline."""
import hashlib
from importlib.resources import files
from council.delivery_contracts import RequirementsDraft, RequirementsRevision

BASELINE_GUIDANCE = (
    'Reuse the established repository architecture, framework, development auth, identity and local workflow. '
    'User-confirmed business rules are authoritative within their stated scope and need no external citation. '
    'Observed baseline entries refer to inspected source, not verification of behavior. Proposals and unknowns '
    'are not facts. Do not invent SSO, entitlement, credential or deployment prerequisites. '
    'Keep inherited deviations outside scope unless this change introduces a concrete correctness problem. '
    'Baseline trust does not excuse regressions, including development-auth 403s. Challenge a baseline with '
    'specific contradictory evidence, affected requirement and concrete consequence; request requirements '
    'revision only for material scope or authorization changes. Do not reissue resolved findings without regression.'
    ' Independently reviewed baseline fact amendments supersede earlier observed interpretations only; '
    'they never change human requirements or user-confirmed operating rules.'
)


class DraftRejected(ValueError):
    """Finite correction reason; rejected draft contents and paths are not diagnostics."""
    def __init__(self, reason):
        if reason not in {'unobserved_source','requirement_id_loss','document_limit'}:
            raise ValueError('Unknown requirements rejection')
        self.reason = reason
        super().__init__('Requirements proposal rejected')


def correction(state, rejection, sources):
    return {'reason':rejection.reason,
        'allowed_observed_source_paths':[source.path for source in sources],
        'required_requirement_ids':[entry.id for entry in state.requirements.draft.requirements] if state.requirements.draft else [],
        'guidance':(
            'Return a corrected complete draft; no new tools or human answers are supplied. '
            'Observed facts must cite only actual retained source paths above. Unsupported repository claims '
            'remain proposals/unknowns, never user-confirmed facts. Preserve all existing requirement IDs '
            'and their meaning; do not omit or retire requirements merely to pass validation. '
            'Keep the rendered document, including original analysis, within 96000 characters. '
            'This correction does not approve the document or accept any limitation.')}


def observed_read_tools(context, sources):
    """Hash exactly the bounded bytes used to produce each intake read response."""
    from langchain_core.tools import tool
    from council.tools.discovery import validate_read_path, MAX_FILE_BYTES
    from council.delivery_contracts import SourceObservation

    @tool
    def read_workspace_file(rel_path: str, start_line: int | None = None,
                            end_line: int | None = None) -> str | dict:
        """Read bounded workspace source lines and retain the observed file identity."""
        if rel_path not in sources and len(sources) >= 128:
            raise ValueError('Intake observation budget exhausted')
        try:
            with validate_read_path(context, rel_path).open('rb') as source:
                data = source.read(MAX_FILE_BYTES + 1)
        except FileNotFoundError:
            # An absent inspection target is feedback, never an observed source.
            # Permission, boundary and size failures retain their existing guards.
            from council.tool_failures import missing_feedback
            return missing_feedback()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('Workspace file exceeds intake read limit')
        lines = data.decode('utf-8', errors='replace').splitlines()
        start = start_line - 1 if start_line and start_line > 0 else 0
        result = '\n'.join(lines[start:end_line or len(lines)])
        sources[rel_path] = SourceObservation(path=rel_path, sha256=hashlib.sha256(data).hexdigest())
        return result

    return [read_workspace_file]


def content_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def template():
    return files('council').joinpath('templates/requirements.md').read_text(encoding='utf-8')


def render(draft, original):
    lines = [f'# Requirements document: {draft.title}', '', '## 1. Purpose and desired outcome', '', original,
             '', '## Requirements summary', '', draft.summary,
             '', '## 2. Scope and ownership', '', draft.scope_and_ownership,
             '', '### Scope exclusions', '']
    lines += [f'- {item}' for item in draft.scope_exclusions]
    lines += ['', '## 3. Existing patterns and integration context', '']
    lines += [f'- **{r.id}** [{r.basis}] {r.statement}\n  Consequence: {r.consequence}\n'
              f'  Sources: {", ".join(r.source_refs) or "user input / unresolved"}' for r in draft.baseline]
    lines += ['', '## 4. Required behavior and business rules', '']
    lines += [f'- **{r.id}** [{r.basis}] {r.statement} (sources: {", ".join(r.source_refs) or "user input"})'
              for r in draft.requirements]
    lines += ['', '### Proposals requiring agreement', ''] + [f'- {item}' for item in draft.proposals]
    lines += ['', '## 5. Data, relationships and lifecycle', '', draft.data_and_lifecycle,
              '', '## 6. Acceptance examples', '']
    lines += [f'- {item}' for item in draft.acceptance]
    lines += [
              '', '## 7. Verification and delivery constraints', '', draft.delivery_constraints,
              '', f'Agreed completion boundary: **{draft.completion_boundary}**',
              '', '## 8. Questions, decisions and approval', '', draft.decisions,
              '', '### Open questions and bounded limitations', '']
    lines += [f'- **{r.id}** {r.question}\n  Consequence: {r.consequence}\n'
              f'  Consequential: {r.consequential}; bounded default: {r.bounded_default or "none"}' for r in draft.questions]
    if draft.retired_requirement_ids:
        lines += ['', '## Explicitly retired requirements', '', ', '.join(draft.retired_requirement_ids)]
    return '\n'.join(lines) + '\n'


def revise(state, draft, sources):
    intake = state.requirements
    if len(intake.revisions) >= 4:
        raise ValueError('Requirements revision budget exhausted')
    draft = RequirementsDraft.model_validate(draft)
    known = {s.path for s in sources}
    for entry in [*draft.requirements, *draft.baseline]:
        if entry.basis == 'observed' and (not entry.source_refs or not set(entry.source_refs) <= known):
            raise DraftRejected('unobserved_source')
    if intake.draft:
        old = {r.id for r in intake.draft.requirements}
        new = {r.id for r in draft.requirements} | set(draft.retired_requirement_ids)
        if not old <= new:
            raise DraftRejected('requirement_id_loss')
    markdown = render(draft, state.task_input)
    if len(markdown)>96000:
        raise DraftRejected('document_limit')
    revision = RequirementsRevision(revision=len(intake.revisions)+1, document_sha256=content_hash(markdown),
        markdown=markdown, feedback_count=len(intake.feedback))
    intake.draft, intake.markdown, intake.document_sha256 = draft, markdown, revision.document_sha256
    intake.sources = sources
    intake.approved_sha256, intake.accepted_limitations = None, []
    intake.revisions.append(revision)


def add_feedback(state, feedback):
    intake = state.requirements
    if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 12000:
        raise ValueError('Feedback must contain 1-12000 characters')
    if len(intake.feedback) >= 4 or len(intake.revisions) >= 4:
        raise ValueError('Requirements revision budget exhausted')
    intake.feedback.append(feedback)
    intake.approved_sha256, intake.accepted_limitations = None, []


def approve(state, response):
    intake = state.requirements
    if (not isinstance(response, dict) or not intake.draft or not intake.document_sha256
            or response.get('requirements_sha256') != intake.document_sha256
            or content_hash(intake.markdown) != intake.document_sha256
            or render(intake.draft, state.task_input) != intake.markdown):
        raise ValueError('Approval requires the exact current requirements SHA256')
    accepted = response.get('accepted_limitations', [])
    if not isinstance(accepted, list) or any(not isinstance(i, str) for i in accepted) or len(set(accepted)) != len(accepted):
        raise ValueError('Invalid limitation acceptance')
    questions = {q.id:q for q in intake.draft.questions}
    if (not set(accepted) <= questions.keys() or any(not questions[q].bounded_default for q in accepted)
            or any(q.consequential and q.id not in accepted for q in questions.values())):
        raise ValueError('Consequential unknowns require explicit bounded acceptance or revision')
    intake.approved_sha256, intake.accepted_limitations = intake.document_sha256, accepted


def effective_requirements(state):
    if not state.intake_enabled:
        return state.task_input
    intake = state.requirements
    if (not intake.approved_sha256 or intake.approved_sha256 != content_hash(intake.markdown)
            or not intake.draft or render(intake.draft, state.task_input) != intake.markdown):
        raise ValueError('Human requirements approval required')
    return intake.markdown


def reopen(state):
    intake = state.requirements
    findings = [f.description for f in [*state.review_finding_ledger,*state.roadmap_finding_ledger]
        if f.kind=='user_decision' and f.status=='unresolved']
    findings += [f.concern+' Consequence: '+f.consequence for f in state.finalization.findings if f.kind=='scope_change']
    findings += [c.consequence for c in intake.challenges if c.route=='human_requirements'
        and c.resolution is None and c.document_sha256==intake.document_sha256]
    if not state.intake_enabled or not findings or len(intake.revisions)>=4 or intake.reopening:
        raise ValueError('A bounded material requirements question is required')
    intake.previous_approval = intake.approved_sha256
    intake.proposed_change = '\n'.join(findings)[:12000]
    intake.reopening = True
    intake.approved_sha256 = None
    intake.accepted_limitations = []


def archive_and_replan(state):
    intake = state.requirements
    if not intake.reopening:
        return
    effective_requirements(state)
    if len(intake.superseded_deliveries)>=3:
        raise ValueError('Requirements reopening budget exhausted')
    intake.superseded_deliveries.append({'requirements_sha256':intake.previous_approval,
        'roadmap_sha256':state.accepted_roadmap_sha256,'plan_sha256':state.accepted_plan_sha256,
        'work_pieces':{k:v.model_dump(mode='json') for k,v in state.work_pieces.items()},
        'shared_contracts':{k:v.model_dump(mode='json') for k,v in state.shared_contracts.items()},
        'contract_history':state.contract_history,
        'execution_ids':[r.id for r in state.execution_records],
        'review_findings':[f.model_dump(mode='json') for f in state.review_finding_ledger]})
    state.plan = state.roadmap = None
    state.accepted_plan_sha256 = state.accepted_roadmap_sha256 = None
    state.work_pieces, state.shared_contracts, state.contract_history = {}, {}, []
    state.current_phase_index = state.current_task_index = 0
    state.review_finding_ledger = []
    state.roadmap_finding_ledger = []
    state.roadmap_review_findings = []
    state.last_reviewed_roadmap_sha256 = None
    state.roadmap_no_progress_count = 0
    state.finalization.approved_content_sha256 = None
    for challenge in intake.challenges:
        if challenge.route=='human_requirements' and challenge.resolution is None:
            challenge.resolution='Reconsidered through exact human approval of '+intake.approved_sha256
    intake.reopening = False
    intake.proposed_change = ''


def approval_payload(state):
    intake = state.requirements
    return {'gate':'requirements', 'status':'REQUIREMENTS_WAITING', 'run_id':state.run_id,
        'revision':len(intake.revisions), 'requirements_sha256':intake.document_sha256,
        'requirements_markdown':intake.markdown,
        'resume_instructions':'Resume with --approve-requirements SHA256 and explicit --accept-limitation Qn, or --feedback-file PATH.'}


def baseline_context(state):
    intake = state.requirements
    from council.baseline import freshness,entries,source_observations
    return {'guidance':BASELINE_GUIDANCE, 'requirements_sha256':intake.approved_sha256,
        'entries':entries(state),
        'sources':[s.model_dump(mode='json') for s in source_observations(state)],
        'accepted_limitations':intake.accepted_limitations,
        'freshness':freshness(state, state.workspace_root) if state.workspace_root else {},
        'challenges':[c.model_dump(mode='json') for c in intake.challenges],
        'coverage':'intake_observed' if intake.draft else 'not_established'}
