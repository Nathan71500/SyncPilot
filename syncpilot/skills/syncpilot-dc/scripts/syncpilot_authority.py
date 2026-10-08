#!/usr/bin/env python3
"""Build bounded receiver authority from the pilot's durable grant and current mission.

Offline and read-only. File locations and independently qualified SHA-256 pins
separate pilot policy from received packages; JSON is never human authentication.
The caller qualifies the original human references and actual project beforehand.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'syncpilot_authority_core',
    Path(__file__).resolve().parents[2] / 'syncpilot-codex/scripts/project_sync.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
MAX_AUTHORITY_FILE = 65_536


def reference(value):
    c.text(value)
    c.require(len(value) <= 4_000 and not any(x in value for x in ('\x00', '\r', '\n')),
              'Bounded single-line qualified reference required')
    c.require('REPLACE_' not in value, 'Actual qualified authority required')
    return value


def regular(path, directory=False):
    path = Path(path)
    c.require(path.is_absolute(), 'Qualified absolute path required')
    for part in (path, *path.parents):
        c.require(not part.is_symlink() and not (hasattr(part, 'is_junction') and part.is_junction()),
                  'Authority paths must not traverse links or junctions')
    c.require(path.is_dir() if directory else path.is_file(), 'Regular qualified path required')
    return path.resolve()


def pinned(path, authority_root, expected):
    c.hex_value(expected, 64)
    path = regular(path)
    c.require(path.parent == authority_root,
              'Use pilot-owned authority files directly under the qualified .authority root, never received operation files')
    c.require(path.stat().st_size <= MAX_AUTHORITY_FILE, 'Authority file too large')
    raw = path.read_bytes()
    c.require(c.digest(raw) == expected, 'Authority bytes differ from independent pilot qualification')
    return c.decode(raw.decode('utf-8', errors='strict')), {'path':str(path), 'size':len(raw), 'sha256':expected}


def build(contract_path, grant_path, mission_path, source, authority_root,
          canonical_root, grant_sha256, mission_sha256):
    """Pins come from independent pilot qualification, never the received package."""
    canonical_root = regular(canonical_root, directory=True)
    contract_path = regular(contract_path)
    c.require(contract_path == canonical_root / c.CONTRACT, 'Use the actual canonical project contract')
    c.require(contract_path.stat().st_size <= c.MAX_FILE, 'Contract too large')
    raw_contract = contract_path.read_bytes()
    config = c.decode(raw_contract.decode('utf-8', errors='strict'))
    c.validate_contract(config)
    c.require(config['schema_version'] == 5, 'Durable receiver authority requires contract v5')
    _, transport_root, paths = c.dc_endpoint(config['transport']['primary']['locator'])
    expected_root = Path(paths.join(transport_root, config['project_id'], '.authority')).resolve()
    authority_root = regular(authority_root, directory=True)
    c.require(authority_root == expected_root, 'Authority root differs from the qualified project transport')
    c.require(not authority_root.is_relative_to(canonical_root)
              and not canonical_root.is_relative_to(Path(transport_root).resolve()),
              'Pilot authority and canonical sources must stay separate from received transport')
    grant, grant_binding = pinned(grant_path, authority_root, grant_sha256)
    mission, mission_binding = pinned(mission_path, authority_root, mission_sha256)

    c.fields(grant, 'format schema_version project_id scope human_author human_reference human_statement qualification_reference allow_create')
    c.require(grant['format'] == 'SYNCPILOT-RECEIVER-GRANT' and type(grant['schema_version']) is int
              and grant['schema_version'] == 1, 'Unsupported receiver grant')
    c.require(grant['project_id'] == config['project_id'], 'Receiver grant belongs to another project')
    c.require(grant['scope'] == 'authorized-project-missions' and grant['allow_create'] is True,
              'Receiver grant must cover creation only within authorized project missions')
    for key in ('human_author', 'human_reference', 'human_statement', 'qualification_reference'):
        reference(grant[key])

    c.fields(mission, 'format schema_version mission_id project_id contract_sha256 canonical_root project_name source_environment destination_environment reference qualification_reference allow_message allow_receiver_selection receiver_thread')
    c.require(mission['format'] == 'SYNCPILOT-AUTHORIZED-MISSION' and type(mission['schema_version']) is int
              and mission['schema_version'] == 1, 'Unsupported current mission mandate')
    c.require(mission['project_id'] == config['project_id'], 'Mission mandate belongs to another project')
    c.hex_value(mission['contract_sha256'], 64)
    c.require(mission['contract_sha256'] == c.digest(raw_contract), 'Mission mandate requires this exact canonical contract')
    c.require(regular(mission['canonical_root'], directory=True) == canonical_root,
              'Mission mandate belongs to another canonical workspace')
    for key in ('mission_id', 'project_name', 'reference', 'qualification_reference'):
        reference(mission[key])
    c.require(mission['source_environment'] in ('work', 'codex')
              and mission['destination_environment'] in ('work', 'codex'), 'Unknown mission environment')
    c.require(mission['source_environment'] != mission['destination_environment'],
              'Same environment uses its canonical source without receiver creation or messaging')
    c.require(mission['allow_message'] is True and type(mission['allow_receiver_selection']) is bool,
              'Current mission must independently authorize the project message')
    if mission['receiver_thread'] is not None:
        reference(mission['receiver_thread'])
    c.require(mission['allow_receiver_selection'] or mission['receiver_thread'] is not None,
              'Mission must name its receiver or authorize selection in this project')

    c.fields(source, 'environment project_id thread_id authority qualification_reference')
    for value in source.values():
        reference(value)
    c.require(source['environment'] == mission['source_environment']
              and source['project_id'] == config['decision_sync']['participants'][source['environment']]['project_id'],
              'Actual source actor differs from the authorized project mission')
    target_environment = mission['destination_environment']
    target_project = config['decision_sync']['participants'][target_environment]['project_id']
    combined_reference = (mission['reference'] + ' | receiver-grant=' + grant['human_reference']
                          + ' | grant-sha256=' + grant_binding['sha256']
                          + ' | mission-sha256=' + mission_binding['sha256'])
    allow_create = mission['allow_receiver_selection'] and mission['receiver_thread'] is None
    return {
        'format':'SYNCPILOT-AUTHORITY-PLAN', 'schema_version':1,
        'project_id':config['project_id'], 'mission_id':mission['mission_id'],
        'project_name':mission['project_name'], 'source':source,
        'destination_environment':target_environment,
        'message_authority':{'project_id':target_project, 'environment':target_environment,
                             'thread_id':mission['receiver_thread'], 'reference':combined_reference},
        'creation_authority':({'project_id':target_project, 'environment':target_environment,
                               'title':mission['project_name'].strip() + '-RECEVEUR',
                               'reference':combined_reference} if allow_create else None),
        'bridge_authority':{'reference':combined_reference, 'allow_message':True, 'allow_create':allow_create},
        'bindings':{'contract':{'path':str(contract_path), 'size':len(raw_contract), 'sha256':c.digest(raw_contract)},
                    'grant':grant_binding, 'mission':mission_binding},
        'human_references':{'author':grant['human_author'], 'grant':grant['human_reference'],
                            'statement':grant['human_statement'], 'mission':mission['reference'],
                            'grant_qualification':grant['qualification_reference'],
                            'mission_qualification':mission['qualification_reference']},
        'dispatch_performed':False, 'receiver_availability_asserted':False,
        'human_authority_authenticated_by_helper':False, 'permissions_changed':False,
    }


def main():
    c.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    for name in ('contract', 'grant', 'mission', 'source', 'authority-root', 'canonical-root'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('grant-sha256', 'mission-sha256'):
        p.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        result = build(args.contract, args.grant, args.mission, c.load(args.source), args.authority_root,
                       args.canonical_root, args.grant_sha256, args.mission_sha256)
        print(c.encode(result).decode('utf-8'), end='')
        return 0
    except (c.SyncError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print('SYNCPILOT AUTHORITY REFUSED: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
