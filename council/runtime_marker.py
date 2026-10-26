"""Installed-distribution attestation, also executable before the new wheel is installed."""
import argparse
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import tempfile
import tomllib
from packaging.version import Version, InvalidVersion


def installed_version():
    try:
        return version('council-orchestrator')
    except PackageNotFoundError:
        return None


def _same(left, right):
    try:
        return isinstance(left,str) and isinstance(right,str) and Version(left)==Version(right)
    except InvalidVersion:
        return False


def inspect_marker(path, *, expected, installed):
    path = Path(path)
    if installed is None:
        return {'status':'metadata_unavailable'}
    if not _same(expected,installed):
        return {'status':'expected_mismatch','expected':expected,'installed':installed}
    if not path.exists():
        return {'status':'missing_marker','installed':installed}
    try:
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or path.stat().st_size>65536:
            raise ValueError('Unsafe marker')
        marker = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(marker,dict) or not isinstance(marker.get('packageVersion'),str):
            raise ValueError('Invalid marker')
    except (OSError,ValueError):
        return {'status':'invalid_marker','installed':installed}
    return {'status':'verified' if _same(marker['packageVersion'],installed) else 'marker_mismatch',
        'installed':installed,'recorded':marker['packageVersion']}


def publish(path, fields, *, expected, installed, checks_passed):
    if checks_passed is not True or not _same(expected,installed):
        raise ValueError('Successful checks and matching installed distribution required')
    path = Path(path)
    for parent in (path,*path.parents):
        if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)():
            raise ValueError('Marker paths cannot traverse links')
    retained = {}
    if path.exists():
        if path.stat().st_size>65536:
            raise ValueError('Marker exceeds bounds')
        retained = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(retained,dict):
            raise ValueError('Invalid historical marker')
    data = json.dumps({**retained,**fields,'packageVersion':installed},sort_keys=True,indent=2).encode('utf-8')
    if len(data)>65536:
        raise ValueError('Marker exceeds bounds')
    descriptor, temporary = tempfile.mkstemp(prefix='council-marker-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['verify','publish'])
    parser.add_argument('--project',required=True)
    parser.add_argument('--marker',required=True)
    parser.add_argument('--source-hash')
    parser.add_argument('--wheel-hash')
    parser.add_argument('--python-version')
    parser.add_argument('--checks-passed',action='store_true')
    args = parser.parse_args()
    with open(args.project,'rb') as source:
        expected = tomllib.load(source)['project']['version']
    installed = installed_version()
    if args.action=='publish':
        fields = {'sourceHash':args.source_hash,'wheelHash':args.wheel_hash,
            'pythonVersion':json.loads(args.python_version)}
        publish(args.marker,fields,expected=expected,installed=installed,checks_passed=args.checks_passed)
    result = inspect_marker(args.marker,expected=expected,installed=installed)
    print(json.dumps(result))
    return 0 if result['status']=='verified' else 1


if __name__=='__main__':
    raise SystemExit(main())
