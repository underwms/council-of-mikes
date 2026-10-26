"""Plan producer/consumer contract with real package files and no provider calls."""
import json
import os
import subprocess

import pytest
from test_engine_integration import lifecycle
from test_format_recovery import execute, transport

NAMES = ['the-architect', 'the-builder', 'the-coder', 'the-codex', 'the-coordinator',
         'the-curator', 'the-gatekeeper', 'the-pipelineer', 'the-prover', 'the-provisioner',
         'the-purifier', 'the-relay', 'the-renderer', 'the-sentinel', 'the-watcher']
SECRET = 'PRIVATE_UNTRUSTED_SPECIALIST_SENTINEL'


def validate(fixture, plan=None, native=True):
    from council import plan_validation
    return plan_validation.validate_plan(plan or fixture.plan, fixture.context, native_coding=native)


def install_catalog(fixture):
    root = fixture.context.council_root
    (root/'manifest.json').write_text(json.dumps({'specialists': NAMES}))
    for name in NAMES:
        package = root/'skills'/name
        package.mkdir(parents=True, exist_ok=True)
        (package/'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic specialist\n---\nInstructions')


def test_every_known_display_call_sign_maps_on_copy_and_canonical_values_stay(lifecycle):
    install_catalog(lifecycle)
    for name in NAMES:
        plan = lifecycle.plan.model_copy(deep=True)
        plan.tasks[0].specialist = '[' + name.upper().replace('-', ' ') + ']'
        validated = validate(lifecycle, plan)
        assert validated.tasks[0].specialist == name
        assert plan.tasks[0].specialist.startswith('['), 'Do not mutate the input plan'
        assert validate(lifecycle, validated).model_dump() == validated.model_dump()


@pytest.mark.parametrize('name', [SECRET, '[THE UNKNOWN]', '[the coder]', 'THE CODER',
                                  ' [THE CODER]', '[THE CODER] ', 'the_coder', '../the-coder', 'brainstorming'])
def test_unknown_near_match_and_path_names_are_rejected_without_echo(lifecycle, name):
    lifecycle.plan.tasks[0].specialist = name
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    from council.diagnostics import describe
    detail = describe(caught.value)
    assert detail['code'] == 'PLAN_SPECIALIST_INVALID'
    assert detail['task_index'] == 1
    assert SECRET not in json.dumps(detail) + str(caught.value)


def test_missing_package_is_distinct_from_unknown_identifier(lifecycle):
    (lifecycle.context.council_root/'skills/the-coder/SKILL.md').unlink()
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    assert getattr(caught.value, 'code', None) == 'PLAN_SPECIALIST_UNAVAILABLE'


def test_declared_catalog_is_authoritative_and_malformed_catalog_is_safe(lifecycle):
    manifest = lifecycle.context.council_root/'manifest.json'
    (lifecycle.context.council_root/'skills/brainstorming').mkdir()
    (lifecycle.context.council_root/'skills/brainstorming/SKILL.md').write_text('workflow')
    lifecycle.plan.tasks[0].specialist = 'brainstorming'
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    assert getattr(caught.value, 'code', None) == 'PLAN_SPECIALIST_INVALID'
    for value in ([], ['../' + SECRET], ['the-coder', 'the-coder'], SECRET):
        manifest.write_text(json.dumps({'specialists': value}))
        with pytest.raises((ValueError, RuntimeError)) as caught:
            validate(lifecycle)
        assert getattr(caught.value, 'code', None) == 'PLAN_CATALOG_INVALID'
        assert SECRET not in str(caught.value)


@pytest.mark.parametrize('field,value,code', [
    ('test_commands', [], 'PLAN_VERIFICATION_INVALID'),
    ('test_commands', [[]], 'PLAN_VERIFICATION_INVALID'),
    ('test_commands', [['']], 'PLAN_VERIFICATION_INVALID'),
    ('working_directory', '../outside', 'PLAN_WORKING_DIRECTORY_INVALID'),
    ('working_directory', 'missing-directory', 'PLAN_WORKING_DIRECTORY_INVALID'),
    ('target_files', ['../outside'], 'PLAN_TARGET_PATH_INVALID'),
])
def test_plan_preflight_failure_codes_are_specific(lifecycle, field, value, code):
    setattr(lifecycle.plan.tasks[0], field, value)
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    from council.diagnostics import describe
    assert describe(caught.value)['code'] == code
    assert describe(caught.value)['task_index'] == 1


