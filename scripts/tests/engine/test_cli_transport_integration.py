"""Default CLI routing preserves graph gates without requiring API keys."""
import json

from langchain_core.messages import AIMessage
from test_engine_integration import lifecycle, ScriptedProvider


def test_default_cli_model_factory_receives_workspace_context(lifecycle, monkeypatch, capsys):
    from council.cli import run_council_task
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda config: {'codex-cli':True})
    provider = ScriptedProvider(lifecycle.plan)
    contexts = []
    def factory(role, configuration=None, *, context=None):
        contexts.append(context)
        assert configuration['roles'][role]['provider'] == 'codex-cli'
        return provider
    monkeypatch.setattr('council.graph.get_llm_for_role', factory)
    code = run_council_task(prompt='fixture', workspace_root=lifecycle.workspace,
                           council_root=lifecycle.context.council_root, no_input=True, approval_mode='manual')
    assert code == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'PAUSED'
    assert contexts and all(context.workspace_root == lifecycle.workspace for context in contexts)
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_cli_readiness_failure_explains_login_instead_of_api_keys(monkeypatch, capsys):
    from council.cli import credentials_available
    monkeypatch.setattr('council.cli.preflight_credentials', lambda config: {'gemini-cli':False})
    assert credentials_available({}) is False
    result = json.loads(capsys.readouterr().out)
    assert result['unavailable_transports'] == ['gemini-cli']
    assert result['missing_credentials'] == []
    assert 'sign in' in result['remediation'].lower()


def test_codex_readiness_failure_explains_saved_chatgpt_login(monkeypatch, capsys):
    from council.cli import credentials_available
    monkeypatch.setattr('council.cli.preflight_credentials', lambda config: {'codex-cli':False})
    assert credentials_available({}) is False
    result = json.loads(capsys.readouterr().out)
    assert result['unavailable_transports'] == ['codex-cli']
    assert result['missing_credentials'] == []
    assert 'Codex' in result['remediation']
    assert 'ChatGPT' in result['remediation']


def test_offline_doctor_distinguishes_cli_cache_from_live_auth(lifecycle, monkeypatch, capsys):
    from council.cli import doctor
    monkeypatch.setattr('council.cli.preflight_credentials', lambda config: {'gemini-cli':True})
    assert doctor(lifecycle.context) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['transport_readiness'] == {'gemini-cli':True}
    assert result['credential_presence'] == {}
    assert result['live_provider_access'] == 'unverified'
    assert result['provider_requests'] == 0


def test_cli_evidence_labels_process_version_without_inventing_provider_ids(monkeypatch):
    from council.config import resolve_model_configuration
    from council.model_evidence import build_call_record
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_PROVIDER','gemini-cli')
    configuration = resolve_model_configuration()
    response = AIMessage(content='fixture', response_metadata={'transport':'gemini_cli',
                         'cli_version':'0.64.0','model_name':'gemini-3.8-flash'})
    record = build_call_record(configuration, 'orchestrator', 'worker', response=response)
    assert record['provider'] == 'gemini-cli'
    assert record['cli_version'] == '0.64.0'
    assert record['returned_model'] == 'gemini-3.8-flash'
    assert 'request_id' not in record and 'response_id' not in record


def test_cli_aggregate_model_is_labeled_as_cli_evidence(monkeypatch):
    from council.config import resolve_model_configuration
    from council.model_evidence import build_call_record
    monkeypatch.setenv('COUNCIL_ORCHESTRATOR_PROVIDER','gemini-cli')
    response = AIMessage(content='fixture', response_metadata={'cli_version':'0.64.0',
                         'cli_reported_model':'gemini-3.8-flash'})
    record = build_call_record(resolve_model_configuration(), 'orchestrator', 'worker', response=response)
    assert record['cli_reported_model'] == 'gemini-3.8-flash'
    assert 'returned_model' not in record


def test_codex_evidence_labels_native_thread_without_provider_identity():
    from council.config import resolve_model_configuration
    from council.model_evidence import build_call_record
    response = AIMessage(content='private coding result',
                         additional_kwargs={'native_file_changes':['private-file.txt']},
                         response_metadata={'transport':'codex-cli', 'cli_version':'0.163.0',
                                            'cli_warning_count':1, 'cli_failed_item_count':2,
                                            'warning_message':'private diagnostic',
                                            'cli_thread_id':'0199a213-81c0-7800-8aa1-bbab2a035a53'},
                         usage_metadata={'input_tokens':5,'output_tokens':3,'total_tokens':8})
    record = build_call_record(resolve_model_configuration(), 'coder', 'worker', response=response)
    assert record['role'] == 'coder'
    assert record['transport'] == 'codex-cli'
    assert record['cli_version'] == '0.163.0'
    assert record['cli_warning_count'] == 1
    assert record['cli_failed_item_count'] == 2
    assert record['cli_thread_id'] == '0199a213-81c0-7800-8aa1-bbab2a035a53'
    assert record['usage']['total_tokens'] == 8
    assert not {'returned_model','request_id','response_id'} & record.keys()
    assert 'private' not in json.dumps(record)
