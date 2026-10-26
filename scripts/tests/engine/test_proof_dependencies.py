"""Actual project topology, shared configuration and conservative fallback."""
import pytest
from council.state import TaskItem


def layout(fixture):
    root = fixture.workspace
    for name in ('tests', 'app', 'shared', 'unrelated'):
        (root/name).mkdir()
        (root/name/'code.cs').write_text(name)
    (root/'tests/tests.csproj').write_text('<Project><ItemGroup><ProjectReference Include="../app/app.csproj" /></ItemGroup></Project>')
    (root/'app/app.csproj').write_text('<Project><ItemGroup><ProjectReference Include="../shared/shared.csproj" /></ItemGroup></Project>')
    (root/'shared/shared.csproj').write_text('<Project />')
    (root/'Directory.Build.props').write_text('<Project />')
    return TaskItem(id='test', specialist='the-prover', description='Verify application',
        working_directory='tests', target_files=['tests/code.cs'],
        test_commands=[['dotnet', 'test', 'tests.csproj']],
        proof_scope={'version':1, 'project':'tests/tests.csproj', 'runtime_mutable':False})


def test_supported_closure_does_not_inventory_unrelated_workspace(graph_workspace, monkeypatch):
    import council.proof_dependencies as dependencies
    task = layout(graph_workspace)
    original = dependencies.snapshot
    seen = []
    def scoped(context, relative, **kwargs):
        seen.append(relative)
        assert relative != '.', 'supported closure must be discovered before inventory'
        return original(context, relative, **kwargs)
    monkeypatch.setattr(dependencies, 'snapshot', scoped)
    result = dependencies.resolve(task, graph_workspace.context)
    assert 'shared/code.cs' in result.hashes
    assert 'unrelated/code.cs' not in result.hashes
    assert seen


def test_unrelated_growth_exceeds_old_traversal_bound_only(graph_workspace, monkeypatch):
    from council import proof_dependencies, native_inventory
    from council.tools import discovery
    from council.diagnostics import DiagnosticRuntimeError
    task = layout(graph_workspace)
    for index in range(100):
        (graph_workspace.workspace/'unrelated'/f'{index}.cs').write_text('unrelated')
    monkeypatch.setattr(discovery, 'MAX_VISITED_ENTRIES', 50)
    with pytest.raises(DiagnosticRuntimeError, match='bounded budget'):
        native_inventory.snapshot(graph_workspace.context, '.')
    assert proof_dependencies.resolve(task, graph_workspace.context).method == 'dotnet_project_closure_v2'


def test_closure_shares_traversal_budget_across_project_roots(graph_workspace, monkeypatch):
    from council import proof_dependencies
    from council.tools import discovery
    from council.diagnostics import DiagnosticRuntimeError
    task = layout(graph_workspace)
    for name in ('tests', 'app', 'shared'):
        for index in range(8):
            (graph_workspace.workspace/name/f'extra-{index}.cs').write_text('source')
    monkeypatch.setattr(discovery, 'MAX_VISITED_ENTRIES', 30)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        proof_dependencies.resolve(task, graph_workspace.context)
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'


def test_closure_shares_byte_budget_across_roots_and_inherited_metadata(graph_workspace, monkeypatch):
    from council import proof_dependencies, native_inventory
    from council.diagnostics import DiagnosticRuntimeError
    task = layout(graph_workspace)
    relevant = [p for name in ('tests', 'app', 'shared') for p in (graph_workspace.workspace/name).iterdir()]
    total = sum(p.stat().st_size for p in relevant) + (graph_workspace.workspace/'Directory.Build.props').stat().st_size
    monkeypatch.setattr(native_inventory, 'MAX_SOURCE_BYTES', total - 1)
    with pytest.raises(DiagnosticRuntimeError) as caught:
        proof_dependencies.resolve(task, graph_workspace.context)
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'


@pytest.mark.parametrize('arguments', [
    ['test', 'tests.csproj', '--filter'], ['test', '--project'],
    ['test', '--nologo'], ['test', 'tests.csproj', '-p:CustomInput=outside'],
])
def test_unresolved_command_inputs_cannot_borrow_narrow_closure(graph_workspace, arguments):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    task.test_commands = [['dotnet', *arguments]]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'workspace_fallback_v1'
    assert value.runtime_mutable
    assert 'unrelated/code.cs' in value.hashes


