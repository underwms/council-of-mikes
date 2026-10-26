import os
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

import pytest
from council import config
from council.config import get_llm, get_llm_for_role, resolve_model_provider
from council.graph import the_architect_node
from council.state import CouncilState


CLI_SETTINGS = {'node_path': 'C:/trusted/node.exe', 'entrypoint': 'C:/trusted/gemini/index.js',
                'cli_version': '0.64.0', 'timeout_seconds': 180}
CODEX_SETTINGS = {'executable': 'C:/trusted/codex.exe', 'cli_version': '0.163.0', 'timeout_seconds': 600}
API_ENV = {'COUNCIL_ORCHESTRATOR_PROVIDER': 'gpt', 'COUNCIL_ORCHESTRATOR_MODEL': 'gpt-6.1-sol',
           'COUNCIL_INVESTIGATOR_PROVIDER': 'gemini', 'COUNCIL_INVESTIGATOR_MODEL': 'gemini-3.8-flash'}
GEMINI_CLI_ENV = {'COUNCIL_ORCHESTRATOR_PROVIDER':'gemini-cli','COUNCIL_INVESTIGATOR_PROVIDER':'gemini-cli'}


@pytest.fixture(autouse=True)
def cli_adapter(monkeypatch):
    """Model the adapter boundary without launching a CLI or accessing OAuth state."""
    module = ModuleType('council.gemini_cli')
    module.resolve_cli_settings = MagicMock(side_effect=lambda: dict(CLI_SETTINGS))
    module.validate_cli_settings = MagicMock(side_effect=lambda settings: dict(settings))
    module.cli_ready = MagicMock(return_value=True)
    module.GeminiCLIChatModel = MagicMock()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


@pytest.fixture(autouse=True)
def codex_adapter(monkeypatch):
    module = ModuleType('council.codex_cli')
    module.resolve_cli_settings = MagicMock(side_effect=lambda: dict(CODEX_SETTINGS))
    module.validate_cli_settings = MagicMock()
    module.cli_ready = MagicMock(return_value=True)
    module.CodexCLIWorker = MagicMock()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def legacy_configuration(version=2):
    providers={name:os.environ.get(name,value) for name,value in GEMINI_CLI_ENV.items()}
    with patch.dict(os.environ,providers):
        data = config.resolve_model_configuration().model_dump()
    data['roles'].pop('coder', None)
    data['version'] = version
    return config.RunModelConfiguration.model_validate(data)


class ConfigTests(unittest.TestCase):
    def test_missing_api_credentials_fail_instead_of_adapter(self):
        with patch.dict(os.environ, API_ENV, clear=True):
            with self.assertRaises(ValueError):
                get_llm_for_role('orchestrator')


class PlanningTests(unittest.TestCase):
    def test_provider_error_is_not_a_fabricated_plan(self):
        with patch('council.graph.get_llm_for_role', side_effect=ValueError('missing')):
            with self.assertRaises(ValueError):
                the_architect_node(CouncilState(run_id='test', task_input='real task'))


@pytest.mark.parametrize('provider,module,constructor,key', [
    ('gpt', 'langchain_openai', 'ChatOpenAI', 'OPENAI_API_KEY'),
    ('gemini', 'langchain_google_genai', 'ChatGoogleGenerativeAI', 'GEMINI_API_KEY'),
])
def test_provider_constructs_exact_model_without_api(provider, module, constructor, key):
    with patch.dict(os.environ, {key: 'local-fake-key'}), patch(module + '.' + constructor) as sdk:
        get_llm(provider, model='exact-configured-model')
        assert sdk.call_args.kwargs['model'] == 'exact-configured-model'
        if provider == 'gpt':
            assert 'temperature' not in sdk.call_args.kwargs
            assert sdk.call_args.kwargs['use_responses_api'] is True
            assert sdk.call_args.kwargs['include_response_headers'] is True
        else:
            assert sdk.call_args.kwargs['temperature'] == 0.1


def test_invalid_provider_role_and_missing_credentials_are_safe():
    with pytest.raises(ValueError):
        resolve_model_provider('unknown')
    with pytest.raises(ValueError):
        get_llm_for_role('unknown')
    for provider, key in [('gpt', 'OPENAI_API_KEY'), ('gemini', 'GEMINI_API_KEY')]:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match=key):
            get_llm(provider)


