#!/usr/bin/env python3
"""Offline routing and batched documentary checks. No messages, network or Git writes.

The caller authenticates observations and human authority. A route is a plan,
never proof of dispatch, destination identity, reception or a finished agent.
"""
from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location('syncpilot_flow_transport', Path(__file__).with_name('syncpilot_transport.py'))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
c = t.core


def actor(value):
    c.fields(value, 'environment project_id thread_id authority qualification_reference')
    c.require(value['environment'] in ('work', 'codex'), 'Unknown actor environment')
    for key, item in value.items():
        c.text(item)
        c.require('REPLACE_' not in item, 'Actual actor qualification required')
    return value


def receiver_title(project_name):
    """Use the authenticated project name, preserving its spelling and case."""
    c.text(project_name)
    c.require(not any(char in project_name for char in ('\r','\n','\x00')), 'Single project name required')
    return project_name.strip()+'-RECEVEUR'


def route(config, source, destination_environment, kind, candidates, message_authority=None,
          can_message=False, canonical_root=None, preferred=None, creation_authority=None,
          can_create=False, journal=None, contract_sha256=None):
    c.validate_contract(config)
    c.require(config['schema_version'] == 5, 'Project routing requires contract v5')
    source = actor(source)
    c.require(source['project_id'] == config['decision_sync']['participants'][source['environment']]['project_id'], 'Wrong source project')
    c.require(destination_environment in ('work', 'codex') and kind in ('documents', 'decisions'), 'Unknown workflow')
    result = {'format':'SYNCPILOT-FLOW-PLAN', 'schema_version':1, 'project_id':config['project_id'],
              'source':source, 'destination_environment':destination_environment, 'kind':kind,
              'receiver':None, 'dispatch_performed':False, 'reception_verified':False,
              'mirror_status':'NOT_ASSERTED', 'automatic_git_integration':False}
    target = config['decision_sync']['participants'][destination_environment]['project_id']
    if creation_authority:
        c.fields(creation_authority, 'project_id environment title reference')
        for key in ('title','reference'):c.text(creation_authority[key])
        c.require(creation_authority['project_id']==target and creation_authority['environment']==destination_environment,
                  'Creation authority outside destination project')
    if journal is not None:
        c.require(kind == 'decisions', 'Existing decision journal required for decision routing')
        ds = importlib.util.spec_from_file_location('syncpilot_flow_decisions', Path(__file__).resolve().parents[2]/'syncpilot-decisions/scripts/decision_sync.py')
        d = importlib.util.module_from_spec(ds); ds.loader.exec_module(d); d.c = c
        operation = d.validate_operation(journal)
        c.require(operation['identity']['source'] == {k:source[k] for k in ('project_id','thread_id')}
                  and operation['identity']['destination']['project_id'] == target
                  and operation['identity']['contract_sha256'] == (contract_sha256 or c.digest(c.encode(config)))
                  and operation['identity']['project_id']==config['project_id']
                  and operation['identity']['direction']==source['environment']+'-to-'+destination_environment
                  and operation['profiles']=={k:config['transport'][k] for k in ('primary','fallback')}, 'Existing operation belongs to another flow')
        d.validate_routing(operation['routing'],config,operation['identity'])
        result.update(operation_id=operation['operation_id'], nonce=operation['nonce'])
        if d.state(journal) in ('VERIFIED','BLOCKED'):
            result.update(action='COLLECT_VERIFIED_RESULTS' if d.state(journal)=='VERIFIED' else 'BLOCKED_EXISTING_OPERATION', message_required=False)
            return result
        selections = [e for e in journal['events'] if e['status']=='RECEIVER_SELECTED']
        if selections:
            result.update(action='FOLLOW_SELECTED_RECEIVER', receiver=selections[0]['receiver'], message_required=False)
            return result
    if source['environment'] == destination_environment:
        result.update(action='USE_CANONICAL_SOURCE' if kind == 'documents' else 'ALIGN_LOCAL_REGISTRY',
                      message_required=False, reason='Same environment: use its qualified source, without an inter-chat round trip.')
        return result
    c.require(isinstance(candidates, list) and len(candidates)<=c.MAX_ENTRIES, 'Bounded observed candidate list required')
    eligible = []
    dedicated_busy = False
    for item in candidates:
        c.fields(item, 'thread_id title environment project_id status updated_at canonical_root qualification_reference')
        c.text(item['thread_id']); c.text(item['title']); c.text(item['qualification_reference'])
        c.require(isinstance(item['updated_at'], (int, float)) and not isinstance(item['updated_at'], bool), 'Invalid candidate time')
        if item['environment'] != destination_environment or item['thread_id'] == source['thread_id']:
            continue
        association = 'application-project'
        if item['project_id'] != target:
            # Missing UI association can be qualified through the authenticated
            # project catalogue and its actual repository; a different project cannot.
            if not (item['project_id'] is None and canonical_root and item['canonical_root']
                    and Path(item['canonical_root']).resolve() == Path(canonical_root).resolve()
                    and destination_environment == 'codex'):
                continue
            association = 'catalogue-and-actual-repository'
        if item['status'] not in ('idle', 'notLoaded'):
            if creation_authority and item['title'] == creation_authority['title']:
                dedicated_busy = True
            continue
        if preferred and item['thread_id'] != preferred:
            continue
        eligible.append((item, association))
    if not eligible:
        if dedicated_busy:
            result.update(action='BLOCKED_RECEIVER_BUSY', message_required=True,
                          reason='The project receiver already exists and is busy; collect its actual state instead of creating a duplicate.')
            return result
        if can_create and creation_authority and destination_environment=='codex' and not preferred:
            result.update(action='CREATE_PROJECT_RECEIVER', message_required=True,
                          creation={'project_id':target,'title':creation_authority['title'],'environment':'local','authority_reference':creation_authority['reference']},
                          reason='No available existing receiver; create once using the actual application project tool and authorized reception prompt, then qualify and follow its result.')
            return result
        result.update(action='BLOCKED_NO_AVAILABLE_RECEIVER', message_required=True,
                      reason='No qualified available actor; do not silently leave an immediate-return mission in a passive inbox.')
        return result
    dedicated = creation_authority['title'] if creation_authority else None
    chosen, association = min(eligible, key=lambda pair: (bool(dedicated) and pair[0]['title'] != dedicated, pair[0]['status'] != 'idle', -pair[0]['updated_at'], pair[0]['thread_id']))
    result['receiver'] = {'environment':destination_environment, 'project_id':target,
                          'thread_id':chosen['thread_id'], 'qualification_reference':chosen['qualification_reference'],
                          'project_association':association}
    result['message_required'] = True
    if not can_message:
        result.update(action='BLOCKED_DISPATCH_UNAVAILABLE', reason='No authenticated owner-application message capability; no invented wakeup or exec resume fallback.')
    elif not message_authority:
        result.update(action='READY_REQUIRES_MESSAGE_AUTHORITY', reason='Obtain or reuse human authority covering the selected recipient or this project workflow.')
    else:
        c.fields(message_authority, 'project_id environment thread_id reference')
        c.text(message_authority['reference'])
        c.require(message_authority['project_id'] == target and message_authority['environment'] == destination_environment,
                  'Message authority outside destination project')
        c.require(message_authority['thread_id'] in (None, chosen['thread_id']), 'Message authority names another recipient')
        result.update(action='SELECT_AND_DISPATCH', message_authority=message_authority,
                      reason='Pilot qualifies and dispatches through actual application tools, then follows and verifies the result.')
    return result


