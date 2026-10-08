"""Offline source identity tests; every native observation is synthetic."""
import contextlib
import copy
import importlib.util
import io
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import test_authority as fixtures

spec = importlib.util.spec_from_file_location('source_tests', Path(__file__).resolve().parents[1] /
    'syncpilot/skills/syncpilot-dc/scripts/syncpilot_source.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.AuthorityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.now = datetime.now(timezone.utc)
        self.sha = 'a' * 64
        self.challenge = s.issue('work', 'test:work', self.sha, self.now - timedelta(seconds=20))
        self.observed = {'format': 'SYNCPILOT-SOURCE-OBSERVATION', 'schema_version': 1,
            'observed_at': self.now.isoformat(), 'environment': 'work', 'project_id': 'test:work',
            'nonce': self.challenge['nonce'], 'tool_reference': 'SIMULATED native app list/read',
            'listing': {'threads': [self.row('parent'), self.row('branch')]},
            'readings': [self.read('parent', 'No marker'), self.read('branch')]}

    def row(self, identity):
        return {'id': identity, 'kind': 'chatgpt', 'projectId': 'test:work', 'title': 'Same arbitrary title'}

    def read(self, identity, text=None):
        return {'thread': {'id': identity, 'kind': 'chatgpt',
            'createdAt': (self.now - timedelta(seconds=100)).timestamp()},
            'page': {'order': 'newest_first'}, 'turns': [{'id': 'turn-' + identity,
            'startedAt': (self.now - timedelta(seconds=10)).timestamp(),
            'items': [{'type': 'agentMessage', 'text': self.challenge['marker'] if text is None else text}]}]}

    def resolve(self):
        return s.resolve(self.f.config, self.challenge, self.observed, self.sha, 'SIMULATED human mandate', self.now)

    def refuse(self):
        with self.assertRaises(s.c.SyncError):
            self.resolve()

    def test_current_branch_and_existing_authority_format(self):
        result = self.resolve()
        self.assertEqual(result['source']['thread_id'], 'branch')
        self.assertFalse(result['auto_introspection_used'])
        self.assertFalse(result['observation_authenticated_by_helper'])
        self.assertFalse(result['dispatch_performed'])
        self.assertEqual(self.f.build(source=result['source'])['source'], result['source'])

    def test_long_running_current_turn_can_issue_its_own_challenge(self):
        branch = self.observed['readings'][1]
        branch['thread']['createdAt'] = (self.now - timedelta(seconds=1800)).timestamp()
        branch['turns'][0]['startedAt'] = (self.now - timedelta(seconds=900)).timestamp()
        self.assertEqual(self.resolve()['source']['thread_id'], 'branch')

    def test_unique_nonce_and_current_request_binding(self):
        self.assertNotEqual(s.issue('work', 'test:work', self.sha)['nonce'], self.challenge['nonce'])
        self.challenge['request_sha256'] = 'b' * 64
        self.refuse()

    def test_title_and_historical_url_are_not_identity(self):
        self.observed['readings'][1]['turns'][0]['items'][0]['text'] = 'Parent title and historical URL'
        self.refuse()

    def test_inherited_parent_turn_predates_fork(self):
        self.observed['readings'][1]['thread']['createdAt'] = self.now.timestamp()
        self.refuse()

    def test_old_turn_never_replaces_current_turn(self):
        branch = self.observed['readings'][1]
        branch['turns'].insert(0, {**copy.deepcopy(branch['turns'][0]), 'items': []})
        self.refuse()

    def test_multiple_matches_are_ambiguous(self):
        self.observed['readings'][0]['turns'][0]['items'][0]['text'] = self.challenge['marker']
        self.refuse()

    def test_user_quote_and_substring_are_not_agent_marker(self):
        item = self.observed['readings'][1]['turns'][0]['items'][0]
        item['type'] = 'userMessage'
        self.refuse()
        item['type'] = 'agentMessage'
        item['text'] = 'Quoted ' + self.challenge['marker']
        self.refuse()

    def test_wrong_actual_project_or_environment(self):
        for key, value in (('projectId', 'another-project'), ('kind', 'codex')):
            row = self.observed['listing']['threads'][1]
            before = row[key]
            row[key] = value
            self.refuse()
            row[key] = before

    def test_unlisted_and_duplicate_readback(self):
        self.observed['listing']['threads'].pop()
        self.refuse()
        self.observed['listing']['threads'].append(self.row('branch'))
        self.observed['readings'].append(copy.deepcopy(self.observed['readings'][1]))
        self.refuse()

    def test_tool_error_is_not_identity_evidence(self):
        self.observed['readings'][1] = {'detail': 'Too many requests'}
        self.refuse()

    def test_stale_future_and_naive_timestamps(self):
        before = self.observed['observed_at']
        for seconds in (-121, 6):
            self.observed['observed_at'] = (self.now + timedelta(seconds=seconds)).isoformat()
            self.refuse()
        self.observed['observed_at'] = self.now.replace(tzinfo=None).isoformat()
        self.refuse()
        self.observed['observed_at'] = before
        self.challenge['issued_at'] = (self.now - timedelta(seconds=601)).isoformat()
        self.refuse()

    def test_wrong_nonce_and_invalid_native_time(self):
        self.observed['nonce'] = '0' * 32
        self.refuse()
        self.observed['nonce'] = self.challenge['nonce']
        for value in (None, True, float('nan')):
            self.observed['readings'][1]['turns'][0]['startedAt'] = value
            self.refuse()

    def test_pinned_cli_output_cannot_be_overwritten(self):
        root = self.f.authority_root
        challenge, observed, output = root/'challenge.json', root/'observation.json', root/'source.json'
        challenge.write_bytes(s.c.encode(self.challenge))
        observed.write_bytes(s.c.encode(self.observed))
        args = ['qualify', '--contract', str(self.f.contract), '--canonical-root', str(self.f.canonical),
            '--authority-root', str(root), '--request-sha256', self.sha, '--output', str(output),
            '--challenge', str(challenge), '--challenge-sha256', s.c.digest(challenge.read_bytes()),
            '--observation', str(observed), '--observation-sha256', s.c.digest(observed.read_bytes()),
            '--authority-reference', 'SIMULATED human mandate']
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(s.main(args), 0)
            before = output.read_bytes()
            self.assertEqual(s.main(args), 2)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(s.c.load(output)['thread_id'], 'branch')
        observed.write_bytes(b'{}')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(s.main(args), 2)

    def test_issue_never_guesses_source_or_dispatches(self):
        path = self.f.authority_root/'issued.json'
        args = ['issue', '--contract', str(self.f.contract), '--canonical-root', str(self.f.canonical),
            '--authority-root', str(self.f.authority_root), '--request-sha256', self.sha,
            '--output', str(path), '--environment', 'work']
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(s.main(args), 0)
        self.assertEqual(s.c.decode(out.getvalue())['action'], 'SOURCE_QUALIFICATION_REQUIRED')
        self.assertNotIn('thread_id', s.c.load(path))


if __name__ == '__main__':
    unittest.main()
