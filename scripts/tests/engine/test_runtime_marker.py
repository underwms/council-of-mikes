"""Installed metadata, failed checks and historical markers remain distinguishable."""
import json
import pytest


def test_publish_uses_actual_version_preserves_fields_and_is_atomic(tmp_path):
    from council.runtime_marker import publish, inspect_marker
    path = tmp_path/'council-runtime.json'
    path.write_text(json.dumps({'sourceHash':'old','custom':'retained','packageVersion':'0.2.40'}))
    publish(path, {'sourceHash':'new','wheelHash':'actual'}, expected='0.2.43',
        installed='0.2.43', checks_passed=True)
    result = json.loads(path.read_text())
    assert result['packageVersion']=='0.2.43'
    assert result['custom']=='retained'
    assert inspect_marker(path,expected='0.2.43',installed='0.2.43')['status']=='verified'
    publish(path, {},expected='0.2.44',installed='0.2.44',checks_passed=True)
    assert json.loads(path.read_text())['packageVersion']=='0.2.44'
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('checks,installed',[(False,'0.2.43'),(True,'0.2.42'),(True,None)])
def test_failed_check_or_mismatch_cannot_publish_success(tmp_path,checks,installed):
    from council.runtime_marker import publish
    path = tmp_path/'marker.json'
    original = b'{"packageVersion":"0.2.40","custom":true}'
    path.write_bytes(original)
    with pytest.raises(ValueError):
        publish(path,{},expected='0.2.43',installed=installed,checks_passed=checks)
    assert path.read_bytes()==original


def test_validation_reports_missing_metadata_and_disagreement(tmp_path):
    from council.runtime_marker import inspect_marker
    path = tmp_path/'marker.json'
    assert inspect_marker(path,expected='0.2.43',installed='0.2.43')['status']=='missing_marker'
    path.write_text('{"packageVersion":"0.2.40"}')
    assert inspect_marker(path,expected='0.2.43',installed=None)['status']=='metadata_unavailable'
    assert inspect_marker(path,expected='0.2.43',installed='0.2.42')['status']=='expected_mismatch'
    assert inspect_marker(path,expected='0.2.43',installed='0.2.43')['status']=='marker_mismatch'
    path.write_text('not json')
    assert inspect_marker(path,expected='0.2.43',installed='0.2.43')['status']=='invalid_marker'