def file_binding(path):
    data = path.read_bytes()
    return {'path':str(path.resolve()), 'size':len(data), 'sha256':c.digest(data)}


def fresh_directory(path, canonical_repository=None):
    if canonical_repository:
        c.require(not path.resolve().is_relative_to(canonical_repository.resolve()), 'Outputs must stay outside the canonical repository')
    c.require(not path.exists() and not path.is_symlink(), 'Preserve existing output; collect before retry')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()


def prepare(args):
    started = time.monotonic()
    output = args.output_directory
    requirement, carrier, package, journal = (output/name for name in ('requirement.json','carrier.json','package.zip','journal-0.json'))
    if output.exists():
        c.require(not output.is_symlink() and output.is_dir(), 'Regular preparation directory required')
        c.require(all(p.is_file() and not p.is_symlink() for p in (requirement, carrier, package, journal)), 'Incomplete preparation preserved; collect or recover explicitly')
        req = c.load(requirement); op = t.validate(c.load(journal))
        c.require(req['source_commit'] == args.commit and req['domains'] == sorted(args.domain) and req['authority'] == args.authority,
                  'Existing preparation belongs to another requirement')
        c.require(op['destination_thread'] == args.receiver_thread and op['authority'] == args.authority, 'Existing operation belongs to another receiver or mandate')
        raw, zip_bytes = c.input_zip(carrier)
        manifest, _ = c.verify_zip(zip_bytes, req)
        c.require(package.read_bytes() == zip_bytes and manifest['sync_id'] == op['identity']['sync_id'], 'Existing package altered')
        c.require(op['files'] == [{'name':'carrier.json', 'size':len(raw), 'sha256':c.digest(raw)},
                                  {'name':'requirement.json', 'size':requirement.stat().st_size, 'sha256':c.digest(requirement.read_bytes())}], 'Existing operation files altered')
        canonical = c.decode(c.snapshot(args.repository, args.commit, c.CONTRACT))
        c.source_check(args.repository, args.commit, canonical)
        c.require(req['contract_sha256'] == c.digest(c.snapshot(args.repository, args.commit, c.CONTRACT)), 'Existing preparation belongs to another repository')
        return {'action':'COLLECT_EXISTING', 'operation_id':op['operation_id'], 'nonce':op['nonce'], 'files':[file_binding(p) for p in (requirement,carrier,package,journal)]}
    # Validate real Git authority before any output directory is created.
    config = c.decode(c.snapshot(args.repository, args.commit, c.CONTRACT))
    c.validate_contract(config); c.source_check(args.repository, args.commit, config)
    c.select_paths(config, args.domain); c.text(args.authority); c.text(args.receiver_thread)
    fresh_directory(output, args.repository)
    c.prepare_requirement(argparse.Namespace(repository=args.repository, commit=args.commit, domain=args.domain, authority=args.authority, output=requirement))
    c.build(argparse.Namespace(repository=args.repository, requirement=requirement, output=package, carrier=carrier, attestation=args.attestation))
    j = t.prepare(carrier, requirement, args.receiver_thread, args.authority)
    c.write_new(journal, c.encode(j))
    result = {'format':'SYNCPILOT-BATCH-PREPARATION', 'schema_version':1, 'action':'PREPARED_NOT_DEPOSITED',
              'operation_id':j['operation']['operation_id'], 'nonce':j['operation']['nonce'],
              'source_commit':args.commit, 'elapsed_seconds':round(time.monotonic()-started, 6),
              'files':[file_binding(p) for p in (requirement,carrier,package,journal)], 'dispatch_performed':False}
    c.write_new(output/'result.json', c.encode(result))
    return result


