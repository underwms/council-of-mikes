"""Actual subprocess test outcomes and conservative count parsing."""
import re
from council.runner import SubprocessRunner


def parse_dotnet_errors(output):
    return re.findall(r'[^\r\n]*error\s+CS\d+:[^\r\n]*', output, re.I)


def parse_deno_errors(output):
    return re.findall(r'(?:error:|AssertionError:)[^\r\n]*', output, re.I)


def parse_test_counts(output):
    output = re.sub(r'\x1b\[[0-9;]*m','',output)
    def count(label):
        matches = re.findall(rf'\b{label}:\s*(\d+)', output, re.I)
        if not matches:
            matches = re.findall(rf'\b(\d+)\s+{label}\b',output,re.I)
        return int(matches[-1]) if matches else None
    passed,failed=count('passed'),count('failed')
    # A known zero-failure summary is supplied by runners, never inferred from exit status.
    return passed, failed


class TestSuiteRunner:
    def __init__(self, runner: SubprocessRunner):
        self.runner = runner

    def run_command(self, command, cwd=None):
        code,out,err=self.runner.run(command,cwd=cwd)
        output=out+'\n'+err
        passed,failed=parse_test_counts(output)
        return {'command':list(command),'passed':code==0,'exit_code':code,
                'tests_passed':passed,'tests_failed':failed,'counts_known':passed is not None and failed is not None,
                'compiler_errors':parse_dotnet_errors(output)+parse_deno_errors(output),
                'raw_output':output[-4000:]}

    def run_dotnet_test(self, solution_or_project, filter_query=None, cwd=None):
        root=self.runner.resolve_cwd(cwd)
        target=(root/solution_or_project).resolve()
        if not target.is_relative_to(self.runner.workspace_root):
            raise PermissionError('Test project escapes selected workspace')
        command=['dotnet','test',str(target)]
        if filter_query:
            command += ['--filter',filter_query]
        return self.run_command(command,cwd=root)

    def run_deno_test(self, cwd=None, filter_query=None):
        command=['deno','test']
        if filter_query:
            command += ['--filter',filter_query]
        return self.run_command(command,cwd=cwd)
