import json

import pytest
from test_engine_integration import lifecycle

from council.runtime_context import RuntimeContext


@pytest.fixture
def context(tmp_path):
    council = tmp_path / 'profile' / '.council'
    council.mkdir(parents=True)
    (council / 'manifest.json').write_text('{}')
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return RuntimeContext(council, workspace, council / 'memory' / 'engine')


def put(root, name, content):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')


def test_loads_shared_profile_and_selected_project_without_private_memory(context):
    from council.prompt_context import load_guidance
    root = context.council_root
    put(root, 'manifest.json', json.dumps({'default_profile': 'test', 'profiles': {'test': 'profiles/test/profile.json'}}))
    put(root, 'instructions/shared.md', 'shared instruction')
    put(root, 'rules/global.md', 'global instruction')
    put(root, 'profiles/test/profile.json', json.dumps({'rules': 'rules.md', 'corporate_rules': 'corporate.md'}))
    put(root, 'profiles/test/rules.md', 'profile instruction')
    put(root, 'profiles/test/corporate.md', 'corporate instruction')
    put(root, 'project-instructions/orders.md', 'orders instruction')
    put(root, 'project-instructions/other.md', 'unrelated instruction')
    put(root, 'memory/active_handoff.md', 'private history')
    put(context.workspace_root, 'orders/AGENTS.md', 'local project guidance')
    result = load_guidance(context, project_names=['orders/src'])
    for text in ('shared instruction', 'global instruction', 'profile instruction', 'corporate instruction', 'orders instruction', 'local project guidance'):
        assert text in result
    assert 'private history' not in result
    assert 'unrelated instruction' not in result


def test_minimal_manifest_and_missing_optional_documents_are_supported(context):
    from council.prompt_context import load_guidance
    assert isinstance(load_guidance(context), str)


def test_manifest_cannot_request_private_or_external_documents(context):
    from council.prompt_context import load_guidance
    for path in ('../outside.md', 'memory/private.md', '.agents/private.md', '.ssh/private.md'):
        put(context.council_root, 'manifest.json', json.dumps({'paths': {'shared': path}}))
        with pytest.raises(PermissionError):
            load_guidance(context)


def test_oversized_guidance_fails_explicitly(context):
    from council.prompt_context import load_guidance
    put(context.council_root, 'instructions/shared.md', 'x' * 100_000)
    with pytest.raises(ValueError, match='limit'):
        load_guidance(context)


def test_project_paths_cannot_escape_workspace(context):
    from council.prompt_context import load_guidance
    with pytest.raises(PermissionError):
        load_guidance(context, project_names=['../private'])


def test_total_guidance_budget_is_enforced(context):
    from council.prompt_context import load_guidance
    for path in ('instructions/shared.md', 'rules/global.md', 'rules/workspace.md'):
        put(context.council_root, path, 'x' * 65_000)
    put(context.workspace_root, 'AGENTS.md', 'x' * 5_000)
    with pytest.raises(ValueError, match='Combined guidance exceeds byte limit'):
        load_guidance(context)


def test_planner_cannot_write_before_first_approval(lifecycle):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from test_engine_integration import ScriptedProvider, open_graph, build

    class HostilePlanner(ScriptedProvider):
        def bind_tools(self, offered):
            assert {tool.name for tool in offered} == {
                'read_workspace_file', 'list_workspace_files', 'search_workspace_text'}
            return SimpleNamespace(invoke=lambda messages: AIMessage(content='', tool_calls=[{
                'name': 'write_workspace_file', 'args': {'rel_path': 'unauthorized.txt', 'content': 'bad'},
                'id': 'malicious-write', 'type': 'tool_call'}]))

    provider = HostilePlanner(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        result = build(lifecycle, saver, provider).invoke(lifecycle.state.model_dump(), lifecycle.config)
    assert result['status'] == 'FAILED'
    assert not result.get('__interrupt__')
    assert not (lifecycle.workspace / 'unauthorized.txt').exists()
    assert result['tool_call_history'] == []


def test_planner_read_response_is_bounded(context):
    from council.tools.tool_registry import get_council_tools
    reader = get_council_tools(specialist='the-architect', context=context)[0]
    put(context.workspace_root, 'large.txt', 'x' * 262_145)
    with pytest.raises(ValueError, match='limit'):
        reader.invoke({'rel_path': 'large.txt'})
    put(context.workspace_root, 'small.txt', 'x' * 262_144)
    assert len(reader.invoke({'rel_path': 'small.txt'})) <= 262_144


def test_planner_reader_rejects_private_files(context):
    from council.tools.tool_registry import get_council_tools
    reader = get_council_tools(specialist='the-architect', context=context)[0]
    put(context.workspace_root, 'repo/.env', 'private credential')
    with pytest.raises(PermissionError):
        reader.invoke({'rel_path': 'repo/.env'})


def test_worker_receives_selected_project_guidance(lifecycle):
    from langgraph.types import Command
    from test_engine_integration import ScriptedProvider, open_graph, build, assert_gate
    put(lifecycle.context.council_root, 'instructions/shared.md', 'SHARED_RULE')
    put(lifecycle.context.council_root, 'project-instructions/repo.md', 'REPO_RULE')
    put(lifecycle.workspace, 'repo/AGENTS.md', 'LOCAL_REPO_RULE')
    lifecycle.plan.tasks[0].target_files = ['repo/target.txt']
    observed = []

    class CapturingProvider(ScriptedProvider):
        def invoke(self, messages):
            if not isinstance(messages, str):
                observed.append(messages[0]['content'])
            return super().invoke(messages)

    provider = CapturingProvider(lifecycle.plan)
    with open_graph(lifecycle, provider) as saver:
        graph = build(lifecycle, saver, provider)
        assert_gate(graph.invoke(lifecycle.state.model_dump(), lifecycle.config), 'GATE_1_PLAN_APPROVAL')
        graph.invoke(Command(resume={'approved': True}), lifecycle.config)
    assert any(all(rule in prompt for rule in ('SHARED_RULE', 'REPO_RULE', 'LOCAL_REPO_RULE')) for prompt in observed)
