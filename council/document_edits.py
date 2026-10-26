"""Atomic, finding-linked edits to draft documents; references never name files."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError


def _json_value(value, depth=0):
    if depth > 32:
        raise ValueError('JSON depth limit')
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth+1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item, depth+1)
        return
    raise ValueError('Not a finite native JSON value')


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


class DocumentEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    op: Literal['add', 'replace', 'remove']
    path: str = Field(min_length=1, max_length=1024)
    value: Any = Field(description='Native JSON value: string, object, array, boolean, number or null. '
        'Do not encode JSON inside a string. Use null for removal. This is data, never executable code.')
    reason_ids: list[str] = Field(min_length=1, max_length=12,
        description='Active finding IDs; U1 denotes recorded user feedback, V1 deterministic preflight correction.')
    after_id: str | None = Field(default=None, max_length=256,
        description='Only for inserted phases/tasks: empty string prepends, null appends, otherwise follow this existing ID.')

    @field_validator('value')
    @classmethod
    def bounded_json(cls, value):
        try:
            _json_value(value)
            if len(_encoded(value).encode('utf-8')) > 65536:
                raise ValueError('JSON value byte limit')
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise PydanticCustomError('revision_json_value', 'Bounded finite native JSON required') from None
        return value


class DocumentRevision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    run_id: str = Field(min_length=1, max_length=256)
    artifact: Literal['roadmap', 'plan']
    base_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    edits: list[DocumentEdit] = Field(min_length=1, max_length=64)


class RevisionRejected(ValueError):
    """Finite correction facts, excluding rejected values and arbitrary paths."""
    def __init__(self, reason, edit_index=0, *, schema=None, response_json=None):
        super().__init__('Document revision rejected')
        from council.schema_feedback import safe_detail
        from council.json_feedback import safe_detail as safe_json_detail
        self.reason, self.edit_index = reason, edit_index
        self.schema, self.response_json = safe_detail(schema), safe_json_detail(response_json)
        if self.schema and self.schema['edit_index'] is not None:
            self.edit_index = self.schema['edit_index']

    def feedback(self, artifact):
        result = {'artifact': artifact, 'reason': self.reason, 'edit_index': self.edit_index}
        if self.schema is not None:
            result['schema'] = self.schema
        if self.response_json is not None:
            result['response_json'] = self.response_json
        return result

    @classmethod
    def from_diagnostic(cls, error):
        from council.diagnostics import describe
        detail = describe(error)
        return cls('EDIT_JSON_INVALID' if detail['code'] in {'GEMINI_RESPONSE_JSON_INVALID','CODEX_RESPONSE_JSON_INVALID'} else 'EDIT_SCHEMA_INVALID',
            schema=detail.get('response_schema'), response_json=detail.get('response_json'))


def document_digest(value, kind):
    if kind == 'roadmap':
        from council.phase_contract import roadmap_digest
        return roadmap_digest(value)
    from council.plan_review import plan_digest
    return plan_digest(value)


def active_reasons(state, kind):
    ledger = state.roadmap_finding_ledger if kind == 'roadmap' else state.review_finding_ledger
    ids = {item.id for item in ledger if item.status == 'unresolved'}
    from council.recovery import review_active
    if kind=='plan' and review_active(state):
        ids.add('R1')
    if state.governance_feedback is not None and state.governance_feedback.get('artifact') == kind:
        ids.add('V1')
    if state.human_feedback:
        ids.add('U1')
    if kind == 'plan' and (state.plan_validation_feedback is not None
            or (state.orchestration_policy_version == 2 and state.plan is not None and len(state.plan.tasks) > 12)):
        ids.add('V1')
    return ids


def _value(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Invalid JSON constant')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def parse_revision(proposal):
    """Read saved legacy edit dictionaries; advertise only native values to models."""
    if isinstance(proposal, DocumentRevision):
        proposal = proposal.model_dump(mode='python')
    if type(proposal) is dict and type(proposal.get('edits')) is list:
        proposal = deepcopy(proposal)
        for index, edit in enumerate(proposal['edits'], 1):
            if type(edit) is dict and 'value_json' in edit and 'value' not in edit:
                text = edit['value_json']
                if type(text) is not str or len(text.encode('utf-8')) > 65536:
                    raise RevisionRejected('EDIT_SCHEMA_INVALID', index)
                try:
                    edit['value'] = _value(text)
                except (ValueError, UnicodeError, RecursionError) as error:
                    from council.json_feedback import from_error
                    raise RevisionRejected('EDIT_JSON_INVALID', index,
                        response_json=from_error(text, error)) from None
                del edit['value_json']
    try:
        return DocumentRevision.model_validate(proposal)
    except ValidationError as error:
        from council.schema_feedback import from_error
        raise RevisionRejected('EDIT_SCHEMA_INVALID', schema=from_error(error)) from None


def _path(path):
    if not path.startswith('/') or re.search(r'~(?![01])', path):
        raise RevisionRejected('REFERENCE_INVALID')
    parts = tuple(part.replace('~1', '/').replace('~0', '~') for part in path[1:].split('/'))
    if any(not part for part in parts):
        raise RevisionRejected('REFERENCE_INVALID')
    return parts


def _index(part, length, adding=False):
    if part == '-' and adding:
        return length
    if not re.fullmatch(r'0|[1-9][0-9]{0,5}', part):
        raise RevisionRejected('REFERENCE_INVALID')
    index = int(part)
    if index >= length + int(adding):
        raise RevisionRejected('REFERENCE_UNKNOWN')
    return index


def _member(document, collection, identity):
    matches = [item for item in document[collection] if item['id'] == identity]
    if len(matches) != 1:
        raise RevisionRejected('REFERENCE_UNKNOWN')
    return matches[0]


def _resolve(document, parts, kind, *, correcting_status=False):
    collection = 'phases' if kind == 'roadmap' else 'tasks'
    if kind=='plan' and parts in {('quality_gates',),('baseline_challenges',)}:
        return document,parts[0]
    if kind == 'plan' and parts[0] == 'contract_changes':
        if len(parts) == 2:
            return document['contract_changes'], parts[1]
        if len(parts) == 3:
            member = _member(document, 'contract_changes', parts[1])
            if parts[2] in member and parts[2] != 'id':
                return member, parts[2]
        raise RevisionRejected('REFERENCE_INVALID')
    if kind == 'roadmap' and parts[0] == 'solution_architecture':
        architecture = document['solution_architecture']
        if len(parts) == 1 and architecture is None:
            return document, 'solution_architecture'
        if not isinstance(architecture, dict):
            raise RevisionRejected('REFERENCE_INVALID')
        if len(parts) == 2 and parts[1] == 'integration_strategy':
            return architecture, parts[1]
        if len(parts) >= 3 and parts[1] in {'executables', 'contracts', 'open_questions'}:
            if len(parts) == 3:
                return architecture[parts[1]], parts[2]
            member = _member(architecture, parts[1], parts[2])
            if parts[3] not in member or parts[3] == 'id':
                raise RevisionRejected('FIELD_NOT_OWNED')
            value = member[parts[3]]
            if len(parts) == 4 and not isinstance(value, list):
                return member, parts[3]
            if len(parts) == 5 and isinstance(value, list):
                return value, parts[4]
        raise RevisionRejected('REFERENCE_INVALID')
    if parts[0] in {'title', 'architecture_summary'} and len(parts) == 1:
        return document, parts[0]
    if kind == 'plan' and parts[0] == 'affected_services' and len(parts) == 2:
        return document['affected_services'], parts[1]
    if parts[0] != collection or len(parts) not in (3, 4):
        raise RevisionRejected('REFERENCE_INVALID')
    member = _member(document, collection, parts[1])
    field = parts[2]
    if field == 'id' or (field == 'status' and not correcting_status) or field not in member:
        raise RevisionRejected('FIELD_NOT_OWNED')
    if len(parts) == 4:
        if not isinstance(member[field], list):
            raise RevisionRejected('REFERENCE_INVALID')
        return member[field], parts[3]
    if isinstance(member[field], list):
        raise RevisionRejected('WHOLE_LIST_REPLACEMENT')
    return member, field


def _inserted(value, kind, identity):
    from council.phase_contract import Phase
    from council.state import TaskItem
    model = Phase if kind == 'roadmap' else TaskItem
    if (not isinstance(value, dict) or set(value) - model.model_fields.keys()
            or value.get('id') != identity or (kind == 'plan' and value.get('status', 'pending') != 'pending')):
        raise RevisionRejected('INSERT_INVALID')
    return model.model_validate(value, strict=True).model_dump(mode='json')


def apply_revision(state, proposal, kind):
    """Resolve all targets against one base and return a validated new document."""
    edit_index = 0
    try:
        revision = parse_revision(proposal)
        base = getattr(state, kind)
        if base is None or revision.run_id != state.run_id or revision.artifact != kind:
            raise RevisionRejected('IDENTITY_MISMATCH')
        if revision.base_sha256 != document_digest(base, kind):
            raise RevisionRejected('STALE_BASE')
        if sum(len(_encoded(edit.value).encode('utf-8')) for edit in revision.edits) > 524288:
            raise RevisionRejected('EDIT_LIMIT')
        allowed = active_reasons(state, kind)
        document = deepcopy(base.model_dump(mode='json'))
        collection = 'phases' if kind == 'roadmap' else 'tasks'
        paths, lists, structures = [], {}, []
        for edit_index, edit in enumerate(revision.edits, 1):
            if (len(set(edit.reason_ids)) != len(edit.reason_ids) or not set(edit.reason_ids) <= allowed):
                raise RevisionRejected('REASON_UNKNOWN')
            value, parts = edit.value, _path(edit.path)
            if edit.op == 'remove' and value is not None:
                raise RevisionRejected('REMOVE_VALUE_INVALID')
            for old_parts, old_edit in paths:
                common = min(len(parts), len(old_parts))
                if parts[:common] == old_parts[:common]:
                    appends = (parts == old_parts and parts[-1] == '-' and edit.op == old_edit.op == 'add'
                               and _encoded(edit.value) != _encoded(old_edit.value))
                    if not appends:
                        raise RevisionRejected('EDIT_CONFLICT')
            paths.append((parts, edit))
            if len(parts) == 2 and parts[0] == collection:
                if edit.op == 'replace':
                    raise RevisionRejected('WHOLE_OBJECT_REPLACEMENT')
                known = [item['id'] for item in document[collection]]
                if edit.op == 'remove':
                    if parts[1] not in known or edit.after_id is not None:
                        raise RevisionRejected('REFERENCE_UNKNOWN')
                else:
                    if parts[1] in known or (edit.after_id not in (None, '') and edit.after_id not in known):
                        raise RevisionRejected('REFERENCE_UNKNOWN')
                    value = _inserted(value, kind, parts[1])
                structures.append((edit, parts[1], value))
                continue
            if edit.after_id is not None:
                raise RevisionRejected('REFERENCE_INVALID')
            correcting_status = (kind == 'plan' and state.plan_validation_feedback is not None
                and state.plan_validation_feedback.field == 'status' and edit.op == 'replace'
                and value == 'pending' and 'V1' in edit.reason_ids)
            parent, key = _resolve(document, parts, kind, correcting_status=correcting_status)
            if isinstance(parent, dict):
                if edit.op != 'replace':
                    raise RevisionRejected('SCALAR_OPERATION_INVALID')
                parent[key] = value
            else:
                index = _index(key, len(parent), edit.op == 'add')
                group = lists.setdefault(parts[:-1], (parent, []))
                group[1].append((edit.op, index, value))
        # Lists are rebuilt from original indices, never shifting subsequent targets.
        for parent, edits in lists.values():
            additions, replacements, removed = defaultdict(list), {}, set()
            for op, index, value in edits:
                if op == 'add': additions[index].append(value)
                elif op == 'replace': replacements[index] = value
                else: removed.add(index)
            result = []
            for index in range(len(parent) + 1):
                result.extend(additions[index])
                if index < len(parent) and index not in removed:
                    result.append(replacements.get(index, parent[index]))
            parent[:] = result
        if structures:
            removed = {identity for edit, identity, _ in structures if edit.op == 'remove'}
            inserts = defaultdict(list)
            for edit, _, value in structures:
                if edit.op == 'add':
                    if edit.after_id in removed:
                        raise RevisionRejected('EDIT_CONFLICT')
                    inserts[edit.after_id].append(value)
            result = list(inserts[''])
            for item in document[collection]:
                if item['id'] not in removed:
                    result.append(item)
                result.extend(inserts[item['id']])
            result.extend(inserts[None])
            document[collection] = result
        if kind == 'roadmap':
            from council.phase_contract import PhaseRoadmap, validate_roadmap
            candidate = validate_roadmap(PhaseRoadmap.model_validate(document, strict=True))
            if state.governance_policy_version == 2:
                from council.governor import validate_architecture, GovernanceRejected
                try:
                    validate_architecture(candidate)
                except GovernanceRejected:
                    raise RevisionRejected('EDIT_SCHEMA_INVALID') from None
            return candidate
        from council.state import MultiSpecialistPlan
        return MultiSpecialistPlan.model_validate(document, strict=True)
    except RevisionRejected as error:
        if not error.edit_index:
            error.edit_index = edit_index
        raise
    except ValidationError as error:
        from council.schema_feedback import from_error
        raise RevisionRejected('EDIT_SCHEMA_INVALID', schema=from_error(error)) from None
    except (ValueError, TypeError, KeyError, RecursionError):
        raise RevisionRejected('EDIT_SCHEMA_INVALID', edit_index) from None


def revision_contract(state, kind):
    return {'run_id': state.run_id, 'artifact': kind,
        'base_sha256': document_digest(getattr(state, kind), kind),
        'active_reason_ids': sorted(active_reasons(state, kind)),
        'governance_correction': state.governance_feedback,
        'instruction': 'Return DocumentRevision, not a replacement document. Preserve all untouched content. '
            'Paths use stable phase/task IDs: /phases/<id>/acceptance_outcomes/- or '
            '/tasks/<id>/acceptance_criteria/- appends one item. Replace/remove an existing list item '
            'using its zero-based index. Replace an individual scalar with /tasks/<id>/description, '
            '/phases/<id>/goal, /title or /architecture_summary. Each value is native JSON: '
            'strings stay strings, objects and arrays are direct JSON, booleans are true/false; '
            'never JSON-encode the value inside a string. Removal uses value:null. '
            'Insert/remove a phase/task using /phases/<id> or /tasks/<id>; '
            'inserts supply its full object and after_id (empty prepends, null appends). '
            'All references and indices address the supplied base, not intermediate edits. '
            'Do not replace whole documents, phase/task objects or lists, or change IDs/status. '
            'Only an explicit V1 preflight status correction may reset an invalid initial status to pending. '
            'Every edit needs active reason_ids. At most 64 edits. No tools in synthesis.',
        'governance_edits': 'Architecture scalar edits use /solution_architecture/contracts/<id>/definition, '
            '/solution_architecture/executables/<id>/repository, /solution_architecture/open_questions/<id>/assumption, '
            'or /solution_architecture/integration_strategy. Architecture collection entries use numeric indices '
            'or - to append; scalar list entries use /solution_architecture/executables/<id>/depends_on/-. '
            'Only when absent, initialize /solution_architecture with a full object. '
            'Piece plan contract proposals use /contract_changes/- to append, numeric indices to replace/remove, '
            'or /contract_changes/<id>/definition, /base_version, /reason for scalar edits. '
            'These edits still need active finding reasons and independent review.',
        'correction': state.document_revision_feedback}