def test_only_supported_roles_and_providers_remain():
    assert config.SUPPORTED_PROVIDERS == {'gpt', 'gemini', 'gemini-cli', 'codex-cli'}
    assert set(config.DEFAULT_ROLES) == {'orchestrator', 'investigator', 'coder'}


def test_default_roles_resolve_to_cli_without_keys_and_no_credentials_in_checkpoint(cli_adapter):
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'private-test-value'}, clear=True):
        result = config.resolve_model_configuration()
    assert result.version == 3
    assert {role.provider for role in result.roles.values()} == {'codex-cli'}
    assert result.roles['coder'].model == 'gpt-6.1-sol'
    assert result.roles['coder'].provider == 'codex-cli'
    assert result.roles['coder'].settings == CODEX_SETTINGS
    assert all(role.settings == CODEX_SETTINGS for role in result.roles.values())
    assert all(role.model == 'gpt-6.1-sol' for role in result.roles.values())
    assert 'private-test-value' not in result.model_dump_json()
    assert config.RunModelConfiguration.model_validate_json(result.model_dump_json()) == result
    cli_adapter.resolve_cli_settings.assert_not_called()
    cli_adapter.GeminiCLIChatModel.assert_not_called()


def test_explicit_api_configuration_remains_supported():
    with patch.dict(os.environ, API_ENV, clear=True):
        result = config.resolve_model_configuration()
    assert result.roles['orchestrator'].provider == 'gpt'
    assert result.roles['orchestrator'].settings == {'use_responses_api': True, 'include_response_headers': True, 'base_url': 'https://api.openai.com/v1'}
    assert result.roles['investigator'].settings == {'temperature': 0.1, 'vertexai': False, 'base_url': 'https://generativelanguage.googleapis.com'}


def test_persisted_api_role_configuration_survives_environment_change():
    with patch.dict(os.environ, {**API_ENV, 'COUNCIL_ORCHESTRATOR_MODEL': 'gpt-exact'}, clear=True):
        result = config.resolve_model_configuration()
    with patch.dict(os.environ, {'COUNCIL_ORCHESTRATOR_MODEL': 'gpt-changed'}, clear=True), patch('council.config.get_llm') as factory:
        get_llm_for_role('orchestrator', result.model_dump())
    factory.assert_called_once_with('gpt', model='gpt-exact', settings={'use_responses_api': True, 'include_response_headers': True, 'base_url': 'https://api.openai.com/v1'})


def test_custom_models_require_explicit_provider_and_preserve_exact_name():
    with patch.dict(os.environ, {'COUNCIL_INVESTIGATOR_MODEL': 'custom-model'}, clear=True):
        with pytest.raises(ValueError, match='explicit'):
            config.resolve_model_configuration()
        with patch.dict(os.environ, {'COUNCIL_INVESTIGATOR_PROVIDER': 'gemini'}):
            result = config.resolve_model_configuration()
    assert result.roles['investigator'].model == 'custom-model'
    assert result.roles['investigator'].provider == 'gemini'


def test_preflight_reports_presence_only_for_selected_api_providers():
    with patch.dict(os.environ, API_ENV, clear=True):
        result = legacy_configuration()
        assert config.preflight_credentials(result) == {'gpt': False, 'gemini': False}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'private-value'}):
            assert config.preflight_credentials(result) == {'gpt': True, 'gemini': False}


def test_configuration_rejects_extra_settings_and_unknown_schema_versions():
    with patch.dict(os.environ, API_ENV, clear=True):
        data = config.resolve_model_configuration().model_dump()
    data['version'] = 4
    with pytest.raises(ValueError):
        config.RunModelConfiguration.model_validate(data)
    data['version'] = 1
    data['roles']['orchestrator']['settings']['api_key'] = 'private-value'
    with pytest.raises(ValueError):
        config.RunModelConfiguration.model_validate(data)


def test_version_one_api_configuration_remains_resumable():
    with patch.dict(os.environ, API_ENV, clear=True):
        data = config.resolve_model_configuration().model_dump()
    data['version'] = 1
    data['roles'].pop('coder', None)
    assert config.RunModelConfiguration.model_validate(data).version == 1


def test_version_one_cannot_claim_cli_provider():
    with patch.dict(os.environ, {}, clear=True):
        data = legacy_configuration().model_dump()
    data['version'] = 1
    with pytest.raises(ValueError):
        config.RunModelConfiguration.model_validate(data)


