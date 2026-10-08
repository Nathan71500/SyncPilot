"""SIMULATIONS only: public mission commands, Git fixtures and official-RPC doubles.

No native message, actual receiver, canonical business source or credentials.
"""
import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import test_authority as fixtures
import test_codex_bridge as bridge_fixtures

SCRIPT = Path(__file__).resolve().parents[1] / 'syncpilot/skills/syncpilot-dc/scripts/syncpilot_mission.py'
spec = importlib.util.spec_from_file_location('mission_tests', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
c = m.c


class FakeRpc(bridge_fixtures.FakeRpc):
    def call(self, method, params, timeout=30):
        try:
            result = super().call(method, params, timeout)
            if method == 'thread/turns/list' and hasattr(self, 'latest_turn_id'):
                result['data'][0]['id'] = self.latest_turn_id
            return result
        except bridge_fixtures.b.RpcRefusal as exc: raise m.b.RpcRefusal(exc.method, exc.error)
        except bridge_fixtures.c.SyncError as exc: raise c.SyncError(str(exc))


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.AuthorityTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.canonical = self.f.canonical; self.ar = self.f.authority_root
        self.f.config['repository'] = 'https://example.invalid/SIMULATED-fixture.git'
        self.f.config['reference_branch'] = 'main'
        self.f.contract.write_bytes(c.encode(self.f.config))
        self.git('init', '-b', 'main'); self.git('config', 'user.name', 'SIMULATED')
        self.git('config', 'user.email', 'simulation@example.invalid')
        (self.canonical / 'docs.txt').write_text('SIMULATED canonical é 🧩\n', encoding='utf-8')
        self.git('add', '.'); self.git('commit', '-m', 'SIMULATED initial canonical')
        self.git('remote', 'add', 'origin', self.f.config['repository'])
        self.f.mission['contract_sha256'] = c.digest(self.f.contract.read_bytes())
        self.f.build()
        self.dirty = self.canonical / 'DIRTY-OWNED.md'
        self.dirty.write_text('SIMULATED attributed change\n', encoding='utf-8')
        self.ownership = {'format': 'SYNCPILOT-MISSION-OWNERSHIP', 'schema_version': 1,
                          'reference': 'SIMULATED pilot qualified current changes',
                          'files': [{'path': self.dirty.name, 'owner': 'SIMULATED authorized mission',
                                     'reference': 'SIMULATED original attribution'}]}
        self.ownership_path = self.ar / 'ownership.json'; self.ownership_path.write_bytes(c.encode(self.ownership))
        self.snapshot_path = self.ar / 'snapshot.json'
        self.snapshot = m.source_snapshot(self.f.contract, self.canonical, self.ownership, 'SIMULATED exact source observation')
        self.snapshot_path.write_bytes(c.encode(self.snapshot))
        self.text = self.ar / 'mission.txt'; self.text.write_text('Mission française é 🧩 : réception seulement.\n', encoding='utf-8')
        self.request = {'format': 'SYNCPILOT-TECHNICAL-MISSION-REQUEST', 'schema_version': 1,
                        'contract': str(self.f.contract), 'canonical_root': str(self.canonical), 'source': self.f.source,
                        'authority': {'grant': str(self.f.grant_path), 'grant_sha256': c.digest(self.f.grant_path.read_bytes()),
                                      'mission': str(self.f.mission_path), 'mission_sha256': c.digest(self.f.mission_path.read_bytes()),
                                      'authority_root': str(self.ar)},
                        'mission': m.binding(self.text), 'snapshot': {'path': str(self.snapshot_path),
                        'sha256': c.digest(self.snapshot_path.read_bytes())}, 'mode': 'reception-only'}
        self.request_path = self.ar / 'request.json'; self.request_path.write_bytes(c.encode(self.request))
        self.executable = self.root / 'SIMULATED-codex.exe'; self.executable.write_bytes(b'SIMULATED official CLI')
        self.clients = []

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.canonical), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def command(self, *args, **changes):
        def factory(exe, cwd):
            client = FakeRpc(exe, cwd)
            for key, value in changes.items(): setattr(client, key, value)
            self.clients.append(client); return client
        out = io.StringIO(); err = io.StringIO()
        with (patch.object(m.b, 'Rpc', factory), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            # The bridge's default factory is definition-bound; inject at the
            # public dispatch seam while retaining the entire common run engine.
            original = m.dispatch
            def dispatch(*values, **options):
                options['rpc_factory'] = factory
                return original(*values, **options)
            with patch.object(m, 'dispatch', dispatch): code = m.main(list(args))
        frames = [c.decode(line) for line in out.getvalue().splitlines() if line.strip()]
        return code, frames[-1] if frames else None, err.getvalue()

    def prepare(self):
        self.request_path.write_bytes(c.encode(self.request))
        code, result, error = self.command('prepare', '--request', str(self.request_path))
        self.assertEqual(code, 0, error)
        self.operation = Path(result['operation_file']); self.op, self.oproot = m.load_operation(self.operation)
        return result

    def dispatch(self, **changes):
        return self.command('dispatch', '--operation', str(self.operation), '--codex', str(self.executable), **changes)

    def finish(self):
        self.prepare(); code, result, error = self.dispatch(); self.assertEqual(code, 0, error)
        self.assertEqual(result['action'], 'FINISHED_AWAITING_PARENT_CONFIRM')
        code, received, error = self.command('receive', '--operation', str(self.operation),
                                             '--thread-id', result['state']['thread_id'], '--turn-id', result['state']['turn_id'])
        self.assertEqual(code, 0, error)
        self.receipt = received['receipt']; return result

    def parent_observation(self, **changes):
        state = m.collect(self.operation)['state']; receipt = m.binding(self.oproot / 'receipt.json')
        value = {'format': 'SYNCPILOT-MISSION-PARENT-OBSERVATION', 'schema_version': 1,
                 'observed_at': datetime.now(timezone.utc).isoformat(), 'qualification_reference': 'SIMULATED actual parent native finish and readback',
                 'operation_id': self.op['operation_id'], 'nonce': self.op['nonce'], 'project_id': self.op['project_id'],
                 'observer_environment': 'work', 'thread_id': state['thread_id'], 'turn_id': state['turn_id'],
                 'native_finished': True, 'receipt_sha256': receipt['sha256'], 'receipt_size': receipt['size'],
                 'source_snapshot_sha256': self.receipt['source_snapshot_sha256'], 'source_preserved': True, 'parent_verified': True}
        value.update(changes); path = self.ar / 'parent.json'; path.write_bytes(c.encode(value)); return path

    def confirm(self, **changes):
        path = self.parent_observation(**changes)
        return self.command('confirm', '--operation', str(self.operation), '--observation', str(path),
                            '--observation-sha256', c.digest(path.read_bytes()))

    def second(self):
        self.previous_op = self.op; self.previous_root = self.oproot
        self.f.mission['mission_id'] = 'SIMULATED-SECOND'; self.f.mission_path.write_bytes(c.encode(self.f.mission))
        self.request['authority']['mission_sha256'] = c.digest(self.f.mission_path.read_bytes())
        self.prepare()

    def recovery(self, latest='SIMULATED-turn', **changes):
        value = {'format': 'SYNCPILOT-CODEX-RECEIVER-AVAILABILITY', 'schema_version': 2,
                 'observed_at': datetime.now(timezone.utc).isoformat(), 'observer_environment': 'codex',
                 'qualification_reference': 'SIMULATED independent owner tools',
                 'authority_reference': self.op['bridge_request']['authority']['reference'], 'project_id': self.op['project_id'],
                 'codex_project_id': 'test:codex', 'thread_id': 'SIMULATED-receiver', 'canonical_root': str(self.canonical),
                 'active_turn_id': None, 'pending_launch': False, 'native_message_channel': 'unavailable',
                 'native_channel_reference': 'SIMULATED current runtime channel unavailable',
                 'last_turn_id': latest, 'last_turn_status': 'completed', 'last_activity_reference': 'SIMULATED independently finished development turn',
                 'completed_job': str(self.previous_root / 'codex-dispatch'), 'parent_confirmed': True,
                 'parent_confirmation_reference': 'SIMULATED exact parent confirmation readback',
                 'confirmation_journal': str(self.previous_root / 'confirmation.json'),
                 'confirmation_journal_sha256': c.digest((self.previous_root / 'confirmation.json').read_bytes()),
                 'previous_confirmation_kind': 'technical-mission'}
        value.update(changes); path = self.ar / 'availability.json'; path.write_bytes(c.encode(value)); return path

    def test_public_snapshot_prepare_exact_dirty_sources_and_no_canonical_write(self):
        before = self.git('status', '--porcelain=v1', '-z', '--untracked-files=all')
        code, result, error = self.command('snapshot', '--contract', str(self.f.contract), '--canonical-root', str(self.canonical),
                                          '--ownership', str(self.ownership_path), '--ownership-sha256', c.digest(self.ownership_path.read_bytes()),
                                          '--qualification-reference', 'SIMULATED exact source observation')
        self.assertEqual(code, 0, error); self.assertEqual(result, self.snapshot)
        prep = self.prepare(); self.assertEqual(prep['action'], 'PREPARED'); self.assertEqual(len(prep['nonce']), 32)
        self.assertEqual(self.git('status', '--porcelain=v1', '-z', '--untracked-files=all'), before)
        self.assertFalse(self.clients); self.assertFalse((self.oproot / 'journal.json').exists())

    def test_unknown_or_missing_dirty_ownership_refused(self):
        for ownership in ({**self.ownership, 'files': []}, {**self.ownership, 'files': self.ownership['files'] * 2}):
            with self.subTest(ownership=ownership), self.assertRaises(c.SyncError):
                m.source_snapshot(self.f.contract, self.canonical, ownership, 'SIMULATED')
        (self.canonical / 'FOREIGN.md').write_text('SIMULATED other mission')
        code, _, error = self.command('prepare', '--request', str(self.request_path))
        self.assertEqual(code, 2); self.assertIn('attribution', error); self.assertFalse(self.clients)

    def test_changed_head_diff_dirty_bytes_or_remote_refuse_before_dispatch(self):
        self.prepare(); self.dirty.write_text('SIMULATED changed bytes')
        code, _, error = self.dispatch(); self.assertEqual(code, 2); self.assertFalse(self.clients)
        self.assertIn('changed after', error)

    def test_mission_and_authority_pins_strict_before_prepare(self):
        cases = []
        for key in ('grant_sha256', 'mission_sha256'):
            request = copy.deepcopy(self.request); request['authority'][key] = '0' * 64; cases.append(request)
        request = copy.deepcopy(self.request); request['mission']['sha256'] = '0' * 64; cases.append(request)
        request = copy.deepcopy(self.request); request['mission']['size'] = True; cases.append(request)
        request = copy.deepcopy(self.request); request['mode'] = 'execute'; cases.append(request)
        request = copy.deepcopy(self.request); request['schema_version'] = True; cases.append(request)
        for request in cases:
            with self.subTest(request=request), self.assertRaises(c.SyncError): m.prepare(request)
        self.assertFalse(self.clients)

    def test_invalid_utf8_oversize_and_received_authority_refused(self):
        for raw in (b'\xff', b'x' * 50_001):
            self.text.write_bytes(raw); request = {**self.request, 'mission': m.binding(self.text)}
            with self.subTest(size=len(raw)), self.assertRaises((c.SyncError, UnicodeError)): m.prepare(request)
        self.text.write_bytes(b'SIMULATED')
        outside = self.ar.parent / 'received-mission.txt'; outside.write_bytes(b'SIMULATED')
        with self.assertRaises(c.SyncError): m.prepare({**self.request, 'mission': m.binding(outside)})

    def test_full_public_reception_receipt_collect_and_technical_confirm(self):
        self.finish(); code, result, error = self.confirm(); self.assertEqual(code, 0, error)
        self.assertEqual(result['action'], 'CONFIRMED'); self.assertEqual(result['confirmation']['decisions_status'], 'NOT_ASSERTED')
        self.assertEqual(result['confirmation']['mirror_status'], 'NOT_ASSERTED')
        self.assertFalse((self.oproot / 'decisions.json').exists())
        self.assertEqual(self.receipt['limits'], m.LIMITS)
        self.assertIn('no-tts', self.receipt['limits'])
        started = [params for name, params in self.clients[0].calls if name == 'turn/start'][0]
        self.assertEqual(started['sandboxPolicy']['writableRoots'], [str(self.oproot)])
        self.assertFalse(started['sandboxPolicy']['networkAccess']); self.assertNotIn('model', started)
        self.assertNotIn('reasoningEffort', started)

    def test_double_prepare_dispatch_collect_after_source_changed_never_replays(self):
        self.finish(); calls = len(self.clients); self.dirty.write_text('SIMULATED later independent work')
        self.assertEqual(self.prepare()['action'], 'COLLECT_PREPARED')
        code, result, error = self.dispatch(); self.assertEqual(code, 0, error)
        self.assertEqual(result['action'], 'COLLECT_EXISTING'); self.assertEqual(len(self.clients), calls)
        self.assertFalse(result['dispatch_repeated'])

    def test_busy_receiver_and_shared_owner_block_before_turn(self):
        self.prepare(); code, result, _ = self.dispatch(receiver_status='active')
        self.assertEqual(code, 2); self.assertFalse(result['state']['dispatch_attempted'])
        self.assertFalse(any(name == 'turn/start' for name, _ in self.clients[0].calls))

    def test_lost_turn_start_response_keeps_owner_and_second_invocation_only_collects(self):
        self.prepare(); code, result, _ = self.dispatch(failure='turn/start')
        self.assertEqual(code, 2); self.assertTrue(result['state']['dispatch_attempted']); self.assertIsNone(result['state']['turn_id'])
        self.assertTrue((self.ar.parent / '.receivers/codex/OWNER.json').exists())
        calls = len(self.clients); code, result, _ = self.dispatch(); self.assertEqual(code, 0)
        self.assertEqual(result['action'], 'FOLLOW_EXISTING_DISPATCH'); self.assertEqual(len(self.clients), calls)

    def test_lost_creation_response_keeps_owner_and_never_recreates(self):
        self.prepare(); _, result, _ = self.dispatch(failure='thread/start')
        self.assertTrue(result['state']['creation_attempted']); self.assertFalse(result['state']['dispatch_attempted'])
        calls = len(self.clients); _, result, _ = self.dispatch(); self.assertEqual(len(self.clients), calls)
        self.assertEqual(result['action'], 'FOLLOW_EXISTING_DISPATCH')

    def test_generic_resume_refusal_is_preserved_and_never_rolls_over(self):
        self.finish(); self.second()
        refusal = {'code': -32600, 'message': 'SIMULATED generic refusal', 'data': {'retain': 'é'}}
        code, result, _ = self.dispatch(resume_error=refusal); self.assertEqual(code, 2)
        self.assertEqual(result['state']['official_error']['error'], refusal)
        self.assertFalse(any(name in ('thread/start', 'turn/start') for name, _ in self.clients[-1].calls))

    def test_exact_writer_without_observation_blocks_without_new_approval_or_duplicate(self):
        self.finish(); self.second(); code, result, _ = self.dispatch(resume_error={'code': -32600, 'message': 'Thread already has an active writer'})
        self.assertEqual(code, 2); self.assertIn('independent current', result['state']['error'])
        self.assertFalse(result['state']['creation_attempted']); self.assertFalse(result['state']['dispatch_attempted'])

    def test_fresh_rollover_after_confirmed_technical_mission_preserves_opnonce_and_registry_history(self):
        self.finish(); self.confirm(); self.second(); observation = self.recovery()
        args = ('dispatch', '--operation', str(self.operation), '--codex', str(self.executable), '--recovery-observation', str(observation),
                '--recovery-observation-sha256', c.digest(observation.read_bytes()))
        code, result, error = self.command(*args, resume_error={'code': -32600, 'message': 'Thread already has an active writer'},
                                           created_thread_id='SIMULATED-replacement')
        self.assertEqual(code, 0, error); self.assertEqual(result['state']['thread_id'], 'SIMULATED-replacement')
        self.assertEqual(result['state']['operation_id'], self.op['operation_id']); self.assertEqual(result['state']['nonce'], self.op['nonce'])
        registry = c.load(self.ar.parent / '.receivers/codex/RECEIVER.json')
        self.assertEqual(registry['replaces_thread_id'], 'SIMULATED-receiver')
        self.assertEqual(len(list((self.ar.parent / '.receivers/codex/history').glob('*.json'))), 1)

    def test_latest_finished_development_separate_from_last_confirmed_sync(self):
        self.finish(); self.confirm(); self.second(); observation = self.recovery(latest='SIMULATED-dev-turn')
        class DevRpc(FakeRpc):
            def call(client, name, params, timeout=30):
                value = super().call(name, params, timeout)
                if name == 'thread/turns/list': value['data'][0]['id'] = 'SIMULATED-dev-turn'
                return value
        def factory(exe, cwd):
            client = DevRpc(exe, cwd); client.resume_error = {'code': -32600, 'message': 'Thread already has an active writer'}
            client.created_thread_id = 'SIMULATED-replacement'; return client
        with contextlib.redirect_stdout(io.StringIO()):
            result = m.dispatch(self.operation, self.executable, rpc_factory=factory, recovery_observation=observation,
                                recovery_observation_sha256=c.digest(observation.read_bytes()))
        self.assertEqual(result['action'], 'FINISHED_AWAITING_PARENT_CONFIRM')
        proof = c.load(self.oproot / 'codex-dispatch/receiver-recovery.json')
        self.assertEqual(proof['official_latest_turn']['id'], 'SIMULATED-dev-turn')
        self.assertEqual(proof['external_observation']['previous_confirmation_kind'], 'technical-mission')

    def test_v2_previous_decisions_sync_does_not_have_to_be_latest_development_turn(self):
        f = bridge_fixtures.BridgeTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.run_bridge(); f.second_operation(); path = f.recovery_observation()
        observed = c.load(path); observed.update(schema_version=2, previous_confirmation_kind='decisions',
                                                last_activity_reference='SIMULATED finished later development', last_turn_id='SIMULATED-dev')
        path.write_bytes(c.encode(observed))
        class DevRpc(FakeRpc):
            def call(client, method, params, timeout=30):
                result = super().call(method, params, timeout)
                if method == 'thread/turns/list': result['data'][0]['id'] = 'SIMULATED-dev'
                return result
        receiver = c.load(f.oproot.parent / '.receivers/codex/RECEIVER.json')
        observed.update(project_id=receiver['project_id'], codex_project_id=receiver['codex_project_id'],
                        thread_id=receiver['thread_id'], canonical_root=str(f.canonical.resolve()))
        path.write_bytes(c.encode(observed))
        result = m.b.replacement_observation(path, c.digest(path.read_bytes()), f.request, receiver,
                                            f.canonical.resolve(), f.oproot.parent.resolve(), DevRpc(self.executable, f.canonical.resolve()))
        self.assertEqual(result['official_latest_turn']['id'], 'SIMULATED-dev')
        self.assertEqual(result['external_observation']['previous_confirmation_kind'], 'decisions')

    def test_busy_uncertain_stale_and_unconfirmed_rollover_rejected_before_create(self):
        self.finish(); self.confirm(); self.second()
        for changes in ({'active_turn_id': 'SIMULATED-busy'}, {'pending_launch': True}, {'parent_confirmed': False},
                        {'observed_at': (datetime.now(timezone.utc) - timedelta(seconds=121)).isoformat()}):
            with self.subTest(changes=changes):
                observation = self.recovery(**changes)
                existing = c.load(self.ar.parent / '.receivers/codex/RECEIVER.json')
                client = FakeRpc(self.executable, self.canonical)
                with self.assertRaises(c.SyncError):
                    m.b.replacement_observation(observation, c.digest(observation.read_bytes()), self.op['bridge_request'],
                                                existing, self.canonical, self.ar.parent, client)
                self.assertFalse(any(name == 'thread/start' for name, _ in client.calls))

    def test_confirmation_requires_terminal_receipt_and_actual_parent_observations(self):
        self.finish()
        for changes in ({'native_finished': False}, {'parent_verified': False}, {'receipt_sha256': '0' * 64},
                        {'turn_id': 'foreign'}, {'source_preserved': False}, {'schema_version': True}):
            with self.subTest(changes=changes):
                code, _, _ = self.confirm(**changes); self.assertEqual(code, 2)
                self.assertFalse((self.oproot / 'confirmation.json').exists())
        self.dirty.write_text('SIMULATED later source change'); code, _, _ = self.confirm(); self.assertEqual(code, 2)

    def test_missing_altered_foreign_receipt_and_failed_native_turn_cannot_confirm(self):
        self.prepare(); _, result, _ = self.dispatch(fail_turn=True)
        self.assertEqual(result['action'], 'RECEIVER_FAILED')
        code, _, _ = self.command('receive', '--operation', str(self.operation), '--thread-id', 'SIMULATED-receiver', '--turn-id', 'SIMULATED-turn')
        self.assertEqual(code, 2); self.assertFalse((self.oproot / 'receipt.json').exists())

    def test_native_only_blocks_cli_before_server_creation(self):
        self.request['channel_policy'] = 'native-only'; self.prepare(); code, _, error = self.dispatch()
        self.assertEqual(code, 2); self.assertIn('native-only', error); self.assertFalse(self.clients)

    def native_availability(self, **changes):
        value = {'format': 'SYNCPILOT-MISSION-NATIVE-AVAILABILITY', 'schema_version': 1,
                 'observed_at': datetime.now(timezone.utc).isoformat(), 'qualification_reference': 'SIMULATED actual native owner tools',
                 'operation_id': self.op['operation_id'], 'nonce': self.op['nonce'], 'project_id': self.op['project_id'],
                 'codex_project_id': 'test:codex', 'thread_id': 'SIMULATED-native', 'canonical_root': str(self.canonical),
                 'active_turn_id': None, 'pending_launch': False, 'native_message_channel': 'available',
                 'native_channel_reference': 'SIMULATED actual owner message tool'}
        value.update(changes); path = self.ar / 'native.json'; path.write_bytes(c.encode(value)); return path

    def test_native_reservation_receive_actual_turn_and_collect_no_replay(self):
        self.request['channel_policy'] = 'native-only'; self.prepare(); path = self.native_availability()
        args = ('dispatch', '--operation', str(self.operation), '--native-observation', str(path), '--native-observation-sha256', c.digest(path.read_bytes()))
        code, result, error = self.command(*args); self.assertEqual(code, 0, error)
        self.assertEqual(result['action'], 'NATIVE_MESSAGE_REQUIRED')
        code, result, _ = self.command(*args); self.assertEqual(code, 0); self.assertEqual(result['action'], 'FOLLOW_EXISTING_DISPATCH')
        self.assertNotIn('prompt', result)
        code, received, error = self.command('receive', '--operation', str(self.operation), '--thread-id', 'SIMULATED-native', '--turn-id', 'SIMULATED-native-turn')
        self.assertEqual(code, 0, error); self.receipt = received['receipt']
        result = {'format': 'SYNCPILOT-MISSION-NATIVE-RESULT', 'schema_version': 1,
                  'observed_at': datetime.now(timezone.utc).isoformat(), 'qualification_reference': 'SIMULATED actual owner wait final',
                  'operation_id': self.op['operation_id'], 'nonce': self.op['nonce'], 'project_id': self.op['project_id'],
                  'thread_id': 'SIMULATED-native', 'turn_id': 'SIMULATED-native-turn',
                  'completion': {'threadId': 'SIMULATED-native', 'turn': {'id': 'SIMULATED-native-turn', 'status': 'completed', 'error': None}},
                  'messages': [{'type': 'agentMessage', 'text': 'SIMULATED reception finished'}]}
        path = self.ar / 'native-result.json'; path.write_bytes(c.encode(result))
        code, result, error = self.command('collect', '--operation', str(self.operation), '--native-result', str(path),
                                           '--native-result-sha256', c.digest(path.read_bytes()))
        self.assertEqual(code, 0, error); self.assertEqual(result['state']['status'], 'FINISHED')
        self.assertIsNone(result['state']['server_exit_code']); self.assertFalse(self.clients)
        code, confirmed, error = self.confirm(); self.assertEqual(code, 0, error); self.assertEqual(confirmed['action'], 'CONFIRMED')

    def test_native_busy_uncertain_actor_cannot_reserve(self):
        self.prepare()
        for changes in ({'active_turn_id': 'active'}, {'pending_launch': True}, {'native_message_channel': 'unavailable'}, {'codex_project_id': 'foreign'}):
            path = self.native_availability(**changes)
            code, _, _ = self.command('dispatch', '--operation', str(self.operation), '--native-observation', str(path),
                                      '--native-observation-sha256', c.digest(path.read_bytes()))
            self.assertEqual(code, 2); self.assertFalse((self.ar.parent / '.receivers/codex/OWNER.json').exists())

    def test_strict_duplicate_json_operation_and_parent_observation_refused(self):
        self.finish(); path = self.parent_observation()
        raw = path.read_bytes().replace(b'"parent_verified":true', b'"parent_verified":false,"parent_verified":true')
        # The canonical encoder may include a space after ':'; use a syntactic insertion instead.
        raw = b'{"parent_verified":false,' + path.read_bytes()[1:]
        path.write_bytes(raw)
        code, _, _ = self.command('confirm', '--operation', str(self.operation), '--observation', str(path),
                                  '--observation-sha256', c.digest(raw)); self.assertEqual(code, 2)
        raw = b'{"nonce":"0",' + self.operation.read_bytes()[1:]; self.operation.write_bytes(raw)
        code, _, _ = self.command('collect', '--operation', str(self.operation)); self.assertEqual(code, 2)

    def test_existing_confirmation_revalidates_receipt_completion_and_parent_pin(self):
        self.finish(); self.confirm()
        confirmation_path = self.oproot / 'confirmation.json'
        job, _, _ = m.current_state(self.op, self.oproot)
        paths = [self.oproot / 'receipt.json', job / 'turn-completed.json', self.ar / 'parent.json', confirmation_path]
        for path in paths:
            with self.subTest(path=path.name):
                raw = path.read_bytes(); data = c.load(path)
                if path == confirmation_path: data['status'] = 'VERIFIED'
                elif path.name == 'receipt.json': data['source_preserved'] = False
                elif path.name == 'parent.json': data['parent_verified'] = False
                else: data['turn']['status'] = 'failed'
                path.write_bytes(c.encode(data))
                code, _, _ = self.command('confirm', '--operation', str(self.operation), '--observation', str(self.ar / 'parent.json'),
                                          '--observation-sha256', '0' * 64)
                self.assertEqual(code, 2)
                code, _, _ = self.command('collect', '--operation', str(self.operation)); self.assertEqual(code, 2)
                path.write_bytes(raw)
        self.dirty.write_text('SIMULATED later independent authorized work')
        code, result, error = self.command('confirm', '--operation', str(self.operation), '--observation', str(self.ar / 'parent.json'),
                                           '--observation-sha256', '0' * 64)
        self.assertEqual(code, 0, error); self.assertEqual(result['action'], 'COLLECT_CONFIRMED')

    def test_native_receipt_rejected_source_preserves_unadopted_turn(self):
        self.prepare(); path = self.native_availability()
        self.command('dispatch', '--operation', str(self.operation), '--native-observation', str(path),
                     '--native-observation-sha256', c.digest(path.read_bytes()))
        self.dirty.write_text('SIMULATED source changed before native receive')
        code, _, _ = self.command('receive', '--operation', str(self.operation), '--thread-id', 'SIMULATED-native', '--turn-id', 'SIMULATED-native-turn')
        self.assertEqual(code, 2)
        _, state, _ = m.current_state(self.op, self.oproot); self.assertIsNone(state['turn_id'])
        self.assertFalse((self.oproot / 'receipt.json').exists())

    def test_native_foreign_owner_refuses_terminal_promotion_before_any_result_write(self):
        self.prepare(); path = self.native_availability()
        self.command('dispatch', '--operation', str(self.operation), '--native-observation', str(path),
                     '--native-observation-sha256', c.digest(path.read_bytes()))
        owner_path = self.ar.parent / '.receivers/codex/OWNER.json'
        owner = c.load(owner_path); owner['nonce'] = '0' * 32; owner_path.write_bytes(c.encode(owner))
        value = {'format': 'SYNCPILOT-MISSION-NATIVE-RESULT', 'schema_version': 1,
                 'observed_at': datetime.now(timezone.utc).isoformat(), 'qualification_reference': 'SIMULATED actual owner terminal',
                 'operation_id': self.op['operation_id'], 'nonce': self.op['nonce'], 'project_id': self.op['project_id'],
                 'thread_id': 'SIMULATED-native', 'turn_id': 'SIMULATED-native-turn',
                 'completion': {'threadId': 'SIMULATED-native', 'turn': {'id': 'SIMULATED-native-turn', 'status': 'completed', 'error': None}}, 'messages': []}
        result_path = self.ar / 'native-result.json'; result_path.write_bytes(c.encode(value))
        code, _, _ = self.command('collect', '--operation', str(self.operation), '--native-result', str(result_path),
                                  '--native-result-sha256', c.digest(result_path.read_bytes()))
        self.assertEqual(code, 2); self.assertEqual(c.load(owner_path), owner)
        job, state, _ = m.current_state(self.op, self.oproot)
        self.assertEqual(state['status'], 'OPEN'); self.assertFalse(state['agent_finished_observed'])
        self.assertFalse((job / 'turn-completed.json').exists())

    def test_snapshot_volume_is_bounded_before_dirty_files_read(self):
        original = c.git
        def huge(root, *args, **options):
            if 'diff' in args: return b'x' * (m.MAX_SNAPSHOT_BYTES + 1)
            return original(root, *args, **options)
        with patch.object(c, 'git', huge), self.assertRaises(c.SyncError):
            m.source_snapshot(self.f.contract, self.canonical, self.ownership, 'SIMULATED')

    def test_exact_writer_explicit_repair_keeps_original_refusal_and_same_operation(self):
        self.finish(); self.confirm(); self.second()
        _, blocked, _ = self.dispatch(resume_error={'code': -32600, 'message': 'Thread already has an active writer'})
        original_state = (self.oproot / 'codex-dispatch/state.json').read_bytes()
        observation = self.recovery()
        code, result, error = self.command('dispatch', '--operation', str(self.operation), '--codex', str(self.executable),
                                           '--recover-native-writer', '--recovery-observation', str(observation),
                                           '--recovery-observation-sha256', c.digest(observation.read_bytes()),
                                           resume_error={'code': -32600, 'message': 'Thread already has an active writer'},
                                           created_thread_id='SIMULATED-repair')
        self.assertEqual(code, 0, error); self.assertEqual(result['state']['thread_id'], 'SIMULATED-repair')
        self.assertEqual(result['state']['nonce'], blocked['state']['nonce'])
        self.assertEqual((self.oproot / 'codex-dispatch/state.json').read_bytes(), original_state)

    def test_qualified_native_proxy_reuses_receiver_after_exact_writer(self):
        self.finish(); self.second()
        temporary = FakeRpc(self.executable, self.canonical)
        temporary.resume_error = {'code': -32600, 'message': 'Thread already has an active writer'}
        native = FakeRpc(self.executable, self.canonical)
        with contextlib.redirect_stdout(io.StringIO()):
            result = m.dispatch(self.operation, self.executable, rpc_factory=lambda exe, cwd: temporary,
                                native_socket=self.root / 'SIMULATED-observed.sock', native_rpc_factory=lambda exe, cwd: native)
        self.assertEqual(result['action'], 'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertEqual(result['state']['channel'], 'official-native-proxy')
        self.assertFalse(result['state']['creation_attempted'])
        self.assertFalse(any(name == 'thread/start' for name, _ in native.calls))

    def test_resealed_received_mission_or_identity_is_rejected_against_original_request(self):
        self.prepare(); _, state, _ = self.dispatch()
        original = self.operation.read_bytes(); mission_raw = (self.oproot / 'mission.txt').read_bytes()
        (self.oproot / 'mission.txt').write_bytes(b'SIMULATED substituted mission')
        op = c.load(self.operation); op['mission'] = m.binding(self.oproot / 'mission.txt')
        op['integrity_sha256'] = m.seal(op); self.operation.write_bytes(c.encode(op))
        code, _, _ = self.command('receive', '--operation', str(self.operation), '--thread-id', 'SIMULATED-receiver', '--turn-id', 'SIMULATED-turn')
        self.assertEqual(code, 2); self.assertFalse((self.oproot / 'receipt.json').exists())
        self.operation.write_bytes(original); (self.oproot / 'mission.txt').write_bytes(mission_raw)
        op = c.load(self.operation); op['request']['source']['thread_id'] = 'SIMULATED other caller'
        op['request_sha256'] = c.digest(c.encode(op['request'])); op['integrity_sha256'] = m.seal(op)
        self.operation.write_bytes(c.encode(op))
        code, _, _ = self.command('collect', '--operation', str(self.operation)); self.assertEqual(code, 2)

    def observe_args(self, **overrides):
        values = {'operation': self.operation, 'codex': self.executable,
                  'completed-job': self.previous_root / 'codex-dispatch',
                  'confirmation': self.previous_root / 'confirmation.json',
                  'confirmation-sha256': c.digest((self.previous_root / 'confirmation.json').read_bytes()),
                  'confirmation-kind': 'technical-mission', 'parent-confirmation-reference': 'SIMULATED actual independent parent confirmation',
                  'observer-environment': 'work', 'qualification-reference': 'SIMULATED current caller and receiver observed',
                  'native-channel': 'unavailable', 'native-channel-reference': 'SIMULATED actual Work catalogue has no owner messaging tool',
                  'evidence-output': self.ar / 'readonly-evidence.json', 'output': self.ar / 'readonly-availability.json'}
        values.update(overrides)
        args = ['observe']
        for key, value in values.items(): args.extend(['--' + key, str(value)])
        return args

    def test_public_observer_reads_official_latest_development_only_and_preserves_dirty_canon(self):
        self.finish(); self.confirm(); self.second()
        index = (self.canonical / '.git/index').read_bytes(); canonical = self.dirty.read_bytes()
        registry = (self.ar.parent / '.receivers/codex/RECEIVER.json').read_bytes()
        code, observed, error = self.command(*self.observe_args(), latest_turn_id='SIMULATED-latest-dev')
        self.assertEqual(code, 0, error)
        self.assertEqual(observed['format'], 'SYNCPILOT-CODEX-RECEIVER-AVAILABILITY'); self.assertEqual(observed['schema_version'], 2)
        self.assertEqual(observed['last_turn_id'], 'SIMULATED-latest-dev')
        self.assertEqual(observed['previous_confirmation_kind'], 'technical-mission')
        self.assertEqual(c.load(self.ar / 'readonly-availability.json'), observed)
        proof = c.load(self.ar / 'readonly-evidence.json')
        self.assertIn('#sha256=' + c.digest((self.ar / 'readonly-evidence.json').read_bytes()), observed['last_activity_reference'])
        self.assertFalse(proof['writer_acquired']); self.assertFalse(proof['dispatch_performed'])
        self.assertFalse(proof['human_authority_authenticated_by_helper'])
        self.assertEqual([name for name, _ in self.clients[-1].calls], ['thread/read', 'thread/turns/list'])
        self.assertEqual(proof['reads']['server_exit_code'], 0)
        self.assertEqual(self.dirty.read_bytes(), canonical); self.assertEqual((self.canonical / '.git/index').read_bytes(), index)
        self.assertEqual((self.ar.parent / '.receivers/codex/RECEIVER.json').read_bytes(), registry)
        self.assertFalse((self.oproot / 'codex-dispatch').exists())

    def test_public_observer_checks_parent_pin_before_reads_or_output(self):
        self.finish(); self.confirm(); self.second(); count = len(self.clients)
        code, _, _ = self.command(*self.observe_args(**{'confirmation-sha256': '0' * 64}))
        self.assertEqual(code, 2); self.assertEqual(len(self.clients), count)
        self.assertFalse((self.ar / 'readonly-evidence.json').exists())

    def test_public_observer_preserves_busy_unknown_pending_or_changed_registry(self):
        self.finish(); self.confirm(); self.second()
        for changes in ({'receiver_status': 'active'}, {'last_turn_status': 'inProgress'},
                        {'turns_error': {'code': -32600, 'message': 'SIMULATED unsupported experimental read'}}):
            with self.subTest(changes=changes):
                code, _, _ = self.command(*self.observe_args(), **changes); self.assertEqual(code, 2)
                self.assertFalse((self.ar / 'readonly-evidence.json').exists())
                self.assertFalse(any(name in ('thread/resume', 'thread/start', 'turn/start') for name, _ in self.clients[-1].calls))
        owner_path = self.ar.parent / '.receivers/codex/OWNER.json'
        owner_path.write_bytes(c.encode({'operation_id': 'SIMULATED-other', 'nonce': 'SIMULATED-uncertain', 'job': 'SIMULATED'}))
        count = len(self.clients); code, _, _ = self.command(*self.observe_args())
        self.assertEqual(code, 2); self.assertEqual(len(self.clients), count); self.assertTrue(owner_path.exists())

    def test_public_observer_refuses_registry_race_and_received_evidence_output(self):
        self.finish(); self.confirm(); self.second()
        registry_path = self.ar.parent / '.receivers/codex/RECEIVER.json'
        old = registry_path.read_bytes()
        def changed():
            value = c.load(registry_path); value['thread_id'] = 'SIMULATED-other'; registry_path.write_bytes(c.encode(value))
        code, _, _ = self.command(*self.observe_args(), on_read=changed)
        self.assertEqual(code, 2); self.assertFalse((self.ar / 'readonly-evidence.json').exists())
        registry_path.write_bytes(old)
        count = len(self.clients)
        code, _, _ = self.command(*self.observe_args(**{'evidence-output': self.oproot / 'received-evidence.json'}))
        self.assertEqual(code, 2); self.assertEqual(len(self.clients), count)

    def test_public_observer_cannot_infer_native_unavailability_or_overwrite_old_evidence(self):
        self.finish(); self.confirm(); self.second(); count = len(self.clients)
        code, _, _ = self.command(*self.observe_args(**{'native-channel': 'available'}))
        self.assertEqual(code, 2); self.assertEqual(len(self.clients), count)
        (self.ar / 'readonly-evidence.json').write_bytes(b'SIMULATED preserved previous evidence')
        code, _, _ = self.command(*self.observe_args())
        self.assertEqual(code, 2); self.assertEqual(len(self.clients), count)
        self.assertEqual((self.ar / 'readonly-evidence.json').read_bytes(), b'SIMULATED preserved previous evidence')


if __name__ == '__main__': unittest.main()
