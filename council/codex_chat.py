"""Text-only Codex adapter for graph planning, inspection and investigation."""
from copy import copy,deepcopy
import json
import re

from langchain_core.messages import message_to_dict
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from council.diagnostics import DiagnosticValueError

_ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}\Z')


def _response_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def constant(_):
        raise ValueError('Invalid JSON constant')
    try:
        return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
    except (ValueError,UnicodeError,RecursionError) as error:
        from council.json_feedback import from_error
        raise DiagnosticValueError('CODEX_RESPONSE_JSON_INVALID',response_json=from_error(text,error)) from None


class CodexCLIChatModel:
    def __init__(self,model,settings,context=None):
        from council.codex_cli import validate_cli_settings
        validate_cli_settings(settings)
        if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}',model):
            raise ValueError('Invalid Codex model identifier')
        self.model,self.settings,self.context=model,deepcopy(settings),context
        self._tools,self._schema,self._include_raw=(),None,False
        self._input_schemas={}

    def bind_tools(self,tools):
        from council.boundaries import READ_TOOLS
        clone=copy(self)
        clone.settings=deepcopy(self.settings)
        tools=tuple(tools)
        clone._tools=tuple(deepcopy(convert_to_openai_tool(tool)['function']) for tool in tools)
        names=[tool['name'] for tool in clone._tools]
        if len(names)!=len(set(names)) or any(name not in READ_TOOLS for name in names):
            raise ValueError('Planning accepts only unique offered read-only tools')
        clone._input_schemas={definition['name']:tool.get_input_schema()
            for tool,definition in zip(tools,clone._tools)}
        clone._schema,clone._include_raw=None,False
        return clone

    def with_structured_output(self,schema,include_raw=False):
        clone=copy(self)
        clone.settings=deepcopy(self.settings)
        clone._schema,clone._include_raw,clone._tools=schema,include_raw,()
        clone._input_schemas={}
        return clone

    def invoke(self,messages):
        if isinstance(messages,str): messages=[{'role':'user','content':messages}]
        request={'instruction':'Follow the supplied conversation as a text-only model. '
            'Native tools are unavailable. Offered graph tools are request descriptions only; never execute them yourself.',
            'messages':[deepcopy(message) if isinstance(message,dict) else message_to_dict(message) for message in messages]}
        if self._schema:
            request['response_schema']=self._schema.model_json_schema()
            request['instruction']+=' Return exactly one complete JSON object matching response_schema; no Markdown or surrounding prose. Use native JSON values without encoding JSON inside strings.'
        elif self._tools:
            request['tools']=self._tools
            request['instruction']+=(' Return exactly one JSON object with exactly content (string) and tool_calls (array). '
                'Each call has exactly name (offered name), args (object matching that tool), and id (unique nonempty string). '
                'At most 16 calls. Finish inspection with {"content":"Inspection complete.","tool_calls":[]}. '
                'Do not return surrounding prose or Markdown.')
        else:
            request['instruction']+=' Return a concise plain-text response.'
        from council.codex_cli import CodexCLIWorker
        context=self.context
        if context is None:
            from council.runtime_context import resolve_context
            context=resolve_context()
        # Council validates its richer schemas locally. In particular native JSON
        # edit values and heterogeneous graph-tool arguments must stay unencoded.
        raw=CodexCLIWorker(self.model,self.settings,context).invoke_read_only(request)
        try:
            return self._decode(raw)
        except DiagnosticValueError as error:
            error.response_metadata = raw.response_metadata
            error.usage_metadata = raw.usage_metadata
            raise

    def _decode(self,raw):
        if self._schema:
            data=_response_json(raw.content)
            try:
                parsed=self._schema.model_validate(data,strict=True)
            except ValidationError as error:
                from council.schema_feedback import from_error
                raise DiagnosticValueError('CODEX_SCHEMA_INVALID',response_schema=from_error(error)) from None
            return {'raw':raw,'parsed':parsed,'parsing_error':None} if self._include_raw else parsed
        if self._tools:
            data=_response_json(raw.content)
            self._validate_calls(data)
            return raw.model_copy(update={'content':data['content'],'tool_calls':data['tool_calls']})
        return raw

    def _validate_calls(self,data):
        if (type(data) is not dict or set(data)!={'content','tool_calls'} or type(data['content']) is not str
                or type(data['tool_calls']) is not list or len(data['tool_calls'])>16):
            raise DiagnosticValueError('CODEX_TOOL_ENVELOPE_INVALID')
        ids=set()
        for call in data['tool_calls']:
            if type(call) is not dict or set(call)!={'name','args','id'}:
                raise DiagnosticValueError('CODEX_TOOL_CALL_INVALID')
            if type(call['name']) is not str or call['name'] not in self._input_schemas:
                raise DiagnosticValueError('CODEX_TOOL_NAME_UNOFFERED')
            if type(call['args']) is not dict:
                raise DiagnosticValueError('CODEX_TOOL_ARGUMENTS_INVALID')
            try:
                self._input_schemas[call['name']].model_validate(call['args'],strict=True)
            except ValidationError:
                raise DiagnosticValueError('CODEX_TOOL_ARGUMENTS_INVALID') from None
            if type(call['id']) is not str or not _ID.fullmatch(call['id']) or call['id'] in ids:
                raise DiagnosticValueError('CODEX_TOOL_CALL_INVALID')
            ids.add(call['id'])
