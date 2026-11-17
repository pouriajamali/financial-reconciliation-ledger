"""Fixed project01 supported-CI controller candidate. Never uses local READY.
Only exact future source/input/host admission can activate it; this file is inert.
"""
import argparse,signal,select,shlex,hashlib,importlib.util,json,os,platform,secrets,subprocess,sys,time,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent

def need(v,m):
    if not v:raise RuntimeError(m)

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def load(p):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=2097152,'BOUND_INPUT')
    return json.loads(p.read_text(encoding='utf-8-sig'))

def module(name,path,expected):
    need(sha(path)==expected,'REVIEWED_SOURCE_BINDING')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value

def write(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

NORMAL_MODULE_SHA='c37e2f48ee21ef1f02e4afb2bb1cd0af397781e487265c31e43fe06ea182befd'
NORMAL_CATALOG_SHA='8995a4d296afbfcdf8e267e1923a4de5365b7fa1ef58457add433dfb6df33e23'
OWN_REPOSITORY='pouriajamali/financial-reconciliation-ledger'

def normal_values(own,files,clock,supervisor):
    # Pure owner-only adapter; finite SDK0 fixtures can inspect this without host/transport.
    need(own['projectId']=='01' and own['rid'] in ('linux-x64','win-x64') and own['repository']==OWN_REPOSITORY,'FOREIGN_NORMAL_DENIED')
    need(set(files)=={'admission','capsEvidence','checkout','contract','controller','profile','sourcePins'} and all(isinstance(x,str) and x for x in files.values()),'NORMAL_OWN_FILES')
    start,end=clock['rowStartedMonotonicNs'],clock['deadlineMonotonicNs']
    need(type(start) is int and type(end) is int and 0<start<end and end-start<=900000000000,'ORIGINAL_OWN_CLOCK')
    need(type(supervisor['pid']) is int and supervisor['pid']>0 and supervisor['start'].startswith('proc-start:' if own['rid']=='linux-x64' else 'FILETIME:'),'OWN_SUPERVISOR_START')
    return dict(files,projectId='01',repository=OWN_REPOSITORY,expectedSourceCommit=own['sourceCommit'],expectedSourceTree=own['sourceTree'],rowStartedMonotonicNs=start,deadlineMonotonicNs=end,supervisorPID=supervisor['pid'],supervisorStartIdentity=supervisor['start'])

def actual_normal_evidence(own,held,before):
    if own['rid']=='win-x64':
        fields=('pid','processStartIdentity','jobName','memoryMaxBytes','tasksMax','cpuRate','logicalHostCpu')
        return {'schema':'sdk11-own-current-cap-evidence/v1','projectId':'01','repository':OWN_REPOSITORY,'sourceCommit':own['sourceCommit'],'sourceTree':own['sourceTree'],'profileSha256':own['profileSha256'],'controllerSha256':own['controllerSha256'],'worker':{k:before[k] for k in fields},'heldBeforeExec':before,'supervisor':{'pid':own['supervisorPID'],'processStartIdentity':own['supervisorStartIdentity'],'deadlineMonotonicNs':own['deadlineMonotonicNs']},'rowStartedMonotonicNs':own['rowStartedMonotonicNs'],'deadlineMonotonicNs':own['deadlineMonotonicNs'],'bootstrap':held['bootstrap']}
    return {'schema':'sdk11-own-current-cap-evidence/v1','projectId':'01','repository':OWN_REPOSITORY,'sourceCommit':own['sourceCommit'],'sourceTree':own['sourceTree'],'profileSha256':own['profileSha256'],'controllerSha256':own['controllerSha256'],'worker':{'pid':held['pid'],'processStartIdentity':'proc-start:'+held['startIdentity'],'uid':held['workerUid'],'gid':held['workerGid'],'cgroup':before['cgroup'],'kernelLimits':before['kernelLimits']},'beforeExec':before,'supervisor':{'pid':own['supervisorPID'],'processStartIdentity':own['supervisorStartIdentity'],'deadlineMonotonicNs':own['deadlineMonotonicNs']},'rowStartedMonotonicNs':own['rowStartedMonotonicNs'],'deadlineMonotonicNs':own['deadlineMonotonicNs'],'bootstrap':held['bootstrap']}

def context(admission,guard):
    host='GitHubHostedWindowsServer2025x64' if os.name=='nt' else 'GitHubHostedUbuntu24.04x64'
    own=guard.observe_machine(host);own['projectId']='01';own['nativeTools']=[]
    paths=[Path(sys.executable).resolve()] + ([] if os.name=='nt' else [Path('/usr/bin/sudo'),Path('/usr/bin/systemd-run'),Path('/usr/bin/systemctl'),Path('/usr/bin/git')])
    for executable in paths:
        need(executable.is_file(),'EXISTING_TOOL_REQUIRED_NO_INSTALL');own['nativeTools'].append({'path':str(executable),'sha256':sha(executable)})
    checkout=Path(os.environ['GITHUB_WORKSPACE']).resolve()
    def git(*args):
        p=subprocess.run(['git','--no-optional-locks','-C',str(checkout),*args],capture_output=True,text=True,timeout=5);need(p.returncode==0,'SOURCE_GIT_METADATA');return p.stdout.strip()
    own.update(checkout=str(checkout),sourceCommit=git('rev-parse','HEAD'),sourceTree=git('rev-parse','HEAD^{tree}'),dirty=bool(git('status','--porcelain')),contractSha256=admission['contractSha256'],controllerSha256=sha(Path(__file__).resolve()),profileSha256=admission['profileSha256'])
    need(own['sourceCommit']==os.environ.get('GITHUB_SHA'),'ACTUAL_CHECKOUT_EVENT_SHA')
    run=own['runId'];attempt=own['runAttempt'];need(run.isdigit() and attempt.isdigit(),'OWN_RUN_IDS')
    url=f'https://api.github.com/repos/pouriajamali/financial-reconciliation-ledger/actions/runs/{run}/attempts/{attempt}/jobs?per_page=100'
    headers={'Accept':'application/vnd.github+json','User-Agent':'frl01-owned-ci-context'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=10) as response:
        raw=response.read(2097153);need(len(raw)<=2097152,'OWN_JOB_METADATA_CAP')
    jobs=json.loads(raw)['jobs'];matches=[j for j in jobs if j['name']=='Guarded native '+own['rid'] and j.get('runner_name')==own['runnerName'] and j.get('status')=='in_progress']
    need(len(matches)==1,'ACTUAL_CURRENT_NUMERIC_JOB_ID');job=matches[0]
    own['repository']=os.environ.get('GITHUB_REPOSITORY');need(own['repository']==OWN_REPOSITORY,'OWN_REPOSITORY')
    own.update(jobId=str(job['id']),jobKey=os.environ.get('GITHUB_JOB',''),instanceIdentity=own['runnerName']+':'+str(job['id'])+':'+attempt,jobStartedAt=job['started_at'])
    # Independently observe own Linux CPU; no producer CPU/cap proof borrowed.
    if os.name!='nt':
        raw=Path('/proc/cpuinfo').read_bytes();need(len(raw)<=8388608 and sys.version_info[:2]==(3,12),'EXISTING_OWN_PYTHON_CPU_INPUT')
        flags=[set(x.split(':',1)[1].split()) for x in raw.decode().splitlines() if x.startswith('flags')]
        need(flags and all({'cx16','popcnt','pni','ssse3','sse4_1','sse4_2','lahf_lm'}<=x for x in flags),'OWN_CPU_V2');own['cpuEvidenceSha256']=hashlib.sha256(raw).hexdigest()
    else:
        own['cpuObservationPendingWithinOwnHeldWorker']=True
    pins=guard.bound(admission['sourcePinTable']);own['sourcePinTableSha256']=hashlib.sha256(json.dumps(pins['sourcePins'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    guard.bound(admission['ownContract']);need(admission['ownContract']['sha256']==own['contractSha256'],'OWN_TRACKED_CONTRACT')
    own['cpuV2']=os.name!='nt'
    return own

def linux_caps():
    rel=[x[3:] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::')]
    need(len(rel)==1 and rel[0]!='/' and os.getuid()>0 and os.getgid()>0,'NONROOT_OWN_CGROUP')
    root=Path('/sys/fs/cgroup');group=root/rel[0].lstrip('/');cpu=(group/'cpu.max').read_text().split()
    memory=(group/'memory.max').read_text().strip();swap=(group/'memory.swap.max').read_text().strip();tasks=(group/'pids.max').read_text().strip()
    need(cpu[0]!='max' and int(cpu[0])<=2*int(cpu[1]) and 0<int(memory)<=2147483648 and swap=='0' and 0<int(tasks)<=64,'EFFECTIVE_OWN_CAPS')
    need(str(os.getpid()) in (group/'cgroup.procs').read_text().split(),'HELD_WORKER_MEMBERSHIP')
    return {'cgroup':str(group),'cpu.max':cpu,'memory.max':memory,'memory.swap.max':swap,'pids.max':tasks}


def observe_windows_bootstrap_members(root,own,kernel):
    # Read only this dedicated named Job, before the shared strict single-main
    # predicate. No global process inventory, cmdline/env, setter or SDK call.
    from ctypes import wintypes as W
    c=kernel.ctypes;K=c.WinDLL('kernel32',use_last_error=True)
    K.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];K.OpenJobObjectW.restype=W.HANDLE
    K.QueryInformationJobObject.argtypes=[W.HANDLE,c.c_int,c.c_void_p,W.DWORD,c.c_void_p]
    K.CloseHandle.argtypes=[W.HANDLE];K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
    K.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,c.POINTER(W.DWORD)]
    K.GetConsoleProcessList.argtypes=[c.POINTER(W.DWORD),W.DWORD];K.GetConsoleProcessList.restype=W.DWORD
    class IDs(c.Structure):_fields_=[('assigned',W.DWORD),('listed',W.DWORD),('pids',c.c_size_t*64)]
    handle=K.OpenJobObjectW(4,False,own['jobName']);need(handle,'OWN_BOOTSTRAP_JOB_QUERY')
    try:
        ids=IDs();need(K.QueryInformationJobObject(handle,3,c.byref(ids),c.sizeof(ids),None) and ids.assigned==ids.listed<=32,'OWN_BOOTSTRAP_MEMBER_BOUND');members=[]
        for pid in ids.pids[:ids.listed]:
            proc=K.OpenProcess(0x1000,False,pid);name='UNAVAILABLE'
            if proc:
                try:
                    length=W.DWORD(32768);buf=c.create_unicode_buffer(length.value)
                    if K.QueryFullProcessImageNameW(proc,0,buf,c.byref(length)):name=Path(buf.value).name
                finally:K.CloseHandle(proc)
            members.append({'pid':int(pid),'imageBaseName':name})
        pids=(W.DWORD*64)();c.set_last_error(0);console_count=int(K.GetConsoleProcessList(pids,64));console_error=c.get_last_error() if console_count==0 else 0
        write(root/'proof/windows-bootstrap-members.json',{'schema':'frl01-own-windows-bootstrap-members/v1','state':'OBSERVATION_ONLY_NOT_ADMISSION','jobName':own['jobName'],'currentPID':os.getpid(),'assigned':int(ids.assigned),'listed':int(ids.listed),'members':members,'consoleClientCount':console_count,'consoleQueryError':console_error})
    finally:K.CloseHandle(handle)

def worker(args,admission,profile,guard,kernel,own,route,root,deadline):
    watch=win=normal=None
    if os.name=='nt':
        observe_windows_bootstrap_members(root,own,kernel)
        normal=module('frl01_shared_normal',HERE.parent/'check_dotnet11.py',NORMAL_MODULE_SHA)
        win=normal._load('normal_windows_input',normal.PINS['windowsNormalHelperSha256'])
        watch=win.OwnJob(normal,own,{'worker':{'jobName':own['jobName']}},own['deadlineMonotonicNs'])
    try:return worker_stages(args,admission,profile,guard,kernel,own,route,root,deadline,normal,win,watch)
    finally:
        if watch is not None:watch.close()


def worker_stages(args,admission,profile,guard,kernel,own,route,root,deadline,normal,win,watch):
    cpu=None
    if os.name=='nt':
        caps=win.host(normal,own,watch);cpu=win.measure_cpu(normal,root)
        need(cpu['processorCount']>0,'OWN_WINDOWS_CPU_V2');own['cpuV2']=True;own['cpuEvidenceSha256']=cpu['evidenceSha256']
        limits={'memoryBytes':caps['memoryMaxBytes'],'cpuEquivalent':caps['effectiveCpuCores'],'processLimit':caps['tasksMax'],'killOnClose':bool(caps['limitFlags']&0x2000),'suspendedBeforeAssignment':True}
    else:
        caps=linux_caps();limits={'memoryBytes':int(caps['memory.max']),'cpuEquivalent':int(caps['cpu.max'][0])/int(caps['cpu.max'][1]),'tasksMax':int(caps['pids.max']),'swapBytes':int(caps['memory.swap.max'])}
        need(os.getuid()==own['uid'] and os.getgid()==own['gid'],'ACTUAL_WORKER_UID_GID')
    held={'projectId':'01','jobId':own['jobId'],'instanceIdentity':own['instanceIdentity'],'pid':os.getpid(),'startIdentity':kernel.start_id(os.getpid()),'childHeld':True,'membershipObservedBeforeRelease':True,'sdkLaunchesBeforeRelease':0,'limits':limits,'kernel':caps,'workerUid':os.getuid() if os.name!='nt' else None,'workerGid':os.getgid() if os.name!='nt' else None}
    held['bootstrap']={'pythonVersion':platform.python_version(),'pythonExeSha256':sha(Path(sys.executable).resolve()),'gitSha256':sha(Path('/usr/bin/git')),'systemctlSha256':sha(Path('/usr/bin/systemctl'))} if os.name!='nt' else caps['bootstrap']
    if cpu is not None:held['cpu']=cpu
    write(root/'held.json',held)
    if os.name!='nt':os.kill(os.getpid(),signal.SIGSTOP)
    while not(root/'release-held.json').exists():need(time.monotonic()<deadline,'HELD_DEADLINE');time.sleep(.05)
    release=load(root/'release-held.json');need(release['token']==args.token and release['heldSha256']==sha(root/'held.json'),'HELD_RELEASE_IDENTITY')
    guard.own_caps(held,own)
    need(load(root/'consumer-host-admission.json')==guard.consumer_record(admission,own,sha(root/'normal-caps-evidence.json')),'ACTUAL_CANONICAL_CONSUMER_RECORD')
    if os.name!='nt':
        signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(RuntimeError('ORIGINAL_ROW_DEADLINE')))
        signal.setitimer(signal.ITIMER_REAL,max(.000001,deadline-time.monotonic()))
    result={'state':'SDK0_CONTROL_ONLY','SDKLaunches':0}
    if args.mode in ('product-ci','input-graph','input-only'):
        if route.get('runNewSdk0ModelFixtures'):
            need(sha(HERE/'test_ci_host_guard.py')==admission['sources']['newTestSha256'] and sha(HERE/'host_boundary_fixtures.json')==admission['sources']['newFixtureSha256'],'NEW_TEST_SOURCE_FIXTURES')
            check=subprocess.run([str(Path(sys.executable).resolve()),'-I','-B',str(HERE/'test_ci_host_guard.py')],capture_output=True,timeout=min(40,max(.1,deadline-time.monotonic())))
            need(check.returncode==0,'NEW_SDK0_BOUNDARY_FAILURE');write(root/'new-sdk0-model-results.json',{'stdout':check.stdout.decode('utf-8'),'stderr':check.stderr.decode('utf-8'),'SDKLaunches':0})
        # A derived current control binds the real own job/parent/kernel, never the producer kernel.
        control=root/'actual-ci-compatibility-control.json'
        write(control,{'schema':'frl01-ci-compatibility-control/v1','guardSha256':admission['sources']['guardSha256'],'managerAdmission':{'path':str(args.admission),'sha256':args.admission_sha256},'ownContext':{'path':str(root/'context.json'),'sha256':sha(root/'context.json')},'ownHeldProof':{'path':str(root/'held.json'),'sha256':sha(root/'held.json')},'candidateCommit':own['sourceCommit'],'helperSha256':sha(Path(own['checkout'])/'tools/check_tech_refresh.py'),'parent':{'pid':os.getpid(),'startIdentity':kernel.start_id(os.getpid())},'work':str(root/'compatibility'),'kernel':caps,'ciOwnership':{'path':str(root/'ownership.json'),'sha256':sha(root/'ownership.json')}})
        route['compatibilityControlBinding']={'path':str(control),'sha256':sha(control)}
        normal=normal or module('frl01_shared_normal',HERE.parent/'check_dotnet11.py',NORMAL_MODULE_SHA)
        need(sha(HERE.parent/'sdk11-normal-inputs.lock.json')==NORMAL_CATALOG_SHA,'BYTE_IDENTICAL_NORMAL_CATALOG')
        files={'admission':str(root/'consumer-host-admission.json'),'capsEvidence':str(root/'normal-caps-evidence.json'),'checkout':own['checkout'],'contract':str(Path(admission['ownContract']['path']).resolve()),'controller':str(Path(__file__).resolve()),'profile':str(args.profile),'sourcePins':str(Path(admission['sourcePinTable']['path']).resolve())}
        normal_context=normal_values(own,files,own,{'pid':own['supervisorPID'],'start':own['supervisorStartIdentity']})
        pipeline=module('frl01_ci_pipeline',HERE/'ci_pipeline.py',admission['sources']['pipelineSha256'])
        execute=pipeline.input_only if args.mode=='input-only' else pipeline.input_graphs if args.mode=='input-graph' else pipeline.pipeline
        result=execute(route,own,root,root/'proof',deadline,normal,normal_context,Path(own['normalDirectory']))
    if os.name!='nt':signal.setitimer(signal.ITIMER_REAL,0)
    write(root/'worker-result.json',{'projectId':'01','result':result,'kernel':caps,'targetExit':0,'currentJobId':own['jobId'],'terminalParentProofPending':True})
    return 0

def own_stop_observer(context_path,root):
    # Fixed nonroot ExecStopPost target, inside the same own unit/caps.
    # Persist actual service cause and last population BEFORE systemd collection.
    own=load(context_path);temp=Path(os.environ['RUNNER_TEMP']).resolve()
    need(os.name=='posix' and root.parent==temp and root.name.startswith('frl01-'+own['jobId']+'-') and root.stat().st_uid==os.getuid()>0 and (root.stat().st_mode&0o777)==0o700,'OWN_STOP_SCOPE')
    held=load(root/'held.json');caps=linux_caps();group=Path(caps['cgroup']);expected='/system.slice/frl01-ci-'+own['jobId']+'-'
    relative='/'+group.relative_to('/sys/fs/cgroup').as_posix();need(relative.startswith(expected) and relative.endswith('.service'),'OWN_STOP_CGROUP')
    population=[int(x) for x in (group/'cgroup.procs').read_text().split()]
    write(root/'stop-outcome.json',{'schema':'frl01-own-nonroot-stop-outcome/v1','jobId':own['jobId'],'workerPID':held['pid'],'workerStartIdentity':held['startIdentity'],'observerPID':os.getpid(),'uid':os.getuid(),'gid':os.getgid(),'cgroup':relative,'actualCaps':caps,'serviceResult':os.environ.get('SERVICE_RESULT'),'exitCode':os.environ.get('EXIT_CODE'),'exitStatus':os.environ.get('EXIT_STATUS'),'populationObserved':population,'remainingPopulationExcludingObserver':len([pid for pid in population if pid!=os.getpid()]),'observedMonotonicNs':time.monotonic_ns(),'causeCapturedBeforeCollection':True})
    return 0


def failed_aggregate_terminal(stop,own,held,unit,launcher_terminal,pidfd_terminal,group_absent,populated):
    # Missing group is evidence only after the exact durable own stop record.
    return (type(stop) is dict and type(held) is dict and launcher_terminal is True and pidfd_terminal is True
        and stop.get('jobId')==own['jobId'] and stop.get('workerPID')==held['pid']
        and stop.get('workerStartIdentity')==held['startIdentity'] and stop.get('cgroup')=='/system.slice/'+unit+'.service'
        and stop.get('remainingPopulationExcludingObserver')==0 and stop.get('causeCapturedBeforeCollection') is True
        and bool(stop.get('serviceResult')) and bool(stop.get('exitCode')) and stop.get('exitStatus') is not None
        and (group_absent is True or populated=='0'))


def capture_linux_failure(error,root,own,held,unit,client,pidfd):
    # No global/service reset or root cleanup. Only retained own worker signal.
    if os.name=='nt' or pidfd is None or unit is None or client is None:return
    if not select.select([pidfd],[],[],0)[0]:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
    remaining=own['rowStartedMonotonicNs']/1e9+900-time.monotonic()
    if remaining<=0:return
    try:client.wait(timeout=min(10,remaining))
    except subprocess.TimeoutExpired:return
    stop_path=root/'stop-outcome.json'
    if not stop_path.is_file():return
    stop=load(stop_path);group=Path('/sys/fs/cgroup/system.slice')/(unit+'.service');events=group/'cgroup.events'
    populated=dict(x.split() for x in events.read_text().splitlines()).get('populated') if events.is_file() else None
    pidfd_terminal=bool(select.select([pidfd],[],[],0)[0]);absent=not group.exists()
    if not failed_aggregate_terminal(stop,own,held,unit,client.poll() is not None,pidfd_terminal,absent,populated):return
    code=str(error);safe=code if type(error) is RuntimeError and 0<len(code)<=128 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-' for c in code) else 'DETAIL_REDACTED'
    value={'schema':'frl01-owned-ci-failure/v1','state':'FAILURE_WITH_ACTUAL_OWNED_TERMINAL_NOT_PRODUCT_PASS','sourceCommit':own['sourceCommit'],'sourceTree':own['sourceTree'],'jobId':own['jobId'],'rid':own['rid'],'errorType':type(error).__name__,'code':safe,'launcherExit':client.returncode,'retainedWorkerPidfdTerminal':pidfd_terminal,'ownGroupAbsentAfterDurableStopCause':absent,'cgroupPopulated':populated,'stopOutcome':stop,'ownHeldProof':held,'SDKProductSuccessInferred':False}
    raw=json.dumps(value,indent=2).encode();need(len(raw)<=65536,'FAILURE_PROOF_BOUND')
    target=Path(own['checkout'])/'artifacts/host-proof';target.mkdir(parents=True,exist_ok=True)
    with (target/'failure.json').open('xb') as f:f.write(raw)
    candidates=[root/'context.json',root/'held.json',stop_path,*list((root/'proof').glob('*.json'))]
    need(sum(p.stat().st_size for p in candidates if p.is_file())+len(raw)<=8388608,'EXISTING_PROOF_ARTIFACT_LIMIT')
    for source in candidates:
        if source.is_file():need(source.stat().st_size<=2097152,'PROOF_FILE_LIMIT');(target/source.name).write_bytes(source.read_bytes())


def validate_windows_held_cpu(held,before,cpu,cpu_sha256):
    need(before['pid']==held['pid'] and before['processStartIdentity']=='FILETIME:'+held['startIdentity'],'OWN_RETAINED_WINDOWS_WORKER')
    current=held['kernel'];need(all(before[k]==current[k] for k in ('pid','processStartIdentity','jobName','memoryMaxBytes','tasksMax','cpuRate','logicalHostCpu')),'OWN_WINDOWS_HELD_KERNEL_MATCH')
    rows=cpu['processors'];need(cpu_sha256==held['cpu']['evidenceSha256'] and type(rows) is list and len(rows)==held['cpu']['processorCount']>0,'OWN_WINDOWS_CPU_ATTACHMENT')
    code=bytes.fromhex('5389c889d10fa241890041895804418948084189500c5bc3')
    need(cpu['codeHex']==code.hex() and cpu['codeSha256']==hashlib.sha256(code).hexdigest(),'OWN_WINDOWS_CPU_MEASUREMENT_SOURCE')
    need(all(type(x['processor']) is int and 0<=x['processor']<64 for x in rows) and len({x['processor'] for x in rows})==len(rows),'OWN_WINDOWS_CPU_SCOPE')
    mask=(1<<0)|(1<<9)|(1<<13)|(1<<19)|(1<<20)|(1<<23)
    need(all(type(x['leaf1Ecx']) is int and type(x['extendedEcx']) is int and x['leaf1Ecx']&mask==mask and x['extendedEcx']&1 for x in rows),'OWN_WINDOWS_ALL_CPU_V2')
    return cpu_sha256


def capture_windows_failure(error,root,own,held,job):
    if os.name!='nt' or job is None or job.job is None:return
    job.terminate();caps=job.readback();created=hasattr(job,'process')
    exited=job.exited() if created else True
    if caps['activeProcesses']!=0 or not exited:return
    code=str(error);safe=code if type(error) is RuntimeError and 0<len(code)<=128 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-' for c in code) else 'DETAIL_REDACTED'
    logs={};worker_code='UNKNOWN'
    for name in ('worker.stdout','worker.stderr'):
        path=root/name
        if path.is_file():
            need(path.stat().st_size<=33554432,'FAILURE_LOG_BOUND');logs[name]={'bytes':path.stat().st_size,'sha256':sha(path)}
            if name=='worker.stderr':
                with path.open('rb') as stream:stream.seek(max(0,path.stat().st_size-4096));tail=stream.read(4096)
                try:
                    value=json.loads(tail.decode('utf-8-sig').splitlines()[-1]);reason=value.get('reason','')
                    if value.get('state')=='HOLD' and type(reason) is str and 0<len(reason)<=128 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-' for c in reason):worker_code=reason
                except (ValueError,UnicodeError,IndexError,AttributeError):pass
    value={'schema':'frl01-owned-ci-failure/v1','state':'FAILURE_WITH_ACTUAL_WINDOWS_JOB_TERMINAL_NOT_PRODUCT_PASS','sourceCommit':own['sourceCommit'],'sourceTree':own['sourceTree'],'jobId':own['jobId'],'rid':'win-x64','errorType':type(error).__name__,'code':safe,'workerCode':worker_code,'retainedWorkerTerminal':exited,'workerWasCreated':created,'workerExit':job.exit_code() if created else None,'ownedPopulation':caps['activeProcesses'],'actualJobCaps':caps,'actualBeforeResume':getattr(job,'beforeResume',None),'ownHeldProof':held,'logs':logs,'SDKProductSuccessInferred':False}
    raw=json.dumps(value,indent=2).encode();need(len(raw)<=65536,'FAILURE_PROOF_BOUND');target=Path(own['checkout'])/'artifacts/host-proof';target.mkdir(parents=True,exist_ok=True)
    with (target/'failure.json').open('xb') as f:f.write(raw)
    candidates=[root/'bootstrap-context.json',root/'context.json',root/'held.json',root/'cpu-evidence.json',*list((root/'proof').glob('*.json'))]
    need(sum(p.stat().st_size for p in candidates if p.is_file())+len(raw)<=8388608,'EXISTING_PROOF_ARTIFACT_LIMIT')
    for source in candidates:
        if source.is_file():need(source.stat().st_size<=2097152,'PROOF_FILE_LIMIT');(target/source.name).write_bytes(source.read_bytes())
    return True

def main():
    bootstrap_start_ns=time.monotonic_ns()
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['sdk0-control','input-only','input-graph','product-ci'],required=True);p.add_argument('--admission',type=Path,required=True);p.add_argument('--admission-sha256',required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--worker',action='store_true');p.add_argument('--context',type=Path);p.add_argument('--root',type=Path);p.add_argument('--token');p.add_argument('--remaining',type=float);a=p.parse_args()
    need(sys.flags.isolated==1 and sys.flags.optimize==0,'ISOLATED_SOURCE_GUARDS')
    a.admission=a.admission.resolve();a.profile=a.profile.resolve()
    admission=load(a.admission);need(sha(a.admission)==a.admission_sha256 and admission['state']=='EXACT_SOURCE_INPUT_HOST_ROUTE_ADMITTED','NO_RUNTIME_ADMISSION')
    profile=load(a.profile);need(sha(a.profile)==admission['profileSha256'] and sha(Path(__file__).resolve())==admission['sources']['controllerSha256'],'EXACT_SOURCE_PROFILE')
    guard=module('frl01_ci_guard',HERE/'ci_host_guard.py',admission['sources']['guardSha256']);kernel=module('frl01_ci_kernel',HERE/'frl01_phase.py',admission['sources']['kernelSha256'])
    own=load(a.context) if a.worker else context(admission,guard)
    need(guard.observe_machine(own['hostClass'])['actualOSAccepted'],'ACTUAL_CURRENT_HOST')
    route=admission['routes'].get(own['hostClass']);need(type(route) is dict,'OWN_CORRESPONDING_ROUTE')
    if a.worker:return worker(a,admission,profile,guard,kernel,own,route,a.root,own['deadlineMonotonicNs']/1e9)
    import datetime
    began=datetime.datetime.fromisoformat(own['jobStartedAt'].replace('Z','+00:00')).timestamp();remaining=min(900,900-(time.time()-began));need(remaining>110,'ORIGINAL_JOB_REMAINING_BUDGET')
    now_ns=time.monotonic_ns();own['rowStartedMonotonicNs']=min(bootstrap_start_ns,now_ns-int((900-remaining)*1e9));own['deadlineMonotonicNs']=own['rowStartedMonotonicNs']+840000000000
    own['supervisorPID']=os.getpid();own['supervisorStartIdentity']=('proc-start:' if os.name!='nt' else 'FILETIME:')+kernel.start_id(os.getpid())
    deadline=own['deadlineMonotonicNs']/1e9
    temp=Path(os.environ['RUNNER_TEMP']).resolve();need(temp.is_dir() and not temp.is_symlink(),'PRIVATE_RUNNER_TEMP')
    token=secrets.token_hex(16);root=temp/('frl01-'+own['jobId']+'-'+token);root.mkdir(mode=0o700);(root/'proof').mkdir(mode=0o700)
    own['normalDirectory']=str(temp/('sdk11-normal-01-'+own['jobId']+'-'+token))
    if os.name=='nt':own['jobName']='Local\\frl01-ci-'+own['jobId']+'-'+token
    write(root/'bootstrap-context.json',own)
    write(root/'ownership.json',{'schema':'frl01-ci-job-ownership/v1','projectId':'01','jobId':own['jobId'],'instanceIdentity':own['instanceIdentity'],'ownerPID':os.getpid(),'ownerStart':kernel.start_id(os.getpid()),'token':token})
    argv=[str(Path(sys.executable).resolve()),'-I','-B',str(Path(__file__).resolve()),'--worker','--mode',a.mode,'--admission',str(a.admission),'--admission-sha256',a.admission_sha256,'--profile',str(a.profile),'--context',str(root/'bootstrap-context.json'),'--root',str(root),'--token',token,'--remaining',str(max(1,deadline-time.monotonic()))]
    job=client=None;unit=None;terminal=False;pidfd=None;failure_closed=False
    try:
        if os.name=='nt':
            rate=min(10000,20000//os.cpu_count());need(rate>0,'CPU_RATE')
            allowed=['SystemRoot','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','GITHUB_ACTIONS','RUNNER_ENVIRONMENT','ImageOS','ImageVersion','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','RUNNER_NAME','GITHUB_REPOSITORY','GITHUB_SHA','GITHUB_WORKSPACE','GITHUB_JOB','RUNNER_OS','RUNNER_TEMP']
            env={k:os.environ[k] for k in allowed if k in os.environ};temp=root/'bootstrap-temp';temp.mkdir();env.update(TEMP=str(temp),TMP=str(temp),PATH='C:/Windows/System32;C:/Windows;C:/Program Files/Git/cmd',PYTHONDONTWRITEBYTECODE='1')
            job=kernel.WindowsJob({'jobMemoryBytes':2147483648,'activeProcessLimit':32,'cpuRatePer10000':rate,'jobName':own['jobName']});job.launch(argv,Path(own['checkout']),env=env,logs=root)
        else:
            need(os.getuid()==own['uid']>0 and os.getgid()==own['gid']>0,'NONROOT_RUNNER')
            unit='frl01-ci-'+own['jobId']+'-'+token[:12]
            observer=shlex.join([str(Path(sys.executable).resolve()),'-I','-B',str(Path(__file__).resolve()),'--own-stop-observer',str(root/'bootstrap-context.json'),str(root)])
            need(not any(c in observer for c in ['\n','\r','%','$']),'FIXED_OBSERVER_ARGV')
            hostenv=['--setenv='+key+'='+os.environ[key] for key in ['GITHUB_ACTIONS','RUNNER_ENVIRONMENT','ImageOS','ImageVersion','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','RUNNER_NAME','GITHUB_REPOSITORY','GITHUB_SHA','GITHUB_WORKSPACE','GITHUB_JOB','RUNNER_OS','RUNNER_TEMP'] if key in os.environ]
            argv=['/usr/bin/sudo','-n','/usr/bin/systemd-run','--unit='+unit,'--uid='+str(own['uid']),'--gid='+str(own['gid']),'--wait','--pipe','--property=Type=exec','--property=ExecStopPost='+observer,'--property=CPUQuota=200%','--property=CPUQuotaPeriodSec=100ms','--property=SendSIGKILL=yes','--property=FinalKillSignal=SIGKILL','--property=MemoryMax=2147483648','--property=MemorySwapMax=0','--property=TasksMax=64','--property=KillMode=control-group','--property=TimeoutStopSec=5','--property=RuntimeMaxSec='+str(max(1,int(deadline-time.monotonic())-25)),*hostenv,*argv]
            client=subprocess.Popen(argv,stdout=(root/'rootstarter.stdout').open('xb'),stderr=(root/'rootstarter.stderr').open('xb'),stdin=subprocess.DEVNULL)
        while not(root/'held.json').exists():
            need(not(job.exited() if job else client.poll() is not None),'WORKER_EXITED_BEFORE_HELD');need(time.monotonic()<deadline,'HELD_TIMEOUT');time.sleep(.05)
        held=load(root/'held.json');guard.own_caps(held,own)
        need(kernel.start_id(held['pid'])==held['startIdentity'],'HELD_PROCESS_START')
        if os.name=='nt':
            before=job.beforeResume
            need(before['pid']==job.pid,'OWN_RETAINED_WINDOWS_WORKER')
            cpu=load(root/'cpu-evidence.json');own['cpuEvidenceSha256']=validate_windows_held_cpu(held,before,cpu,sha(root/'cpu-evidence.json'));own['cpuV2']=True
        else:
            pidfd=os.pidfd_open(held['pid']);stop_deadline=min(deadline,time.monotonic()+2)
            while True:
                raw=Path('/proc',str(held['pid']),'stat').read_text();state=raw[raw.rfind(')')+2:].split()[0]
                if state in {'T','t'}:break
                need(time.monotonic()<stop_deadline and client.poll() is None,'WAIT_ACTUAL_STOPPED_WORKER');time.sleep(.01)
            need(state in {'T','t'} and not select.select([pidfd],[],[],0)[0],'ACTUAL_STOPPED_RETAINED_WORKER')
            group=Path('/proc',str(held['pid']),'cgroup').read_text();expected='/system.slice/'+unit+'.service';need(('0::'+expected) in group.splitlines(),'OWN_STOPPED_SYSTEM_UNIT')
            limits={k:(Path('/sys/fs/cgroup')/expected.lstrip('/')/k).read_text().strip() for k in ['memory.max','memory.swap.max','pids.max','cpu.max']}
            need(limits=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cpu.max':'200000 100000'},'OWN_STOPPED_KERNEL_LIMITS')
            before={'pid':held['pid'],'processStartIdentity':'proc-start:'+held['startIdentity'],'cgroup':expected,'kernelLimits':limits,'state':'T','membershipBeforeRelease':True,'retainedStartHandle':True}
        hand=guard.handshake(admission,own);write(root/'context.json',own);write(root/'handshake.json',hand)
        write(root/'normal-caps-evidence.json',actual_normal_evidence(own,held,before))
        write(root/'consumer-host-admission.json',guard.consumer_record(admission,own,sha(root/'normal-caps-evidence.json')))
        write(root/'release-held.json',{'token':token,'heldSha256':sha(root/'held.json')})
        if os.name!='nt':signal.pidfd_send_signal(pidfd,signal.SIGCONT)
        while (not job.exited()) if job else (client.poll() is None):
            need(time.monotonic()<deadline,'ROW_DEADLINE');kernel.size_budget({'checkout':own['checkout'],'outputRoot':str(root),'extraOutputRoots':[own['normalDirectory']]},root)
            logs=sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and p.suffix in {'.stdout','.stderr','.log'});need(logs<=33554432,'AGGREGATE_LOG_LIMIT');time.sleep(.1)
        result=load(root/'worker-result.json')
        if job:
            status=job.readback();terminal=job.exit_code()==0 and status['activeProcesses']==0
        else:
            stop=load(root/'stop-outcome.json');need(stop['jobId']==own['jobId'] and stop['workerPID']==held['pid'] and stop['workerStartIdentity']==held['startIdentity'] and stop['cgroup']=='/system.slice/'+unit+'.service','OWN_STOP_SUBJECT')
            query=subprocess.run(['/usr/bin/systemctl','show',unit,'--property=LoadState','--property=MainPID','--property=ControlPID','--property=Result','--property=ActiveState','--property=ControlGroup'],capture_output=True,text=True,timeout=min(5,max(.1,deadline-time.monotonic())))
            fields=dict(x.split('=',1) for x in query.stdout.splitlines() if '=' in x);group=Path('/sys/fs/cgroup')/stop['cgroup'].lstrip('/')
            populated=(group/'cgroup.events').read_text() if (group/'cgroup.events').exists() else None;group_absent=not group.exists()
            pidfd_terminal=bool(select.select([pidfd],[],[],0)[0]);zero=group_absent or (populated is not None and dict(x.split() for x in populated.splitlines()).get('populated')=='0')
            status={'rootstarterExit':client.returncode,'systemctlExit':query.returncode,'stdout':query.stdout,'stderr':query.stderr,'cgroupEvents':populated,'ownCgroupAbsentAfterDurableStopCause':group_absent,'retainedWorkerPidfdTerminal':pidfd_terminal,'stopOutcome':stop}
            terminal=client.returncode==0 and pidfd_terminal and stop['serviceResult']=='success' and stop['exitCode']=='exited' and stop['exitStatus']=='0' and stop['remainingPopulationExcludingObserver']==0 and zero and (fields.get('LoadState')=='not-found' or fields.get('MainPID')==fields.get('ControlPID')=='0')
        write(root/'terminal.json',{'currentJobId':own['jobId'],'ownCaps':held,'result':result,'actualTerminalState':status,'terminal':terminal})
        need(terminal,'NO_ACTUAL_TERMINAL_PROOF_NO_UPLOAD')
        # Publish only bounded existing proof/application outputs after own terminal proof.
        target=Path(own['checkout'])/'artifacts/host-proof';target.mkdir(parents=True,exist_ok=False)
        sources=([root/'stop-outcome.json'] if os.name!='nt' else [root/'cpu-evidence.json'])+[root/'normal-caps-evidence.json',root/'consumer-host-admission.json',root/'context.json',root/'handshake.json',root/'held.json',root/'worker-result.json',root/'terminal.json'];need(sum(p.stat().st_size for p in sources)<=8388608,'EXISTING_PROOF_ARTIFACT_LIMIT')
        sources.extend((root/'proof').glob('*.json'))
        need(sum(p.stat().st_size for p in sources)<=8388608,'EXISTING_PROOF_ARTIFACT_LIMIT')
        for source in sources:
            need(source.stat().st_size<=2097152,'PROOF_FILE_LIMIT');(target/source.name).write_bytes(source.read_bytes())
    except BaseException as error:
        failure_closed=capture_windows_failure(error,root,own,locals().get('held'),job) is True
        capture_linux_failure(error,root,own,locals().get('held'),unit,client,pidfd)
        raise
    finally:
        if job:
            if not terminal and not failure_closed:job.terminate()
            job.close()
        if pidfd is not None:
            if not terminal and not select.select([pidfd],[],[],0)[0]:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
            os.close(pidfd)
        # No local lane reset, service repair/root shell, alternate host or fallback.
    return 0

def typed_worker_cause(error):
    kind=type(error).__name__;kind=kind if kind.isascii() and kind.isidentifier() and len(kind)<=64 else 'UNKNOWN'
    value={'schema':'frl01-typed-worker-cause/v1','state':'CAUSE_ONLY_NOT_ADMISSION','exceptionType':kind,'code':'DETAIL_REDACTED','missingIdentifier':None,'errno':None,'frames':[],'normalInputCleanup':None}
    code=str(error)
    if type(error) in (RuntimeError,ValueError) and 0<len(code)<=128 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-' for c in code):value['code']=code
    identifier=error.args[0] if type(error) is KeyError and len(error.args)==1 else getattr(error,'name',None) if type(error) is NameError else None
    if type(identifier) is str and identifier.isascii() and identifier.isidentifier() and len(identifier)<=64:value['missingIdentifier']=identifier
    number=getattr(error,'winerror',getattr(error,'errno',None))
    if type(number) is int and 0<=number<=4294967295:value['errno']=number
    tb=error.__traceback__;checkout=HERE.parent.parent
    while tb is not None:
        path=Path(tb.tb_frame.f_code.co_filename)
        if path.is_absolute() and path.is_relative_to(checkout):
            name=tb.tb_frame.f_code.co_name
            if len(name)<=80 and all(c.isascii() and (c.isalnum() or c in '_<>') for c in name):value['frames'].append({'module':path.relative_to(checkout).as_posix(),'function':name,'line':tb.tb_lineno})
        tb=tb.tb_next
    value['frames']=value['frames'][-12:]
    cleanup=getattr(error,'normalInputCleanup',None)
    if type(cleanup) is dict and cleanup.get('state') in ('NO_ALLOCATION','OWN_FRESH_ALLOCATION_REMOVED','UNKNOWN_OR_DEADLINE_PARTIAL_RETAINED') and type(cleanup.get('allocationCreated')) is bool:value['normalInputCleanup']={'state':cleanup['state'],'allocationCreated':cleanup['allocationCreated']}
    need(len(json.dumps(value,separators=(',',':')).encode())<=8192,'TYPED_WORKER_CAUSE_BOUND');return value


def record_typed_worker_cause(error):
    if '--worker' not in sys.argv or '--root' not in sys.argv:return
    root=Path(sys.argv[sys.argv.index('--root')+1]).resolve();temp=Path(os.environ['RUNNER_TEMP']).resolve()
    need(root.parent==temp and root.name.startswith('frl01-') and (root/'proof').is_dir(),'OWN_FAILURE_CAUSE_SCOPE')
    write(root/'proof/worker-cause.json',typed_worker_cause(error))

if __name__=='__main__':
    try:raise SystemExit(own_stop_observer(Path(sys.argv[2]),Path(sys.argv[3])) if len(sys.argv)==4 and sys.argv[1]=='--own-stop-observer' else main())
    except Exception as error:
        record_typed_worker_cause(error)
        print(json.dumps({'state':'HOLD','reason':str(error)}),file=sys.stderr);raise SystemExit(3)
