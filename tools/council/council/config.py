"""Multi-provider LLM factory supporting Gemini, Claude, and GPT."""
import os
from pathlib import Path
from typing import Optional, Any

# Attempt to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Minimal standard library .env loader
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

SUPPORTED_PROVIDERS = {"gemini", "claude", "gpt"}

def resolve_model_provider(name: str) -> str:
    """Normalizes and validates model provider names."""
    normalized = name.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported model provider '{name}'. Supported options: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )
    return normalized

class BaseChatAdapter:
    """Fallback LLM chat adapter for environments prior to pip installation."""
    def __init__(self, provider: str, model_name: str):
        self.provider = provider
        self.model_name = model_name

    def __repr__(self) -> str:
        return f"<ChatAdapter provider={self.provider} model={self.model_name}>"

def get_llm(model_name: str = "gemini") -> Any:
    """Factory creating configured LLM chat models for the Council engine."""
    provider = resolve_model_provider(model_name)
    
    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required to execute with Google Gemini."
            )
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
        except ImportError:
            return BaseChatAdapter("gemini", "gemini-2.0-flash")

    elif provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required to execute with Anthropic Claude."
            )
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.1)
        except ImportError:
            return BaseChatAdapter("claude", "claude-3-5-sonnet-20241022")

    elif provider == "gpt":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required to execute with OpenAI GPT."
            )
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o", temperature=0.1)
        except ImportError:
            return BaseChatAdapter("gpt", "gpt-4o")