def validate_intake(args):
    j = c.load(args.journal); op = t.validate(j)
    c.require(t.state(j) == 'DEPOSITED', 'Collect a deposited operation; never receive a blocked, prepared or verified operation')
    actual = actor(c.load(args.receiver))
    c.require(actual['environment'] == 'work' and actual['project_id'] == op['identity']['destination']
              and actual['thread_id'] == op['destination_thread'], 'Wrong actual Work receiver')
    raw, archive = c.input_zip(args.input)
    req = c.load(args.requirement); manifest, entries = c.verify_zip(archive, req)
    config = c.decode(entries[c.CONTRACT])
    expected = {'project_id':req['project_id'], 'destination':req['destination'], 'source_commit':req['source_commit'],
                'sync_id':manifest['sync_id'], 'requirement_sha256':c.digest(c.encode(req)), 'contract_sha256':req['contract_sha256']}
    c.require(expected == op['identity'] and t.profiles(config) == op['profiles'], 'Operation and package authority differ')
    c.require(op['files'] == [{'name':'carrier.json','size':len(raw),'sha256':c.digest(raw)},
                              {'name':'requirement.json','size':args.requirement.stat().st_size,'sha256':c.digest(args.requirement.read_bytes())}], 'Operation bytes altered')
    c.require(args.channel in op['profiles'], 'Unknown channel')
    if args.channel == 'primary':
        device, root, pm = c.dc_endpoint(op['profiles']['primary']['locator'])
        expected_locator = 'dc://'+device+'/'+quote(pm.join(root, req['project_id'], op['operation_id'], 'carrier.json'), safe='')
        c.require(args.artifact_locator == expected_locator, 'Artifact outside exact operation')
    else:
        import re
        c.require(any(e['status']=='DC_UNAVAILABLE' and e['delivery']=='not-delivered' for e in j['events']), 'Drive unavailable without qualified DC failure')
        c.require(re.fullmatch(r'gdrive:file:[A-Za-z0-9_-]+', args.artifact_locator), 'Exact Drive file required')
    observation = {'destination':req['destination'], 'artifact_locator':args.artifact_locator, 'retrieved_sha256':c.digest(raw)}
    return op, req, observation


