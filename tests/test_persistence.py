import copy
import importlib.util
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import test_decisions as fixtures

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('persistence', ROOT / 'syncpilot/skills/syncpilot-persistence/scripts/work_persistence.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
spec2 = importlib.util.spec_from_file_location('identity', ROOT / 'tools/check_release_identity.py')
identity = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(identity)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DecisionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.old = self.fixture.config
        self.profile = {'target': {'kind': 'page-files', 'project_id': 'work-project', 'container_id': 'qualified-test-page'}, 'registry': 'page:qualified-test-page#registry', 'policy': p.POLICY}
        self.config = p.migrate(self.old, self.profile)
        self.transport = {'operation_id': 'test-operation', 'nonce': 'test-nonce', 'destination': 'work-project', 'destination_thread': 'work-thread', 'status': 'VERIFIED', 'proof_sha256': 'a'*64, 'receipt_sha256': 'b'*64, 'authority': 'SIMULATED TEST ONLY'}
        self.artifacts = [{'name': 'document.md', 'size': 10, 'sha256': 'c'*64}]
        self.j = p.prepare(self.config, self.transport, self.artifacts)

    def observation(self, files=True):
        op = self.j['operation']
        return {'persistence_id': op['persistence_id'], 'operation_id': op['operation_id'], 'nonce': op['nonce'], 'target': op['target'], 'registry': op['registry'], 'registry_verified': True, 'routing_verified': True, 'authority': 'SIMULATED fresh destination read', 'observed_at': datetime.now(timezone.utc).isoformat(), 'complete': True, 'outcome': 'available', 'files': [{**self.artifacts[0], 'reference': 'library-file:qualified', 'linked': True, 'access_confirmed': True, 'read_in_new_context': True}] if files else [], 'project_source_ingested': False}

    def test_migration_preserves_all_prior_parameters(self):
        self.assertEqual({k:v for k,v in self.config.items() if k not in ('schema_version','work_persistence')}, {k:v for k,v in self.old.items() if k != 'schema_version'})
        self.assertEqual(self.old['schema_version'], 3)

    def test_migration_rejects_wrong_project(self):
        bad = copy.deepcopy(self.profile); bad['target']['project_id'] = 'other'
        with self.assertRaises(p.c.SyncError): p.migrate(self.old, bad)

    def test_old_contract_has_no_implicit_persistence(self):
        with self.assertRaises(p.c.SyncError): p.contract(self.old)

    def test_transport_verification_required(self):
        for status in ('PREPARED','RECEIVED','BLOCKED'):
            with self.assertRaises(p.c.SyncError): p.prepare(self.config, {**self.transport, 'status': status}, self.artifacts)

    def test_destination_binding_required(self):
        with self.assertRaises(p.c.SyncError): p.prepare(self.config, {**self.transport,'destination_thread':'other'}, self.artifacts)

    def test_identity_preserved_from_transport(self):
        self.assertEqual(self.j['operation']['operation_id'], self.transport['operation_id'])
        self.assertEqual(self.j['operation']['nonce'], self.transport['nonce'])

    def test_work_origin_decision_can_remain_available_after_codex_receipt(self):
        binding={**self.transport,'destination':'codex-project','destination_thread':'codex-thread'}
        journal=p.prepare(self.config,binding,self.artifacts)
        self.assertEqual(journal['operation']['destination_thread'],'work-thread')
        self.assertEqual(journal['operation']['transport_proof_sha256'],binding['proof_sha256'])
        self.assertEqual(journal['operation']['nonce'],binding['nonce'])
        with self.assertRaises(p.c.SyncError):p.prepare(self.config,{**binding,'destination_thread':'work-thread'},self.artifacts)

    def test_inventory_rejects_duplicates_paths_and_oversize(self):
        for artifacts in (self.artifacts*2, [{**self.artifacts[0],'name':'../escape'}], [{**self.artifacts[0],'size':10*1024*1024+1}]):
            with self.assertRaises(p.c.SyncError): p.prepare(self.config,self.transport,artifacts)

    def test_complete_absence_allows_single_upload(self):
        self.assertEqual(p.plan(self.j,self.observation(False))['action'],'UPLOAD_ONCE')

    def test_incomplete_discovery_prevents_upload(self):
        for patch in ({'complete':False},{'outcome':'unknown'}):
            self.assertEqual(p.plan(self.j,{**self.observation(False),**patch})['action'],'COLLECT_EXISTING')

    def test_unknown_upload_commit_prevents_duplicate(self):
        self.j = p.record(self.j,'UPLOAD_ATTEMPTED','document.md','qualified connector invocation')
        self.assertEqual(p.plan(self.j,self.observation(False))['action'],'COLLECT_EXISTING')
        with self.assertRaises(p.c.SyncError): p.record(self.j,'UPLOAD_ATTEMPTED','document.md','retry')

    def test_conclusive_no_commit_allows_retry(self):
        self.j = p.record(self.j,'UPLOAD_ATTEMPTED','document.md','connector')
        self.j = p.record(self.j,'WRITE_NOT_COMMITTED','document.md','qualified no-commit proof')
        self.assertEqual(p.plan(self.j,self.observation(False))['action'],'UPLOAD_ONCE')

    def test_existing_unlinked_file_reused(self):
        obs = self.observation();obs['files'][0]['linked'] = False
        self.assertEqual(p.plan(self.j,obs)['action'],'LINK_EXISTING')

    def test_storage_failure_never_changes_transport(self):
        result = p.plan(self.j,{**self.observation(False),'outcome':'unavailable'})
        self.assertEqual(result['action'],'BLOCKED');self.assertFalse(result['transport_change'])

    def test_integrity_identity_and_external_reference_rejected(self):
        for key,value in (('sha256','d'*64),('reference','dc://external'),('size',9)):
            obs=self.observation();obs['files'][0][key]=value
            with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,obs)
        for key,value in (('nonce','other'),('target',{**self.profile['target'],'container_id':'other'})):
            with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,{**self.observation(),key:value})

    def test_rejection_terminal_even_after_channel_change(self):
        self.j=p.record(self.j,'VALIDATION_REJECTED','*','independent rejection')
        with self.assertRaises(p.c.SyncError):p.plan(self.j,self.observation())

    def test_fresh_context_and_access_required(self):
        for key in ('linked','access_confirmed','read_in_new_context'):
            obs=self.observation();obs['files'][0][key]=False
            with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,obs)

    def test_registry_and_routing_required(self):
        for key in ('registry_verified','routing_verified'):
            with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,{**self.observation(),key:False})

    def test_stale_and_future_observations_rejected(self):
        for seconds in (-301,60):
            obs={**self.observation(),'observed_at':(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat()}
            with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,obs)

    def test_page_availability_never_claims_native_source(self):
        proof=p.confirm(self.config,self.j,self.observation())
        self.assertEqual(proof['completion_status'],'WORK_PAGE_AVAILABLE')
        self.assertEqual(proof['project_sources_status'],'NOT_ASSERTED')
        with self.assertRaises(p.c.SyncError):p.confirm(self.config,self.j,{**self.observation(),'project_source_ingested':True})

    def test_native_adapter_absence_blocks(self):
        config=copy.deepcopy(self.config);config['work_persistence']['target']['kind']='project-sources'
        self.j=p.prepare(config,self.transport,self.artifacts)
        self.assertEqual(p.plan(self.j,self.observation(False))['reason'],'NATIVE_PROJECT_SOURCE_ADAPTER_NOT_AVAILABLE')
        with self.assertRaises(p.c.SyncError):p.confirm(config,self.j,self.observation())

    def test_parent_accepts_only_exact_origin_and_fresh_read(self):
        proof=p.confirm(self.config,self.j,self.observation())
        origin={'destination_thread':'work-thread','target':self.profile['target'],'proof_sha256':p.c.digest(p.c.encode(proof)),'authority':'SIMULATED authenticated destination retrieval'}
        self.assertEqual(p.accept(self.config,self.j,proof,self.observation(),origin)['completion_status'],'WORK_PAGE_AVAILABLE')
        with self.assertRaises(p.c.SyncError):p.accept(self.config,self.j,proof,self.observation(),{**origin,'destination_thread':'other'})
        proof['nonce']='other'
        with self.assertRaises(p.c.SyncError):p.accept(self.config,self.j,proof,self.observation(),origin)

    def test_availability_loss_requires_review_not_reupload(self):
        proof=p.confirm(self.config,self.j,self.observation())
        origin={'destination_thread':'work-thread','target':self.profile['target'],'proof_sha256':p.c.digest(p.c.encode(proof)),'authority':'SIMULATED authenticated destination retrieval'}
        self.j=p.accept(self.config,self.j,proof,self.observation(),origin)['journal']
        self.assertEqual(p.plan(self.j,self.observation(False))['action'],'BLOCKED')

    def test_manual_record_cannot_claim_verification(self):
        with self.assertRaises(p.c.SyncError):p.record(self.j,'PERSISTENCE_VERIFIED','*','self assertion')


class IdentityTests(unittest.TestCase):
    def archive(self, root_name='syncpilot', alias=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);path=Path(tmp.name)/'candidate.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name in ('syncpilot/plugin.json','syncpilot/.codex-plugin/plugin.json'):
                z.writestr(name,json.dumps({'name':root_name,'version':'0.5.0'}))
            for skill in ('init','codex','work','dc','decisions','persistence'):
                z.writestr('syncpilot/skills/syncpilot-'+skill+'/SKILL.md','test')
            if alias:z.writestr('syncpilot/skills/project-sync-init/SKILL.md','old alias')
        return path

    def test_new_identity_required_for_old_backend(self):
        with self.assertRaises(ValueError):identity.check(self.archive(),{'name':'project-sync'})

    def test_deployment_wrapper_rejected(self):
        with self.assertRaises(ValueError):identity.check(self.archive('project-sync'))

    def test_alias_packaging_rejected(self):
        with self.assertRaises(ValueError):identity.check(self.archive(alias=True))

    def test_canonical_identity_allowed(self):
        self.assertEqual(identity.check(self.archive())['publication_action'],'CREATE_NEW_IDENTITY_AT_CHECKPOINT')


if __name__=='__main__':unittest.main()
