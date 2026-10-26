"""The current fixture must match fresh CLI startup, independently of defaults."""

from types import SimpleNamespace

from council import cli
from council.config import RunModelConfiguration

from graph_fixtures import CURRENT_AUTONOMOUS_POLICIES


def test_current_fixture_matches_state_created_by_fresh_autonomous_cli(current_autonomous_run, monkeypatch):
    run = current_autonomous_run
    captured = {}

    def invoke(state, configuration):
        captured.update(state)
        return {**state, 'status': 'FAILED', 'error': 'Synthetic startup capture'}

    monkeypatch.setattr(cli, 'build_council_graph', lambda **kwargs: SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(cli, 'resolve_model_configuration', lambda **kwargs:
        RunModelConfiguration.model_validate(run.fixture.state.model_configuration))
    monkeypatch.setattr(cli, 'credentials_available', lambda configuration: True)
    monkeypatch.setattr(cli, 'emit', lambda payload: None)
    code = cli.run_council_task(prompt='Capture fresh policy without executing tasks',
        workspace_root=run.fixture.workspace, council_root=run.fixture.context.council_root,
        no_input=True, viewer=False)

    assert code == 1  # The graph boundary intentionally reports failure after capture.
    assert captured['approval_policy'] == run.state['approval_policy'] == 'autonomous'
    assert captured['auto_approve'] is run.state['auto_approve'] is False
    assert captured['max_steps'] == run.state['max_steps'] == 400
    for field, expected in CURRENT_AUTONOMOUS_POLICIES.items():
        assert captured[field] == run.state[field] == expected, field
    assert run.provider.attempts == {}, 'Startup capture must not dispatch fixture work'
