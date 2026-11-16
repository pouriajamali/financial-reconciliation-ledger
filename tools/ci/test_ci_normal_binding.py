"""Bounded owner-value SDK0 fixture. No host/native/transport imports or targets.
Partial symbolic projections only; never a real fact/admission/kernel receipt.
"""
import ast,copy,json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def functions(name,names):
    tree=ast.parse((HERE/name).read_text(encoding='utf-8'))
    body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in body}!=set(names):raise RuntimeError('FIXTURE_SOURCE_SHAPE')
    env={'OWN_REPOSITORY':'pouriajamali/financial-reconciliation-ledger'}
    exec(compile(ast.Module(body=body,type_ignores=[]),'<reviewed-pure-owner-values>','exec'),env)
    return env

def main():
    control=functions('ci_host_controller.py',{'need','normal_values','actual_normal_evidence'});pipe=functions('ci_pipeline.py',{'need','validate_normal_receipt'})
    own={'projectId':'01','rid':'linux-x64','repository':'pouriajamali/financial-reconciliation-ledger','sourceCommit':'MODEL_OWN_SOURCE','sourceTree':'MODEL_OWN_TREE','runId':'900','jobKey':'verify','runAttempt':'2','runnerName':'MODEL_CURRENT_RUNNER','profileSha256':'MODEL_OWN_PROFILE','controllerSha256':'MODEL_OWN_CONTROLLER','supervisorPID':100,'supervisorStartIdentity':'proc-start:777','rowStartedMonotonicNs':1000000000,'deadlineMonotonicNs':841000000000}
    files={k:'/MODEL/'+k for k in ['admission','capsEvidence','checkout','contract','controller','profile','sourcePins']};clock={k:own[k] for k in ['rowStartedMonotonicNs','deadlineMonotonicNs']};supervisor={'pid':100,'start':'proc-start:777'}
    ctx=control['normal_values'](own,files,clock,supervisor);passed=['exact_own_context']
    if ctx['deadlineMonotonicNs']!=clock['deadlineMonotonicNs'] or set(ctx)!=set(files)|{'projectId','repository','expectedSourceCommit','expectedSourceTree','rowStartedMonotonicNs','deadlineMonotonicNs','supervisorPID','supervisorStartIdentity'}:raise RuntimeError('EXACT_CONTEXT_KEYS_CLOCK')
    receipt={'schema':'sdk11-shared-normal-input-receipt/v1','state':'OWN_CURRENT_CALLER_INPUT_VERIFIED_NO_SDK_EXECUTION','projectId':'01','rid':'linux-x64','SDKExecutions':0,'SDKPathOrGitHubEnvironmentExports':0,'SDKCacheOrArtifactUploads':0,'normalCatalogSha256':'686c6c778f7841e6015fa401f3892b853df80e3341fbb5d02b27c682887c1c78','producerFactSha256':'757abf2d3dde65d10cd895cfc97eaeccb7fc11e8685b94ad046e6a8ec8829007','producerAcceptanceSha256':'0452e1f3b4f2662d57e9b273428bb37ab0c5a733551a92394ca2a4e8b9b4ac08','originalRowStartedMonotonicNs':clock['rowStartedMonotonicNs'],'absoluteOriginalDeadlineNs':clock['deadlineMonotonicNs'],'ownCurrent':{'repository':own['repository'],'commit':own['sourceCommit'],'tree':own['sourceTree'],'runId':'900','job':'verify','attempt':'2','instanceId':'MODEL_CURRENT_RUNNER'},'producerQualifiedOn':{'runId':'DIFFERENT_PRODUCER_RUN','instanceId':'DIFFERENT_PRODUCER_INSTANCE'}}
    pipe['validate_normal_receipt'](receipt,own,ctx);passed.append('different_producer_current_identity_allowed')
    def deny(label,fn,args):
        try:fn(*args)
        except RuntimeError:passed.append(label);return
        raise RuntimeError('EXPECTED_DENIAL_'+label)
    for label,key,value in [('windows_denied','rid','win-x64'),('foreign_owner_denied','projectId','04'),('foreign_repository_denied','repository','MODEL_FOREIGN')]:
        changed=dict(own);changed[key]=value;deny(label,control['normal_values'],[changed,files,clock,supervisor])
    bad=dict(files,extra='/MODEL/EXTRA');deny('extra_context_input_denied',control['normal_values'],[own,bad,clock,supervisor])
    for label,bad in [('clock_extension_denied',dict(clock,deadlineMonotonicNs=901000000001)),('reversed_clock_denied',dict(clock,deadlineMonotonicNs=1)),('boolean_clock_denied',dict(clock,rowStartedMonotonicNs=True))]:deny(label,control['normal_values'],[own,files,bad,supervisor])
    deny('unretained_supervisor_denied',control['normal_values'],[own,files,clock,{'pid':100,'start':'MODEL_UNRETAINED'}])
    for label,key,value in [('sdk_execution_denied','SDKExecutions',1),('wrong_catalog_denied','normalCatalogSha256','MODEL_WRONG'),('wrong_producer_fact_denied','producerFactSha256','MODEL_WRONG'),('transport_clock_reset_denied','originalRowStartedMonotonicNs',2)]:
        changed=dict(receipt);changed[key]=value;deny(label,pipe['validate_normal_receipt'],[changed,own,ctx])
    changed=copy.deepcopy(receipt);changed['ownCurrent']['job']='MODEL_WRONG_JOB';deny('borrowed_current_job_denied',pipe['validate_normal_receipt'],[changed,own,ctx])
    held={'pid':101,'startIdentity':'888','workerUid':2001,'workerGid':2001,'bootstrap':{'fixtureOnly':True}};before={'cgroup':'/system.slice/frl01-ci-MODEL.service','kernelLimits':{'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cpu.max':'200000 100000'},'state':'T','pid':101,'processStartIdentity':'proc-start:888','membershipBeforeRelease':True,'retainedStartHandle':True}
    evidence=control['actual_normal_evidence'](own,held,before)
    if evidence['worker']['kernelLimits']['memory.max']!='2147483648' or evidence['worker']['processStartIdentity']!='proc-start:888' or evidence['beforeExec'] is not before or evidence['deadlineMonotonicNs']!=clock['deadlineMonotonicNs']:raise RuntimeError('OWN_HELD_EVIDENCE_MAPPING')
    passed.append('own2GiB_held_evidence_projection')
    print(json.dumps({'schema':'frl01-sdk0-normal-owner-values-result/v1','fixtureOnly':True,'scope':'PURE_PARTIAL_VALUES_ONLY_NOT_FACT_KERNEL_OR_RUNTIME_QUALIFICATION','cases':len(passed),'passed':passed,'SDKLaunches':0,'networkAttempts':0,'nativeTargets':0,'sharedModuleImported':False,'oldHealthySuitesExecuted':False}))
if __name__=='__main__':main()
