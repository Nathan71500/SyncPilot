"""SIMULATED offline incident regression. No chat, transport or canonical writes."""
import argparse
import copy
import subprocess
import sys
import unittest

import test_decisions as fixtures
import test_persistence as persistence
import test_syncpilot as packages

d=fixtures.d
c=fixtures.c


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.DecisionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.old=copy.deepcopy(self.f.config)
        self.config=d.migrate_routing(self.old)
        self.f.config=self.config;self.f.contract.write_bytes(c.encode(self.config))
        self.f.ledger=d.capture(self.config,self.f.base,self.f.draft,self.f.approval,'work',source_thread='work-new-session')
        self.f.input.write_bytes(c.encode(self.f.ledger))
        self.route={'format':'SYNCPILOT-DECISION-ROUTING','schema_version':1,'source':{'project_id':'work-project','thread_id':'work-new-session'},'destination':{'project_id':'codex-project','thread_id':'codex-new-session'},'authority':'SIMULATED HUMAN MANDATE','qualification_reference':'SIMULATED application observation','delivery':'application-message'}
        self.prepare()

    def prepare(self,route=None,direction='work-to-codex'):
        self.f.req,self.f.j=d.prepare(self.f.contract,self.f.input,None,direction,'SIMULATED TEST ONLY',self.route if route is None else route)
        self.f.requirement.write_bytes(c.encode(self.f.req))

    def pickup(self,thread='codex-pickup-session'):
        obs={'environment':'codex','project_id':'codex-project','thread_id':thread,'authority':'SIMULATED authorized receiver','qualification_reference':'SIMULATED current app observation'}
        self.f.j=d.select_receiver(self.f.j,obs,'primary')
        return obs

    def inbox(self):
        self.route['delivery']='shared-inbox';self.route['destination']['thread_id']=None
        self.prepare()

    def observed_receiver(self):
        return {**self.f.observation(),**{k:v for k,v in d.receiver(self.f.j['operation'],self.f.j).items() if k in ('project_id','thread_id')}}

    def roundtrip(self):
        store,proof,registry,_=self.f.receive(observation=self.observed_receiver())
        d.check(self.f.contract,store,self.f.requirement,self.f.j,'primary')
        receipt=self.f.receipt(self.f.j,proof,registry,'primary')
        observed=self.f.returned_observation(self.f.j,proof,receipt,registry,'primary')
        observed.update({k:v for k,v in self.observed_receiver().items() if k in ('project_id','thread_id')})
        result=d.confirm(self.f.contract,self.f.input,self.f.requirement,self.f.j,None,proof,receipt,registry,observed)
        self.assertEqual(d.state(result),'VERIFIED')
        self.assertEqual(c.load(registry),self.f.ledger)
        self.assertEqual(c.load(proof)['code_status'],'NOT_ASSESSED')

    def test_migration_changes_only_version_and_participant_threads(self):
        restored=copy.deepcopy(self.config);restored['schema_version']=3
        restored['decision_sync']['participants']=self.old['decision_sync']['participants']
        self.assertEqual(restored,self.old)
        self.assertEqual(self.old['decision_sync']['participants']['codex']['thread_id'],'codex-thread')
        self.assertTrue(all(set(p)=={'project_id'} for p in self.config['decision_sync']['participants'].values()))

    def test_history_keeps_actual_old_and_new_thread_origins(self):
        old=d.capture(self.old,self.f.base,self.f.draft,self.f.approval,'work')
        d.validate_ledger(old,self.config)
        self.assertEqual(old['records'][0]['origin']['thread_id'],'work-thread')
        self.assertEqual(self.f.ledger['records'][0]['origin']['thread_id'],'work-new-session')
        with self.assertRaises(c.SyncError):d.validate_ledger(self.f.ledger,self.old)

    def test_capture_requires_actual_thread_and_exact_validation(self):
        with self.assertRaises(c.SyncError):d.capture(self.config,self.f.base,self.f.draft,self.f.approval,'work')
        with self.assertRaises(c.SyncError):d.capture(self.config,self.f.base,self.f.draft,{**self.f.approval,'text_sha256':'0'*64},'work',source_thread='actual')
        approval={**self.f.approval,'mode':'oral'}
        ledger=d.capture(self.config,self.f.base,self.f.draft,approval,'work',source_thread='actual')
        self.assertEqual(ledger,d.capture(self.config,ledger,self.f.draft,approval,'work',source_thread='actual'))

    def test_scope_is_not_widened_with_session_flexibility(self):
        for key in ('source_reference','reference'):
            with self.assertRaises(c.SyncError):d.capture(self.config,self.f.base,self.f.draft,{**self.f.approval,key:'chat:unqualified'},'work',source_thread='actual')
        bad=copy.deepcopy(self.f.ledger);bad['records'][0]['origin']['project_id']='another-project'
        with self.assertRaises(c.SyncError):d.validate_ledger(bad,self.config)

    def test_new_session_uses_durable_human_evidence_without_contract_change(self):
        before=c.encode(self.config)
        approval={**self.f.approval,'source_reference':'external:work-registry#SIMULATED-human-evidence-1','reference':'external:work-registry#SIMULATED-human-evidence-1','mode':'oral'}
        ledger=d.capture(self.config,self.f.base,self.f.draft,approval,'work',source_thread='another-work-session')
        self.assertEqual(ledger['records'][0]['origin']['thread_id'],'another-work-session')
        self.assertEqual(c.encode(self.config),before)
        with self.assertRaises(c.SyncError):d.capture(self.config,self.f.base,self.f.draft,{**approval,'reference':'external:codex-registry#other-role'},'work',source_thread='actual')
        with self.assertRaises(c.SyncError):d.capture(self.old,self.f.base,self.f.draft,approval,'work')

    def test_v5_routing_cannot_be_missing_or_foreign(self):
        with self.assertRaises(c.SyncError):d.prepare(self.f.contract,self.f.input,None,'work-to-codex','TEST')
        for key in ('source','destination'):
            bad=copy.deepcopy(self.route);bad[key]['project_id']='foreign'
            with self.assertRaises(c.SyncError):self.prepare(bad)

    def test_exec_resume_is_not_a_delivery_channel(self):
        bad={**self.route,'delivery':'codex-exec-resume'}
        with self.assertRaises(c.SyncError):self.prepare(bad)

    def test_legacy_operation_cannot_be_reinterpreted_as_v5(self):
        path=self.f.root/'old-contract.json';path.write_bytes(c.encode(self.old))
        old_ledger=d.capture(self.old,self.f.base,self.f.draft,self.f.approval,'work')
        source=self.f.root/'old-ledger.json';source.write_bytes(c.encode(old_ledger))
        with self.assertRaises(c.SyncError):d.prepare(path,source,None,'work-to-codex','TEST',self.route)
        req,journal=d.prepare(path,source,None,'work-to-codex','TEST')
        requirement=self.f.root/'old-requirement.json';requirement.write_bytes(c.encode(req))
        with self.assertRaises(c.SyncError):d.verify(self.f.contract,source,requirement,journal)

    def test_new_sessions_complete_without_original_sessions(self):
        self.roundtrip()

    def test_codex_to_work_uses_the_qualified_current_work_chat(self):
        route={**self.route,'source':self.route['destination'],'destination':self.route['source']}
        self.prepare(route,'codex-to-work');self.roundtrip()

    def test_inbox_deposit_does_not_need_any_codex_session(self):
        self.inbox()
        self.assertIsNone(self.f.j['operation']['identity']['destination']['thread_id'])
        plan=d.plan(self.f.j,self.f.discovery(),'primary')
        self.assertEqual(plan['action'],'DEPOSIT_ONCE')
        with self.assertRaises(c.SyncError):d.receiver(self.f.j['operation'],self.f.j)
        with self.assertRaises(c.SyncError):self.f.receive()
        self.assertFalse((self.f.root/'store').exists())

    def test_inbox_pickup_keeps_operation_nonce_and_targets(self):
        self.inbox();before=copy.deepcopy(self.f.j['operation']);targets=d.targets(before,'primary')
        self.pickup()
        self.assertEqual(self.f.j['operation'],before)
        self.assertEqual(d.targets(self.f.j['operation'],'primary'),targets)
        self.roundtrip()

    def test_inbox_has_one_receiver_without_repeated_dispatch(self):
        self.inbox();observation=self.pickup();before=copy.deepcopy(self.f.j)
        self.assertEqual(d.select_receiver(self.f.j,observation,'primary'),before)
        with self.assertRaises(c.SyncError):self.pickup('second-session')
        bad={**observation,'project_id':'foreign'}
        with self.assertRaises(c.SyncError):d.select_receiver(self.f.j,bad,'primary')

    def test_receiver_cannot_be_rebound_after_pickup(self):
        self.inbox();self.pickup()
        wrong={**self.observed_receiver(),'thread_id':'another-session'}
        with self.assertRaises(c.SyncError):self.f.receive(observation=wrong)
        self.assertFalse((self.f.root/'registry.json').exists())

    def test_routing_tamper_and_invented_history_are_rejected(self):
        changed=copy.deepcopy(self.f.j);changed['operation']['routing']['destination']['thread_id']='another'
        with self.assertRaises(c.SyncError):d.validate_operation(changed)
        self.inbox();self.pickup();changed=copy.deepcopy(self.f.j)
        changed['events'][0]['receiver']['project_id']='foreign'
        with self.assertRaises(c.SyncError):d.validate_operation(changed)

    def test_same_routing_reuses_nonce_and_new_route_cannot_overwrite(self):
        req,j=d.prepare(self.f.contract,self.f.input,None,'work-to-codex','SIMULATED TEST ONLY',self.route)
        self.assertEqual(j,self.f.j)
        journal=self.f.root/'journal.json';journal.write_bytes(c.encode(j));before=journal.read_bytes()
        route=self.f.root/'routing.json';route.write_bytes(c.encode({**self.route,'destination':{**self.route['destination'],'thread_id':'another'}}))
        missing_requirement=self.f.root/'not-created.json'
        result=subprocess.run([sys.executable,str(fixtures.SCRIPT),'prepare','--contract',str(self.f.contract),'--ledger',str(self.f.input),'--direction','work-to-codex','--authority','SIMULATED TEST ONLY','--routing',str(route),'--journal',str(journal),'--requirement',str(missing_requirement)],capture_output=True)
        self.assertEqual(result.returncode,2,result.stdout)
        self.assertEqual(journal.read_bytes(),before);self.assertFalse(missing_requirement.exists())

    def test_v5_with_or_without_persistence_preserves_required_target(self):
        c.validate_contract(self.config)
        fixture=persistence.PersistenceTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        migrated=d.migrate_routing(fixture.config);c.validate_contract(migrated)
        self.assertEqual(migrated['work_persistence'],fixture.config['work_persistence'])
        job=persistence.p.prepare(migrated,{**fixture.transport,'destination_thread':'work-new'},fixture.artifacts)
        self.assertEqual(job['operation']['destination_thread'],'work-new')
        with self.assertRaises(persistence.p.c.SyncError):persistence.p.contract(self.config)
        foreign={**fixture.transport,'destination':'other'}
        with self.assertRaises(persistence.p.c.SyncError):persistence.p.prepare(migrated,foreign,fixture.artifacts)

    def test_v5_git_package_roundtrip_keeps_persistence_requirement(self):
        for with_persistence in (False,True):
            f=packages.SyncPilotTests();f.setUp();self.addCleanup(f.doCleanups)
            core=packages.c
            f.contract['schema_version']=4 if with_persistence else 3
            f.contract['decision_sync']=copy.deepcopy(self.old['decision_sync'])
            f.contract['decision_sync']['participants']['work']={'project_id':'test:work','thread_id':'historic-work-thread'}
            if with_persistence:
                f.contract['work_persistence']={'target':{'kind':'page-files','project_id':'test:work','container_id':'qualified-page'},'registry':'page:qualified-page#registry','policy':persistence.p.POLICY}
            f.contract=d.migrate_routing(f.contract)
            (f.repo/core.CONTRACT).write_bytes(core.encode(f.contract))
            f.git('add',core.CONTRACT);f.git('-c','commit.gpgsign=false','commit','-m','SIMULATED v5')
            f.req=f.root/'v5-requirement.json';f.package=f.root/'v5-package.zip';f.carrier=f.root/'v5-carrier.json'
            core.prepare_requirement(argparse.Namespace(repository=f.repo,commit=f.git('rev-parse','HEAD'),domain=['docs'],authority='SIMULATED',output=f.req))
            core.build(argparse.Namespace(repository=f.repo,requirement=f.req,output=f.package,carrier=f.carrier,attestation=None))
            f.j=packages.t.prepare(f.carrier,f.req,'test:thread','SIMULATED')
            receipt,observed,proof,evidence=f.receipt_fixture()
            journal,result=packages.t.confirm(f.j,receipt,observed,f.carrier,f.req,proof,evidence)
            self.assertEqual(packages.t.state(journal),'VERIFIED')
            self.assertEqual('completion_status' in result,with_persistence)
            if with_persistence:self.assertEqual(result['work_availability'],'NOT_VERIFIED')


if __name__=='__main__':unittest.main()
