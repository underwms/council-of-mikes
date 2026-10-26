"""Load the active source explicitly, including under Python isolated mode."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from graph_fixtures import (  # noqa: E402 — source root must precede Council imports.
    current_autonomous_run,
    graph_workspace,
    legacy_lifecycle,
    legacy_monolithic_run,
    lifecycle,
)


@pytest.fixture(autouse=True)
def narration_requires_an_explicit_test_opt_in(monkeypatch):
    """Regression tests never launch background provider calls by default."""
    monkeypatch.setenv('COUNCIL_NARRATION_ENABLED', '0')


def pytest_configure(config):
    config.addinivalue_line('markers', 'current_policy: uses the complete fresh autonomous policy fixture')
    config.addinivalue_line('markers', 'legacy_policy: uses a version-one or monolithic compatibility fixture')


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        fixtures = set(item.fixturenames)
        if 'current_autonomous_run' in fixtures:
            item.add_marker(pytest.mark.current_policy)
        elif fixtures & {'lifecycle', 'legacy_lifecycle', 'legacy_monolithic_run'}:
            item.add_marker(pytest.mark.legacy_policy)
