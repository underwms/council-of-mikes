"""Resolve provider settings once per run, without credentials in checkpoints."""
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_PROVIDERS = {'gemini', 'gpt', 'gemini-cli', 'codex-cli'}
DEFAULT_ROLES = {'orchestrator': 'gpt-6.1-sol', 'investigator': 'gpt-6.1-sol',
                 'coder': 'gpt-6.1-sol'}
LEGACY_ROLES = {'orchestrator', 'investigator'}
AUTONOMOUS_ROLES = {**DEFAULT_ROLES, 'reviewer': 'gpt-6.1-sol'}
PROVIDER_DEFAULT_MODELS = {'gpt': 'gpt-6.1-sol', 'gemini': 'gemini-2.5-pro',
                           'gemini-cli': 'gemini-2.5-pro', 'codex-cli': 'gpt-6.1-sol'}
PROVIDER_KEYS = {'gpt': 'OPENAI_API_KEY', 'gemini': 'GEMINI_API_KEY'}


def resolve_model_provider(name):
    normalized = name.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError('Unsupported model provider')
    return normalized


def _provider_settings(provider):
    if provider == 'codex-cli':
        from council.codex_cli import resolve_cli_settings
        return resolve_cli_settings()
    if provider == 'gemini-cli':
        from council.gemini_cli import resolve_cli_settings
        return resolve_cli_settings()
    return ({'use_responses_api': True, 'include_response_headers': True,
             'base_url': 'https://api.openai.com/v1'} if provider == 'gpt' else
            {'temperature': 0.1, 'vertexai': False,
             'base_url': 'https://generativelanguage.googleapis.com'})


class RoleModelConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['gpt', 'gemini', 'gemini-cli', 'codex-cli']
    model: str = Field(min_length=1, max_length=200)
    settings: dict[str, Any]

    @model_validator(mode='after')
    def validate_settings(self):
        if self.provider == 'codex-cli':
            from council.codex_cli import validate_cli_settings
            validate_cli_settings(self.settings)
        elif self.provider == 'gemini-cli':
            from council.gemini_cli import validate_cli_settings
            validate_cli_settings(self.settings)
        elif self.settings != _provider_settings(self.provider):
            raise ValueError('Unsupported provider settings')
        if self.model != self.model.strip() or any(ord(char) < 32 for char in self.model):
            raise ValueError('Invalid model identifier')
        return self


class RunModelConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1, 2, 3, 4] = 3
    roles: dict[str, RoleModelConfiguration]

    @model_validator(mode='after')
    def validate_roles(self):
        expected = set(AUTONOMOUS_ROLES) if self.version == 4 else set(DEFAULT_ROLES) if self.version == 3 else LEGACY_ROLES
        if set(self.roles) != expected:
            raise ValueError('Configuration requires exactly the supported Council roles')
        if self.version == 1 and any(role.provider.endswith('-cli') for role in self.roles.values()):
            raise ValueError('Version one configuration does not support CLI providers')
        if self.version < 3 and any(role.provider == 'codex-cli' for role in self.roles.values()):
            raise ValueError('Legacy reasoning snapshots do not support Codex CLI')
        if self.version >= 3 and self.roles['coder'].provider != 'codex-cli':
            raise ValueError('The coder role requires Codex CLI')
        if self.version == 4 and self.roles['reviewer'].provider != 'codex-cli':
            raise ValueError('The reviewer role requires Codex CLI')
        return self


def resolve_model_configuration(*, autonomous=False):
    roles = {}
    settings = {}
    for role, default in (AUTONOMOUS_ROLES if autonomous else DEFAULT_ROLES).items():
        model = os.environ.get(f'COUNCIL_{role.upper()}_MODEL', default)
        provider = os.environ.get(f'COUNCIL_{role.upper()}_PROVIDER')
        if provider:
            provider = resolve_model_provider(provider)
            model = os.environ.get(f'COUNCIL_{role.upper()}_MODEL', PROVIDER_DEFAULT_MODELS[provider])
        if not provider:
            lower = model.lower()
            provider = ('gemini-cli' if lower.startswith('gemini') else
                        'codex-cli' if lower.startswith(('gpt', 'o1', 'o3', 'o4')) else None)
        if not provider:
            raise ValueError('Custom models require an explicit Council role provider')
        provider = resolve_model_provider(provider)
        if provider not in settings:
            settings[provider] = _provider_settings(provider)
        roles[role] = RoleModelConfiguration(provider=provider, model=model, settings=settings[provider])
    return RunModelConfiguration(version=4 if autonomous else 3, roles=roles)


def preflight_credentials(configuration):
    """Report API key presence or CLI readiness without making model requests."""
    resolved = RunModelConfiguration.model_validate(configuration)
    readiness = {}
    for role in resolved.roles.values():
        if role.provider == 'codex-cli':
            from council.codex_cli import cli_ready
            ready = cli_ready(role.settings)
        elif role.provider == 'gemini-cli':
            from council.gemini_cli import cli_ready
            ready = cli_ready(role.settings)
        else:
            ready = bool(os.environ.get(PROVIDER_KEYS[role.provider]))
        readiness[role.provider] = readiness.get(role.provider, True) and bool(ready)
    return readiness


def get_llm(model_name='gpt', *, model=None, settings=None, context=None):
    provider = resolve_model_provider(model_name)
    selected = model or PROVIDER_DEFAULT_MODELS[provider]
    validated = RoleModelConfiguration(provider=provider, model=selected,
                                       settings=_provider_settings(provider) if settings is None else settings)
    if provider == 'codex-cli':
        from council.codex_cli import CodexCLIWorker
        return CodexCLIWorker(model=validated.model, settings=validated.settings, context=context)
    if provider == 'gemini-cli':
        from council.gemini_cli import GeminiCLIChatModel
        return GeminiCLIChatModel(model=validated.model, settings=validated.settings, context=context)
    key = PROVIDER_KEYS[provider]
    if not os.environ.get(key):
        raise ValueError(f'{key} is required for provider {provider}')
    if provider == 'gpt':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=validated.model, **validated.settings)
    # The installed LangChain wrapper omits vertexai=False when creating its
    # underlying SDK client; reject the ambient switch before it can drift.
    if os.environ.get('GOOGLE_GENAI_USE_VERTEXAI', '').lower() == 'true':
        raise ValueError('Gemini Developer API requires GOOGLE_GENAI_USE_VERTEXAI unset or false')
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=validated.model, google_api_key=os.environ[key], **validated.settings)


def get_llm_for_role(role, configuration=None, *, context=None):
    if role not in AUTONOMOUS_ROLES:
        raise ValueError('Unknown Council role')
    resolved = resolve_model_configuration() if configuration is None else RunModelConfiguration.model_validate(configuration)
    if role not in resolved.roles:
        raise ValueError('Unknown Council role in persisted configuration')
    selected = resolved.roles[role]
    if selected.provider == 'codex-cli' and role in {'orchestrator','investigator'}:
        from council.codex_chat import CodexCLIChatModel
        return CodexCLIChatModel(model=selected.model,settings=selected.settings,context=context)
    context_args = {'context': context} if selected.provider in {'gemini-cli', 'codex-cli'} and context is not None else {}
    return get_llm(selected.provider, model=selected.model, settings=selected.settings, **context_args)
