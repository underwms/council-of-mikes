import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

class RuntimePathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='council paths ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.council = self.base / 'profile' / '.council'
        self.council.mkdir(parents=True)
        (self.council / 'manifest.json').write_text('{}')
        self.workspace = self.base / 'development space'
        self.workspace.mkdir()
    def resolve(self, workspace=None):
        from council.runtime_context import resolve_context
        return resolve_context(workspace or self.workspace, self.council)
    def test_explicit_workspace_never_depends_on_cwd_or_creates_memory(self):
        context = self.resolve()
        self.assertEqual(context.workspace_root, self.workspace.resolve())
        self.assertFalse(context.memory_root.exists())
    def test_metadata_workspace_resolution(self):
        from council.runtime_context import resolve_context
        (self.council/'installation.json').write_text(json.dumps({'workspaceRoot':str(self.workspace)}))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_context(council_root=self.council).workspace_root,self.workspace)
    def test_missing_workspace_fails_closed(self):
        from council.runtime_context import resolve_context
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): resolve_context(council_root=self.council)
    def test_profile_ancestor_and_private_source_rejected(self):
        for root in (self.base, self.council.parent, self.council):
            with self.subTest(root=root), self.assertRaises(ValueError): self.resolve(root)
    def test_private_profile_directories_are_not_workspaces(self):
        private=self.council.parent/'.codex'
        private.mkdir()
        with self.assertRaises(ValueError): self.resolve(private)

    def test_private_memory_override_cannot_escape(self):
        with patch.dict(os.environ, {'COUNCIL_MEMORY_ROOT':str(self.workspace)}):
            with self.assertRaises(ValueError): self.resolve()
    def test_file_paths_reject_absolute_and_traversal(self):
        from council.tools.file_tools import FileTools
        files=FileTools(self.resolve())
        for path in ('../secret',str(self.workspace/'absolute.txt')):
            with self.assertRaises(PermissionError): files.write_file(path,'no')
        files.write_file('nested/file.txt','yes')
        self.assertEqual(files.read_file('nested/file.txt'),'yes')
    def test_runner_literal_arguments_and_cwd(self):
        import sys
        from council.runner import SubprocessRunner
        runner=SubprocessRunner(self.resolve())
        code,out,err=runner.run([sys.executable,'-c','import os,sys;print(os.getcwd());print(sys.argv[1])',"literal '$() ; text"])
        self.assertEqual(code,0,err)
        self.assertIn(str(self.workspace),out)
        self.assertIn("literal '$() ; text",out)
        with self.assertRaises(PermissionError): runner.run([sys.executable,'-V'],cwd=self.base)

    def test_symlink_redirect_cannot_read_outside_workspace(self):
        import subprocess
        from council.tools.file_tools import FileTools
        outside=self.base/'outside'
        outside.mkdir()
        (outside/'secret.txt').write_text('private')
        link=self.workspace/'redirect'
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(PermissionError): FileTools(self.resolve()).read_file('redirect/secret.txt')
        with self.assertRaises(PermissionError):
            from council.runner import SubprocessRunner
            SubprocessRunner(self.resolve()).run(['cmd','/c','echo','no'],cwd=link)

    def test_registry_injects_workspace_and_scopes_architect(self):
        from council.tools.tool_registry import get_council_tools
        tools={tool.name:tool for tool in get_council_tools(context=self.resolve(),specialist='the-coder')}
        tools['write_workspace_file'].invoke({'rel_path':'sample.txt','content':'before'})
        tools['patch_workspace_file'].invoke({'rel_path':'sample.txt','old_string':'before','new_string':'after'})
        self.assertEqual(tools['read_workspace_file'].invoke({'rel_path':'sample.txt'}),'after')
        self.assertEqual([tool.name for tool in get_council_tools(context=self.resolve(),specialist='the-architect')],['read_workspace_file'])
        with self.assertRaises(PermissionError):
            tools['write_workspace_file'].invoke({'rel_path':'../private.txt','content':'blocked'})

    def test_memory_junction_cannot_redirect_private_state(self):
        import subprocess
        outside=self.base/'external memory'
        outside.mkdir()
        result=subprocess.run(['cmd','/c','mklink','/J',str(self.council/'memory'),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(ValueError): self.resolve()

    def test_specialist_name_escape_rejected(self):
        from council.specialists import SpecialistLoader
        skills=self.council/'skills'/'the-builder'
        skills.mkdir(parents=True)
        (skills/'SKILL.md').write_text('description: Builder\nactual instructions')
        loader=SpecialistLoader(context=self.resolve())
        self.assertEqual(loader.get_specialist('the-builder').description,'Builder')
        with self.assertRaises(ValueError): loader.get_specialist('../private')

    def test_context_environment_precedence_and_invalid_roots(self):
        from council.runtime_context import resolve_context,resolve_workspace_root
        other=self.base/'other'; other.mkdir()
        with patch.dict(os.environ,{'COUNCIL_ROOT':str(self.council),'COUNCIL_WORKSPACE_ROOT':str(other)}):
            self.assertEqual(resolve_workspace_root(),other)
            self.assertEqual(resolve_context(self.workspace).workspace_root,self.workspace)
        with self.assertRaises(ValueError): self.resolve(self.base/'missing')
        (self.council/'manifest.json').unlink()
        with self.assertRaises(ValueError): self.resolve()

    def test_file_slicing_missing_patch_and_repetition(self):
        from council.tools.file_tools import FileTools
        files=FileTools(context=self.resolve())
        with self.assertRaises(FileNotFoundError): files.read_file('missing.txt')
        self.assertFalse(files.patch_file('missing.txt','before','after'))
        files.write_file('lines.txt','one\ntwo\nthree')
        self.assertEqual(files.read_file('lines.txt',start_line=2,end_line=2),'two')
        self.assertFalse(files.patch_file('lines.txt','absent','after'))
        files.write_file('duplicate.txt','a a')
        self.assertFalse(files.patch_file('duplicate.txt','a','b'))
        repeating=FileTools(context=self.resolve())
        repeating.read_file('lines.txt'); repeating.read_file('lines.txt')
        with self.assertRaises(RuntimeError): repeating.read_file('lines.txt')

    def test_entire_specialist_root_cannot_redirect_outside_council(self):
        import subprocess
        from council.specialists import SpecialistLoader
        outside=self.base/'external trusted definitions'; outside.mkdir()
        package=outside/'the-builder'; package.mkdir()
        (package/'SKILL.md').write_text('description: Untrusted outside instructions')
        result=subprocess.run(['cmd','/c','mklink','/J',str(self.council/'skills'),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(PermissionError): SpecialistLoader(context=self.resolve())

    def test_specialist_discovery_missing_and_redirected_packages(self):
        import subprocess
        from council.specialists import SpecialistLoader
        loader=SpecialistLoader(context=self.resolve())
        self.assertEqual(loader.list_available_specialists(),[])
        self.assertIsNone(loader.get_specialist('the-missing'))
        skills=self.council/'skills'; skills.mkdir()
        (skills/'unrelated').mkdir()
        package=skills/'the-builder'; package.mkdir()
        (package/'SKILL.md').write_text('instructions without description')
        self.assertEqual(loader.list_available_specialists(),['the-builder'])
        self.assertEqual(loader.get_specialist('the-builder').description,'the-builder')
        with self.assertRaises(PermissionError): SpecialistLoader(self.workspace,context=self.resolve())
        outside=self.base/'external skills'; outside.mkdir()
        (outside/'SKILL.md').write_text('private')
        result=subprocess.run(['cmd','/c','mklink','/J',str(skills/'the-redirect'),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(PermissionError): loader.get_specialist('the-redirect')

    def test_registry_native_errors_test_results_and_gatekeeper_scoping(self):
        from council.tools.tool_registry import get_council_tools
        with patch.dict(os.environ,{'COUNCIL_ROOT':str(self.council),'COUNCIL_WORKSPACE_ROOT':str(self.workspace)}):
            tools={tool.name:tool for tool in get_council_tools()}
        result=tools['run_workspace_validator'].invoke({})
        self.assertFalse(result['passed'])
        self.assertIn('missing',result['error'].lower())
        with self.assertRaises(PermissionError): tools['run_deno_test'].invoke({'dir_path':'../outside'})
        with self.assertRaises(PermissionError): tools['run_dotnet_test'].invoke({'solution_or_project':'../outside.csproj'})
        self.assertFalse(tools['patch_workspace_file'].invoke({'rel_path':'missing','old_string':'a','new_string':'b'})['passed'])
        self.assertEqual(len(get_council_tools(context=self.resolve(),specialist='the-prover')),3)
        self.assertEqual(len(get_council_tools(context=self.resolve(),specialist='the-gatekeeper')),4)
        self.assertEqual(len(get_council_tools(context=self.resolve(),specialist='the-codex')),1)

    def test_public_path_resolution_rejects_absolute_and_redirected_paths(self):
        import subprocess
        from council.tools.file_tools import FileTools
        context=self.resolve()
        self.assertEqual(FileTools(context=context).resolve_path('nested/file.txt'),self.workspace/'nested'/'file.txt')
        with self.assertRaises(PermissionError): context.workspace_path(str(self.workspace/'file.txt'))
        outside=self.base/'redirected path'; outside.mkdir()
        result=subprocess.run(['cmd','/c','mklink','/J',str(self.workspace/'redirect'),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(PermissionError): context.workspace_path('redirect/secret.txt')

    def test_specialist_instruction_symlink_cannot_escape_canonical_packages(self):
        import subprocess
        from council.specialists import SpecialistLoader
        package=self.council/'skills'/'the-builder'; package.mkdir(parents=True)
        outside=self.base/'external instructions.md'; outside.write_text('private instructions')
        result=subprocess.run(['cmd','/c','mklink',str(package/'SKILL.md'),str(outside)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(PermissionError): SpecialistLoader(context=self.resolve()).get_specialist('the-builder')

    def test_specialist_representation_identifies_persona_without_dumping_instructions(self):
        from council.specialists import SpecialistPackage
        specialist=SpecialistPackage('the-builder','Builder','private full instructions','[THE BUILDER]')
        self.assertIn('[THE BUILDER]',repr(specialist))
        self.assertNotIn('private full instructions',repr(specialist))

if __name__=='__main__': unittest.main()
