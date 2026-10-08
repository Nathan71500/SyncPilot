"""Offline authority simulations. No test authenticates a human or creates a chat."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'syncpilot/skills/syncpilot-dc/scripts/syncpilot_authority.py'
spec = importlib.util.spec_from_file_location('authority_tests', SCRIPT)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
c = a.c


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.canonical = self.root / 'canonical'
        self.canonical.mkdir()
        self.transport = self.root / 'transport'
        self.authority_root = self.transport / 'fixture' / '.authority'
        self.authority_root.mkdir(parents=True)
        self.config = {
            'schema_version':5, 'project_id':'fixture', 'repository':None, 'reference_branch':None,
            'destination':'test:work', 'authority':'SIMULATION ONLY', 'shared_sources':[],
            'domains':{'docs':['docs.txt']},
            'transport':{'primary':{'channel':'desktop-commander',
                         'locator':'dc://11111111-1111-4111-8111-111111111111/' + quote(str(self.transport), safe=''),
                         'account':'test-dc'},
                         'fallback':{'channel':'drive', 'locator':'gdrive:folder:TEST_ONLY', 'account':'test-drive'},
                         'policy':{'fallback_on':['desktop-commander-unavailable'], 'uncertain_reception':'collect-before-resume',
                                   'validation_rejected':'block', 'resume':'same-operation'},
                         'persistence':{'desktop_commander':'external-folder', 'drive':'external-folder',
                                        'work_sources':'explicit-ingestion-required'}},
            'decision_sync':{'participants':{'work':{'project_id':'test:work'}, 'codex':{'project_id':'test:codex'}},
                             'registries':{'work':'dc://11111111-1111-4111-8111-111111111111/' + quote(str(self.transport / 'work'), safe=''),
                                           'codex':'dc://11111111-1111-4111-8111-111111111111/' + quote(str(self.transport / 'codex'), safe='')},
                             'sources':{'work':['https://example.invalid/work'], 'codex':['codex://threads/test:codex']},
                             'policy':{'capture':'human-validated-only', 'oral':'preserve-existing-validation',
                                       'conflicts':'block-and-arbitrate', 'git':'review-before-integration',
                                       'new_project':'recommend-if-work-and-codex'}}}
        self.contract = self.canonical / c.CONTRACT
        self.contract.write_bytes(c.encode(self.config))
        self.grant = {'format':'SYNCPILOT-RECEIVER-GRANT', 'schema_version':1, 'project_id':'fixture',
                      'scope':'authorized-project-missions', 'human_author':'SIMULATION human',
                      'human_reference':'https://example.invalid/validated-human-grant',
                      'human_statement':'Création automatique du receveur dans une mission autorisée 🧩',
                      'qualification_reference':'SIMULATION independent original grant reread', 'allow_create':True}
        self.mission = {'format':'SYNCPILOT-AUTHORIZED-MISSION', 'schema_version':1, 'mission_id':'SIMULATION-01',
                        'project_id':'fixture', 'contract_sha256':c.digest(self.contract.read_bytes()),
                        'canonical_root':str(self.canonical), 'project_name':'Fixture',
                        'source_environment':'work', 'destination_environment':'codex',
                        'reference':'https://example.invalid/current-authorized-mission',
                        'qualification_reference':'SIMULATION authenticated current project and workspace',
                        'allow_message':True, 'allow_receiver_selection':True, 'receiver_thread':None}
        self.source = {'environment':'work', 'project_id':'test:work', 'thread_id':'current-source',
                       'authority':'SIMULATION current mission', 'qualification_reference':'SIMULATION actual source observed'}
        self.grant_path = self.authority_root / 'receiver-creation-grant.json'
        self.mission_path = self.authority_root / 'mission-SIMULATION-01.json'

    def build(self, grant=None, mission=None, source=None, **overrides):
        self.grant_path.write_bytes(c.encode(self.grant if grant is None else grant))
        self.mission_path.write_bytes(c.encode(self.mission if mission is None else mission))
        args = {'contract_path':self.contract, 'grant_path':self.grant_path, 'mission_path':self.mission_path,
                'source':self.source if source is None else source, 'authority_root':self.authority_root,
                'canonical_root':self.canonical, 'grant_sha256':c.digest(self.grant_path.read_bytes()),
                'mission_sha256':c.digest(self.mission_path.read_bytes())}
        args.update(overrides)
        return a.build(**args)

    def test_existing_human_grant_builds_compatible_authorities_without_original_chat(self):
        plan = self.build()
        self.assertTrue(plan['bridge_authority']['allow_create'])
        self.assertEqual(plan['creation_authority']['title'], 'Fixture-RECEVEUR')
        self.assertEqual(plan['message_authority']['project_id'], 'test:codex')
        self.assertIsNone(plan['message_authority']['thread_id'])
        self.assertIn(plan['bindings']['grant']['sha256'], plan['bridge_authority']['reference'])
        self.assertFalse(plan['dispatch_performed'])
        self.assertFalse(plan['receiver_availability_asserted'])
        self.assertFalse(plan['human_authority_authenticated_by_helper'])
        self.assertFalse(plan['permissions_changed'])
        changed_source = {**self.source, 'thread_id':'later-pilot-chat'}
        self.assertEqual(self.build(source=changed_source)['creation_authority'], plan['creation_authority'])

    def test_work_and_codex_current_missions_reuse_grant(self):
        mission = {**self.mission, 'source_environment':'codex', 'destination_environment':'work', 'project_name':'Alias Humain'}
        source = {**self.source, 'environment':'codex', 'project_id':'test:codex'}
        plan = self.build(mission=mission, source=source)
        self.assertEqual(plan['message_authority']['project_id'], 'test:work')
        self.assertEqual(plan['creation_authority']['title'], 'Alias Humain-RECEVEUR')

    def test_authorities_are_compatible_with_existing_flow_and_prefer_reuse(self):
        spec = importlib.util.spec_from_file_location('authority_flow', SCRIPT.with_name('syncpilot_flow.py'))
        flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flow)
        authority = self.build()
        plan = flow.route(self.config, self.source, 'codex', 'decisions', [],
                          authority['message_authority'], True, self.canonical,
                          creation_authority=authority['creation_authority'], can_create=True)
        self.assertEqual(plan['action'], 'CREATE_PROJECT_RECEIVER')
        candidate = {'thread_id':'available', 'title':'Fixture-RECEVEUR', 'environment':'codex',
                     'project_id':'test:codex', 'status':'idle', 'updated_at':1,
                     'canonical_root':str(self.canonical), 'qualification_reference':'SIMULATION actual candidate'}
        plan = flow.route(self.config, self.source, 'codex', 'decisions', [candidate],
                          authority['message_authority'], True, self.canonical,
                          creation_authority=authority['creation_authority'], can_create=True)
        self.assertEqual(plan['action'], 'SELECT_AND_DISPATCH')
        self.assertNotIn('creation', plan)
        candidate['status'] = 'setup-in-progress'
        plan = flow.route(self.config, self.source, 'codex', 'decisions', [candidate],
                          authority['message_authority'], True, self.canonical,
                          creation_authority=authority['creation_authority'], can_create=True)
        self.assertEqual(plan['action'], 'BLOCKED_RECEIVER_BUSY')
        self.assertNotIn('creation', plan)

    def test_fixed_receiver_does_not_authorize_replacement(self):
        for selection in (True, False):
            plan = self.build(mission={**self.mission, 'receiver_thread':'already-selected',
                                       'allow_receiver_selection':selection})
            self.assertFalse(plan['bridge_authority']['allow_create'])
            self.assertIsNone(plan['creation_authority'])
            self.assertEqual(plan['message_authority']['thread_id'], 'already-selected')

    def test_creation_grant_never_supplies_message_mandate(self):
        for mission in ({**self.mission, 'allow_message':False},
                        {**self.mission, 'allow_receiver_selection':False},
                        {**self.mission, 'allow_message':1}):
            with self.subTest(mission=mission), self.assertRaises(c.SyncError):
                self.build(mission=mission)

    def test_cross_project_contract_workspace_and_source_refused(self):
        cases = [({'grant':{**self.grant, 'project_id':'another'}}),
                 ({'mission':{**self.mission, 'project_id':'another'}}),
                 ({'mission':{**self.mission, 'contract_sha256':'0' * 64}}),
                 ({'source':{**self.source, 'project_id':'another'}}),
                 ({'source':{**self.source, 'environment':'codex', 'project_id':'test:codex'}}),
                 ({'mission':{**self.mission, 'canonical_root':str(self.transport)}})]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(c.SyncError):
                self.build(**kwargs)

    def test_both_same_environment_routes_refused(self):
        for environment in ('work', 'codex'):
            mission = {**self.mission, 'source_environment':environment, 'destination_environment':environment}
            source = {**self.source, 'environment':environment, 'project_id':'test:' + environment}
            with self.subTest(environment=environment), self.assertRaises(c.SyncError):
                self.build(mission=mission, source=source)

    def test_received_operation_files_and_unqualified_root_refused(self):
        operation = self.transport / 'fixture' / 'received-operation'
        operation.mkdir()
        received_grant = operation / 'receiver-creation-grant.json'
        received_grant.write_bytes(c.encode(self.grant))
        with self.assertRaises(c.SyncError):
            self.build(grant_path=received_grant)
        with self.assertRaises(c.SyncError):
            self.build(authority_root=operation)
        # Even matching SHA pins cannot turn a contract copied into transport into the canon.
        received_contract = operation / c.CONTRACT
        received_contract.write_bytes(self.contract.read_bytes())
        with self.assertRaises(c.SyncError):
            self.build(contract_path=received_contract, canonical_root=operation,
                       mission={**self.mission, 'canonical_root':str(operation)})

    def test_changed_pins_malformed_grant_and_extra_permissions_refused(self):
        with self.assertRaises(c.SyncError):
            self.build(grant_sha256='0' * 64)
        with self.assertRaises(c.SyncError):
            self.build(mission_sha256='0' * 64)
        for grant in ({**self.grant, 'scope':'all-permissions'},
                      {**self.grant, 'allow_create':1},
                      {**self.grant, 'allow_message':True},
                      {**self.grant, 'human_reference':'REPLACE_HUMAN_REFERENCE'},
                      {**self.grant, 'human_statement':'x' * 4_001}):
            with self.subTest(grant=grant), self.assertRaises(c.SyncError):
                self.build(grant=grant)

    def test_duplicate_json_and_oversized_authority_refused(self):
        self.build()
        self.grant_path.write_bytes(b'{"format":"first","format":"second"}')
        with self.assertRaises(c.SyncError):
            a.pinned(self.grant_path, self.authority_root, c.digest(self.grant_path.read_bytes()))
        self.grant_path.write_bytes(c.encode(self.grant).decode('utf-8').encode('utf-16'))
        with self.assertRaises(UnicodeError):
            a.pinned(self.grant_path, self.authority_root, c.digest(self.grant_path.read_bytes()))
        self.grant_path.write_bytes(b' ' * (a.MAX_AUTHORITY_FILE + 1))
        with self.assertRaises(c.SyncError):
            a.pinned(self.grant_path, self.authority_root, c.digest(self.grant_path.read_bytes()))

    def test_cli_strict_utf8_and_read_only_output(self):
        expected = self.build()
        source_path = self.root / 'observed-source.json'
        source_path.write_bytes(c.encode(self.source))
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        env = {**os.environ, 'PYTHONUTF8':'0', 'PYTHONIOENCODING':'cp1252:strict'}
        args = [sys.executable, str(SCRIPT), 'build', '--contract', str(self.contract), '--grant', str(self.grant_path),
                '--mission', str(self.mission_path), '--source', str(source_path), '--authority-root', str(self.authority_root),
                '--canonical-root', str(self.canonical), '--grant-sha256', expected['bindings']['grant']['sha256'],
                '--mission-sha256', expected['bindings']['mission']['sha256']]
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='strict', env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(c.decode(result.stdout.encode('utf-8')), expected)
        self.assertIn('🧩', result.stdout)
        self.assertEqual(before, {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