def test_discovery_metadata_race_cannot_produce_narrow_receipt(graph_workspace, monkeypatch):
    from council import proof_dependencies as dependencies
    task = layout(graph_workspace)
    original = dependencies.snapshot
    def changed(context, relative, **kwargs):
        (graph_workspace.workspace/'app/app.csproj').write_text('<Project />')
        return original(context, relative, **kwargs)
    monkeypatch.setattr(dependencies, 'snapshot', changed)
    assert dependencies.resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_nested_project_and_declared_external_input_are_both_fingerprinted(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    nested = graph_workspace.workspace/'shared/nested'
    nested.mkdir()
    (nested/'nested.csproj').write_text('<Project />')
    (nested/'code.cs').write_text('nested')
    (graph_workspace.workspace/'shared/shared.csproj').write_text(
        '<Project><ItemGroup><ProjectReference Include="nested/nested.csproj" /></ItemGroup></Project>')
    (graph_workspace.workspace/'generated.cs').write_text('consumed input outside project roots')
    task.proof_scope.generated_inputs = ['generated.cs']
    value = resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert {'shared/nested/code.cs', 'generated.cs'} <= value.hashes.keys()
    (graph_workspace.workspace/'generated.cs').write_text('changed consumed input')
    assert resolve(task, graph_workspace.context).hashes != value.hashes


def test_incomplete_project_inventory_cannot_produce_narrow_receipt(graph_workspace, monkeypatch):
    from council import proof_dependencies as dependencies
    task = layout(graph_workspace)
    original = dependencies.snapshot
    def missing_project(context, relative, **kwargs):
        result = original(context, relative, **kwargs)
        if relative != '.':
            result.pop('app/app.csproj', None)
        return result
    monkeypatch.setattr(dependencies, 'snapshot', missing_project)
    assert dependencies.resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_bounded_metadata_reader_rejects_entities_without_tracking_hashes(graph_workspace):
    from council.proof_dependencies import _xml
    layout(graph_workspace)
    assert _xml(graph_workspace.context, 'shared/shared.csproj').tag == 'Project'
    (graph_workspace.workspace/'shared/shared.csproj').write_text(
        '<!DOCTYPE Project [<!ENTITY input SYSTEM "private">]><Project />')
    with pytest.raises(ValueError, match='Unsupported project metadata'):
        _xml(graph_workspace.context, 'shared/shared.csproj')


def test_exhausted_shared_traversal_budget_cannot_restart_at_another_root(graph_workspace):
    from council.native_inventory import InventoryBudget, snapshot
    from council.tools.discovery import MAX_VISITED_ENTRIES
    from council.diagnostics import DiagnosticRuntimeError
    layout(graph_workspace)
    budget = InventoryBudget(visited_entries=[MAX_VISITED_ENTRIES])
    with pytest.raises(DiagnosticRuntimeError) as caught:
        snapshot(graph_workspace.context, 'tests', budget=budget)
    assert caught.value.code == 'NATIVE_INVENTORY_LIMIT'


@pytest.mark.parametrize('metadata', [
    '<Project><Import Project="custom.targets" /></Project>',
    '<Project><ItemGroup><Compile Include="elsewhere.cs" /></ItemGroup></Project>',
    '<Project><PropertyGroup Condition="$(Unknown)"><Flag>true</Flag></PropertyGroup></Project>',
])
def test_inherited_metadata_with_unsupported_inputs_remains_conservative(graph_workspace, metadata):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    (graph_workspace.workspace/'Directory.Build.props').write_text(metadata)
    value = resolve(task, graph_workspace.context)
    assert value.method == 'workspace_fallback_v1'
    assert value.runtime_mutable
    assert 'unrelated/code.cs' in value.hashes


def test_all_explicit_command_projects_contribute_inputs(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    (graph_workspace.workspace/'tools').mkdir()
    (graph_workspace.workspace/'tools/tool.csproj').write_text('<Project />')
    (graph_workspace.workspace/'tools/tool.cs').write_text('independent input')
    task.test_commands = [
        ['dotnet', 'restore', '../app/app.csproj'],
        ['dotnet', 'build', '../tools/tool.csproj', '--no-restore'],
        ['dotnet', 'test', '--project', 'tests.csproj', '--filter', 'FullyQualifiedName~Unit'],
    ]
    value = resolve(task, graph_workspace.context)
    assert value.method == 'dotnet_project_closure_v2'
    assert {'app/code.cs', 'shared/code.cs', 'tests/code.cs', 'tools/tool.cs'} <= value.hashes.keys()
    assert 'unrelated/code.cs' not in value.hashes


def test_unrelated_project_preserves_but_transitive_source_invalidates(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    first = resolve(task, graph_workspace.context)
    assert first.method == 'dotnet_project_closure_v2'
    (graph_workspace.workspace/'unrelated/code.cs').write_text('irrelevant edit')
    assert resolve(task, graph_workspace.context) == first
    (graph_workspace.workspace/'shared/code.cs').write_text('shared edit')
    assert resolve(task, graph_workspace.context).hashes != first.hashes


@pytest.mark.parametrize('path', ['Directory.Build.props', 'global.json', 'tests/new.cs', 'shared/new.cs'])
def test_config_and_new_inputs_invalidate(graph_workspace, path):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    first = resolve(task, graph_workspace.context)
    (graph_workspace.workspace/path).write_text('changed')
    assert resolve(task, graph_workspace.context).hashes != first.hashes


def test_dependency_addition_and_removal_change_scope(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    first = resolve(task, graph_workspace.context)
    (graph_workspace.workspace/'app/app.csproj').write_text('<Project />')
    second = resolve(task, graph_workspace.context)
    assert second.hashes != first.hashes
    assert 'shared/code.cs' not in second.hashes


def test_corrupt_and_unsupported_metadata_use_broad_scope(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    (graph_workspace.workspace/'tests/tests.csproj').write_text('<Project><Import Project="$(Unknown)/custom.targets" /></Project>')
    value = resolve(task, graph_workspace.context)
    assert value.method == 'workspace_fallback_v1'
    assert 'unrelated/code.cs' in value.hashes
    (graph_workspace.workspace/'tests/tests.csproj').write_text('broken XML')
    assert resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_generated_consumed_input_is_not_treated_as_incidental_output(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    generated = graph_workspace.workspace/'tests/generated.cs'
    generated.write_text('generated source')
    task.proof_scope.generated_inputs = ['tests/generated.cs']
    first = resolve(task, graph_workspace.context)
    (graph_workspace.workspace/'tests/coverage').mkdir()
    (graph_workspace.workspace/'tests/coverage/report.txt').write_text('output')
    assert resolve(task, graph_workspace.context) == first
    generated.write_text('new generated source')
    assert resolve(task, graph_workspace.context) != first


def test_new_scope_does_not_change_legacy_plan_identity(graph_workspace):
    from council.plan_review import plan_digest
    import hashlib, json
    plan = graph_workspace.plan
    old = plan.model_dump(mode='json')
    old.pop('contract_changes')
    old.pop('quality_gates', None)
    old.pop('baseline_challenges', None)
    for task in old['tasks']:
        task.pop('status'); task.pop('kind'); task.pop('readiness_for')
        task.pop('verification_phase'); task.pop('red_verification')
        task.pop('proof_scope', None)
        task.pop('delivery_stage', None)
    assert plan_digest(plan) == hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def test_receipt_admission_and_final_boundary_use_common_dependency_identity(graph_workspace):
    from council.graph_integrity import record_execution, matching_execution
    from council.state import CouncilState, MultiSpecialistPlan, TestExecutionResult
    from council.plan_review import plan_digest
    task = layout(graph_workspace)
    state = CouncilState(run_id='proof', task_input='Test', graph_integrity_policy_version=2,
        plan=MultiSpecialistPlan(title='Proof', architecture_summary='Test', tasks=[task]))
    state.accepted_plan_sha256 = plan_digest(state.plan)
    result = TestExecutionResult(command='dotnet', passed=True, exit_code=0, expectation_met=True)
    record = record_execution(state, task, 1, result, graph_workspace.context)
    (graph_workspace.workspace/'unrelated/code.cs').write_text('unrelated')
    assert matching_execution(state, task, 1, graph_workspace.context).id == record.id
    (graph_workspace.workspace/'shared/code.cs').write_text('relevant edit')
    assert matching_execution(state, task, 1, graph_workspace.context) is None


def test_mutable_fixture_receipt_cannot_cross_later_boundary(graph_workspace):
    from council.graph_integrity import record_execution, matching_execution
    from council.state import CouncilState, MultiSpecialistPlan, TestExecutionResult
    from council.plan_review import plan_digest
    task = layout(graph_workspace)
    task.proof_scope.runtime_mutable = True
    state = CouncilState(run_id='proof', task_input='Test', graph_integrity_policy_version=2,
        plan=MultiSpecialistPlan(title='Proof', architecture_summary='Test', tasks=[task]))
    state.accepted_plan_sha256 = plan_digest(state.plan)
    result = TestExecutionResult(command='dotnet', passed=True, exit_code=0, expectation_met=True)
    record_execution(state, task, 1, result, graph_workspace.context)
    assert matching_execution(state, task, 1, graph_workspace.context) is not None
    state.status = 'FINAL_REVIEW'
    assert matching_execution(state, task, 1, graph_workspace.context) is None


def test_other_command_cannot_borrow_a_project_scope(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    task.test_commands = [['python', 'external-verifier.py']]
    assert resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_condition_on_reference_group_prevents_narrow_scope(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    (graph_workspace.workspace/'tests/tests.csproj').write_text(
        '<Project><ItemGroup Condition="$(Configuration)"><ProjectReference Include="../app/app.csproj" /></ItemGroup></Project>')
    assert resolve(task, graph_workspace.context).method == 'workspace_fallback_v1'


def test_model_cannot_declare_unknown_test_runtime_immutable(graph_workspace):
    from council.proof_dependencies import resolve
    task = layout(graph_workspace)
    assert task.proof_scope.runtime_mutable is False
    assert resolve(task,graph_workspace.context).runtime_mutable is True


def test_dependency_budget_reserves_all_receipt_metadata_keys(graph_workspace):
    from council.graph_integrity import source_hashes
    from council.diagnostics import DiagnosticRuntimeError
    task=layout(graph_workspace)
    for index in range(503):
        (graph_workspace.workspace/'tests'/f'extra-{index}.cs').write_text('source')
    with pytest.raises(DiagnosticRuntimeError) as caught:
        source_hashes(task,graph_workspace.context)
    assert caught.value.code=='NATIVE_INVENTORY_LIMIT'


def test_readiness_environment_commands_do_not_claim_product_closure(graph_workspace,monkeypatch):
    from council.graph_integrity import source_hashes,digest
    from council import proof_dependencies
    task=layout(graph_workspace);task.kind='readiness'
    task.test_commands=[['dotnet','restore','tests.csproj'],['docker','info'],
        ['dotnet','run','--project','tests.csproj','--','--filter-class','*PersistenceReadinessTests']]
    def forbidden(*args,**kwargs):raise AssertionError('Readiness cannot claim closed product dependency proof')
    monkeypatch.setattr(proof_dependencies,'resolve',forbidden)
    values=source_hashes(task,graph_workspace.context)
    assert values['@proof:method']==digest('readiness_observation_v1')
    assert values['@proof:runtime_mutable']==digest(True)
    assert {'tests/code.cs','tests/tests.csproj'}<=values.keys()
    assert 'unrelated/code.cs' not in values


def test_readiness_observation_retains_explicit_input_limits(graph_workspace,monkeypatch):
    from council.graph_integrity import source_hashes
    from council import native_inventory
    from council.diagnostics import DiagnosticRuntimeError
    task=layout(graph_workspace);task.kind='readiness'
    monkeypatch.setattr(native_inventory,'MAX_SOURCE_BYTES',1)
    with pytest.raises(DiagnosticRuntimeError) as caught:source_hashes(task,graph_workspace.context)
    assert caught.value.code=='NATIVE_INVENTORY_LIMIT'


@pytest.mark.parametrize('input_kind',['missing','excluded','permission'])
def test_readiness_explicit_inputs_preserve_read_guards(graph_workspace,monkeypatch,input_kind):
    from council.graph_integrity import source_hashes
    from council.tools import discovery
    task=layout(graph_workspace);task.kind='readiness'
    task.proof_scope.generated_inputs=['missing.cs' if input_kind=='missing' else '.env' if input_kind=='excluded' else 'tests/code.cs']
    if input_kind=='missing':
        assert source_hashes(task,graph_workspace.context)['missing.cs'] is None
        return
    if input_kind=='permission':
        def denied(*args,**kwargs):raise PermissionError('PRIVATE_PERMISSION_CANARY')
        monkeypatch.setattr(discovery,'validate_read_path',denied)
    with pytest.raises(PermissionError):source_hashes(task,graph_workspace.context)


def test_readiness_observation_still_limits_receipt_size(graph_workspace):
    from council.graph_integrity import source_hashes
    from council.diagnostics import DiagnosticRuntimeError
    task=layout(graph_workspace);task.kind='readiness'
    for index in range(510):(graph_workspace.workspace/'tests'/str(index)).write_text('probe')
    task.test_commands=[['python',*[str(i) for i in range(510)]]]
    with pytest.raises(DiagnosticRuntimeError) as caught:source_hashes(task,graph_workspace.context)
    assert caught.value.code=='NATIVE_INVENTORY_LIMIT'
