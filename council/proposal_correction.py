"""One format-only challenge before admitting a read-only model proposal."""
import json
from pydantic import ValidationError
from council.diagnostics import DiagnosticValueError,DiagnosticRuntimeError,describe

STRUCTURED_FORMAT_CODES=frozenset({'CODEX_SCHEMA_INVALID','CODEX_RESPONSE_JSON_INVALID',
    'GEMINI_SCHEMA_INVALID','GEMINI_RESPONSE_JSON_INVALID','PROPOSAL_FORMAT_INVALID'})
_BOUNDARIES={
    'roadmap':('orchestrator','roadmap_format_retry'),
    'planning':('orchestrator','planning_format_retry'),
    'intake_draft':('orchestrator','intake_format_retry'),
    'roadmap_review':('reviewer','roadmap_review_format_retry'),
    'plan_review':('reviewer','plan_review_format_retry'),
    'arbiter':('orchestrator','arbiter_format_retry'),
    'investigation':('investigator','investigation_format_retry'),
    'finished_change_review':('reviewer','finished_change_review_format_retry'),
}


def _candidate(response):
    if isinstance(response,dict) and 'parsed' in response:
        error=response.get('parsing_error')
        if error:
            if isinstance(error,(PermissionError,RuntimeError)) or type(error) is DiagnosticValueError:
                raise error
            raise DiagnosticValueError('PROPOSAL_FORMAT_INVALID')
        return response['parsed']
    return response


def invoke_challenged(state,operation,payload,generate,invoke,*,schema=None,parse=None,strict=None,charge_retry=None):
    """Validate before success accounting; never replay execution or infer approval."""
    if operation not in _BOUNDARIES or (schema is None)==(parse is None):
        raise ValueError('A supported read-only proposal boundary and validator are required')
    from council.graph_integrity import prepare_payload,context_consumer
    from council.schema_feedback import from_error,correction
    role,retry_operation=_BOUNDARIES[operation]
    consumer=context_consumer(operation)
    request=prepare_payload(state,consumer,payload)
    def checked(current):
        response=generate(current)
        try:
            if parse is not None:parse(response)
            else:schema.model_validate(_candidate(response),strict=strict)
        except (ValidationError,DiagnosticValueError) as caught:
            error=(DiagnosticValueError('PROPOSAL_FORMAT_INVALID',response_schema=from_error(caught))
                if isinstance(caught,ValidationError) else caught)
            raw=response.get('raw') if isinstance(response,dict) and 'raw' in response else response
            if not getattr(error,'response_metadata',None):
                error.response_metadata=getattr(raw,'response_metadata',{})
                error.usage_metadata=getattr(raw,'usage_metadata',None)
            raise error from None
        return response
    try:
        return invoke(state,role,operation,lambda:checked(request),request=request)
    except DiagnosticValueError as error:
        allowed=STRUCTURED_FORMAT_CODES | ({'PLAN_REVIEW_INVALID'} if operation in {'roadmap_review','plan_review'} else set())
        if type(error) is not DiagnosticValueError or error.code not in allowed:
            raise
        if charge_retry is not None and not charge_retry():
            raise
        detail=describe(error)
        feedback={'instruction':'Return exactly one complete response matching the original supplied response contract. '
            'Correct only JSON/schema format. Preserve requirements, evidence, identities, acceptance and scope. '
            'Do not execute tools or commands, add observations, invent proof or infer approval. '
            'This is the one format challenge; a second invalid response remains blocked.',
            'diagnostic':detail,'schema_guidance':correction(detail.get('response_schema'))}
        if isinstance(request,list):
            corrected=[*request,{'role':'user','content':json.dumps(feedback)}]
        elif isinstance(request,dict):
            corrected={**request,'format_correction':feedback}
        else:
            raise DiagnosticRuntimeError('GRAPH_CONTEXT_INVALID')
        corrected=prepare_payload(state,consumer,corrected)
        # Deliberately outside the try: no correction loop and no rejected text.
        return invoke(state,role,retry_operation,lambda:checked(corrected),request=corrected)
