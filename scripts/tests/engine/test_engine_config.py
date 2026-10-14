import os
import unittest
from unittest.mock import patch
from council.config import get_llm_for_role
from council.graph import the_architect_node
from council.state import CouncilState

class ConfigTests(unittest.TestCase):
    def test_missing_credentials_fail_instead_of_adapter(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                get_llm_for_role('orchestrator')

class PlanningTests(unittest.TestCase):
    def test_provider_error_is_not_a_fabricated_plan(self):
        with patch('council.graph.get_llm_for_role', side_effect=ValueError('missing')):
            with self.assertRaises(ValueError):
                the_architect_node(CouncilState(run_id='test', task_input='real task'))

if __name__ == '__main__': unittest.main()

import pytest
from council.config import get_llm,resolve_model_provider

@pytest.mark.parametrize('provider,module,constructor,key',[
 ('gpt','langchain_openai','ChatOpenAI','OPENAI_API_KEY'),
 ('gemini','langchain_google_genai','ChatGoogleGenerativeAI','GEMINI_API_KEY'),
 ('claude','langchain_anthropic','ChatAnthropic','ANTHROPIC_API_KEY')])
def test_provider_constructs_exact_model_without_api(provider,module,constructor,key):
    with patch.dict(os.environ,{key:'local-fake-key'}),patch(module+'.'+constructor) as sdk:
        get_llm(provider,model='exact-configured-model')
        assert sdk.call_args.kwargs['model']=='exact-configured-model'
        assert sdk.call_args.kwargs['temperature']==0.1

def test_invalid_provider_role_and_missing_credentials_are_safe():
    with pytest.raises(ValueError):resolve_model_provider('unknown')
    with pytest.raises(ValueError):get_llm_for_role('unknown')
    for provider,key in [('gpt','OPENAI_API_KEY'),('gemini','GEMINI_API_KEY'),('claude','ANTHROPIC_API_KEY')]:
        with patch.dict(os.environ,{},clear=True),pytest.raises(ValueError,match=key):get_llm(provider)

@pytest.mark.parametrize('role,model,expected',[('investigator','gemini-exact','gemini'),('escalation','claude-exact','claude')])
def test_heterogeneous_role_model_forwarding(role,model,expected):
    with patch.dict(os.environ,{'COUNCIL_'+role.upper()+'_MODEL':model},clear=True),patch('council.config.get_llm') as factory:
        get_llm_for_role(role)
        factory.assert_called_once_with(expected,model=model)
