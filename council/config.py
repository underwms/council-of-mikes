"""Exact role/provider selection without silent substitutes or implicit dotenv reads."""
import os
SUPPORTED_PROVIDERS = {'gemini', 'claude', 'gpt'}
DEFAULT_ROLES = {'orchestrator': 'gpt-6.1-sol', 'investigator': 'gemini-3.8-flash', 'escalation': 'claude-4.5-sonnet'}
ESCALATION_ENABLED = os.environ.get('COUNCIL_ENABLE_ESCALATION', 'false').lower() in ('true', '1', 'yes')

def resolve_model_provider(name):
    normalized = name.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError('Unsupported model provider')
    return normalized

def get_llm(model_name='gpt', *, model=None):
    provider = resolve_model_provider(model_name)
    selected = model or {'gpt': DEFAULT_ROLES['orchestrator'], 'gemini': DEFAULT_ROLES['investigator'], 'claude': DEFAULT_ROLES['escalation']}[provider]
    key = {'gpt': 'OPENAI_API_KEY', 'gemini': 'GEMINI_API_KEY', 'claude': 'ANTHROPIC_API_KEY'}[provider]
    if not os.environ.get(key):
        raise ValueError(f'{key} is required for provider {provider}')
    if provider == 'gpt':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=selected, temperature=0.1)
    if provider == 'gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=selected, temperature=0.1, google_api_key=os.environ[key])
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=selected, temperature=0.1)

def get_llm_for_role(role):
    if role not in DEFAULT_ROLES:
        raise ValueError('Unknown Council role')
    model = os.environ.get(f'COUNCIL_{role.upper()}_MODEL', DEFAULT_ROLES[role])
    provider = os.environ.get(f'COUNCIL_{role.upper()}_PROVIDER')
    if not provider:
        provider = 'gemini' if model.lower().startswith('gemini') else 'claude' if model.lower().startswith('claude') else 'gpt' if model.lower().startswith(('gpt','o1','o3','o4')) else None
    if not provider:
        raise ValueError('Custom models require an explicit Council role provider')
    return get_llm(provider, model=model)