def test_cli_preflight_checks_adapter_readiness_without_api_keys(cli_adapter):
    with patch.dict(os.environ, GEMINI_CLI_ENV, clear=True):
        resolved = config.resolve_model_configuration()
        assert config.preflight_credentials(resolved) == {'gemini-cli': True, 'codex-cli': True}
        cli_adapter.cli_ready.return_value = False
        assert config.preflight_credentials(resolved) == {'gemini-cli': False, 'codex-cli': True}
    cli_adapter.GeminiCLIChatModel.assert_not_called()


def test_cli_factory_forwards_persisted_settings_and_explicit_runtime_context(cli_adapter):
    context = object()
    with patch.dict(os.environ, GEMINI_CLI_ENV, clear=True):
        resolved = config.resolve_model_configuration()
        get_llm_for_role('orchestrator', resolved.model_dump(), context=context)
    cli_adapter.GeminiCLIChatModel.assert_called_once_with(model='gemini-2.5-pro', settings=CLI_SETTINGS, context=context)


def test_cli_settings_validation_uses_persisted_configuration_not_rediscovery(cli_adapter):
    with patch.dict(os.environ, GEMINI_CLI_ENV, clear=True):
        data = config.resolve_model_configuration().model_dump()
    cli_adapter.resolve_cli_settings.reset_mock()
    data['roles']['orchestrator']['settings']['node_path'] = 'C:/pinned/node.exe'
    result = config.RunModelConfiguration.model_validate(data)
    assert result.roles['orchestrator'].settings['node_path'] == 'C:/pinned/node.exe'
    cli_adapter.resolve_cli_settings.assert_not_called()
    cli_adapter.validate_cli_settings.assert_called()


def test_gemini_model_environment_infers_cli_while_api_provider_is_explicit():
    with patch.dict(os.environ, {'COUNCIL_ORCHESTRATOR_MODEL': 'gemini-exact'}, clear=True):
        result = config.resolve_model_configuration()
        assert result.roles['orchestrator'].provider == 'gemini-cli'
        assert result.roles['orchestrator'].model == 'gemini-exact'
        with patch.dict(os.environ, {'COUNCIL_ORCHESTRATOR_PROVIDER': 'gemini'}):
            assert config.resolve_model_configuration().roles['orchestrator'].provider == 'gemini'


def test_official_openai_endpoint_overrides_ambient_sdk_endpoints():
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fake-key',
            'OPENAI_BASE_URL': 'https://invalid.example/v1',
            'OPENAI_API_BASE': 'https://invalid.example/v1'}):
        model = get_llm('gpt')
    assert model.model_name == 'gpt-6.1-sol'
    assert str(model.root_client.base_url).rstrip('/') == 'https://api.openai.com/v1'
    assert model.use_responses_api is True
    assert model.include_response_headers is True
    from langchain_core.messages import HumanMessage
    payload = model._get_request_payload([HumanMessage(content='offline configuration check')])
    assert 'temperature' not in payload
    assert 'input' in payload


def test_gemini_pins_developer_api_and_endpoint_despite_ambient_base_url():
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-fake-key',
            'GOOGLE_GEMINI_BASE_URL': 'https://invalid.example',
            'GOOGLE_GENAI_USE_VERTEXAI': 'false'}):
        model = get_llm('gemini')
    try:
        assert model.vertexai is False
        assert model.client.vertexai is False
        assert model.client._api_client._http_options.base_url == 'https://generativelanguage.googleapis.com'
    finally:
        model.client.close()


def test_gemini_rejects_ambient_vertex_switch_before_constructing_client():
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-fake-key',
            'GOOGLE_GENAI_USE_VERTEXAI': 'true'}), patch('langchain_google_genai.ChatGoogleGenerativeAI') as sdk:
        with pytest.raises(ValueError, match='Developer API'):
            get_llm('gemini')
        sdk.assert_not_called()


def test_explicit_provider_without_model_uses_provider_specific_default(cli_adapter):
    with patch.dict(os.environ, {'COUNCIL_ORCHESTRATOR_PROVIDER': 'gpt',
                                  'COUNCIL_INVESTIGATOR_PROVIDER': 'gemini'}, clear=True):
        result = config.resolve_model_configuration()
    assert result.roles['orchestrator'].model == 'gpt-6.1-sol'
    assert result.roles['investigator'].model == 'gemini-2.5-pro'
    cli_adapter.resolve_cli_settings.assert_not_called()