def intake(args):
    started = time.monotonic()
    op, req, observation = validate_intake(args)
    output = args.output_directory
    store, proof_path, receipt_path = output/'store', output/'proof.json', output/'receipt.json'
    receipt = {'format':'SYNCPILOT-RECEIPT', 'schema_version':1, 'operation_id':op['operation_id'], 'nonce':op['nonce'],
               'identity':op['identity'], 'destination_thread':op['destination_thread'], 'channel':args.channel,
               'status':'RECEIVED_VERIFIED', 'files':op['files']}
    if output.exists():
        c.require(output.is_dir() and not output.is_symlink(), 'Regular intake directory required')
        c.require(all(p.is_file() and not p.is_symlink() for p in (proof_path,receipt_path,output/'result.json')), 'Incomplete intake preserved; collect or recover explicitly')
        proof = c.check_store(store, req)
        raw_proof = proof_path.read_bytes()
        c.require(raw_proof == c.encode(proof) and proof['observation'] == observation, 'Existing proof belongs to another artifact')
        receipt['proof_sha256'] = c.digest(raw_proof)
        c.require(c.load(receipt_path) == receipt, 'Existing receipt belongs to another operation or receiver')
        result = c.load(output/'result.json')
        c.require(result['operation_id']==op['operation_id'] and result['nonce']==op['nonce'], 'Existing result belongs to another operation')
        for item in result['files']:
            p=Path(item['path']); c.require(p.resolve().is_relative_to(output.resolve()) and not p.is_symlink(), 'Existing result outside intake')
            c.require(file_binding(p)==item, 'Existing result bytes changed')
        return {'action':'COLLECT_EXISTING', 'result':result, 'result_file':file_binding(output/'result.json')}
    fresh_directory(output)
    observation_path = output/'observation.json'
    c.write_new(observation_path, c.encode(observation))
    proof = c.receive(argparse.Namespace(input=args.input, requirement=args.requirement, observation=observation_path, store=store, output=proof_path))
    c.check_store(store, req, proof)
    receipt['proof_sha256'] = c.digest(proof_path.read_bytes())
    c.write_new(receipt_path, c.encode(receipt))
    c.require(c.load(receipt_path) == receipt, 'Receipt readback differs')
    result = {'format':'SYNCPILOT-BATCH-INTAKE', 'schema_version':1, 'action':'RECEIVED_AWAITING_PARENT_CONFIRM',
              'operation_id':op['operation_id'], 'nonce':op['nonce'], 'receiver':actor(c.load(args.receiver)),
              'source_commit':req['source_commit'], 'sources':len(req['sources']), 'domains':req['domains'],
              'elapsed_seconds':round(time.monotonic()-started,6), 'local_checks_finished':True,
              'agent_finished_observed':False, 'parent_confirmed':False,
              'files':[file_binding(p) for p in (proof_path,receipt_path,observation_path)]}
    c.write_new(output/'result.json', c.encode(result))
    return result


def main():
    c.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('route')
    for name in ('contract','source','candidates'):
        r.add_argument('--'+name, type=Path, required=True)
    r.add_argument('--destination-environment', choices=('work','codex'), required=True)
    r.add_argument('--kind', choices=('documents','decisions'), required=True)
    r.add_argument('--message-authority', type=Path)
    r.add_argument('--can-message', action='store_true')
    r.add_argument('--canonical-root', type=Path)
    r.add_argument('--preferred')
    r.add_argument('--creation-authority', type=Path)
    r.add_argument('--can-create', action='store_true')
    r.add_argument('--journal', type=Path)
    p = sub.add_parser('prepare')
    p.add_argument('--repository', type=Path, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--domain', action='append', required=True)
    p.add_argument('--authority', required=True)
    p.add_argument('--receiver-thread', required=True)
    p.add_argument('--output-directory', type=Path, required=True)
    p.add_argument('--attestation', type=Path)
    p = sub.add_parser('intake')
    for name in ('input','requirement','journal','receiver','output-directory'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--channel', choices=('primary','fallback'), required=True)
    p.add_argument('--artifact-locator', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'route':
            result = route(c.load(args.contract), c.load(args.source), args.destination_environment, args.kind,
                           c.load(args.candidates)['candidates'], c.load(args.message_authority) if args.message_authority else None,
                           args.can_message, args.canonical_root, args.preferred,
                           c.load(args.creation_authority) if args.creation_authority else None, args.can_create,
                           c.load(args.journal) if args.journal else None, c.digest(args.contract.read_bytes()))
        else:
            result = prepare(args) if args.command=='prepare' else intake(args)
        print(c.encode(result).decode(), end='')
        return 0
    except (c.SyncError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print('SYNCPILOT FLOW REFUSED: '+str(exc), file=__import__('sys').stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
