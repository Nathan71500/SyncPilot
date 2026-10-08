"""Isolated flow simulations; none establishes a real destination or reception."""
import argparse
import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'syncpilot/skills/syncpilot-dc/scripts/syncpilot_flow.py'
spec=importlib.util.spec_from_file_location('flow_tests',SCRIPT)
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
c=f.c;t=f.t


class FlowTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.config={'schema_version':5,'project_id':'fixture','repository':'https://example.invalid/fixture',
                     'reference_branch':'main','destination':'test:work','authority':'SIMULATION ONLY',
                     'shared_sources':[],'domains':{'docs':['docs.txt']},
                     'transport':{'primary':{'channel':'desktop-commander','locator':'dc://11111111-1111-4111-8111-111111111111/'+quote('/test/isolated',safe=''),'account':'test-dc'},
                                  'fallback':{'channel':'drive','locator':'gdrive:folder:TEST_ONLY','account':'test-drive'},'policy':t.POLICY,'persistence':t.PERSISTENCE},
                     'decision_sync':{'participants':{'work':{'project_id':'test:work'},'codex':{'project_id':'test:codex'}},
                                      'registries':{'work':'dc://11111111-1111-4111-8111-111111111111/'+quote('/test/work',safe=''),'codex':'dc://11111111-1111-4111-8111-111111111111/'+quote('/test/codex',safe='')},
                                      'sources':{'work':['https://example.invalid/work'],'codex':['codex://threads/test:codex']},
                                      'policy':{'capture':'human-validated-only','oral':'preserve-existing-validation','conflicts':'block-and-arbitrate','git':'review-before-integration','new_project':'recommend-if-work-and-codex'}}}
        (self.repo/'project-sync.json').write_bytes(c.encode(self.config))
        (self.repo/'docs.txt').write_bytes('Document témoin\r\nSIMULATION ONLY\r\n'.encode())
        self.git('init','-b','main');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
        self.git('config','core.autocrlf','false');self.git('remote','add','origin',self.config['repository'])
        self.git('add','.');self.git('-c','commit.gpgsign=false','commit','-m','SIMULATION ONLY')
        self.commit=self.git('rev-parse','HEAD')
        self.args=argparse.Namespace(repository=self.repo,commit=self.commit,domain=['docs'],authority='SIMULATION ONLY',receiver_thread='receiver',output_directory=self.root/'prepared',attestation=None)
        self.work=self.actor('work','sender')

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.DEVNULL,text=True).strip()

    def actor(self,env,thread):
        return {'environment':env,'project_id':'test:'+env,'thread_id':thread,'authority':'SIMULATION ONLY','qualification_reference':'https://example.invalid/qualified'}

    def candidate(self,thread='candidate',**changes):
        value={'thread_id':thread,'title':thread,'environment':'codex','project_id':'test:codex','status':'idle','updated_at':2,'canonical_root':str(self.repo),'qualification_reference':'https://example.invalid/candidate'}
        value.update(changes);return value

    def scope(self,**changes):
        value={'project_id':'test:codex','environment':'codex','thread_id':None,'reference':'https://example.invalid/human-workflow-authority'}
        value.update(changes);return value

    def test_same_environment_avoids_both_self_syncs_without_false_current(self):
        for env in ('work','codex'):
            plan=f.route(self.config,self.actor(env,'origin'),env,'documents',[])
            self.assertEqual(plan['action'],'USE_CANONICAL_SOURCE')
            self.assertFalse(plan['message_required']);self.assertFalse(plan['reception_verified'])
            self.assertEqual(plan['mirror_status'],'NOT_ASSERTED')
        self.assertEqual(f.route(self.config,self.work,'work','decisions',[])['action'],'ALIGN_LOCAL_REGISTRY')

    def test_generic_project_receiver_name_and_reuse(self):
        for name in ('Alpha','Beta','Example'):
            self.assertEqual(f.receiver_title(name),name+'-RECEVEUR')
        scope={'project_id':'test:codex','environment':'codex','title':'Fixture-RECEVEUR','reference':'https://example.invalid/human-creation-authority'}
        plan=f.route(self.config,self.work,'codex','decisions',[self.candidate('recent',updated_at=999),self.candidate('dedicated',title='Fixture-RECEVEUR',updated_at=1)],self.scope(),True,creation_authority=scope,can_create=True)
        self.assertEqual(plan['receiver']['thread_id'],'dedicated');self.assertNotIn('creation',plan)

    def test_filters_wrong_project_busy_and_source_then_chooses_idle(self):
        candidates=[self.candidate('wrong',project_id='another',updated_at=999),self.candidate('busy',status='active',updated_at=999),self.candidate('sender',updated_at=999),self.candidate('asleep',status='notLoaded',updated_at=999),self.candidate('older',updated_at=1),self.candidate('idle')]
        plan=f.route(self.config,self.work,'codex','decisions',candidates,self.scope(),True)
        self.assertEqual(plan['action'],'SELECT_AND_DISPATCH');self.assertEqual(plan['receiver']['thread_id'],'idle')
        self.assertFalse(plan['dispatch_performed'])

    def test_missing_project_requires_exact_catalogue_repository(self):
        candidate=self.candidate(project_id=None)
        self.assertEqual(f.route(self.config,self.work,'codex','decisions',[candidate])['action'],'BLOCKED_NO_AVAILABLE_RECEIVER')
        plan=f.route(self.config,self.work,'codex','decisions',[candidate],self.scope(),True,self.repo)
        self.assertEqual(plan['receiver']['project_association'],'catalogue-and-actual-repository')
        candidate['project_id']='another'
        self.assertEqual(f.route(self.config,self.work,'codex','decisions',[candidate],canonical_root=self.repo)['action'],'BLOCKED_NO_AVAILABLE_RECEIVER')

    def test_message_authority_and_tool_required(self):
        candidates=[self.candidate()]
        self.assertEqual(f.route(self.config,self.work,'codex','decisions',candidates,self.scope())['action'],'BLOCKED_DISPATCH_UNAVAILABLE')
        self.assertEqual(f.route(self.config,self.work,'codex','decisions',candidates,can_message=True)['action'],'READY_REQUIRES_MESSAGE_AUTHORITY')
        for scope in (self.scope(project_id='other'),self.scope(thread_id='other')):
            with self.assertRaises(c.SyncError):f.route(self.config,self.work,'codex','decisions',candidates,scope,True)

    def test_creation_only_if_authorized_and_no_receiver(self):
        scope={'project_id':'test:codex','environment':'codex','title':'TEST-RECEVEUR','reference':'https://example.invalid/human-creation-authority'}
        plan=f.route(self.config,self.work,'codex','decisions',[],creation_authority=scope,can_create=True)
        self.assertEqual(plan['action'],'CREATE_PROJECT_RECEIVER');self.assertEqual(plan['creation']['environment'],'local')
        existing=f.route(self.config,self.work,'codex','decisions',[self.candidate()],self.scope(),True,creation_authority=scope,can_create=True)
        self.assertEqual(existing['action'],'SELECT_AND_DISPATCH')
        self.assertEqual(f.route(self.config,self.work,'codex','decisions',[],creation_authority=scope)['action'],'BLOCKED_NO_AVAILABLE_RECEIVER')
        busy=f.route(self.config,self.work,'codex','decisions',[self.candidate('busy',title='TEST-RECEVEUR',status='active')],creation_authority=scope,can_create=True)
        self.assertEqual(busy['action'],'BLOCKED_RECEIVER_BUSY');self.assertNotIn('creation',busy)
        preferred=f.route(self.config,self.work,'codex','decisions',[],preferred='selected',creation_authority=scope,can_create=True)
        self.assertEqual(preferred['action'],'BLOCKED_NO_AVAILABLE_RECEIVER')
        with self.assertRaises(c.SyncError):
            f.route(self.config,self.work,'codex','decisions',[self.candidate()],creation_authority={**scope,'project_id':'another'})

    def test_preferred_busy_actor_does_not_silently_substitute(self):
        plan=f.route(self.config,self.work,'codex','decisions',[self.candidate(),self.candidate('preferred',status='active')],self.scope(),True,preferred='preferred')
        self.assertEqual(plan['action'],'BLOCKED_NO_AVAILABLE_RECEIVER')

    def test_prepare_resume_preserves_nonce_and_bytes(self):
        first=f.prepare(self.args)
        before={p.name:p.read_bytes() for p in self.args.output_directory.iterdir()}
        again=f.prepare(self.args)
        self.assertEqual(again['action'],'COLLECT_EXISTING');self.assertEqual(first['nonce'],again['nonce'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.args.output_directory.iterdir()})
        self.args.receiver_thread='other'
        with self.assertRaises(c.SyncError):f.prepare(self.args)

    def test_dirty_git_and_incomplete_preparation_are_preserved(self):
        (self.repo/'docs.txt').write_bytes(b'foreign work')
        with self.assertRaises(c.SyncError):f.prepare(self.args)
        self.assertFalse(self.args.output_directory.exists());self.assertEqual((self.repo/'docs.txt').read_bytes(),b'foreign work')
        self.git('checkout','--','docs.txt')  # Only this test owns its isolated fixture.
        self.args.output_directory.mkdir();marker=self.args.output_directory/'marker';marker.write_bytes(b'preserve')
        with self.assertRaises(c.SyncError):f.prepare(self.args)
        self.assertEqual(marker.read_bytes(),b'preserve')

    def intake_args(self):
        f.prepare(self.args)
        directory=self.args.output_directory
        journal=t.record(c.load(directory/'journal-0.json'),'DEPOSITED','primary','present','SIMULATION ONLY byte readback')
        path=directory/'journal-deposited.json';path.write_bytes(c.encode(journal))
        receiver=self.root/'receiver.json';receiver.write_bytes(c.encode(self.actor('work','receiver')))
        op=journal['operation'];profile=op['profiles']['primary'];device,root,pm=c.dc_endpoint(profile['locator'])
        locator='dc://'+device+'/'+quote(pm.join(root,'fixture',op['operation_id'],'carrier.json'),safe='')
        return argparse.Namespace(input=directory/'carrier.json',requirement=directory/'requirement.json',journal=path,receiver=receiver,channel='primary',artifact_locator=locator,output_directory=self.root/'intake')

    def test_intake_exact_bytes_receipt_and_idempotent_resume(self):
        args=self.intake_args();result=f.intake(args)
        self.assertEqual(result['action'],'RECEIVED_AWAITING_PARENT_CONFIRM')
        self.assertFalse(result['agent_finished_observed']);self.assertFalse(result['parent_confirmed'])
        self.assertEqual((args.output_directory/'store/sources/docs.txt').read_bytes(),(self.repo/'docs.txt').read_bytes())
        before={p.relative_to(args.output_directory).as_posix():p.read_bytes() for p in args.output_directory.rglob('*') if p.is_file()}
        self.assertEqual(f.intake(args)['action'],'COLLECT_EXISTING')
        self.assertEqual(before,{p.relative_to(args.output_directory).as_posix():p.read_bytes() for p in args.output_directory.rglob('*') if p.is_file()})

    def test_wrong_receiver_or_locator_refused_before_writes(self):
        args=self.intake_args();original=args.receiver.read_bytes()
        args.receiver.write_bytes(c.encode(self.actor('codex','receiver')))
        with self.assertRaises(c.SyncError):f.intake(args)
        self.assertFalse(args.output_directory.exists())
        args.receiver.write_bytes(original);args.artifact_locator='dc://11111111-1111-4111-8111-111111111111/'+quote('/wrong/carrier.json',safe='')
        with self.assertRaises(c.SyncError):f.intake(args)
        self.assertFalse(args.output_directory.exists())

    def test_altered_carrier_or_existing_mirror_refused_without_overwrite(self):
        args=self.intake_args();original=args.input.read_bytes();carrier=c.load(args.input);carrier['zip_sha256']='0'*64;args.input.write_bytes(c.encode(carrier))
        with self.assertRaises(c.SyncError):f.intake(args)
        self.assertFalse(args.output_directory.exists())
        args.input.write_bytes(original);f.intake(args)
        path=args.output_directory/'store/sources/docs.txt';path.write_bytes(b'changed destination')
        with self.assertRaises(c.SyncError):f.intake(args)
        self.assertEqual(path.read_bytes(),b'changed destination')


