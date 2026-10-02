"""Test execution and compiler diagnostic parser for .NET and Deno."""
import re
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from council.runner import SubprocessRunner

def parse_dotnet_errors(output: str) -> List[str]:
    """Extracts CS compiler errors and fatal build failures."""
    error_pattern = re.compile(r"([^\r\n]*error\s+CS\d+:[^\r\n]*)", re.IGNORECASE)
    matches = error_pattern.findall(output)
    return [m.strip() for m in matches]

def parse_test_counts(output: str) -> Tuple[int, int]:
    """Extracts passed and failed test counts from dotnet test or MSTest output."""
    passed_match = re.search(r"Passed:\s*(\d+)", output, re.IGNORECASE)
    failed_match = re.search(r"Failed:\s*(\d+)", output, re.IGNORECASE)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    return passed, failed

def parse_deno_errors(output: str) -> List[str]:
    """Extracts Deno test assertion failures and error traces."""
    error_pattern = re.compile(r"(error:\s*[^\r\n]+|AssertionError:[^\r\n]+)", re.IGNORECASE)
    matches = error_pattern.findall(output)
    return [m.strip() for m in matches]

class TestSuiteRunner:
    """Executes test suites and parses structured diagnostic feedback."""

    def __init__(self, runner: SubprocessRunner):
        self.runner = runner

    def run_dotnet_test(
        self, 
        solution_or_project: str, 
        filter_query: Optional[str] = None, 
        cwd: Optional[Path] = None
    ) -> Dict[str, Any]:
        cmd = f"dotnet test {solution_or_project}"
        if filter_query:
            cmd += f" --filter \"{filter_query}\""

        exit_code, stdout, stderr = self.runner.run(cmd, cwd=cwd)
        combined = stdout + "\n" + stderr
        compiler_errors = parse_dotnet_errors(combined)
        passed_count, failed_count = parse_test_counts(combined)

        return {
            "command": cmd,
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "tests_passed": passed_count,
            "tests_failed": failed_count,
            "compiler_errors": compiler_errors,
            "raw_output": combined if exit_code != 0 else ""
        }

    def run_deno_test(self, cwd: Optional[Path] = None, filter_query: Optional[str] = None) -> Dict[str, Any]:
        cmd = "deno test"
        if filter_query:
            cmd += f" --filter \"{filter_query}\""

        exit_code, stdout, stderr = self.runner.run(cmd, cwd=cwd)
        combined = stdout + "\n" + stderr
        deno_errors = parse_deno_errors(combined)

        return {
            "command": cmd,
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "compiler_errors": deno_errors,
            "raw_output": combined if exit_code != 0 else ""
        }
