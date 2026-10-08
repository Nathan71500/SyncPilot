"""SIMULATED app-server responses; no real actor, server or canonical write."""
import copy
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

import test_decisions as fixtures

SCRIPT=Path(__file__).resolve().parents[1]/'syncpilot/skills/syncpilot-dc/scripts/syncpilot_codex_bridge.py'
spec=importlib.util.spec_from_file_location('bridge_tests',SCRIPT)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
c=b.c;d=b.d


class FakeRpc:
    def __init__(self,executable,cwd):
        self.cwd=cwd;self.process=SimpleNamespace(pid=12345);self.calls=[];self.events=[]
        self.failure=None;self.wrong_completion=False;self.fail_turn=False;self.fail_before_work=False
        self.resume_error=None;self.receiver_status='idle';self.last_turn_status='completed'
        self.created_thread_id='SIMULATED-receiver';self.active_thread_id='SIMULATED-receiver'
        self.on_read=None;self.initialize_error=False;self.initialize_refusal=False;self.turns_error=None

    def initialize(self):
        if self.initialize_refusal:raise b.RpcRefusal('initialize',{'code':-32600,'message':'SIMULATED generic native API refusal'})
        if self.initialize_error:raise c.SyncError('SIMULATED unavailable native socket')
        return {'userAgent':'SIMULATED official API'}

    def call(self,method,params,timeout=30):
        self.calls.append((method,params))
        if method==self.failure:raise c.SyncError('SIMULATED lost response')
        if method=='thread/resume' and self.resume_error:raise b.RpcRefusal(method,self.resume_error)
        if method=='thread/read':
            if self.on_read:self.on_read()
            return {'thread':{'id':params['threadId'],'cwd':str(self.cwd),'status':{'type':self.receiver_status}}}
        if method=='thread/turns/list':
            if self.turns_error:raise b.RpcRefusal(method,self.turns_error)
            return {'data':[{'id':'SIMULATED-turn','status':self.last_turn_status,'items':[]}]}
        if method in ('thread/start','thread/resume'):
            self.active_thread_id=params.get('threadId',self.created_thread_id)
            return {'thread':{'id':self.active_thread_id,'cwd':str(self.cwd),'status':{'type':self.receiver_status}}}
        if method=='turn/start':
            if self.fail_before_work:
                self.events=[{'method':'turn/completed','params':{'threadId':self.active_thread_id,
                    'turn':{'id':'SIMULATED-turn','status':'failed','items':[],
                    'error':{'message':json.dumps({'type':'error','status':400,'error':{'type':'invalid_request_error',
                             'message':"The 'SIMULATED' model is not supported when using Codex with a ChatGPT account."}})}}}}]
                return {'turn':{'id':'SIMULATED-turn','status':'inProgress'}}
            self.events=[{'method':'item/completed','params':{'threadId':self.active_thread_id,'turnId':'SIMULATED-turn',
                          'item':{'type':'agentMessage','text':'SIMULATED final \u00e9 \U0001f9e9'}}},
                         {'method':'turn/completed','params':{'threadId':'another' if self.wrong_completion else self.active_thread_id,
                          'turn':{'id':'SIMULATED-turn','status':'failed' if self.fail_turn else 'completed','error':{'message':'SIMULATED error'} if self.fail_turn else None}}}]
            return {'turn':{'id':'SIMULATED-turn','status':'inProgress'}}
        if method=='turn/interrupt':
            self.events=[{'method':'turn/completed','params':{'threadId':self.active_thread_id,
                          'turn':{'id':'SIMULATED-turn','status':'interrupted','error':None}}}]
        return {}

    def next(self,timeout):return self.events.pop(0) if self.events else None

    def close(self):return 0


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.DecisionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.canonical=self.f.root/'canonical';self.canonical.mkdir()
        self.config=d.migrate_routing(self.f.config)
        storage=self.f.root/'transport'
        self.config['transport']['primary']['locator']='dc://11111111-1111-4111-8111-111111111111/'+quote(str(storage),safe='')
        self.contract=self.canonical/'project-sync.json';self.contract.write_bytes(c.encode(self.config))
        self.ledger=d.capture(self.config,self.f.base,self.f.draft,self.f.approval,'work',source_thread='SIMULATED-work')
        self.f.input.write_bytes(c.encode(self.ledger))
        routing={'format':'SYNCPILOT-DECISION-ROUTING','schema_version':1,
                 'source':{'project_id':'work-project','thread_id':'SIMULATED-work'},
                 'destination':{'project_id':'codex-project','thread_id':None},'authority':'SIMULATED authorized circuit',
                 'qualification_reference':'SIMULATED observed project','delivery':'shared-inbox'}
        self.req,self.j=d.prepare(self.contract,self.f.input,None,'work-to-codex','SIMULATED TEST ONLY',routing)
        self.j=d.append(self.j,'DEPOSITED','primary','present','SIMULATED exact-byte deposit')
        self.oproot=storage/'new-project'/self.j['operation']['operation_id'];self.oproot.mkdir(parents=True)
        (self.oproot/'decisions.json').write_bytes(c.encode(self.ledger));(self.oproot/'requirement.json').write_bytes(c.encode(self.req))
        self.journal=self.oproot/'journal-deposited.json';self.journal.write_bytes(c.encode(self.j))
        self.request={'contract':str(self.contract),'journal':str(self.journal),'canonical_root':str(self.canonical),
                      'project_name':'Example','source':{'environment':'work','project_id':'work-project','thread_id':'SIMULATED-work',
                      'authority':'SIMULATED human mandate','qualification_reference':'SIMULATED independent source'},
                      'authority':{'reference':'SIMULATED human circuit mandate','allow_message':True,'allow_create':True},
                      'prompt':'SIMULATED read exact packet and return independent proof; no Git write.'}
        self.clients=[]

    def run_bridge(self,retry_before_work=False,bridge_options=None,**changes):
        def factory(executable,cwd):
            client=FakeRpc(executable,cwd)
            for name,value in changes.items():setattr(client,name,value)
            self.clients.append(client);return client
        with contextlib.redirect_stdout(io.StringIO()):
            options=dict(bridge_options or {})
            if options.get('recovery_observation') and 'recovery_observation_sha256' not in options:
                options['recovery_observation_sha256']=c.digest(options['recovery_observation'].read_bytes())
            return b.run(self.request,Path('/SIMULATED/codex'),rpc_factory=factory,retry_before_work=retry_before_work,**options)

    def second_operation(self):
        self.previous_job=self.oproot/'codex-dispatch'
        self.req,self.j=d.prepare(self.contract,self.f.input,None,'work-to-codex','SIMULATED SECOND MANDATE',self.j['operation']['routing'])
        self.j=d.append(self.j,'DEPOSITED','primary','present','SIMULATED second deposit')
        self.oproot=self.oproot.parent/self.j['operation']['operation_id'];self.oproot.mkdir()
        (self.oproot/'decisions.json').write_bytes(c.encode(self.ledger))
        (self.oproot/'requirement.json').write_bytes(c.encode(self.req))
        self.journal=self.oproot/'journal-deposited.json';self.journal.write_bytes(c.encode(self.j))
        self.request['journal']=str(self.journal)

    def recovery_observation(self,**changes):
        confirmation=c.load(self.previous_job/'journal-selected.json')
        confirmation=d.append(confirmation,'RECEIVED','primary','present','SIMULATED independent reception')
        confirmation=d.append(confirmation,'VERIFIED','primary','present','SIMULATED parent confirmed exact return')
        confirmation_path=self.previous_job.parent/'journal-confirmed.json';confirmation_path.write_bytes(c.encode(confirmation))
        observed={'format':'SYNCPILOT-CODEX-RECEIVER-AVAILABILITY','schema_version':1,
                  'observed_at':datetime.now(timezone.utc).isoformat(),'observer_environment':'codex',
                  'qualification_reference':'SIMULATED independent native wait_threads completion',
                  'authority_reference':self.request['authority']['reference'],'project_id':'new-project',
                  'codex_project_id':'codex-project','thread_id':'SIMULATED-receiver','canonical_root':str(self.canonical),
                  'active_turn_id':None,'pending_launch':False,'native_message_channel':'unavailable',
                  'native_channel_reference':'SIMULATED official native message/proxy unavailable',
                  'last_turn_id':'SIMULATED-turn','last_turn_status':'completed','completed_job':str(self.previous_job),
                  'parent_confirmed':True,'parent_confirmation_reference':'SIMULATED independently reread parent confirm',
                  'confirmation_journal':str(confirmation_path),'confirmation_journal_sha256':c.digest(confirmation_path.read_bytes())}
        observed.update(changes)
        authority=self.oproot.parent/'.authority';authority.mkdir(exist_ok=True)
        path=authority/(self.j['operation']['operation_id']+'-receiver-observation.json')
        path.write_bytes(c.encode(observed));return path

    def writer_conflict(self):return {'code':-32600,'message':'Thread already has an active writer'}

    def test_dispatch_finish_exact_operation_and_no_false_parent_confirmation(self):
        before=self.contract.read_bytes();result=self.run_bridge();state=result['state']
        self.assertEqual(result['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertTrue(state['agent_finished_observed']);self.assertFalse(state['parent_confirmed'])
        self.assertEqual(state['operation_id'],self.j['operation']['operation_id']);self.assertEqual(state['nonce'],self.j['operation']['nonce'])
        self.assertEqual(self.contract.read_bytes(),before)
        self.assertEqual(c.load(self.oproot.parent/'.receivers/codex/RECEIVER.json')['title'],'Example-RECEVEUR')
        self.assertFalse((self.oproot.parent/'.receivers/codex/OWNER.json').exists())

    def test_collect_does_not_dispatch_again_and_preserves_exact_results(self):
        self.run_bridge();before={p.name:p.read_bytes() for p in (self.oproot/'codex-dispatch').iterdir()}
        result=self.run_bridge();self.assertEqual(result['action'],'COLLECT_EXISTING');self.assertEqual(len(self.clients),1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.oproot/'codex-dispatch').iterdir()})
        # Collection does not require today's mutable canonical worktree.
        self.contract.write_bytes(b'changed after reception')
        self.assertEqual(self.run_bridge()['action'],'COLLECT_EXISTING')

    def test_changed_prompt_and_altered_result_refused_without_new_actor(self):
        self.run_bridge();self.request['prompt']+=' changed'
        with self.assertRaises(c.SyncError):self.run_bridge()
        self.request['prompt']=self.request['prompt'].removesuffix(' changed')
        (self.oproot/'codex-dispatch/final-messages.json').write_bytes(b'{}')
        with self.assertRaises(c.SyncError):self.run_bridge()
        self.assertEqual(len(self.clients),1)

    def test_message_and_creation_authority_required_before_start(self):
        for key in ('allow_message','allow_create'):
            request=copy.deepcopy(self.request);request['authority'][key]=False
            with self.assertRaises(c.SyncError):b.run(request,Path('/SIMULATED/codex'),rpc_factory=FakeRpc)
        self.assertFalse((self.oproot/'codex-dispatch').exists())

    def test_wrong_source_project_and_altered_packet_refused_before_start(self):
        request=copy.deepcopy(self.request);request['source']['project_id']='foreign'
        with self.assertRaises(c.SyncError):b.run(request,Path('/SIMULATED/codex'),rpc_factory=FakeRpc)
        (self.oproot/'decisions.json').write_bytes(b'{}')
        with self.assertRaises(c.SyncError):self.run_bridge()
        self.assertFalse((self.oproot/'codex-dispatch').exists())

    def test_owner_application_selection_is_never_resumed(self):
        observation={'environment':'codex','project_id':'codex-project','thread_id':'SIMULATED-owner-application',
                     'authority':'SIMULATED','qualification_reference':'SIMULATED owner app'}
        self.journal.write_bytes(c.encode(d.select_receiver(self.j,observation,'primary')))
        with self.assertRaises(c.SyncError):self.run_bridge()
        self.assertFalse((self.oproot/'codex-dispatch').exists())

    def test_lost_creation_response_retains_owner_and_no_repeat(self):
        result=self.run_bridge(failure='thread/start')
        self.assertEqual(result['action'],'BLOCKED_DISPATCH');self.assertFalse(result['state']['agent_finished_observed'])
        self.assertTrue((self.oproot.parent/'.receivers/codex/OWNER.json').exists())
        self.assertEqual(self.run_bridge()['action'],'FOLLOW_EXISTING_DISPATCH');self.assertEqual(len(self.clients),1)

    def test_lost_turn_start_response_retains_owner_and_no_repeat(self):
        result=self.run_bridge(failure='turn/start')
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertTrue(result['state']['dispatch_attempted'])
        self.assertFalse(result['state']['agent_finished_observed'])
        self.assertIsNone(result['state']['turn_id'])
        self.assertTrue((self.oproot.parent/'.receivers/codex/OWNER.json').exists())
        self.assertEqual(self.run_bridge()['action'],'FOLLOW_EXISTING_DISPATCH');self.assertEqual(len(self.clients),1)

    def test_next_operation_reuses_only_registered_bridge_receiver(self):
        self.run_bridge()
        self.second_operation()
        self.request['authority']['allow_create']=False
        self.assertEqual(self.run_bridge()['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertTrue(any(m=='thread/resume' for m,_ in self.clients[-1].calls))
        self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_wrong_completion_is_refused_and_own_turn_interrupted(self):
        result=self.run_bridge(wrong_completion=True)
        self.assertEqual(result['action'],'BLOCKED_DISPATCH');self.assertIn('another actor',result['state']['error'])
        self.assertTrue(any(m=='turn/interrupt' for m,_ in self.clients[0].calls))
        self.assertFalse(result['state']['parent_confirmed'])

    def test_failed_turn_is_reported_as_failed_not_received_or_verified(self):
        result=self.run_bridge(fail_turn=True)
        self.assertEqual(result['action'],'RECEIVER_FAILED');self.assertEqual(result['state']['status'],'FAILED')
        self.assertTrue(result['state']['agent_finished_observed']);self.assertFalse(result['state']['parent_confirmed'])

    def test_explicit_pre_work_capability_repair_preserves_old_proofs_and_receiver(self):
        self.run_bridge(fail_before_work=True)
        original=self.oproot/'codex-dispatch';before={p.name:p.read_bytes() for p in original.iterdir()}
        self.assertEqual(self.run_bridge()['action'],'COLLECT_EXISTING');self.assertEqual(len(self.clients),1)
        result=self.run_bridge(retry_before_work=True)
        self.assertEqual(result['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertEqual(result['state']['operation_id'],self.j['operation']['operation_id'])
        self.assertEqual(result['state']['nonce'],self.j['operation']['nonce'])
        self.assertTrue(any(m=='thread/resume' for m,_ in self.clients[-1].calls))
        self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))
        self.assertEqual(before,{name:(original/name).read_bytes() for name in before})
        self.assertEqual(self.run_bridge(retry_before_work=True)['action'],'COLLECT_EXISTING');self.assertEqual(len(self.clients),2)

    def test_retry_refused_when_reception_result_might_exist(self):
        self.run_bridge(fail_before_work=True);(self.oproot/'proof.json').write_bytes(b'possible partial result')
        with self.assertRaises(c.SyncError):self.run_bridge(retry_before_work=True)
        self.assertEqual(len(self.clients),1)

    def test_exact_writer_conflict_is_preserved_and_idle_alone_cannot_replace(self):
        self.run_bridge();self.second_operation()
        result=self.run_bridge(resume_error=self.writer_conflict())
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertEqual(result['state']['official_error']['error'],self.writer_conflict())
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))
        self.assertEqual(self.run_bridge()['action'],'FOLLOW_EXISTING_DISPATCH')

    def test_qualified_replacement_preserves_registry_history_and_exact_operation(self):
        self.run_bridge();self.second_operation()
        receiver=self.oproot.parent/'.receivers/codex/RECEIVER.json';before=receiver.read_bytes()
        previous={p.name:p.read_bytes() for p in self.previous_job.iterdir()}
        path=self.recovery_observation()
        result=self.run_bridge(resume_error=self.writer_conflict(),created_thread_id='SIMULATED-replacement',
                               bridge_options={'recovery_observation':path})
        self.assertEqual(result['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertEqual(result['state']['thread_id'],'SIMULATED-replacement')
        self.assertEqual(result['state']['operation_id'],self.j['operation']['operation_id'])
        self.assertEqual(result['state']['nonce'],self.j['operation']['nonce'])
        self.assertFalse(result['state']['parent_confirmed'])
        self.assertEqual(c.load(receiver)['replaces_thread_id'],'SIMULATED-receiver')
        self.assertEqual((receiver.parent/'history'/(c.digest(before)+'.json')).read_bytes(),before)
        self.assertEqual(previous,{p.name:p.read_bytes() for p in self.previous_job.iterdir()})
        self.assertEqual(sum(m=='thread/start' for m,_ in self.clients[-1].calls),1)
        self.assertEqual(self.run_bridge()['action'],'COLLECT_EXISTING')

    def test_busy_stale_changed_or_uncertain_external_observation_never_replaces(self):
        cases=[{'active_turn_id':'SIMULATED-active'},{'pending_launch':True},
               {'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()},
               {'observed_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()},
               {'thread_id':'other'},{'last_turn_id':'other'},{'native_message_channel':'available'},
               {'parent_confirmed':False}]
        for change in cases:
            with self.subTest(change=change):
                self.setUp();self.run_bridge();self.second_operation()
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':self.recovery_observation(**change)})
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_official_busy_or_changed_last_turn_blocks_qualified_replacement(self):
        for change in ({'receiver_status':'active'},{'last_turn_status':'inProgress'}):
            with self.subTest(change=change):
                self.setUp();self.run_bridge();self.second_operation()
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':self.recovery_observation()},**change)
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_generic_refusal_or_lost_response_never_uses_replacement_evidence(self):
        for change in ({'resume_error':{'code':-32600,'message':'SIMULATED generic refusal'}},{'failure':'thread/resume'}):
            with self.subTest(change=change):
                self.setUp();self.run_bridge();self.second_operation()
                result=self.run_bridge(bridge_options={'recovery_observation':self.recovery_observation()},**change)
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_registry_changed_during_observation_is_refused_before_creation(self):
        self.run_bridge();self.second_operation();receiver=self.oproot.parent/'.receivers/codex/RECEIVER.json'
        result=self.run_bridge(resume_error=self.writer_conflict(),on_read=lambda:receiver.write_bytes(b'{}'),
                               bridge_options={'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_lost_replacement_creation_response_retains_owner_and_never_repeats(self):
        self.run_bridge();self.second_operation()
        result=self.run_bridge(resume_error=self.writer_conflict(),failure='thread/start',
                               bridge_options={'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertTrue((self.oproot.parent/'.receivers/codex/OWNER.json').exists())
        self.assertEqual(self.run_bridge()['action'],'FOLLOW_EXISTING_DISPATCH');self.assertEqual(len(self.clients),2)

    def test_one_explicit_repair_after_writer_refusal_preserves_original_failure(self):
        self.run_bridge();self.second_operation();self.run_bridge(resume_error=self.writer_conflict())
        original=self.oproot/'codex-dispatch';before={p.name:p.read_bytes() for p in original.iterdir()}
        result=self.run_bridge(resume_error=self.writer_conflict(),created_thread_id='SIMULATED-replacement',
                               bridge_options={'recover_native_writer':True,'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertEqual(before,{name:(original/name).read_bytes() for name in before})
        self.assertEqual(self.run_bridge(bridge_options={'recover_native_writer':True})['action'],'COLLECT_EXISTING')
        self.assertEqual(len(self.clients),3)

    def test_native_owner_channel_reuses_receiver_and_busy_owner_cannot_be_bypassed(self):
        for busy in (False,True):
            with self.subTest(busy=busy):
                self.setUp();self.run_bridge();self.second_operation();native=FakeRpc(None,self.canonical)
                native.receiver_status='active' if busy else 'idle'
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'native_socket':self.f.root/'SIMULATED.sock',
                    'native_rpc_factory':lambda exe,cwd:native,'recovery_observation':self.recovery_observation()})
                self.assertEqual(result['action'],'BLOCKED_DISPATCH' if busy else 'FINISHED_AWAITING_PARENT_CONFIRM')
                self.assertFalse(any(m=='thread/start' for m,_ in native.calls+self.clients[-1].calls))
                if not busy:self.assertEqual(result['state']['channel'],'official-native-proxy')

    def test_unavailable_native_proxy_requires_external_qualification(self):
        self.run_bridge();self.second_operation();native=FakeRpc(None,self.canonical);native.initialize_error=True
        result=self.run_bridge(resume_error=self.writer_conflict(),created_thread_id='SIMULATED-replacement',
            bridge_options={'native_socket':self.f.root/'SIMULATED.sock','native_rpc_factory':lambda exe,cwd:native,
                            'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'FINISHED_AWAITING_PARENT_CONFIRM')
        self.assertIn('unavailable',result['state']['native_channel_error'])
        self.assertEqual(result['state']['channel'],'temporary-stdio')

    def test_connected_native_api_refusal_is_never_bypassed(self):
        self.run_bridge();self.second_operation();native=FakeRpc(None,self.canonical);native.initialize_refusal=True
        result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'native_socket':self.f.root/'SIMULATED.sock',
            'native_rpc_factory':lambda exe,cwd:native,'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertEqual(result['state']['official_error']['method'],'initialize')
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in native.calls+self.clients[-1].calls))

    def test_replacement_requires_creation_authority_and_valid_old_completion(self):
        for change in ('authority','completion'):
            with self.subTest(change=change):
                self.setUp();self.run_bridge();self.second_operation();path=self.recovery_observation()
                if change=='authority':self.request['authority']['allow_create']=False
                else:(self.previous_job/'turn-completed.json').write_bytes(b'{}')
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_creation_known_but_registration_incomplete_retains_owner(self):
        self.run_bridge();self.second_operation()
        result=self.run_bridge(resume_error=self.writer_conflict(),failure='thread/name/set',created_thread_id='SIMULATED-replacement',
                               bridge_options={'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertEqual(result['state']['thread_id'],'SIMULATED-replacement')
        self.assertFalse(result['state']['receiver_registered'])
        self.assertTrue((self.oproot.parent/'.receivers/codex/OWNER.json').exists())
        self.assertEqual(self.run_bridge()['action'],'FOLLOW_EXISTING_DISPATCH');self.assertEqual(len(self.clients),2)

    def test_uncertain_launch_and_model_repair_cannot_renew_receiver(self):
        self.run_bridge(failure='turn/start')
        with self.assertRaises(c.SyncError):self.run_bridge(bridge_options={'recover_native_writer':True})
        self.setUp();self.run_bridge(fail_before_work=True)
        result=self.run_bridge(retry_before_work=True,resume_error=self.writer_conflict())
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_other_open_owner_blocks_before_any_connection_or_new_job(self):
        self.run_bridge();self.second_operation()
        owner=self.oproot.parent/'.receivers/codex/OWNER.json';owner.write_bytes(c.encode({'operation_id':'SIMULATED-other-owner'}))
        with self.assertRaises(c.SyncError):self.run_bridge(bridge_options={'recovery_observation':self.recovery_observation()})
        self.assertEqual(len(self.clients),1)
        self.assertFalse((self.oproot/'codex-dispatch').exists())

    def test_initialize_opts_into_official_experimental_read_capability(self):
        rpc=object.__new__(b.Rpc);calls=[];notifications=[]
        rpc.call=lambda method,params:calls.append((method,params)) or {'SIMULATED':True}
        rpc.send=lambda value:notifications.append(value)
        rpc.initialize()
        self.assertEqual(calls[0][1]['capabilities'],{'experimentalApi':True})
        self.assertEqual(notifications,[{'method':'initialized'}])

    def test_experimental_read_refusal_blocks_replacement_without_success_claim(self):
        self.run_bridge();self.second_operation()
        result=self.run_bridge(resume_error=self.writer_conflict(),turns_error={'code':-32600,'message':'SIMULATED experimental API unsupported'},
                               bridge_options={'recovery_observation':self.recovery_observation()})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertEqual(result['state']['official_error']['method'],'thread/turns/list')
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_received_operation_file_or_wrong_independent_pin_cannot_authorize_replacement(self):
        for change in ('operation-file','pin'):
            with self.subTest(change=change):
                self.setUp();self.run_bridge();self.second_operation();path=self.recovery_observation()
                options={'recovery_observation':path}
                if change=='operation-file':
                    received=self.oproot/'received-observation.json';received.write_bytes(path.read_bytes());options['recovery_observation']=received
                else:options['recovery_observation_sha256']='0'*64
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options=options)
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_symbolic_link_observation_is_refused(self):
        # No OS privilege needed: the filesystem link observation is simulated.
        from unittest.mock import patch
        self.run_bridge();self.second_operation();path=self.recovery_observation()
        with patch.object(Path,'is_symlink',return_value=True):
            with self.assertRaises(c.SyncError):b.observation_path(path,path.parent)

    def test_parent_confirmation_must_be_verified_and_bound_to_previous_operation(self):
        self.run_bridge();self.second_operation();path=self.recovery_observation()
        observed=c.load(path);confirmation_path=Path(observed['confirmation_journal'])
        unconfirmed=c.load(self.previous_job/'journal-selected.json')
        confirmation_path.write_bytes(c.encode(unconfirmed))
        observed['confirmation_journal_sha256']=c.digest(confirmation_path.read_bytes());path.write_bytes(c.encode(observed))
        result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertFalse(any(m=='thread/start' for m,_ in self.clients[-1].calls))

    def test_fresh_pinned_observation_with_duplicate_launch_state_is_refused(self):
        self.run_bridge();self.second_operation();path=self.recovery_observation()
        raw=path.read_bytes().replace(b'"pending_launch":false',b'"pending_launch":true,"pending_launch":false')
        path.write_bytes(raw)
        result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertIn('Duplicate JSON key',result['state']['error'])
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_boolean_observation_schema_version_is_refused(self):
        self.run_bridge();self.second_operation();path=self.recovery_observation(schema_version=True)
        result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertIn('Wrong receiver observation format',result['state']['error'])
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_pinned_ambiguous_confirmation_or_completion_is_refused(self):
        for boundary in ('confirmation','completion'):
            with self.subTest(boundary=boundary):
                self.setUp();self.run_bridge();self.second_operation();path=self.recovery_observation()
                observed=c.load(path)
                if boundary=='confirmation':
                    confirmation_path=Path(observed['confirmation_journal'])
                    raw=confirmation_path.read_bytes()
                    # The final occurrence would retain a valid journal under permissive decoding.
                    raw=b'{"format":"AMBIGUOUS",'+raw[1:]
                    confirmation_path.write_bytes(raw)
                    observed['confirmation_journal_sha256']=c.digest(raw);path.write_bytes(c.encode(observed))
                else:
                    completion_path=self.previous_job/'turn-completed.json'
                    raw=completion_path.read_bytes().replace(b'"status":"completed"',b'"status":"inProgress","status":"completed"')
                    completion_path.write_bytes(raw)
                    state_path=self.previous_job/'state.json';state=c.load(state_path)
                    for binding in state['returned_files']:
                        if binding['name']=='turn-completed.json':binding.update(sha256=c.digest(raw),size=len(raw))
                    state_path.write_bytes(c.encode(state))
                result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
                self.assertEqual(result['action'],'BLOCKED_DISPATCH')
                self.assertIn('Duplicate JSON key',result['state']['error'])
                self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_pinned_observation_is_strict_utf8(self):
        self.run_bridge();self.second_operation();path=self.recovery_observation()
        path.write_bytes(path.read_text(encoding='utf-8').encode('utf-16'))
        result=self.run_bridge(resume_error=self.writer_conflict(),bridge_options={'recovery_observation':path})
        self.assertEqual(result['action'],'BLOCKED_DISPATCH')
        self.assertFalse(any(m in ('thread/start','turn/start') for m,_ in self.clients[-1].calls))

    def test_unknown_or_unfinished_failure_cannot_be_retried(self):
        with self.assertRaises(c.SyncError):self.run_bridge(retry_before_work=True)
        self.run_bridge(fail_turn=True)
        with self.assertRaises((c.SyncError,ValueError)):self.run_bridge(retry_before_work=True)
        self.assertEqual(len(self.clients),1)


if __name__=='__main__':unittest.main()
