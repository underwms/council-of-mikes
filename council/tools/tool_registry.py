"""LangChain-compatible tool registry for Council specialists."""
from typing import Optional

from council.runner import SubprocessRunner
from council.tools.file_tools import FileTools
from council.tools.test_runner import TestSuiteRunner
from council.tools.validator_bridge import run_workspace_audit

from langchain_core.tools import tool as lc_tool


def get_council_tools(workspace_root=None, specialist=None, *, context=None):
    """Build workspace-bound tools using the graph's explicit runtime context."""
    from council.runtime_context import resolve_context
    context = context or resolve_context(workspace_root)
    file_tools = FileTools(context=context)
    runner = SubprocessRunner(context=context)
    test_runner = TestSuiteRunner(runner)

    def read_file_fn(rel_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Reads content from a workspace file within optional start_line and end_line bounds."""
        return file_tools.read_file(rel_path, start_line=start_line, end_line=end_line)

    def write_file_fn(rel_path: str, content: str) -> str:
        """Writes complete content to a file inside the workspace."""
        file_tools.write_file(rel_path, content)
        return f"Successfully wrote {len(content)} characters to {rel_path}"

    def patch_file_fn(rel_path: str, old_string: str, new_string: str):
        """Replaces exactly one occurrence of old_string with new_string in a file."""
        success = file_tools.patch_file(rel_path, old_string, new_string)
        if success:
            return f"Successfully patched {rel_path}"
        return {"passed": False, "error": "Patch target missing or original text was absent or not unique"}

    def run_dotnet_test_fn(solution_or_project: str, filter_query: Optional[str] = None) -> dict:
        """Run dotnet test using literal arguments and return actual outcomes."""
        return test_runner.run_dotnet_test(solution_or_project, filter_query=filter_query)

    def run_deno_test_fn(dir_path: Optional[str] = None, filter_query: Optional[str] = None) -> dict:
        """Run Deno tests inside a selected workspace directory."""
        cwd = context.workspace_path(dir_path or '.')
        return test_runner.run_deno_test(cwd=cwd, filter_query=filter_query)

    def run_workspace_validator_fn() -> dict:
        """Execute the available workspace validator and return actual status."""
        passed, summary = run_workspace_audit(context=context)
        return {"passed": passed, **summary}

    # The active engine requires LangChain tools; missing dependencies fail at import.
    t_read = lc_tool(read_file_fn)
    t_read.name = "read_workspace_file"
    t_write = lc_tool(write_file_fn)
    t_write.name = "write_workspace_file"
    t_patch = lc_tool(patch_file_fn)
    t_patch.name = "patch_workspace_file"
    t_dotnet = lc_tool(run_dotnet_test_fn)
    t_dotnet.name = "run_dotnet_test"
    t_deno = lc_tool(run_deno_test_fn)
    t_deno.name = "run_deno_test"
    t_validator = lc_tool(run_workspace_validator_fn)
    t_validator.name = "run_workspace_validator"

    all_tools = {
        "read_workspace_file": t_read,
        "write_workspace_file": t_write,
        "patch_workspace_file": t_patch,
        "run_dotnet_test": t_dotnet,
        "run_deno_test": t_deno,
        "run_workspace_validator": t_validator
    }

    # Specialist-scoped tool selection
    if specialist in ("the-prover",):
        return [t_read, t_dotnet, t_deno]
    elif specialist in ("the-gatekeeper",):
        return [t_read, t_validator, t_dotnet, t_deno]
    elif specialist in ("the-architect", "the-codex"):
        return [t_read]
    elif specialist in ("the-coder", "the-curator", "the-purifier", "the-renderer"):
        return [t_read, t_patch, t_write, t_dotnet, t_deno]
    
    return list(all_tools.values())
