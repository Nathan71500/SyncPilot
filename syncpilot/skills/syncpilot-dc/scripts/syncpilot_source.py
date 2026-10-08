#!/usr/bin/env python3
"""Offline qualification of a current conversation, including forks.
The pilot authenticates native application observations; JSON and hashes do not.
This helper neither dispatches messages nor grants permissions.
"""
import argparse
import importlib.util
import math
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('source_authority', Path(__file__).with_name('syncpilot_authority.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
c = a.c


def stamp(value):
    a.reference(value)
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    c.require(moment.tzinfo is not None, 'Explicit observation timezone required')
    return moment.timestamp()


def native_time(value):
    c.require(type(value) in (int, float) and math.isfinite(value), 'Actual native timestamp required')
    return value


def issue(environment, project_id, request_sha256, now=None):
    c.require(environment in ('work', 'codex'), 'Unknown source environment')
    a.reference(project_id)
    c.hex_value(request_sha256, 64)
    nonce = secrets.token_hex(16)
    return {'format': 'SYNCPILOT-SOURCE-CHALLENGE', 'schema_version': 1,
            'environment': environment, 'project_id': project_id,
            'request_sha256': request_sha256, 'nonce': nonce,
            'marker': 'SYNCPILOT-SOURCE:' + nonce,
            'issued_at': (now or datetime.now(timezone.utc)).isoformat()}


def resolve(config, challenge, observation, request_sha256, authority_reference, now=None):
    c.validate_contract(config)
    c.require(config['schema_version'] == 5, 'Source qualification requires contract v5')
    c.fields(challenge, 'format schema_version environment project_id request_sha256 nonce marker issued_at')
    c.require(challenge['format'] == 'SYNCPILOT-SOURCE-CHALLENGE'
              and type(challenge['schema_version']) is int and challenge['schema_version'] == 1,
              'Unsupported source challenge')
    environment = challenge['environment']
    c.require(environment in ('work', 'codex'), 'Unknown source environment')
    project = config['decision_sync']['participants'][environment]['project_id']
    c.hex_value(request_sha256, 64)
    c.hex_value(challenge['nonce'], 32)
    c.require(challenge['project_id'] == project and challenge['request_sha256'] == request_sha256,
              'Challenge belongs to another current request or project')
    c.require(challenge['marker'] == 'SYNCPILOT-SOURCE:' + challenge['nonce'], 'Altered source marker')
    current = (now or datetime.now(timezone.utc)).timestamp()
    issued = stamp(challenge['issued_at'])
    c.require(-5 <= current - issued <= 600, 'Source challenge expired or is in the future')
    c.fields(observation, 'format schema_version observed_at environment project_id nonce tool_reference listing readings')
    c.require(observation['format'] == 'SYNCPILOT-SOURCE-OBSERVATION'
              and type(observation['schema_version']) is int and observation['schema_version'] == 1,
              'Unsupported native source observation')
    observed = stamp(observation['observed_at'])
    c.require(-5 <= current - observed <= 120 and observed >= issued - 5,
              'Fresh native source observation required')
    c.require(observation['environment'] == environment and observation['project_id'] == project
              and observation['nonce'] == challenge['nonce'], 'Observation belongs to another challenge')
    a.reference(authority_reference)
    a.reference(observation['tool_reference'])
    listing = observation['listing']
    c.require(isinstance(listing, dict), 'Actual application inventory required')
    regular = listing.get('threads', [])
    pinned = listing.get('pinnedThreads', [])
    c.require(isinstance(regular, list) and isinstance(pinned, list)
              and len(regular) + len(pinned) <= 128, 'Bounded native inventory required')
    inventory = {}
    for row in pinned + regular:
        c.require(isinstance(row, dict) and isinstance(row.get('id'), str), 'Malformed native inventory')
        c.require(row['id'] not in inventory, 'Duplicate native identity')
        inventory[row['id']] = row
    readings = observation['readings']
    c.require(isinstance(readings, list) and len(readings) <= 128, 'Bounded native readbacks required')
    matches, seen = [], set()
    kind = 'chatgpt' if environment == 'work' else 'codex'
    for reading in readings:
        c.require(isinstance(reading, dict) and isinstance(reading.get('thread'), dict),
                  'Tool errors are not source identity evidence')
        thread = reading['thread']
        identity = thread.get('id')
        c.require(isinstance(identity, str) and identity in inventory and identity not in seen,
                  'Unlisted or duplicate readback identity')
        seen.add(identity)
        row = inventory[identity]
        c.require(row.get('kind') == kind and thread.get('kind') == kind
                  and row.get('projectId') == project, 'Wrong actual source environment or project')
        c.require(isinstance(reading.get('page'), dict) and reading['page'].get('order') == 'newest_first',
                  'Native latest-turn ordering required')
        turns = reading.get('turns')
        c.require(isinstance(turns, list) and len(turns) <= 20, 'Bounded native turns required')
        if not turns:
            continue
        turn = turns[0]
        c.require(isinstance(turn, dict), 'Malformed native turn')
        started = native_time(turn.get('startedAt'))
        created = native_time(thread.get('createdAt'))
        # A copied parent turn predates the fork. Never search old turns for a match.
        # A live source turn can start before it issues its own challenge.
        # Freshness comes from the nonce and native observation, not turn duration.
        if started < created or started > observed + 5:
            continue
        items = turn.get('items')
        c.require(isinstance(items, list) and len(items) <= 256, 'Bounded native turn items required')
        for item in items:
            if isinstance(item, dict) and item.get('type') == 'agentMessage':
                text = item.get('text')
                if isinstance(text, str) and challenge['marker'] in text.splitlines():
                    a.reference(identity)
                    a.reference(turn.get('id'))
                    matches.append((identity, turn['id']))
                    break
    c.require(matches, 'SOURCE_IDENTITY_UNRESOLVED: no current source turn matches')
    c.require(len(matches) == 1, 'SOURCE_IDENTITY_AMBIGUOUS: never choose a parent, title or latest chat')
    identity, turn_id = matches[0]
    reference = observation['tool_reference'] + ' | source-challenge=' + challenge['nonce'] + ' | source-turn=' + turn_id
    a.reference(reference)
    return {'action': 'SOURCE_IDENTITY_QUALIFIED',
            'source': {'environment': environment, 'project_id': project, 'thread_id': identity,
                       'authority': authority_reference, 'qualification_reference': reference},
            'source_turn_id': turn_id, 'auto_introspection_used': False,
            'observation_authenticated_by_helper': False, 'dispatch_performed': False}


def roots(contract, canonical, authority_root):
    canonical = a.regular(canonical, directory=True)
    contract = a.regular(contract)
    c.require(contract == canonical / c.CONTRACT, 'Actual canonical contract required')
    config = c.load(contract)
    c.validate_contract(config)
    c.require(config['schema_version'] == 5, 'Source qualification requires contract v5')
    _, storage, paths = c.dc_endpoint(config['transport']['primary']['locator'])
    root = a.regular(authority_root, directory=True)
    c.require(root == Path(paths.join(storage, config['project_id'], '.authority')).resolve()
              and not root.is_relative_to(canonical) and not canonical.is_relative_to(Path(storage).resolve()),
              'Source proofs belong in pilot authority, outside received data and the canon')
    return config, root


def save_new(path, root, value):
    c.require(path.is_absolute() and path.parent == root, 'New output must be directly under pilot authority')
    c.write_new(path, c.encode(value))


def main(argv=None):
    c.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('issue', 'qualify'):
        p = sub.add_parser(name)
        for key in ('contract', 'canonical-root', 'authority-root', 'output'):
            p.add_argument('--' + key, type=Path, required=True)
        p.add_argument('--request-sha256', required=True)
        if name == 'issue':
            p.add_argument('--environment', choices=('work', 'codex'), required=True)
        else:
            for key in ('challenge', 'observation'):
                p.add_argument('--' + key, type=Path, required=True)
                p.add_argument('--' + key + '-sha256', required=True)
            p.add_argument('--authority-reference', required=True)
    args = parser.parse_args(argv)
    try:
        config, root = roots(args.contract, args.canonical_root, args.authority_root)
        if args.command == 'issue':
            value = issue(args.environment, config['decision_sync']['participants'][args.environment]['project_id'],
                          args.request_sha256)
            save_new(args.output, root, value)
            result = {'action': 'SOURCE_QUALIFICATION_REQUIRED', 'challenge_file': str(args.output),
                      'marker': value['marker'], 'dispatch_performed': False}
        else:
            challenge, challenge_pin = a.pinned(args.challenge, root, args.challenge_sha256)
            observation, observation_pin = a.pinned(args.observation, root, args.observation_sha256)
            result = resolve(config, challenge, observation, args.request_sha256, args.authority_reference)
            result['source']['qualification_reference'] += ' | observation-sha256=' + observation_pin['sha256']
            a.reference(result['source']['qualification_reference'])
            save_new(args.output, root, result['source'])
            result.update(source_file=str(args.output), challenge=challenge_pin, observation=observation_pin)
        print(c.encode(result).decode('utf-8'), end='')
        return 0
    except (c.SyncError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print('SYNCPILOT SOURCE REFUSED: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