def test_cli_validator_may_validate_in_place_without_returning_settings(cli_adapter):
    cli_adapter.validate_cli_settings.side_effect = lambda settings: None
    with patch.dict(os.environ, GEMINI_CLI_ENV, clear=True):
        result = config.resolve_model_configuration()
    assert all(role.settings == CLI_SETTINGS for name, role in result.roles.items() if name != 'coder')


def test_coder_default_settings_resolve_once_and_never_construct_worker(codex_adapter):
    with patch.dict(os.environ, {}, clear=True):
        result = config.resolve_model_configuration()
    assert result.roles['coder'].settings == CODEX_SETTINGS
    codex_adapter.resolve_cli_settings.assert_called_once()
    codex_adapter.CodexCLIWorker.assert_not_called()


def test_coder_factory_forwards_pinned_model_settings_and_context(codex_adapter):
    context = object()
    with patch.dict(os.environ, {}, clear=True):
        resolved = config.resolve_model_configuration()
    codex_adapter.resolve_cli_settings.reset_mock()
    with patch.dict(os.environ, {'COUNCIL_CODER_MODEL': 'gpt-changed'}, clear=True):
        get_llm_for_role('coder', resolved.model_dump(), context=context)
    codex_adapter.CodexCLIWorker.assert_called_once_with(model='gpt-6.1-sol', settings=CODEX_SETTINGS, context=context)
    codex_adapter.resolve_cli_settings.assert_not_called()


@pytest.mark.parametrize('version', [1, 2])
def test_legacy_api_snapshots_keep_exact_two_roles_and_no_coder(version):
    with patch.dict(os.environ, API_ENV, clear=True):
        saved = legacy_configuration(version)
    assert set(saved.roles) == {'orchestrator', 'investigator'}
    with pytest.raises(ValueError, match='role'):
        get_llm_for_role('coder', saved)
    data = saved.model_dump()
    data['roles']['coder'] = {'provider': 'codex-cli', 'model': 'gpt-6.1-sol', 'settings': CODEX_SETTINGS}
    with pytest.raises(ValueError):
        config.RunModelConfiguration.model_validate(data)


def test_version_two_cli_snapshot_keeps_original_routing_without_coder(cli_adapter, codex_adapter):
    with patch.dict(os.environ, {}, clear=True):
        saved = legacy_configuration()
    get_llm_for_role('orchestrator', saved)
    cli_adapter.GeminiCLIChatModel.assert_called_once()
    codex_adapter.CodexCLIWorker.assert_not_called()
    with pytest.raises(ValueError):
        get_llm_for_role('coder', saved)


@pytest.mark.parametrize('role', ['orchestrator', 'investigator'])
def test_codex_reasoning_roles_use_text_adapter_instead_of_coding_worker(role):
    with patch.dict(os.environ, {f'COUNCIL_{role.upper()}_PROVIDER': 'codex-cli'}, clear=True):
        resolved=config.resolve_model_configuration()
    with patch('council.codex_chat.CodexCLIChatModel') as adapter:
        get_llm_for_role(role,resolved,context='fixture-context')
    adapter.assert_called_once_with(model='gpt-6.1-sol',settings=CODEX_SETTINGS,context='fixture-context')


def test_native_coder_role_rejects_non_native_provider():
    with patch.dict(os.environ, {'COUNCIL_CODER_PROVIDER': 'gpt'}, clear=True):
        with pytest.raises(ValueError):
            config.resolve_model_configuration()


def test_version_three_requires_all_three_roles():
    with patch.dict(os.environ, {}, clear=True):
        data = config.resolve_model_configuration().model_dump()
    data['roles'].pop('coder', None)
    data['version'] = 3
    with pytest.raises(ValueError):
        config.RunModelConfiguration.model_validate(data)


def test_coder_preflight_uses_native_readiness_without_api_credentials(codex_adapter):
    with patch.dict(os.environ, {}, clear=True):
        resolved = config.resolve_model_configuration()
        codex_adapter.cli_ready.return_value = False
        assert config.preflight_credentials(resolved) == {'codex-cli': False}
    codex_adapter.CodexCLIWorker.assert_not_called()


def test_state_can_roundtrip_coder_role():
    state = CouncilState(run_id='coder-test', task_input='fixture', active_role='coder')
    assert CouncilState.model_validate_json(state.model_dump_json()).active_role == 'coder'