def test_multi_repository_workspace_rejects_root_native_edit_scope(lifecycle):
    for name in ('service-a', 'service-b'):
        (lifecycle.workspace/name/'.git').mkdir(parents=True)
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    assert getattr(caught.value, 'code', None) == 'PLAN_WORKING_DIRECTORY_INVALID'
    assert getattr(caught.value, 'task_index', None) == 1


def test_generated_call_sign_is_normalized_before_gate_one(lifecycle, transport):
    lifecycle.plan.tasks[0].specialist = '[THE CODER]'
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    result, saved = execute(lifecycle, transport.model)
    assert result['__interrupt__'][0].value['gate'] == 'GATE_1_PLAN_APPROVAL'
    assert saved['plan']['tasks'][0]['specialist'] == 'the-coder'
    assert result['__interrupt__'][0].value['plan'] == saved['plan']
    assert saved['modified_files'] == [] and saved['test_results'] == []
    assert all(call['role'] == 'orchestrator' for call in saved['model_calls'])


def test_failure_checkpoint_and_events_have_fixed_code_and_task_index(lifecycle, transport, capsys):
    from council.diagnostics import DiagnosticSession
    lifecycle.plan.tasks[1].specialist = SECRET
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    with DiagnosticSession(lifecycle.state.run_id, lifecycle.context.memory_root):
        result, saved = execute(lifecycle, transport.model)
    assert result['status'] == 'FAILED'
    assert saved['diagnostic']['code'] == 'PLAN_SPECIALIST_INVALID'
    assert saved['diagnostic']['task_index'] == 2
    output = capsys.readouterr().err
    assert SECRET not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert any(r.get('task_index') == 2 and r.get('code') == 'PLAN_SPECIALIST_INVALID' for r in records)


def test_redirected_package_remains_rejected(lifecycle, monkeypatch):
    if os.name == 'nt':
        package = lifecycle.context.council_root/'skills/the-coder'
        assert package.resolve().is_relative_to(lifecycle.context.council_root)
        (package/'SKILL.md').unlink()
        package.rmdir()
        outside = lifecycle.workspace/'outside-package'
        outside.mkdir()
        (outside/'SKILL.md').write_text(SECRET)
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(package), str(outside)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    else:
        def denied(*args):
            raise PermissionError(SECRET)
        monkeypatch.setattr('council.plan_validation.SpecialistLoader.get_specialist', denied)
    with pytest.raises(ValueError) as caught:
        validate(lifecycle)
    assert caught.value.code == 'PLAN_SPECIALIST_UNAVAILABLE'
    assert SECRET not in str(caught.value)


def test_dryrun_normalizes_assignments_and_supplies_canonical_catalog(lifecycle, transport, monkeypatch, capsys):
    from council.cli import main
    lifecycle.plan.tasks[0].specialist = '[THE CODER]'
    transport.responses.extend(['{"content":"Done.","tool_calls":[]}', lifecycle.plan.model_dump_json()])
    monkeypatch.setattr('council.graph.get_llm_for_role', lambda *args, **kwargs: transport.model)
    monkeypatch.setattr('council.cli.preflight_credentials', lambda _: {'gpt': True, 'gemini': True})
    assert main(['--workspace', str(lifecycle.workspace), '--council-root', str(lifecycle.context.council_root),
                 '--dry-run', 'Synthetic specialist fixture']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['plan']['tasks'][0]['specialist'] == 'the-coder'
    assert 'canonical specialist package identifiers' in json.dumps(transport.requests[0])
    assert not list(lifecycle.workspace.glob('target-*.txt'))


def test_task_index_diagnostic_is_bounded_and_ignores_untrusted_attributes():
    from council.diagnostics import DiagnosticValueError, describe
    for invalid in (True, 0, -1, 100001, SECRET):
        assert 'task_index' not in describe(DiagnosticValueError('PLAN_SPECIALIST_INVALID', task_index=invalid))
    unknown = ValueError(SECRET)
    unknown.task_index = 2
    assert 'task_index' not in describe(unknown)


def test_legacy_directory_rule_and_invalid_catalog_io_are_preserved(lifecycle, monkeypatch):
    lifecycle.plan.tasks[0].working_directory = 'future-directory'
    assert validate(lifecycle, native=False).tasks[0].working_directory == 'future-directory'
    def unreadable(*args):
        raise PermissionError(SECRET)
    monkeypatch.setattr('council.plan_validation._read', unreadable)
    with pytest.raises(RuntimeError) as caught:
        validate(lifecycle)
    assert caught.value.code == 'PLAN_CATALOG_INVALID'
    assert SECRET not in str(caught.value)
