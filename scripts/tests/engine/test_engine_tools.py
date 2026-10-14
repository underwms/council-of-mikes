import tempfile, unittest, sys
from pathlib import Path
from council.runner import SubprocessRunner
from council.tools.test_runner import TestSuiteRunner as SuiteRunner, parse_test_counts
from council.tools.validator_bridge import run_workspace_audit

class EngineToolsTests(unittest.TestCase):
    def test_unknown_counts_are_not_passing_tests(self):
        self.assertEqual(parse_test_counts('successful build'),(None,None))
    def test_real_dotnet_and_deno_count_formats(self):
        self.assertEqual(parse_test_counts('Passed: 12 Failed: 2'),(12,2))
        self.assertEqual(parse_test_counts('ok | 7 passed | 1 failed'),(7,1))
    def test_missing_validator_is_failure(self):
        with tempfile.TemporaryDirectory() as root:
            passed,summary=run_workspace_audit(Path(root))
            self.assertFalse(passed)
            self.assertIn('missing',summary['error'].lower())
    def test_real_validator_subprocess_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix='validator space ') as root:
            workspace=Path(root).resolve()
            (workspace/'scripts').mkdir()
            validator=workspace/'scripts'/'validate_workspace.py'
            validator.write_text('import os,sys; assert sys.argv[1] == os.getcwd(), sys.argv; print(os.getcwd()); raise SystemExit(3)')
            passed,summary=run_workspace_audit(workspace)
            self.assertFalse(passed)
            self.assertEqual(summary['exit_code'],3)
            self.assertIn(str(workspace),summary['output'])

    def test_real_command_failure_retains_measured_counts(self):
        with tempfile.TemporaryDirectory() as root:
            suite=SuiteRunner(SubprocessRunner(Path(root)))
            result=suite.run_command([sys.executable,'-c','print("3 passed | 2 failed");raise SystemExit(1)'])
            self.assertFalse(result['passed'])
            self.assertEqual(result['exit_code'],1)
            self.assertEqual(result['tests_passed'],3)
            self.assertEqual(result['tests_failed'],2)
            self.assertTrue(result['counts_known'])

    def test_real_success_without_counts_is_explicitly_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            suite=SuiteRunner(SubprocessRunner(Path(root)))
            result=suite.run_command([sys.executable,'-c','print("build successful")'])
            self.assertTrue(result['passed'])
            self.assertIsNone(result['tests_passed'])
            self.assertFalse(result['counts_known'])

    def test_runner_timeout_missing_binary_and_literal_echo(self):
        with tempfile.TemporaryDirectory() as root:
            runner=SubprocessRunner(Path(root))
            self.assertEqual(runner.run([sys.executable,'-c','import time;time.sleep(10)'],timeout=0.01)[0],124)
            self.assertEqual(runner.run([str(Path(root)/'missing.exe')])[0],127)
            code,out,err=runner.run_echo("literal ' $() ; text")
            self.assertEqual(code,0,err)
            self.assertEqual(out.strip(),"literal ' $() ; text")
            for command in ('echo unsafe',[],[1]):
                with self.assertRaises(ValueError): runner.run(command)

    def test_test_cli_arguments_and_filters_remain_literal(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            workspace=Path(root).resolve()
            runner=SubprocessRunner(workspace)
            suite=SuiteRunner(runner)
            with patch.object(runner,'run',return_value=(0,'Passed: 4 Failed: 0','')) as execute:
                result=suite.run_dotnet_test('project with spaces.csproj',filter_query='Name="a; $()"')
                self.assertTrue(result['passed'])
                self.assertEqual(execute.call_args.args[0],['dotnet','test',str(workspace/'project with spaces.csproj'),'--filter','Name="a; $()"'])
                suite.run_dotnet_test('project.csproj')
                self.assertEqual(len(execute.call_args.args[0]),3)
                suite.run_deno_test(filter_query='literal ; filter')
                self.assertEqual(execute.call_args.args[0],['deno','test','--filter','literal ; filter'])
                suite.run_deno_test()
                self.assertEqual(execute.call_args.args[0],['deno','test'])
            with self.assertRaises(PermissionError): suite.run_dotnet_test('../outside.csproj')
            with self.assertRaises(PermissionError): suite.run_dotnet_test(str(workspace.parent/'outside.csproj'))

    def test_powershell_validator_executes_actual_context_arguments(self):
        from council.runtime_context import RuntimeContext
        with tempfile.TemporaryDirectory() as root:
            base=Path(root).resolve()
            workspace=base/'workspace'; workspace.mkdir()
            council=base/'profile'/'.council'; council.mkdir(parents=True)
            (council/'manifest.json').write_text('{}')
            context=RuntimeContext(council,workspace,council/'memory'/'engine')
            (workspace/'scripts').mkdir()
            (workspace/'scripts'/'validate-workspace.ps1').write_text('param([string]$WorkspaceRoot,[string]$GlobalGeminiRoot)\nif ($WorkspaceRoot -ne (Get-Location).Path -or $GlobalGeminiRoot -ne '+"'"+str(council)+"'"+') {exit 9}\nWrite-Output "validator actual"; exit 0')
            passed,summary=run_workspace_audit(context=context)
            self.assertTrue(passed,summary)
            self.assertIn('validator actual',summary['output'])
            from unittest.mock import patch
            with patch('council.tools.validator_bridge.shutil.which',return_value=None):
                passed,summary=run_workspace_audit(context=context)
                self.assertFalse(passed)
                self.assertIn('PowerShell',summary['error'])

    def test_redirected_validator_is_never_executed(self):
        import subprocess
        with tempfile.TemporaryDirectory() as root:
            base=Path(root).resolve()
            workspace=base/'workspace'; workspace.mkdir()
            outside=base/'outside'; outside.mkdir()
            (outside/'validate_workspace.py').write_text('raise RuntimeError("must not execute")')
            result=subprocess.run(['cmd','/c','mklink','/J',str(workspace/'scripts'),str(outside)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            passed,summary=run_workspace_audit(workspace)
            self.assertFalse(passed)
            self.assertIn('outside',summary['error'])

    def test_missing_langchain_dependency_fails_import(self):
        import builtins,runpy
        from unittest.mock import patch
        import council.tools.tool_registry as registry
        original=builtins.__import__
        def import_dependency(name,*args,**kwargs):
            if name=='langchain_core.tools': raise ImportError('missing required langchain-core')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=import_dependency):
            with self.assertRaises(ImportError): runpy.run_path(registry.__file__)

    def test_validator_resolves_installed_context_when_no_arguments_supplied(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            base=Path(root).resolve()
            workspace=base/'workspace'; workspace.mkdir()
            council=base/'profile'/'.council'; council.mkdir(parents=True)
            (council/'manifest.json').write_text('{}')
            (workspace/'scripts').mkdir()
            (workspace/'scripts'/'validate_workspace.py').write_text('import os,sys; assert sys.argv[1] == os.getcwd(); print("context validator actual")')
            with patch.dict(os.environ,{'COUNCIL_ROOT':str(council),'COUNCIL_WORKSPACE_ROOT':str(workspace)}):
                passed,summary=run_workspace_audit()
            self.assertTrue(passed,summary)
            self.assertIn('context validator actual',summary['output'])

    def test_explicit_workspace_validator_needs_no_profile_context(self):
        with tempfile.TemporaryDirectory() as root:
            workspace=Path(root).resolve()
            (workspace/'scripts').mkdir()
            (workspace/'scripts'/'validate-workspace.ps1').write_text('param([string]$WorkspaceRoot)\nif ($WorkspaceRoot -ne (Get-Location).Path) {exit 9}\nWrite-Output "workspace validator actual"; exit 0')
            passed,summary=run_workspace_audit(workspace)
            self.assertTrue(passed,summary)
            self.assertIn('workspace validator actual',summary['output'])

if __name__=='__main__': unittest.main()