class ExistingFlowTests(unittest.TestCase):
    def setUp(self):
        import test_routing as fixtures
        self.fixture=fixtures.RoutingTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.inbox()
        self.source={'environment':'work','project_id':'work-project','thread_id':'work-new-session','authority':'SIMULATION ONLY','qualification_reference':'SIMULATED qualified source'}

    def test_selected_receiver_followed_without_dispatch_or_creation(self):
        selected=self.fixture.pickup()
        plan=f.route(self.fixture.config,self.source,'codex','decisions',[],journal=self.fixture.f.j)
        self.assertEqual(plan['action'],'FOLLOW_SELECTED_RECEIVER')
        self.assertEqual(plan['receiver'],selected);self.assertFalse(plan['message_required'])
        self.assertNotIn('creation',plan)

    def test_raw_contract_and_foreign_existing_operation(self):
        raw=(json.dumps(self.fixture.config,indent=2)+'\n').encode()
        self.fixture.f.contract.write_bytes(raw);self.fixture.prepare();self.fixture.pickup()
        plan=f.route(self.fixture.config,self.source,'codex','decisions',[],journal=self.fixture.f.j,contract_sha256=c.digest(raw))
        self.assertEqual(plan['action'],'FOLLOW_SELECTED_RECEIVER')
        with self.assertRaises(c.SyncError):f.route(self.fixture.config,self.source,'codex','decisions',[],journal=self.fixture.f.j,contract_sha256='0'*64)


if __name__=='__main__':unittest.main()
