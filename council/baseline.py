"""Common baseline provenance and bounded challenges; never a recovery scheduler."""
import hashlib
from pathlib import Path
from council.delivery_contracts import BaselineChallenge, BaselineAmendment, SourceObservation


def entries(state):
    intake=state.requirements
    values={e.id:e.model_dump(mode='json') for e in intake.draft.baseline} if intake.draft else {}
    for amendment in intake.baseline_amendments:
        if amendment.requirements_sha256==intake.document_sha256 and amendment.baseline_id in values:
            values[amendment.baseline_id].update(statement=amendment.statement,basis='observed',
                consequence=amendment.consequence,
                source_refs=[s.path for s in amendment.sources],review_sha256=amendment.review_sha256,
                challenge_id=amendment.challenge_id)
    return list(values.values())


def source_observations(state):
    observations={s.path:s for s in state.requirements.sources}
    for amendment in state.requirements.baseline_amendments:
        if amendment.requirements_sha256==state.requirements.document_sha256:
            observations.update({s.path:s for s in amendment.sources})
    return list(observations.values())


def freshness(state, workspace_root):
    from council.runtime_context import RuntimeContext
    from council.tools.discovery import validate_read_path, MAX_FILE_BYTES
    # Only the established read boundary may inspect baseline paths.
    from types import SimpleNamespace
    reader = SimpleNamespace(workspace_root=Path(workspace_root).resolve(),
        council_root=Path(state.council_root).resolve())
    reader.workspace_path = lambda relative: RuntimeContext.workspace_path(reader, relative)

    observations = {s.path:s.sha256 for s in source_observations(state)}
    current = {}
    for relative, expected in observations.items():
        try:
            target = validate_read_path(reader, relative)
            with target.open('rb') as source:
                data = source.read(MAX_FILE_BYTES + 1)
            current[relative] = len(data) <= MAX_FILE_BYTES and hashlib.sha256(data).hexdigest() == expected
        except (OSError, ValueError):
            current[relative] = False
    return {entry['id']: ('user_confirmed' if entry['basis'] == 'user' else
        'current' if entry['basis'] == 'observed' and entry['source_refs'] and
            all(current.get(path, False) for path in entry['source_refs']) else
        'stale' if entry['basis'] == 'observed' else entry['basis']) for entry in entries(state)}


def challenge(state, *, baseline_id, requirement_id, reason, evidence_refs, consequence,
              replacement_statement=None,replacement_source_refs=None):
    intake = state.requirements
    if (not intake.draft or baseline_id not in {e.id for e in intake.draft.baseline}
            or requirement_id not in {e.id for e in intake.draft.requirements}):
        raise ValueError('Challenge requires current baseline and requirement identities')
    known = {s.path for s in source_observations(state)} | {e.id for e in state.execution_records}
    if reason == 'requirement_change':
        known.add(requirement_id)
    if not evidence_refs or not set(evidence_refs) <= known:
        raise ValueError('Challenge requires retained evidence')
    if len(intake.challenges) >= 32 or any(
            c.baseline_id == baseline_id and c.requirement_id == requirement_id and c.reason == reason
            and c.evidence_refs == evidence_refs and c.document_sha256 == intake.document_sha256
            for c in intake.challenges):
        raise ValueError('Challenge budget exhausted or unchanged challenge already retained')
    item = BaselineChallenge(id=f'C{len(intake.challenges)+1}', baseline_id=baseline_id,
        requirement_id=requirement_id, document_sha256=intake.document_sha256, reason=reason,
        evidence_refs=evidence_refs, consequence=consequence,
        replacement_statement=replacement_statement,replacement_source_refs=replacement_source_refs or [],
        route='human_requirements' if reason == 'requirement_change' else 'existing_review')
    intake.challenges.append(item)
    return item


def resolve(state, challenge_id, resolution):
    item = next((c for c in state.requirements.challenges if c.id == challenge_id), None)
    if item is None or item.resolution is not None or not isinstance(resolution, str) or not resolution.strip() or len(resolution) > 2000:
        raise ValueError('Resolution requires an open challenge and bounded rationale')
    item.resolution = resolution


def admit_plan_challenges(state, *, context=None,review_sha256=None):
    """Stage the complete batch; only independently reviewed repository facts may amend the baseline."""
    probe=state.model_copy(deep=False)
    probe.requirements=state.requirements.model_copy(deep=True)
    for proposal in state.plan.baseline_challenges:
        item=challenge(probe,**proposal.model_dump(mode='json'))
        if proposal.replacement_statement is None:
            if proposal.replacement_source_refs:
                raise ValueError('Replacement sources require a replacement fact')
            continue
        original=next(e for e in probe.requirements.draft.baseline if e.id==proposal.baseline_id)
        if original.basis=='user' or proposal.reason=='requirement_change' or not proposal.replacement_source_refs:
            raise ValueError('Human rules require human revision; fact corrections require observed sources')
        if context is None:
            from council.runtime_context import RuntimeContext
            context=RuntimeContext(Path(state.council_root),Path(state.workspace_root),Path(state.memory_root))
        from council.tools.discovery import validate_read_path,MAX_FILE_BYTES
        retained={s.path:s.sha256 for s in source_observations(probe) if s.path in proposal.evidence_refs}
        for receipt in state.execution_records:
            if receipt.id in proposal.evidence_refs:
                retained.update({p:h for p,h in receipt.source_hashes.items() if not p.startswith('@proof:')})
        observations=[]
        for path in proposal.replacement_source_refs:
            with validate_read_path(context,path).open('rb') as source:
                data=source.read(MAX_FILE_BYTES+1)
            actual=hashlib.sha256(data).hexdigest()
            if len(data)>MAX_FILE_BYTES or retained.get(path)!=actual:
                raise ValueError('Baseline correction requires a retained current source observation')
            observations.append(SourceObservation(path=path,sha256=actual))
        if len({s.path for s in [*source_observations(probe),*observations]})>128:
            raise ValueError('Baseline source observation budget exhausted')
        if review_sha256 is not None:
            if len(probe.requirements.baseline_amendments)>=32:
                raise ValueError('Baseline amendment budget exhausted')
            probe.requirements.baseline_amendments.append(BaselineAmendment(
                baseline_id=proposal.baseline_id,requirements_sha256=probe.requirements.document_sha256,
                challenge_id=item.id,statement=proposal.replacement_statement,sources=observations,
                consequence=proposal.consequence,
                review_sha256=review_sha256))
            item.resolution='Repository fact corrected by independent plan review '+review_sha256
    state.requirements=probe.requirements
