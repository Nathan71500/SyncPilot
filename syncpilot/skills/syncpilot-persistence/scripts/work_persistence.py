#!/usr/bin/env python3
"""Offline Work publication gates. Authenticated connectors perform every real IO.

Observations are qualified pilot inputs, not cryptographic identity signatures.
Transport verification and durable Work availability are separate proofs.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('persistence_core', Path(__file__).resolve().parents[2] / 'syncpilot-codex/scripts/project_sync.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
POLICY = {'required': True, 'write': 'reuse-before-create', 'unknown_commit': 'inspect-before-retry', 'revalidation': 'fresh-read-at-mission-start', 'transport': 'separate-from-publication'}
EVENTS = ('UPLOAD_ATTEMPTED', 'WRITE_NOT_COMMITTED', 'VALIDATION_REJECTED', 'PERSISTENCE_VERIFIED')


def now():
    return datetime.now(timezone.utc).isoformat()


def contract(value):
    c.validate_contract(value)
    c.require(value['schema_version'] in (4,5) and 'work_persistence' in value, 'Explicit persistence target in contract v4/v5 required; migrate separately')
    return value


def migrate(old, persistence):
    c.validate_contract(old)
    c.require(old['schema_version'] == 3, 'Migrate old transport/decisions to v3 first')
    candidate = {**copy.deepcopy(old), 'schema_version': 4, 'work_persistence': copy.deepcopy(persistence)}
    contract(candidate)
    return candidate


def prepare(config, transport, artifacts, work_thread=None):
    contract(config)
    c.fields(transport, 'operation_id nonce destination destination_thread status proof_sha256 receipt_sha256 authority')
    c.require(transport['status'] == 'VERIFIED', 'Verify independent transport proof and receipt before publication')
    participants = config['decision_sync']['participants']
    c.text(transport['destination_thread'])
    if config['schema_version']==5:
        c.require(any(transport['destination']==participant['project_id'] for participant in participants.values()),'Wrong transport destination')
        if transport['destination']==participants['work']['project_id']:
            c.require(work_thread is None or work_thread==transport['destination_thread'],'Wrong qualified Work thread')
            work_thread=transport['destination_thread']
        c.text(work_thread);c.require('REPLACE_' not in work_thread,'Qualified actual Work thread required')
    else:
        c.require(any(transport['destination'] == participant['project_id'] and transport['destination_thread'] == participant['thread_id'] for participant in participants.values()), 'Wrong transport destination')
        c.require(work_thread is None or work_thread==participants['work']['thread_id'],'Legacy Work thread is fixed')
        work_thread=participants['work']['thread_id']
    for key in ('operation_id', 'nonce', 'authority'):
        c.text(transport[key])
    for key in ('proof_sha256', 'receipt_sha256'):
        c.hex_value(transport[key], 64)
    c.require(isinstance(artifacts, list) and artifacts, 'Explicit verified artifact inventory required')
    names = []
    for item in artifacts:
        c.fields(item, 'name size sha256')
        names.append(c.safe_path(item['name']))
        c.require(type(item['size']) is int and 0 <= item['size'] <= 10 * 1024 * 1024, 'Unsupported Page file size')
        c.hex_value(item['sha256'], 64)
    c.path_list(names)
    op = {'operation_id': transport['operation_id'], 'nonce': transport['nonce'], 'contract_sha256': c.digest(c.encode(config)), 'project_id': config['project_id'], 'destination_thread': work_thread, 'target': copy.deepcopy(config['work_persistence']['target']), 'registry': config['work_persistence']['registry'], 'authority': transport['authority'], 'transport_proof_sha256': transport['proof_sha256'], 'transport_receipt_sha256': transport['receipt_sha256'], 'artifacts': sorted(copy.deepcopy(artifacts), key=lambda x: x['name'])}
    op['persistence_id'] = c.digest(c.encode(op))
    return {'format': 'SYNCPILOT-PERSISTENCE-OPERATION', 'schema_version': 1, 'operation': op, 'events': []}


def state(j):
    statuses = [e['status'] for e in j['events']]
    if 'VALIDATION_REJECTED' in statuses:
        return 'BLOCKED'
    if 'PERSISTENCE_VERIFIED' in statuses:
        return 'AVAILABLE'
    return 'PENDING'


def validate(j):
    c.fields(j, 'format schema_version operation events')
    c.require(j['format'] == 'SYNCPILOT-PERSISTENCE-OPERATION' and type(j['schema_version']) is int and j['schema_version'] == 1, 'Unknown persistence operation')
    op = j['operation']
    c.fields(op, 'persistence_id operation_id nonce contract_sha256 project_id destination_thread target registry authority transport_proof_sha256 transport_receipt_sha256 artifacts')
    c.require(op['persistence_id'] == c.digest(c.encode({k: v for k, v in op.items() if k != 'persistence_id'})), 'Persistence identity changed')
    c.require(isinstance(j['events'], list), 'Invalid persistence history')
    prior = {**j, 'events': []}
    names = {x['name'] for x in op['artifacts']}
    pending = set()
    for e in j['events']:
        c.fields(e, 'status name reference observed_at previous_sha256')
        c.require(state(prior) == 'PENDING' and e['status'] in EVENTS, 'Invalid or terminal persistence transition')
        c.require(e['previous_sha256'] == c.digest(c.encode(prior)), 'Persistence history changed')
        c.require(e['name'] in names or e['name'] == '*', 'Unknown artifact in history')
        if e['status'] in ('UPLOAD_ATTEMPTED', 'WRITE_NOT_COMMITTED'):
            c.require(e['name'] in names, 'Per-file write history required')
        c.text(e['reference'])
        datetime.fromisoformat(e['observed_at'])
        if e['status'] == 'UPLOAD_ATTEMPTED':
            c.require(e['name'] not in pending, 'Unresolved upload; inspect before retry')
            pending.add(e['name'])
        if e['status'] == 'WRITE_NOT_COMMITTED':
            c.require(e['name'] in pending, 'No unresolved write attempt to resolve')
            pending.remove(e['name'])
        prior = {**prior, 'events': prior['events'] + [e]}
    return op


def record(j, status, name, reference):
    c.require(status != 'PERSISTENCE_VERIFIED', 'Only independent proof acceptance may mark persistence verified')
    return _append(j, status, name, reference)


def _append(j, status, name, reference):
    validate(j)
    result = copy.deepcopy(j)
    result['events'].append({'status': status, 'name': name, 'reference': reference, 'observed_at': now(), 'previous_sha256': c.digest(c.encode(j))})
    validate(result)
    return result


def inspect(j, observation):
    op = validate(j)
    c.require(state(j) != 'BLOCKED', 'Integrity/identity rejection is terminal; no storage or channel bypass')
    c.fields(observation, 'persistence_id operation_id nonce target registry registry_verified routing_verified authority observed_at complete outcome files project_source_ingested')
    c.require(observation['registry'] == op['registry'], 'Wrong persistence registry')
    c.require(type(observation['registry_verified']) is bool and type(observation['routing_verified']) is bool, 'Explicit registry and routing verification required')
    for key in ('persistence_id', 'operation_id', 'nonce', 'target'):
        c.require(observation[key] == op[key], 'Wrong persistence observation identity')
    c.text(observation['authority'])
    stamp = datetime.fromisoformat(observation['observed_at'])
    c.require(stamp.tzinfo is not None, 'Qualified observation timestamp required')
    c.require(stamp <= datetime.now(timezone.utc), 'Future observation')
    if j['events']:
        c.require(stamp >= datetime.fromisoformat(j['events'][-1]['observed_at']), 'Stale observation before last operation event')
    c.require(type(observation['complete']) is bool and type(observation['project_source_ingested']) is bool, 'Explicit discovery coverage and ingestion status required')
    c.require(observation['outcome'] in ('available', 'unknown', 'unavailable', 'rejected'), 'Unknown destination outcome')
    c.require(isinstance(observation['files'], list), 'File observations required')
    expected = {f['name']: f for f in op['artifacts']}
    seen = {}
    for f in observation['files']:
        c.fields(f, 'name reference size sha256 linked access_confirmed read_in_new_context')
        c.require(f['name'] in expected and f['name'] not in seen, 'Unexpected or duplicate persistent artifact')
        c.require(f['size'] == expected[f['name']]['size'] and f['sha256'] == expected[f['name']]['sha256'], 'Persistent content integrity rejected')
        c.require(type(f['size']) is int and all(type(f[k]) is bool for k in ('linked', 'access_confirmed', 'read_in_new_context')), 'Invalid file observation')
        c.text(f['reference'])
        c.require(f['reference'].startswith(('library-file:', 'project-file:')), 'Opaque native file reference required; no external folder substitution')
        seen[f['name']] = f
    return op, seen


def plan(j, observation):
    op, seen = inspect(j, observation)
    result = {'persistence_id': op['persistence_id'], 'operation_id': op['operation_id'], 'nonce': op['nonce'], 'target': op['target'], 'transport_change': False}
    if observation['outcome'] == 'rejected':
        return {**result, 'action': 'BLOCKED', 'reason': 'VALIDATION_REJECTED'}
    if observation['outcome'] == 'unavailable':
        return {**result, 'action': 'BLOCKED', 'reason': 'PERSISTENCE_UNAVAILABLE_NOT_DC_FAILURE'}
    if observation['outcome'] == 'unknown' or not observation['complete']:
        return {**result, 'action': 'COLLECT_EXISTING', 'reason': 'INCOMPLETE_DISCOVERY_NO_UPLOAD'}
    missing = [f for f in op['artifacts'] if f['name'] not in seen]
    if state(j) == 'AVAILABLE' and (missing or not all(f['linked'] for f in seen.values())):
        return {**result, 'action': 'BLOCKED', 'reason': 'DURABLE_AVAILABILITY_LOST_REVIEW_REQUIRED'}
    pending = set()
    for e in j['events']:
        if e['status'] == 'UPLOAD_ATTEMPTED': pending.add(e['name'])
        if e['status'] == 'WRITE_NOT_COMMITTED': pending.discard(e['name'])
    if any(f['name'] in pending for f in missing):
        return {**result, 'action': 'COLLECT_EXISTING', 'reason': 'UNKNOWN_COMMIT_NO_REUPLOAD'}
    if missing:
        if op['target']['kind'] != 'page-files':
            return {**result, 'action': 'BLOCKED', 'reason': 'NATIVE_PROJECT_SOURCE_ADAPTER_NOT_AVAILABLE'}
        return {**result, 'action': 'UPLOAD_ONCE', 'artifacts': missing}
    if not all(f['linked'] for f in seen.values()):
        return {**result, 'action': 'LINK_EXISTING', 'files': list(seen.values())}
    return {**result, 'action': 'REVALIDATE', 'files': list(seen.values())}


def confirm(config, j, observation):
    contract(config)
    op, seen = inspect(j, observation)
    c.require(op['target'] == config['work_persistence']['target'] and op['registry'] == config['work_persistence']['registry'], 'Wrong persistence destination or registry')
    c.require(op['contract_sha256'] == c.digest(c.encode(config)), 'Contract changed during persistence')
    c.require(plan(j, observation)['action'] == 'REVALIDATE', 'Work availability not ready')
    c.require(all(f['linked'] and f['access_confirmed'] and f['read_in_new_context'] for f in seen.values()), 'Independent fresh-context file and link read required')
    c.require(observation['registry_verified'] and observation['routing_verified'], 'Durable registry and project routing not verified')
    c.require((datetime.now(timezone.utc) - datetime.fromisoformat(observation['observed_at'])).total_seconds() <= 300, 'Fresh observation older than five minutes')
    kind = op['target']['kind']
    if kind == 'project-sources':
        c.require(observation['project_source_ingested'], 'Native project Source ingestion not observed')
    else:
        c.require(not observation['project_source_ingested'], 'Page Files do not prove native project Source ingestion')
    return {'format': 'SYNCPILOT-PERSISTENCE-PROOF', 'schema_version': 1, 'persistence_id': op['persistence_id'], 'operation_id': op['operation_id'], 'nonce': op['nonce'], 'contract_sha256': op['contract_sha256'], 'destination_thread': op['destination_thread'], 'target': op['target'], 'transport_proof_sha256': op['transport_proof_sha256'], 'transport_receipt_sha256': op['transport_receipt_sha256'], 'completion_status': 'WORK_PAGE_AVAILABLE' if kind == 'page-files' else 'PROJECT_SOURCE_AVAILABLE', 'project_sources_status': 'NOT_ASSERTED' if kind == 'page-files' else 'INGESTED_VERIFIED', 'files': sorted(seen.values(), key=lambda f: f['name']), 'observation': copy.deepcopy(observation)}


def accept(config, j, proof, fresh_observation, origin):
    c.fields(origin, 'destination_thread target proof_sha256 authority')
    c.text(origin['authority'])
    op = validate(j)
    c.require(origin['destination_thread'] == op['destination_thread'] and origin['target'] == op['target'], 'Wrong authenticated persistence proof origin')
    c.require(origin['proof_sha256'] == c.digest(c.encode(proof)), 'Proof digest changed')
    observed = confirm(config, j, fresh_observation)
    # The read-back has a new timestamp/authority; all immutable proof bindings remain exact.
    c.require({k: v for k, v in observed.items() if k != 'observation'} == {k: v for k, v in proof.items() if k != 'observation'}, 'Destination proof differs from fresh independent read')
    journal = j if state(j) == 'AVAILABLE' else _append(j, 'PERSISTENCE_VERIFIED', '*', origin['authority'] + '; proof_sha256=' + origin['proof_sha256'])
    return {'completion_status': observed['completion_status'], 'operation_id': op['operation_id'], 'nonce': op['nonce'], 'registry': op['registry'], 'target': op['target'], 'files': observed['files'], 'project_sources_status': observed['project_sources_status'], 'transport_status': 'VERIFIED', 'journal': journal}


def main():
    c.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name, arguments in {'migrate': 'contract persistence output', 'prepare': 'contract transport artifacts output', 'plan': 'journal observation', 'record': 'journal status name reference output', 'confirm': 'contract journal observation output', 'accept': 'contract journal proof observation origin output', 'check': 'contract journal observation'}.items():
        p = sub.add_parser(name)
        for arg in arguments.split(): p.add_argument('--' + arg, required=True)
        if name=='prepare':p.add_argument('--work-thread')
    args = parser.parse_args()
    load = lambda key: c.load(Path(getattr(args, key)))
    try:
        if args.command == 'migrate': result = migrate(load('contract'), load('persistence'))
        elif args.command == 'prepare':
            inventory = load('artifacts')
            c.fields(inventory, 'files')
            result = prepare(load('contract'), load('transport'), inventory['files'], args.work_thread)
        elif args.command == 'plan': result = plan(load('journal'), load('observation'))
        elif args.command == 'record': result = record(load('journal'), args.status, args.name, args.reference)
        elif args.command == 'accept': result = accept(load('contract'), load('journal'), load('proof'), load('observation'), load('origin'))
        else: result = confirm(load('contract'), load('journal'), load('observation'))
        if hasattr(args, 'output'): c.write_new(Path(args.output), c.encode(result))
        sys.stdout.buffer.write(c.encode(result))
    except (c.SyncError, ValueError, OSError, KeyError, TypeError) as exc:
        print('SyncPilot persistence blocked: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
