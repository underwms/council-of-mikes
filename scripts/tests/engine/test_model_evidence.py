"""Evidence contains provider metadata only, never prompts or generated text."""
import importlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from council.config import resolve_model_configuration
from test_engine_integration import lifecycle


def record(response=None, error=None):
    evidence = importlib.import_module('council.model_evidence')
    from council.config import RunModelConfiguration, RoleModelConfiguration, _provider_settings
    configuration = RunModelConfiguration(version=2, roles={
        'orchestrator':RoleModelConfiguration(provider='gpt', model='gpt-6.1-sol', settings=_provider_settings('gpt')),
        'investigator':RoleModelConfiguration(provider='gemini', model='gemini-3.8-flash', settings=_provider_settings('gemini'))})
    return evidence.build_call_record(configuration, 'orchestrator', 'planning', response=response, error=error)


def test_record_reports_actual_provider_metadata_without_response_content():
    message = SimpleNamespace(id='resp_123', content='private-generated-text',
        response_metadata={'model_name': 'gpt-returned', 'request_id': 'req_123',
                           'headers': {'authorization': 'private-token'}},
        usage_metadata={'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30})
    result = record(message)
    assert result['provider'] == 'gpt'
    assert result['requested_model'] == 'gpt-6.1-sol'
    assert result['returned_model'] == 'gpt-returned'
    assert result['request_id'] == 'req_123'
    assert result['response_id'] == 'resp_123'
    assert result['usage'] == {'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30}
    assert result['status'] == 'succeeded'
    assert 'private-' not in json.dumps(result)


def test_structured_response_uses_raw_metadata_only():
    raw = SimpleNamespace(id='resp_456', response_metadata={'model': 'gpt-snapshot'}, usage_metadata={})
    result = record({'raw': raw, 'parsed': {'private': 'private-plan'}, 'parsing_error': None})
    assert result['returned_model'] == 'gpt-snapshot'
    assert result['response_id'] == 'resp_456'
    assert 'private-plan' not in json.dumps(result)


def test_agent_response_uses_last_model_message_metadata():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    response = {'messages': [HumanMessage(content='private-prompt'),
        AIMessage(content='private-initial', response_metadata={'model_name': 'gpt-first'}),
        ToolMessage(content='private-file', tool_call_id='call_1'),
        AIMessage(content='private-final', response_metadata={'model_name': 'gpt-final'})]}
    result = record(response)
    assert result['returned_model'] == 'gpt-final'
    assert 'private-' not in json.dumps(result)


def test_absent_metadata_stays_unknown_instead_of_claiming_requested_model():
    result = record({'some': 'response'})
    assert result.get('returned_model') is None
    assert result['usage'] == {}


def test_error_records_type_without_error_message_or_payload():
    result = record(error=ValueError('private-key-or-response'))
    assert result['status'] == 'failed'
    assert result['error_type'] == 'ValueError'
    assert 'private-key-or-response' not in json.dumps(result)


def test_ids_and_usage_are_bounded_and_sensitive_values_omitted():
    raw = SimpleNamespace(id='x' * 5000,
        response_metadata={'model': 'invalid\nprivate-text', 'request_id': 'sk-secret',
                           'token_usage': {'prompt_tokens': 5, 'completion_tokens': 2,
                                           'total_tokens': 7, 'arbitrary_payload': 'private'}},
        usage_metadata={'input_tokens': -1, 'output_tokens': True, 'total_tokens': 'private'})
    result = record(raw)
    assert result.get('returned_model') is None
    assert result.get('request_id') is None
    assert len(result.get('response_id', '')) <= 256
    assert result['usage'] == {'input_tokens': 5, 'output_tokens': 2, 'total_tokens': 7}
    assert len(json.dumps(result)) < 2000


def test_configured_credentials_cannot_be_mistaken_for_response_metadata():
    raw = SimpleNamespace(response_metadata={'model': 'secretvalue'}, usage_metadata={})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'secretvalue'}):
        result = record(raw)
    assert result.get('returned_model') is None


def test_framework_message_ids_are_not_provider_response_ids():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    response = FakeListChatModel(responses=['offline test']).invoke('offline test')
    assert response.id.startswith('lc_run--')
    result = record(response)
    assert 'response_id' not in result
    response.response_metadata['id'] = response.id
    assert 'response_id' not in record(response)


def test_provider_response_ids_remain_available_without_framework_fallback():
    raw = SimpleNamespace(id='lc_run--framework',
                          response_metadata={'response_id': 'google-server-id'}, usage_metadata={})
    assert record(raw)['response_id'] == 'google-server-id'
    raw.response_metadata = {'id': 'resp_openai-server'}
    assert record(raw)['response_id'] == 'resp_openai-server'


def test_durable_resume_forwards_original_configuration_to_real_role_factory(lifecycle, monkeypatch):
    from copy import deepcopy
    from langgraph.types import Command
    from test_engine_integration import ScriptedProvider, open_graph, assert_gate
    from council.graph import build_council_graph
    provider = ScriptedProvider(lifecycle.plan)
    observed = []

    def capture(role, configuration=None, **kwargs):
        observed.append((role, deepcopy(configuration)))
        return provider

    monkeypatch.setattr('council.graph.get_llm_for_role', capture)
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_MODEL', 'gpt-before-restart')
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context)
        result = graph.invoke(lifecycle.state.model_dump(), lifecycle.config)
        assert_gate(result, 'GATE_1_PLAN_APPROVAL')
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_MODEL', 'gpt-after-restart')
    observed.clear()
    with open_graph(lifecycle, provider) as saver:
        graph = build_council_graph(checkpointer=saver, context=lifecycle.context)
        result = graph.invoke(Command(resume={'approved': True}), lifecycle.config)
        assert_gate(result, 'GATE_2_PRE_SUBMIT_APPROVAL')
    assert observed
    assert all(configuration['roles']['orchestrator']['model'] == 'gpt-before-restart'
               for role, configuration in observed)
