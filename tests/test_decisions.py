import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'syncpilot/skills/syncpilot-decisions/scripts/decision_sync.py'
spec=importlib.util.spec_from_file_location('decisions',SCRIPT);d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d);c=d.c


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config={'schema_version':3,'project_id':'new-project','repository':None,'reference_branch':None,'destination':'work-project','authority':'TEST ONLY','shared_sources':[],'domains':{'decisions':['decisions.json']},'transport':{'primary':{'channel':'desktop-commander','locator':'dc://11111111-1111-4111-8111-111111111111/'+quote('/test/intake',safe=''),'account':'test-dc'},'fallback':{'channel':'drive','locator':'gdrive:folder:TEST_ONLY','account':'test-drive'},'policy':{'fallback_on':['desktop-commander-unavailable'],'uncertain_reception':'collect-before-resume','validation_rejected':'block','resume':'same-operation'},'persistence':{'desktop_commander':'external-folder','drive':'external-folder','work_sources':'explicit-ingestion-required'}},'decision_sync':{'participants':{'work':{'project_id':'work-project','thread_id':'work-thread'},'codex':{'project_id':'codex-project','thread_id':'codex-thread'}},'sources':{'work':['chat:work-thread'],'codex':['chat:codex-thread']},'registries':{'work':'external:work-registry','codex':'external:codex-registry'},'policy':d.POLICY}}
        self.contract=self.root/'project-sync.json';self.contract.write_bytes(c.encode(self.config))
        self.base=d.empty('new-project');self.draft={'decision_id':'engine','topic':'implementation.engine','text':'Use the approved engine.','consequences':['Constrain the implementation.']}
        self.approval=self.approve(self.draft['text'],'work')
        self.ledger=d.capture(self.config,self.base,self.draft,self.approval,'work')
        self.input=self.root/'decisions.json';self.input.write_bytes(c.encode(self.ledger))
        self.req,self.j=d.prepare(self.contract,self.input,None,'work-to-codex','TEST ONLY')
        self.requirement=self.root/'requirement.json';self.requirement.write_bytes(c.encode(self.req))

    def approve(self,text,env,mode='written'):
        return {'validated_by':'TEST FIXTURE HUMAN (SIMULATED)','mode':mode,'validated_at':'2026-10-04T10:00:00Z','reference':'chat:'+env+'-thread#human-1','source_reference':'chat:'+env+'-thread#human-1','text_sha256':c.digest(text.encode())}

    def observation(self,j=None,req=None,channel='primary'):
        j=j or self.j;req=req or self.req;op=j['operation'];i=op['identity'];env=i['destination_environment']
        return {'environment':env,**i['destination'],'artifact_locator':d.targets(op,'primary')['decisions.json'] if channel=='primary' else 'gdrive:file:TEST_DECISIONS','retrieved_sha256':op['files'][0]['sha256'],'qualified_validations':req['validation_references'],'registry_locator':self.config['decision_sync']['registries'][env],'authority':'TEST ONLY SIMULATED qualification'}

    def discovery(self,j=None,primary='absent',fallback='absent'):
        j=j or self.j;op=j['operation']
        return {'operation_id':op['operation_id'],'nonce':op['nonce'],'journal_sha256':c.digest(c.encode(j)),'results':{key:{'status':value,'reference':'TEST ONLY observed'} for key,value in [('primary',primary),('fallback',fallback)]},'authority':'TEST ONLY'}

    def receive(self,j=None,req=None,channel='primary',base=None,observation=None,suffix=''):
        store=self.root/('store'+suffix);proof=self.root/('proof'+suffix+'.json');registry=self.root/('registry'+suffix+'.json')
        p=d.receive(self.contract,self.input,self.requirement,j or self.j,observation or self.observation(j,req,channel),base,channel,store,proof,registry)
        return store,proof,registry,p

    def receipt(self,j,proof,registry,channel):
        op=j['operation'];value={'format':'SYNCPILOT-DECISION-RECEIPT','schema_version':1,'operation_id':op['operation_id'],'nonce':op['nonce'],'identity':op['identity'],'channel':channel,'status':'RECEIVED_VERIFIED','files':op['files'],'proof_sha256':c.digest(proof.read_bytes()),'registry_sha256':c.digest(registry.read_bytes())}
        path=self.root/'receipt.json';path.write_bytes(c.encode(value));return path

    def returned_observation(self,j,proof,receipt,registry,channel):
        op=j['operation'];env=op['identity']['destination_environment'];p=op['profiles'][channel];targets=d.targets(op,'primary')
        return {'environment':env,**op['identity']['destination'],'channel':channel,'account':p['account'],'storage_root':p['locator'],'artifact_locator':targets['decisions.json'] if channel=='primary' else 'gdrive:file:TEST_DECISIONS','proof_locator':targets['proof.json'] if channel=='primary' else 'gdrive:file:TEST_PROOF','receipt_locator':targets['receipt.json'] if channel=='primary' else 'gdrive:file:TEST_RECEIPT','registry_file_locator':targets['registry.json'] if channel=='primary' else 'gdrive:file:TEST_REGISTRY','proof_sha256':c.digest(proof.read_bytes()),'receipt_sha256':c.digest(receipt.read_bytes()),'registry_sha256':c.digest(registry.read_bytes()),'receiver_finished':True,'authority':'TEST ONLY SIMULATED destination qualification'}

    def test_work_bootstrap_without_git(self):
        c.validate_contract(self.config)
        self.assertIsNone(self.config['repository'])
        _,_,registry,p=self.receive();self.assertEqual(c.load(registry),self.ledger);self.assertEqual(p['code_status'],'NOT_ASSESSED')

    def test_proposed_decision_not_synchronized(self):
        proposed=d.capture(self.config,self.base,self.draft,None,'work');self.assertEqual(proposed['state'],'PROPOSED')
        with self.assertRaises(c.SyncError):d.validate_ledger(proposed,self.config)

    def test_oral_codex_decision_no_second_validation(self):
        draft={**self.draft,'decision_id':'ui','topic':'ui.style','text':'Use the validated visual style.'}
        ledger=d.capture(self.config,self.ledger,draft,self.approve(draft['text'],'codex','oral'),'codex')
        self.assertEqual(ledger['records'][1]['validation']['mode'],'oral')
        self.assertEqual(d.capture(self.config,ledger,draft,self.approve(draft['text'],'codex','oral'),'codex'),ledger)

    def test_validation_covers_exact_text(self):
        with self.assertRaises(c.SyncError):d.capture(self.config,self.base,self.draft,{**self.approval,'text_sha256':'0'*64},'work')

    def test_foreign_origin_or_validation_scope_rejected(self):
        for key in ['reference','source_reference']:
            with self.assertRaises(c.SyncError):d.capture(self.config,self.base,self.draft,{**self.approval,key:'chat:other'},'work')

    def test_revision_requires_exact_previous(self):
        revised={**self.draft,'text':'Use the revised approved engine.'};approval=self.approve(revised['text'],'codex','oral')
        with self.assertRaises(c.SyncError):d.capture(self.config,self.ledger,revised,approval,'codex')
        new=d.capture(self.config,self.ledger,revised,approval,'codex',d.record_hash(self.ledger['records'][0]));self.assertEqual(new['records'][1]['revision'],2)

    def test_conflicting_revision_no_last_write_wins(self):
        other=d.capture(self.config,self.base,{**self.draft,'text':'Use another engine.'},self.approve('Use another engine.','codex'),'codex')
        with self.assertRaises(c.SyncError):d.merge(self.ledger,other,self.config)

    def test_topic_collision_requires_arbitration(self):
        other=d.capture(self.config,self.base,{**self.draft,'decision_id':'another-engine'},self.approval,'work')
        with self.assertRaises(c.SyncError):d.merge(self.ledger,other,self.config)

    def test_record_origin_identity_cannot_be_forged(self):
        ledger=copy.deepcopy(self.ledger);ledger['records'][0]['origin']['thread_id']='other'
        with self.assertRaises(c.SyncError):d.validate_ledger(ledger,self.config)

    def test_prepare_reuses_operation_and_nonce(self):
        req,j=d.prepare(self.contract,self.input,None,'work-to-codex','TEST ONLY');self.assertEqual(req,self.req);self.assertEqual(j,self.j)

    def test_channel_does_not_change_identity(self):
        j=d.append(self.j,'DC_UNAVAILABLE','primary','not-delivered','TEST ONLY offline')
        p=d.plan(j,self.discovery(j,primary='unavailable'),'fallback');self.assertEqual(p['operation_id'],self.j['operation']['operation_id']);self.assertEqual(p['nonce'],self.j['operation']['nonce'])

    def test_no_drive_if_dc_available(self):
        with self.assertRaises(c.SyncError):d.plan(self.j,self.discovery(),'fallback')

    def test_generic_failure_does_not_authorize_drive(self):
        j=d.append(self.j,'TRANSPORT_FAILED','primary','not-delivered','TEST ONLY encoding error')
        with self.assertRaises(c.SyncError):d.plan(j,self.discovery(j,primary='unavailable'),'fallback')

    def test_uncertain_receipt_blocks_both(self):
        j=d.append(self.j,'DC_UNAVAILABLE','primary','unknown','TEST ONLY timeout')
        for channel in ('primary','fallback'):self.assertEqual(d.plan(j,self.discovery(j,primary='unavailable'),channel)['action'],'BLOCKED')

    def test_rejection_blocks_other_channel(self):
        j=d.append(self.j,'VALIDATION_REJECTED','primary','present','TEST ONLY wrong identity');self.assertEqual(d.plan(j,self.discovery(j,primary='unavailable'),'fallback')['action'],'BLOCKED')

    def test_resume_collects_and_never_redeposits(self):
        j=d.append(self.j,'DEPOSITED','primary','present','TEST ONLY bytes');self.assertEqual(d.plan(j,self.discovery(j,primary='available'),'primary')['action'],'COLLECT_EXISTING')

    def test_stale_discovery_and_changed_history(self):
        j=d.append(self.j,'RECEIVED','primary','present','TEST ONLY')
        with self.assertRaises(c.SyncError):d.plan(j,self.discovery(),'primary')
        j['events'][0]['previous_sha256']='0'*64
        with self.assertRaises(c.SyncError):d.validate_operation(j)

    def test_wrong_receiver_or_unqualified_validation(self):
        for key,value in [('thread_id','other'),('environment','work'),('qualified_validations',[])]:
            obs={**self.observation(),key:value}
            with self.assertRaises(c.SyncError):self.receive(observation=obs)
        self.assertFalse((self.root/'store').exists())

    def test_modified_packet_has_no_store_or_proof(self):
        self.input.write_bytes(self.input.read_bytes()+b' ')
        with self.assertRaises(c.SyncError):self.receive()
        self.assertFalse((self.root/'store').exists());self.assertFalse((self.root/'proof.json').exists())

    def test_destination_changed_blocks_without_mutation(self):
        base=self.root/'actual-base.json';base.write_bytes(c.encode(self.ledger));before=base.read_bytes()
        with self.assertRaises(c.SyncError):self.receive(base=base)
        self.assertEqual(base.read_bytes(),before);self.assertFalse((self.root/'store').exists())

    def test_merge_preserves_local_decisions(self):
        draft={**self.draft,'decision_id':'ui','topic':'ui.style','text':'Keep local validated style.'}
        local=d.capture(self.config,self.base,draft,self.approve(draft['text'],'codex','oral'),'codex')
        merged=d.merge(local,self.ledger,self.config);self.assertEqual(len(merged['records']),2);self.assertEqual(d.merge(merged,self.ledger,self.config),merged)

    def test_receive_check_confirm_both_channels(self):
        for channel in ['primary','fallback']:
            with self.subTest(channel=channel):
                j=self.j if channel=='primary' else d.append(self.j,'DC_UNAVAILABLE','primary','not-delivered','TEST ONLY')
                store,proof,registry,_=self.receive(j=j,channel=channel,suffix=channel)
                d.check(self.contract,store,self.requirement,j,channel)
                receipt=self.receipt(j,proof,registry,channel);obs=self.returned_observation(j,proof,receipt,registry,channel)
                done=d.confirm(self.contract,self.input,self.requirement,j,None,proof,receipt,registry,obs);self.assertEqual(d.state(done),'VERIFIED')

    def test_return_direction_codex_to_work(self):
        self.req,self.j=d.prepare(self.contract,self.input,None,'codex-to-work','TEST ONLY');self.requirement.write_bytes(c.encode(self.req))
        store,proof,registry,_=self.receive();self.assertEqual(c.load(proof)['observation']['environment'],'work')
        receipt=self.receipt(self.j,proof,registry,'primary');obs=self.returned_observation(self.j,proof,receipt,registry,'primary')
        self.assertEqual(d.state(d.confirm(self.contract,self.input,self.requirement,self.j,None,proof,receipt,registry,obs)),'VERIFIED')

    def test_foreign_or_unfinished_return_rejected(self):
        _,proof,registry,_=self.receive();receipt=self.receipt(self.j,proof,registry,'primary');obs=self.returned_observation(self.j,proof,receipt,registry,'primary')
        for key,value in [('receiver_finished',False),('thread_id','other'),('registry_sha256','0'*64),('proof_locator','gdrive:file:WRONG')]:
            with self.assertRaises(c.SyncError):d.confirm(self.contract,self.input,self.requirement,self.j,None,proof,receipt,registry,{**obs,key:value})

    def test_registry_and_store_tamper_rejected(self):
        store,proof,registry,_=self.receive();(store/'registry.json').write_bytes(c.encode(self.base))
        with self.assertRaises(c.SyncError):d.check(self.contract,store,self.requirement,self.j,'primary')

    def test_outputs_not_overwritten(self):
        self.receive();before=(self.root/'registry.json').read_bytes()
        with self.assertRaises(c.SyncError):self.receive()
        self.assertEqual((self.root/'registry.json').read_bytes(),before)

    def test_capture_cli_proposal_and_repeat_prepare(self):
        draft=self.root/'draft.json';draft.write_bytes(c.encode(self.draft));output=self.root/'proposal.json'
        run=lambda args:subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True)
        import sys
        self.assertEqual(run(['capture','--contract',str(self.contract),'--ledger',str(self.input),'--draft',str(draft),'--environment','codex','--output',str(output)]).returncode,0)
        self.assertEqual(c.load(output)['state'],'PROPOSED')
        journal=self.root/'journal.json';args=['prepare','--contract',str(self.contract),'--ledger',str(self.input),'--requirement',str(self.requirement),'--journal',str(journal),'--direction','work-to-codex','--authority','TEST ONLY']
        self.assertEqual(run(args).returncode,0);recorded=d.append(c.load(journal),'DEPOSITED','primary','present','TEST ONLY');journal.write_bytes(c.encode(recorded));self.assertEqual(run(args).returncode,0);self.assertEqual(c.load(journal),recorded)

    def test_migration_v2_preserves_every_existing_setting(self):
        legacy={k:v for k,v in self.config.items() if k!='decision_sync'};legacy['schema_version']=2;legacy['repository']='https://example.invalid/project';legacy['reference_branch']='main'
        old=self.root/'old.json';old.write_bytes(c.encode(legacy));settings=self.root/'settings.json';settings.write_bytes(c.encode(self.config['decision_sync']));output=self.root/'new.json'
        import sys
        result=subprocess.run([sys.executable,str(SCRIPT),'migrate','--contract',str(old),'--decision-config',str(settings),'--output',str(output)],capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout)
        upgraded=c.load(output)
        for key in legacy:
            if key!='schema_version':self.assertEqual(upgraded[key],legacy[key])


if __name__=='__main__':unittest.main()
