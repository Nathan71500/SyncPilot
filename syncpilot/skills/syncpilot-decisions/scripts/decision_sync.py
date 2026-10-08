#!/usr/bin/env python3
"""Bidirectional validated decisions. Offline gates; no Git writes or networking."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location('decision_core', Path(__file__).resolve().parents[2] / 'syncpilot-codex/scripts/project_sync.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
POLICY = {'capture':'human-validated-only','oral':'preserve-existing-validation','conflicts':'block-and-arbitrate','git':'review-before-integration','new_project':'recommend-if-work-and-codex'}
EVENTS = ('DEPOSITED','RECEIVED','TRANSPORT_FAILED','DC_UNAVAILABLE','RECEPTION_UNCERTAIN','VALIDATION_REJECTED','RECEIVER_SELECTED','VERIFIED')


def contract(path):
    value=c.load(path);c.validate_contract(value)
    c.require(value['schema_version'] in (3,4,5),'Decision synchronization requires explicit contract v3/v4/v5')
    return value


def empty(project):
    return {'format':'SYNCPILOT-DECISION-LEDGER','schema_version':1,'project_id':project,'records':[]}


def scoped(reference, allowed):
    return isinstance(reference,str) and any(reference==p or reference.startswith(p+'#') for p in allowed)


def decision_sources(config, environment):
    declared=config['decision_sync']['sources'][environment]
    # v5 evidence may live in the qualified durable project registry, independent
    # of a session. Its human authority still needs external qualification.
    return declared+[config['decision_sync']['registries'][environment]] if config['schema_version']==5 else declared


def stamp(value):
    c.text(value)
    from datetime import datetime
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    c.require(d.tzinfo is not None,'Timestamp needs timezone')


def record_hash(record):
    return c.digest(c.encode(record))


def validate_ledger(ledger, config):
    c.fields(ledger,'format schema_version project_id records')
    c.require(ledger['format']=='SYNCPILOT-DECISION-LEDGER' and type(ledger['schema_version']) is int and ledger['schema_version']==1 and ledger['project_id']==config['project_id'],'Wrong decision ledger')
    c.require(isinstance(ledger['records'],list) and len(ledger['records'])<=c.MAX_ENTRIES,'Invalid decision scope')
    heads={}; topics={}; order=[]
    for r in ledger['records']:
        c.fields(r,'decision_id topic revision previous_sha256 text consequences origin validation status')
        for key in ('decision_id','topic'):
            c.require(isinstance(r[key],str) and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,95}',r[key]),'Invalid stable decision key')
        c.require(type(r['revision']) is int and r['revision']>=1 and r['status']=='validated','Only validated revisions can synchronize')
        c.text(r['text']); c.documentary('decision text',r['text'].encode('utf-8'))
        c.require(isinstance(r['consequences'],list),'Consequences must be explicit')
        for x in r['consequences']: c.text(x);c.documentary('consequence',x.encode())
        c.fields(r['origin'],'environment project_id thread_id source_reference')
        origin=r['origin'];env=origin['environment'];c.require(env in ('work','codex'),'Unknown origin')
        expected=config['decision_sync']['participants'][env]
        c.text(origin['thread_id'])
        c.require('REPLACE_' not in origin['thread_id'],'Actual origin thread required')
        c.require(origin['project_id']==expected['project_id'] and (config['schema_version']==5 or origin['thread_id']==expected['thread_id']),'Decision origin identity mismatch')
        c.require(scoped(origin['source_reference'],decision_sources(config,env)),'Origin outside declared source scope')
        v=r['validation'];c.fields(v,'validated_by mode validated_at reference text_sha256')
        c.text(v['validated_by']);stamp(v['validated_at'])
        c.require(v['mode'] in ('written','oral') and v['text_sha256']==c.digest(r['text'].encode()),'Validation does not cover exact decision text')
        c.require(scoped(v['reference'],decision_sources(config,env)),'Validation outside declared human source')
        previous=heads.get(r['decision_id'])
        c.require(r['revision']==(previous['revision']+1 if previous else 1),'Missing or reordered decision revision')
        c.require(r['previous_sha256']==(record_hash(previous) if previous else None),'Decision history fork')
        if previous: c.require(r['topic']==previous['topic'],'Topic identity cannot change silently')
        c.require(r['topic'] not in topics or topics[r['topic']]==r['decision_id'],'Two decision IDs claim same topic; arbitrate')
        topics[r['topic']]=r['decision_id'];heads[r['decision_id']]=r;order.append((r['decision_id'],r['revision']))
    c.require(order==sorted(order),'Canonical ledger order required')
    c.require(len(c.encode(ledger))<=c.MAX_FILE,'Ledger too large')
    return heads


def capture(config, ledger, draft, approval, environment, previous=None, source_thread=None):
    heads=validate_ledger(ledger,config);c.fields(draft,'decision_id topic text consequences')
    c.require(environment in ('work','codex'),'Unknown recording environment')
    c.text(draft['text'])
    if approval is None:
        return {'format':'SYNCPILOT-DECISION-PROPOSAL','schema_version':1,'project_id':config['project_id'],'state':'PROPOSED','draft':draft,'environment':environment}
    c.fields(approval,'validated_by mode validated_at reference text_sha256 source_reference')
    current=heads.get(draft['decision_id'])
    participant=config['decision_sync']['participants'][environment]
    if config['schema_version']==5:
        c.text(source_thread);c.require('REPLACE_' not in source_thread,'Qualified actual source thread required')
        participant={**participant,'thread_id':source_thread}
    else:
        c.require(source_thread is None or source_thread==participant['thread_id'],'Legacy source thread is fixed; migrate explicitly')
    validation={k:v for k,v in approval.items() if k!='source_reference'}
    origin={'environment':environment,**participant,'source_reference':approval['source_reference']}
    if current and all(current[k]==draft[k] for k in draft) and current['validation']==validation and current['origin']==origin:
        return copy.deepcopy(ledger)
    c.require(previous==(record_hash(current) if current else None),'Explicit exact previous decision required for revision')
    r={**draft,'revision':current['revision']+1 if current else 1,'previous_sha256':previous,'origin':origin,'validation':validation,'status':'validated'}
    result=copy.deepcopy(ledger);result['records'].append(r);result['records'].sort(key=lambda x:(x['decision_id'],x['revision']))
    validate_ledger(result,config);return result


def merge(base, incoming, config):
    validate_ledger(base,config);validate_ledger(incoming,config)
    records={(r['decision_id'],r['revision']):r for r in base['records']}
    for r in incoming['records']:
        key=(r['decision_id'],r['revision'])
        c.require(key not in records or records[key]==r,'BLOCKED_CONFLICT: concurrent decision revision; no last-write-wins')
        records[key]=r
    result={**base,'records':[records[k] for k in sorted(records)]}
    validate_ledger(result,config);return result


def references(ledger):
    return [{'record_sha256':record_hash(r),'reference':r['validation']['reference'],'validated_by':r['validation']['validated_by'],'mode':r['validation']['mode']} for r in ledger['records']]


def validate_routing(routing, config=None, identity=None):
    """Validate pilot observations, not authenticate chats or authorize messages."""
    c.fields(routing,'format schema_version source destination authority qualification_reference delivery')
    c.require(routing['format']=='SYNCPILOT-DECISION-ROUTING' and type(routing['schema_version']) is int and routing['schema_version']==1,'Wrong operation routing')
    c.require(routing['delivery'] in ('application-message','shared-inbox'),'Use the owning application or durable inbox, never exec resume as messaging')
    for key in ('source','destination'):
        c.fields(routing[key],'project_id thread_id')
        for field,value in routing[key].items():
            if key=='destination' and field=='thread_id' and routing['delivery']=='shared-inbox' and value is None:continue
            c.text(value);c.require('REPLACE_' not in value,'Routing must be qualified')
        if identity:
            c.require(routing[key]==identity[key],'Routing/operation identity mismatch')
            if config:
                env=identity[key+'_environment']
                c.require(routing[key]['project_id']==config['decision_sync']['participants'][env]['project_id'],'Routing outside contracted project')
    c.require(routing['source']['thread_id']!=routing['destination']['thread_id'],'Distinct operation threads required')
    for key in ('authority','qualification_reference'):
        c.text(routing[key]);c.require('REPLACE_' not in routing[key],'Qualified routing authority required')
    if routing['delivery']=='shared-inbox':
        c.require(routing['destination']['thread_id'] is None,'Inbox is addressed to the project; select the receiver at pickup')
    return routing


def receiver(op, journal):
    if op.get('routing',{}).get('delivery')!='shared-inbox':return op['identity']['destination']
    selected=[e['receiver'] for e in journal['events'] if e['status']=='RECEIVER_SELECTED']
    c.require(bool(selected),'Inbox awaits a qualified receiver; no contractual chat to resume')
    return selected[0]


def select_receiver(journal, observed, channel):
    op=validate_operation(journal)
    c.require(op.get('routing',{}).get('delivery')=='shared-inbox','Receiver selection applies only to a v5 project inbox')
    c.fields(observed,'environment project_id thread_id authority qualification_reference')
    c.require(observed['environment']==op['identity']['destination_environment'] and observed['project_id']==op['identity']['destination']['project_id'],'Receiver outside contracted project')
    for key in ('thread_id','authority','qualification_reference'):
        c.text(observed[key]);c.require('REPLACE_' not in observed[key],'Qualify the actual receiver via the application')
    for e in journal['events']:
        if e['status']=='RECEIVER_SELECTED':
            c.require(e['receiver']==observed,'Receiver already bound; collect its results instead of dispatching twice')
            return copy.deepcopy(journal)
    event={'status':'RECEIVER_SELECTED','channel':channel,'delivery':'not-delivered','reference':observed['qualification_reference'],'previous_sha256':c.digest(c.encode(journal)),'receiver':copy.deepcopy(observed)}
    event_check(journal,event)
    result=copy.deepcopy(journal);result['events'].append(event);validate_operation(result);return result


def migrate_routing(config):
    c.validate_contract(config)
    c.require(config['schema_version'] in (3,4),'Explicit migration from v3/v4 required')
    result=copy.deepcopy(config);result['schema_version']=5
    for participant in result['decision_sync']['participants'].values():
        del participant['thread_id']
    c.validate_contract(result)
    return result


def prepare(config_path, ledger_path, destination_base, direction, authority, routing=None):
    config=contract(config_path);ledger=c.load(ledger_path);validate_ledger(ledger,config)
    c.require(bool(ledger['records']),'No validated decisions to send')
    c.require(direction in ('work-to-codex','codex-to-work'),'Unknown direction');c.text(authority)
    source,destination=direction.split('-to-')
    base=c.load(destination_base) if destination_base else empty(config['project_id']);validate_ledger(base,config)
    # A known conflict blocks preparation too, never changing channel to bypass it.
    merge(base,ledger,config)
    identity={'project_id':config['project_id'],'direction':direction,'source_environment':source,'destination_environment':destination,'source':config['decision_sync']['participants'][source],'destination':config['decision_sync']['participants'][destination],'contract_sha256':c.digest(config_path.read_bytes()),'source_version':c.digest(ledger_path.read_bytes()),'destination_base_sha256':c.digest(c.encode(base)),'authority':authority}
    if config['schema_version']==5:
        c.require(routing is not None,'v5 needs qualified operation routing, not a contractual session')
        validate_routing(routing)
        for key in ('source','destination'):identity[key]=copy.deepcopy(routing[key])
        validate_routing(routing,config,identity)
    else:
        c.require(routing is None,'Legacy routing is fixed; migrate explicitly before choosing another chat')
    req={'format':'SYNCPILOT-DECISION-REQUIREMENT','schema_version':1,'identity':identity,'validation_references':references(ledger)}
    files=[{'name':'decisions.json','size':ledger_path.stat().st_size,'sha256':identity['source_version']},{'name':'requirement.json','size':len(c.encode(req)),'sha256':c.digest(c.encode(req))}]
    binding={'identity':identity,'profiles':{k:config['transport'][k] for k in ('primary','fallback')},'files':files}
    if routing is not None:binding['routing']=copy.deepcopy(routing)
    # Content identity is deterministic; retries cannot invent another operation/nonce.
    binding['nonce']=str(uuid.uuid5(uuid.NAMESPACE_URL,'syncpilot:'+c.digest(c.encode(binding))))
    binding['operation_id']=c.digest(c.encode(binding))
    return req,{'format':'SYNCPILOT-DECISION-OPERATION','schema_version':2 if routing is not None else 1,'operation':binding,'events':[]}


def state(j):
    statuses=[e['status'] for e in j['events']]
    if 'VALIDATION_REJECTED' in statuses:return 'BLOCKED'
    if 'VERIFIED' in statuses:return 'VERIFIED'
    return next((e['status'] for e in reversed(j['events']) if e['status'] in ('DEPOSITED','RECEIVED','RECEPTION_UNCERTAIN')),'PREPARED')


def validate_operation(j):
    c.fields(j,'format schema_version operation events')
    c.require(j['format']=='SYNCPILOT-DECISION-OPERATION' and type(j['schema_version']) is int and j['schema_version'] in (1,2),'Wrong decision operation')
    op=j['operation'];c.fields(op,'identity profiles files nonce operation_id'+(' routing' if j['schema_version']==2 else ''))
    c.require(op['operation_id']==c.digest(c.encode({k:v for k,v in op.items() if k!='operation_id'})),'Operation changed')
    c.require(str(uuid.UUID(op['nonce']))==op['nonce'],'Wrong nonce')
    seed={k:v for k,v in op.items() if k not in ('operation_id','nonce')}
    c.require(op['nonce']==str(uuid.uuid5(uuid.NAMESPACE_URL,'syncpilot:'+c.digest(c.encode(seed)))),'Retry cannot change nonce')
    i=op['identity'];c.fields(i,'project_id direction source_environment destination_environment source destination contract_sha256 source_version destination_base_sha256 authority')
    c.require(i['direction'] in ('work-to-codex','codex-to-work') and i['direction']==i['source_environment']+'-to-'+i['destination_environment'],'Wrong direction binding')
    for key in ('source','destination'):
        c.fields(i[key],'project_id thread_id')
        for field,value in i[key].items():
            if key=='destination' and field=='thread_id' and j['schema_version']==2 and op['routing']['delivery']=='shared-inbox' and value is None:continue
            c.text(value)
    if j['schema_version']==2:validate_routing(op['routing'],identity=i)
    for key in ('contract_sha256','source_version','destination_base_sha256'):c.hex_value(i[key],64)
    c.text(i['authority']);c.require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',i['project_id']),'Wrong project key')
    c.fields(op['profiles'],'primary fallback')
    for p in op['profiles'].values():c.validate_endpoint(p)
    c.require(op['profiles']['primary']['channel']=='desktop-commander' and op['profiles']['fallback']['channel']=='drive','Wrong channel priority')
    c.require(isinstance(op['files'],list) and [f['name'] for f in op['files']]==['decisions.json','requirement.json'],'Wrong files')
    for f in op['files']:
        c.fields(f,'name size sha256');c.hex_value(f['sha256'],64);c.require(type(f['size']) is int and 0<f['size']<=c.MAX_FILE,'Invalid file size')
    c.require(isinstance(j['events'],list),'Wrong event history')
    previous={**j,'events':[]}
    for e in j['events']:
        c.fields(e,'status channel delivery reference previous_sha256'+(' receiver' if e['status']=='RECEIVER_SELECTED' else ''))
        c.require(e['previous_sha256']==c.digest(c.encode(previous)),'History changed')
        event_check(previous,e);previous['events']=previous['events']+[e]
    return op


def event_check(j,e):
    c.require(state(j) not in ('BLOCKED','VERIFIED'),'Operation terminal')
    c.require(e['status'] in EVENTS and e['channel'] in ('primary','fallback') and e['delivery'] in ('present','unknown','not-delivered'),'Wrong event')
    c.text(e['reference'])
    if e['status']=='RECEIVER_SELECTED':
        op=j['operation'];actual=e['receiver']
        c.require(op.get('routing',{}).get('delivery')=='shared-inbox','No receiver selection on fixed-chat routing')
        c.require(not any(x['status']=='RECEIVER_SELECTED' for x in j['events']),'Receiver already selected')
        c.fields(actual,'environment project_id thread_id authority qualification_reference')
        c.require(actual['environment']==op['identity']['destination_environment'] and actual['project_id']==op['identity']['destination']['project_id'],'Wrong selected project')
        for key in ('thread_id','authority','qualification_reference'):
            c.text(actual[key]);c.require('REPLACE_' not in actual[key],'Actual receiver qualification required')
        c.require(e['reference']==actual['qualification_reference'] and e['delivery']=='not-delivered','Selection is not receipt or transport')
    if e['status']=='DC_UNAVAILABLE':c.require(e['channel']=='primary','Only DC can be unavailable')
    if e['channel']=='fallback':c.require(any(x['status']=='DC_UNAVAILABLE' and x['delivery']=='not-delivered' for x in j['events']),'No conclusive DC unavailability')
    if e['status'] in ('DEPOSITED','RECEIVED','VERIFIED'):c.require(e['delivery']=='present','Actual bytes required')


def append(j,status,channel,delivery,reference):
    validate_operation(j);event={'status':status,'channel':channel,'delivery':delivery,'reference':reference,'previous_sha256':c.digest(c.encode(j))}
    event_check(j,event);result=copy.deepcopy(j);result['events'].append(event);validate_operation(result);return result


def targets(op,channel):
    p=op['profiles'][channel];names=['decisions.json','requirement.json','proof.json','receipt.json','registry.json']
    if channel=='primary':
        device,root,pm=c.dc_endpoint(p['locator']);base=pm.join(root,op['identity']['project_id'],op['operation_id'])
        return {name:'dc://'+device+'/'+quote(pm.join(base,name),safe='') for name in names}
    return {name:{'parent':p['locator'],'name':op['operation_id']+'-'+name} for name in names}


def plan(j,discovery,channel):
    op=validate_operation(j);c.fields(discovery,'operation_id nonce journal_sha256 results authority')
    c.require(discovery['operation_id']==op['operation_id'] and discovery['nonce']==op['nonce'] and discovery['journal_sha256']==c.digest(c.encode(j)),'Stale/wrong discovery')
    c.text(discovery['authority']);c.fields(discovery['results'],'primary fallback')
    for value in discovery['results'].values():
        c.fields(value,'status reference');c.text(value['reference']);c.require(value['status'] in ('absent','unavailable','available','rejected'),'Wrong search state')
    c.require(channel in ('primary','fallback'),'Unknown channel')
    statuses=[x['status'] for x in discovery['results'].values()]
    action='DEPOSIT_ONCE'
    if state(j)=='BLOCKED' or 'rejected' in statuses:action='BLOCKED'
    elif state(j)=='VERIFIED':action='DONE'
    elif 'available' in statuses:action='COLLECT_EXISTING'
    elif state(j) in ('DEPOSITED','RECEIVED','RECEPTION_UNCERTAIN') or any(e['status'] in ('TRANSPORT_FAILED','DC_UNAVAILABLE') and e['delivery']!='not-delivered' for e in j['events']):action='BLOCKED'
    else:
        if channel=='fallback':c.require(discovery['results']['primary']['status']=='unavailable' and any(e['status']=='DC_UNAVAILABLE' and e['delivery']=='not-delivered' for e in j['events']),'Drive only if DC currently unavailable and non-delivery conclusive')
        c.require(discovery['results'][channel]['status']=='absent','Selected destination not empty')
    return {'action':action,'operation_id':op['operation_id'],'nonce':op['nonce'],'direction':op['identity']['direction'],'channel':channel,'targets':targets(op,channel) if action=='DEPOSIT_ONCE' else {},'files':op['files']}


def verify(config_path,input_path,requirement_path,journal):
    config=contract(config_path);op=validate_operation(journal);req=c.load(requirement_path);c.fields(req,'format schema_version identity validation_references')
    c.require(req['format']=='SYNCPILOT-DECISION-REQUIREMENT' and type(req['schema_version']) is int and req['schema_version']==1 and req['identity']==op['identity'],'Wrong requirement')
    i=op['identity'];c.require(c.digest(config_path.read_bytes())==i['contract_sha256'] and config['project_id']==i['project_id'],'Wrong contract')
    if config['schema_version']==5:
        c.require(journal['schema_version']==2,'v5 needs an operation routing binding')
        validate_routing(op['routing'],config,i)
    else:
        c.require(journal['schema_version']==1,'Legacy contract needs legacy operation')
        for env,key in ((i['source_environment'],'source'),(i['destination_environment'],'destination')):c.require(i[key]==config['decision_sync']['participants'][env],'Wrong participant identity')
    c.require(op['profiles']=={k:config['transport'][k] for k in ('primary','fallback')},'Wrong access profiles')
    for p,binding in ((input_path,op['files'][0]),(requirement_path,op['files'][1])):
        c.require(p.stat().st_size==binding['size'] and c.digest(p.read_bytes())==binding['sha256'],'Transport altered')
    c.require(op['files'][0]['sha256']==i['source_version'],'Wrong source version')
    ledger=c.load(input_path);validate_ledger(ledger,config);c.require(req['validation_references']==references(ledger),'Wrong validation references')
    return config,op,req,ledger


def qualification(observed,op,req,config,channel,journal):
    c.fields(observed,'environment project_id thread_id artifact_locator retrieved_sha256 qualified_validations registry_locator authority')
    i=op['identity'];actual=receiver(op,journal);c.require(observed['environment']==i['destination_environment'] and observed['project_id']==actual['project_id'] and observed['thread_id']==actual['thread_id'],'Wrong observed receiver')
    c.require(observed['retrieved_sha256']==op['files'][0]['sha256'] and observed['qualified_validations']==req['validation_references'],'Human validation not independently qualified')
    c.require(observed['registry_locator']==config['decision_sync']['registries'][observed['environment']],'Wrong registry authority')
    c.text(observed['authority']);locator(op,channel,observed['artifact_locator'],'decisions.json')


def locator(op,channel,value,name):
    c.text(value)
    if channel=='primary':c.require(value==targets(op,channel)[name],'DC object outside exact operation')
    else:c.require(re.fullmatch(r'gdrive:file:[A-Za-z0-9_-]+',value),'Exact Drive file ID required')


def proof_for(op,req,observed,base,merged):
    return {'format':'SYNCPILOT-DECISION-PROOF','schema_version':1,'operation_id':op['operation_id'],'nonce':op['nonce'],'identity':op['identity'],'requirement_sha256':c.digest(c.encode(req)),'observation':observed,'records':references(merged),'base_ledger_sha256':c.digest(c.encode(base)),'registry_sha256':c.digest(c.encode(merged)),'mirror_status':'CURRENT','alignment_status':'VALIDATED_DECISIONS_RECORDED','code_status':'NOT_ASSESSED','work_sources_status':'EXTERNAL_ONLY'}


def receive(config_path,input_path,requirement_path,journal,observed,base_path,channel,store,proof_path,registry_output):
    config,op,req,incoming=verify(config_path,input_path,requirement_path,journal)
    c.require(state(journal) not in ('BLOCKED','VERIFIED'),'Operation terminal')
    if channel=='fallback':c.require(any(e['status']=='DC_UNAVAILABLE' and e['delivery']=='not-delivered' for e in journal['events']),'Drive not authorized')
    qualification(observed,op,req,config,channel,journal)
    base=c.load(base_path) if base_path else empty(config['project_id']);validate_ledger(base,config)
    c.require(c.digest(c.encode(base))==op['identity']['destination_base_sha256'],'Destination registry changed; reconcile before retry')
    merged=merge(base,incoming,config)  # Reject conflict before writing anything.
    c.require(not store.exists() and not proof_path.exists() and not registry_output.exists(),'Preserve existing intake/results; collect before retry')
    writes=[store/name for name in ('decisions.json','requirement.json','base.json','registry.json','proof.json')]+[proof_path,registry_output]
    c.require(len({p.resolve() for p in writes})==len(writes),'Output paths collide')
    proof=proof_for(op,req,observed,base,merged)
    # Exclusive versioned registry, never overwrite an existing canonical/Git file.
    c.write_new(store/'decisions.json',input_path.read_bytes());c.write_new(store/'requirement.json',requirement_path.read_bytes());c.write_new(store/'base.json',c.encode(base));c.write_new(store/'registry.json',c.encode(merged));c.write_new(store/'proof.json',c.encode(proof))
    c.write_new(registry_output,c.encode(merged));c.write_new(proof_path,c.encode(proof));return proof


def check(config_path,store,requirement_path,journal,channel):
    config,op,req,incoming=verify(config_path,store/'decisions.json',requirement_path,journal)
    base=c.load(store/'base.json');c.require(c.digest(c.encode(base))==op['identity']['destination_base_sha256'],'Wrong stored base')
    merged=merge(base,incoming,config);proof=c.load(store/'proof.json');qualification(proof['observation'],op,req,config,channel,journal)
    c.require(c.load(store/'registry.json')==merged and proof==proof_for(op,req,proof['observation'],base,merged),'Stored mirror changed');return proof


def confirm(config_path,input_path,requirement_path,journal,base_path,proof_path,receipt_path,registry_path,observed):
    config,op,req,incoming=verify(config_path,input_path,requirement_path,journal)
    receipt=c.load(receipt_path);c.fields(receipt,'format schema_version operation_id nonce identity channel status files proof_sha256 registry_sha256')
    c.require(receipt['format']=='SYNCPILOT-DECISION-RECEIPT' and type(receipt['schema_version']) is int and receipt['schema_version']==1 and receipt['status']=='RECEIVED_VERIFIED','Independent receipt required')
    for key in ('operation_id','nonce','identity','files'):c.require(receipt[key]==op[key],'Wrong receipt '+key)
    channel=receipt['channel'];c.require(channel in op['profiles'],'Wrong receipt channel');profile=op['profiles'][channel]
    c.fields(observed,'environment project_id thread_id channel account storage_root artifact_locator proof_locator receipt_locator registry_file_locator proof_sha256 receipt_sha256 registry_sha256 receiver_finished authority')
    i=op['identity'];actual=receiver(op,journal);c.require(observed['environment']==i['destination_environment'] and observed['project_id']==actual['project_id'] and observed['thread_id']==actual['thread_id'] and observed['receiver_finished'] is True,'Receiver origin/finish not qualified')
    c.require(observed['channel']==channel and observed['account']==profile['account'] and observed['storage_root']==profile['locator'],'Wrong observed access');c.text(observed['authority'])
    for key,name in [('artifact_locator','decisions.json'),('proof_locator','proof.json'),('receipt_locator','receipt.json'),('registry_file_locator','registry.json')]:locator(op,channel,observed[key],name)
    for key,path in [('proof_sha256',proof_path),('receipt_sha256',receipt_path),('registry_sha256',registry_path)]:c.require(observed[key]==c.digest(path.read_bytes()),'Return bytes not reread '+key)
    c.require(receipt['proof_sha256']==observed['proof_sha256'] and receipt['registry_sha256']==observed['registry_sha256'],'Receipt not bound to returned proof/registry')
    proof=c.load(proof_path);base=c.load(base_path) if base_path else empty(config['project_id'])
    c.require(c.digest(c.encode(base))==i['destination_base_sha256'],'Wrong expected destination base')
    merged=merge(base,incoming,config);qualification(proof['observation'],op,req,config,channel,journal)
    c.require(proof['observation']['thread_id']==observed['thread_id'],'Proof and authenticated return must come from the same receiver')
    c.require(proof['observation']['artifact_locator']==observed['artifact_locator'] and proof==proof_for(op,req,proof['observation'],base,merged) and registry_path.read_bytes()==c.encode(merged),'Independent decision proof mismatch')
    return append(journal,'VERIFIED',channel,'present',observed['authority'])


def main():
    c.utf8_stdio()
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    def command(name,paths):
        p=sub.add_parser(name)
        for key in paths.split():p.add_argument('--'+key,type=Path,required=True)
        return p
    p=command('capture','contract ledger draft output');p.add_argument('--approval',type=Path);p.add_argument('--environment',choices=('work','codex'),required=True);p.add_argument('--previous');p.add_argument('--source-thread')
    p=command('prepare','contract ledger requirement journal');p.add_argument('--destination-base',type=Path);p.add_argument('--direction',choices=('work-to-codex','codex-to-work'),required=True);p.add_argument('--authority',required=True);p.add_argument('--routing',type=Path)
    p=command('plan','journal discovery');p.add_argument('--channel',choices=('primary','fallback'),default='primary')
    p=command('record','journal output');p.add_argument('--status',choices=tuple(e for e in EVENTS if e not in ('RECEIVER_SELECTED','VERIFIED')),required=True);p.add_argument('--channel',choices=('primary','fallback'),required=True);p.add_argument('--delivery',choices=('present','unknown','not-delivered'),required=True);p.add_argument('--reference',required=True)
    p=command('select-receiver','journal observation output');p.add_argument('--channel',choices=('primary','fallback'),default='primary')
    p=command('receive','contract input requirement journal observation store proof registry-output');p.add_argument('--base',type=Path);p.add_argument('--channel',choices=('primary','fallback'),required=True)
    p=command('check','contract store requirement journal');p.add_argument('--channel',choices=('primary','fallback'),required=True)
    p=command('confirm','contract input requirement journal proof receipt registry observation output');p.add_argument('--base',type=Path)
    p=command('align','contract ledger');p.add_argument('--environment',choices=('work','codex'),required=True)
    p=command('migrate','contract decision-config output')
    p=command('migrate-routing','contract output')
    args=parser.parse_args()
    try:
        if args.command=='capture':result=capture(contract(args.contract),c.load(args.ledger),c.load(args.draft),c.load(args.approval) if args.approval else None,args.environment,args.previous,args.source_thread)
        elif args.command=='prepare':
            req,j=prepare(args.contract,args.ledger,args.destination_base,args.direction,args.authority,c.load(args.routing) if args.routing else None)
            # Inspect both outputs before writing either, including after interruption.
            for path,value in ((args.requirement,req),(args.journal,j)):
                if path.exists():
                    actual=c.load(path)
                    if path==args.journal:validate_operation(actual);c.require(actual['operation']==value['operation'],'Another operation owns output');j=actual
                    else:c.require(actual==value,'Another requirement owns output')
            for path,value in ((args.requirement,req),(args.journal,j)):
                if not path.exists():c.write_new(path,c.encode(value))
            result=j
        elif args.command=='plan':result=plan(c.load(args.journal),c.load(args.discovery),args.channel)
        elif args.command=='select-receiver':result=select_receiver(c.load(args.journal),c.load(args.observation),args.channel)
        elif args.command=='record':result=append(c.load(args.journal),args.status,args.channel,args.delivery,args.reference)
        elif args.command=='receive':result=receive(args.contract,args.input,args.requirement,c.load(args.journal),c.load(args.observation),args.base,args.channel,args.store,args.proof,args.registry_output)
        elif args.command=='check':result=check(args.contract,args.store,args.requirement,c.load(args.journal),args.channel)
        elif args.command=='confirm':result=confirm(args.contract,args.input,args.requirement,c.load(args.journal),args.base,args.proof,args.receipt,args.registry,c.load(args.observation))
        elif args.command=='migrate-routing':result=migrate_routing(c.load(args.contract))
        elif args.command=='migrate':
            old=c.load(args.contract);c.validate_contract(old);c.require(old['schema_version']==2,'Migrate v1 transport explicitly to v2 first')
            result={**old,'schema_version':3,'decision_sync':c.load(args.decision_config)};c.validate_contract(result)
        else:
            config=contract(args.contract);ledger=c.load(args.ledger);heads=validate_ledger(ledger,config)
            result={'project_id':config['project_id'],'environment':args.environment,'source_version':c.digest(args.ledger.read_bytes()),'decisions':[{**r,'record_sha256':record_hash(r)} for r in heads.values()],'code_status':'NOT_ASSESSED','next_step':'Use these validated decisions in mission preflight; review differences before any Git integration'}
        if hasattr(args,'output'):c.write_new(args.output,c.encode(result))
        print(c.encode(result).decode(),end='');return 0
    except (c.SyncError,OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        print(c.encode({'state':'BLOCKED','mirror_status':'UNKNOWN','alignment_status':'UNKNOWN','error':str(exc)}).decode(),end='');return 2


if __name__=='__main__':sys.exit(main())
