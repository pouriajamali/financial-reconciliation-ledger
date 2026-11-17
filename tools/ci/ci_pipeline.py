"""Fixed project01 CI pipeline; invoked only in its own admitted held worker.
No qualification replay, global READY, package upgrade or ambient SDK fallback.
"""
import contextlib, signal, hashlib, json, os, subprocess, sys, time, tarfile, zipfile
from pathlib import Path, PurePosixPath

def need(ok, message):
    if not ok: raise RuntimeError(message)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1048576),b''): h.update(data)
    return h.hexdigest()

def run(argv, cwd, env, directory, name, seconds, deadline):
    remaining=min(seconds,deadline-time.monotonic())
    need(remaining>0,'ROW_DEADLINE')
    out,err=directory/(name+'.stdout'),directory/(name+'.stderr')
    with out.open('xb') as stdout,err.open('xb') as stderr:
        p=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=(subprocess.DETACHED_PROCESS if os.name=='nt' else 0))
        began=time.monotonic()
        try:
            while p.poll() is None:
                need(time.monotonic()-began<remaining,'STAGE_DEADLINE')
                need(out.stat().st_size+err.stat().st_size<=33554432,'LOG_LIMIT')
                time.sleep(.1)
            code=p.wait(timeout=5)
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=5)
    need(code==0,'STAGE_EXIT_'+name)
    for path in [out,err]:
        need(path.stat().st_size<=33554432,'LOG_LIMIT')
        need(b'NU1900' not in path.read_bytes() and b'NU1905' not in path.read_bytes(),'AUDIT_UNKNOWN')
    return {'name':name,'argv':argv,'exit':code,'stdoutSha256':sha(out),'stderrSha256':sha(err)}

def payload_paths(names):
    seen=set()
    for name in names:
        pure=PurePosixPath(name);key=name.rstrip('/').casefold()
        need(isinstance(name,str) and name and not pure.is_absolute() and all(x not in {'','.','..'} for x in name.rstrip('/').split('/')) and '\\' not in name and ':' not in name and all(ord(c)>=32 and ord(c)!=127 for c in name),'PAYLOAD_PATH')
        need(key not in seen,'PAYLOAD_CASE_DUPLICATE');seen.add(key)

def safe_extract(archive,destination):
    need(not destination.exists(),'FRESH_ARCHIVE_DESTINATION')
    destination.mkdir()
    if archive.suffix=='.zip':
        with zipfile.ZipFile(archive) as z:
            members=z.infolist();need(len(members)<=1024,'PAYLOAD_COUNT');payload_paths([m.filename for m in members])
            for m in members:
                p=Path(m.filename);need(not p.is_absolute() and '..' not in p.parts and '\\' not in m.filename and ':' not in m.filename and (m.external_attr>>16)&0o170000!=0o120000,'PAYLOAD_PATH_LINK')
            need(sum(m.file_size for m in members)<=536870912,'PAYLOAD_EXPANSION')
            for m in members:
                path=destination/m.filename
                if m.is_dir():path.mkdir(parents=True,exist_ok=True);continue
                path.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as src,path.open('xb') as dst:
                    for b in iter(lambda:src.read(1048576),b''):dst.write(b)
    else:
        with tarfile.open(archive,'r:gz') as z:
            members=z.getmembers();need(len(members)<=1024 and sum(m.size for m in members)<=536870912,'PAYLOAD_EXPANSION');payload_paths([m.name for m in members])
            for m in members:
                p=Path(m.name);need(not p.is_absolute() and '..' not in p.parts and '\\' not in m.name and ':' not in m.name and (m.isfile() or m.isdir()),'PAYLOAD_PATH_TYPE')
            for m in members:
                path=destination/m.name
                if m.isdir():path.mkdir(parents=True,exist_ok=True);continue
                path.parent.mkdir(parents=True,exist_ok=True)
                with z.extractfile(m) as src,path.open('xb') as dst:
                    for b in iter(lambda:src.read(1048576),b''):dst.write(b)
                path.chmod(0o755 if m.mode&0o111 else 0o644)
    roots=list(destination.iterdir());need(len(roots)==1 and roots[0].is_dir(),'ONE_PACKAGE_ROOT');return roots[0]

@contextlib.contextmanager
def stage_alarm(seconds,deadline,normal=None,context=None):
    if os.name=='nt':
        need(normal is not None and context is not None,'OWN_WINDOWS_STAGE_CONTROL')
        helper=normal._load('normal_windows_input',normal.PINS['windowsNormalHelperSha256'])
        caps=normal._read(Path(context['capsEvidence']),65536)
        end=min(context['deadlineMonotonicNs'],time.monotonic_ns()+int(seconds*1000000000))
        watch=helper.OwnJob(normal,context,caps,end)
        try:yield
        finally:watch.close()
        return
    need(os.name=='posix','WINDOWS_NORMAL_DENIED')
    prior=signal.getitimer(signal.ITIMER_REAL);handler=signal.getsignal(signal.SIGALRM);began=time.monotonic();need(prior[1]==0,'NO_PERIODIC_TIMER')
    bound=min(deadline-began,seconds,prior[0] if prior[0]>0 else seconds);need(bound>0,'ORIGINAL_DEADLINE')
    def stop(*_):raise RuntimeError('STRICT_STAGE_DEADLINE')
    signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,bound)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)
        if prior[0]>0:
            left=prior[0]-(time.monotonic()-began);need(left>0,'ORIGINAL_ALARM_EXPIRED');signal.setitimer(signal.ITIMER_REAL,left)

def validate_normal_receipt(receipt,own,ctx):
    need(receipt['schema']=='sdk11-shared-normal-input-receipt/v1' and receipt['state']=='OWN_CURRENT_CALLER_INPUT_VERIFIED_NO_SDK_EXECUTION' and receipt['projectId']=='01' and receipt['rid']==own['rid'],'NORMAL_RECEIPT_SCOPE')
    need(receipt['SDKExecutions']==0 and receipt['SDKPathOrGitHubEnvironmentExports']==0 and receipt['SDKCacheOrArtifactUploads']==0,'NORMAL_NO_SDK_SIDE_EFFECTS')
    need(receipt['normalCatalogSha256']=='8995a4d296afbfcdf8e267e1923a4de5365b7fa1ef58457add433dfb6df33e23' and (receipt['producerFactSha256'],receipt['producerAcceptanceSha256'])=={'linux-x64':('757abf2d3dde65d10cd895cfc97eaeccb7fc11e8685b94ad046e6a8ec8829007','0452e1f3b4f2662d57e9b273428bb37ab0c5a733551a92394ca2a4e8b9b4ac08'),'win-x64':('ec8e9b405ca74bd7bbc748575265de2555056d84ff5780a8979bbb01cbd27c48','9713a70f809ac7f50a1c73650fc6d3390bccda109e7a2d15c9be581ff91dc8f6')}[own['rid']],'NORMAL_CAUSAL_PINS')
    need(receipt['originalRowStartedMonotonicNs']==ctx['rowStartedMonotonicNs'] and receipt['absoluteOriginalDeadlineNs']==ctx['deadlineMonotonicNs'],'NO_TRANSPORT_CLOCK_RESET')
    current=receipt['ownCurrent'];need(current['repository']==ctx['repository'] and current['commit']==ctx['expectedSourceCommit'] and current['tree']==ctx['expectedSourceTree'] and current['runId']==own['runId'] and current['job']==own['jobKey'] and current['attempt']==own['runAttempt'] and current['instanceId']==own['runnerName'],'OWN_RECEIPT_SUBJECT')
    # Deliberately do not equate producerQualifiedOn run/job/instance/image with this consumer.
    return receipt

def native_prerequisites(sdk,checkout,env,proof,deadline):
    if os.name=='nt':return windows_native_prerequisites(sdk,checkout,env,proof,deadline)
    need(Path('/usr/bin/ldd').is_file() and Path('/usr/sbin/ldconfig').is_file(),'EXISTING_NATIVE_INSPECTORS_NO_INSTALL')
    libraries=sorted({x for pattern in ['libhostfxr.so','libhostpolicy.so','libcoreclr.so','libSystem.*.Native.so'] for x in sdk.rglob(pattern)})
    need(3<=len(libraries)<=32,'FIXED_RUNTIME_NATIVE_SET');records=[]
    for index,path in enumerate(libraries):
        record=run(['/usr/bin/ldd','--',str(path)],checkout,env,proof,'native-closure-'+str(index),5,deadline)
        need(b'not found' not in (proof/('native-closure-'+str(index)+'.stdout')).read_bytes(),'NATIVE_CLOSURE_UNKNOWN');records.append(record)
    records.append(run(['/usr/sbin/ldconfig','-p'],checkout,env,proof,'native-dynamic-catalog',5,deadline))
    data=(proof/'native-dynamic-catalog.stdout').read_bytes();need(all(x in data for x in [b'libicuuc.so',b'libicui18n.so',b'libssl.so.3',b'libcrypto.so.3']),'NATIVE_DYNAMIC_PREREQUISITES')
    return records

def pipeline(route,context,root,proof,deadline,normal,normal_context,normal_directory):
    checkout=Path(context['checkout']);python=str(Path(sys.executable).resolve());rid=context['rid']
    env=sdk_environment(root)
    # Full product row requires reviewed net11 locks beforehand. No unlocked fallback.
    for p in [checkout/'src/Ledger/packages.lock.json',checkout/'tests/Ledger.Tests/packages.lock.json']:
        need(set(json.loads(p.read_text(encoding='utf-8-sig'))['dependencies'])=={'net11.0'},'NET11_LOCK_INPUT_NOT_SEALED')
    need(rid in ('linux-x64','win-x64'),'OWN_SUPPORTED_RID');records=[]
    # Same process/main worker: __main__ remains the tracked own controller.
    # The shared API receives the ORIGINAL row start/end; a stricter150s alarm
    # bounds materialization/native prerequisites without replacing that clock.
    with stage_alarm(150,deadline,normal,normal_context):
        sdk,receipt=normal.transport(rid,normal_directory,normal_context)
        need(sdk==normal_directory/'sdk','OWN_FRESH_NORMAL_RESULT_PATH');validate_normal_receipt(receipt,context,normal_context)
        raw=json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();need(len(raw)<=1048576,'NORMAL_RECEIPT_CAP')
        with (proof/'normal-input-receipt.json').open('xb') as f:f.write(raw)
        records.extend(native_prerequisites(sdk,checkout,env,proof,deadline))
    entry=sdk/('dotnet.exe' if rid=='win-x64' else 'dotnet')
    env.update(DOTNET_ROOT=str(sdk),DOTNET_ROOT_X64=str(sdk),DOTNET_HOST_PATH=str(entry),DOTNET_MULTILEVEL_LOOKUP='0',RestoreLockedMode='true',PATH=str(sdk)+os.pathsep+env.get('PATH','/usr/bin:/bin'))
    normal.inspect_sdk(rid,sdk,normal_context)
    records.append(run([str(entry),'restore','tests/Ledger.Tests','--locked-mode'],checkout,env,proof,'locked-restore',100,deadline))
    normal.inspect_sdk(rid,sdk,normal_context)
    records.append(run([str(entry),'run','--project','tests/Ledger.Tests','-c','Release','--no-restore','--','--work','artifacts/tests'],checkout,env,proof,'original-regressions',150,deadline))
    normal.inspect_sdk(rid,sdk,normal_context)
    records.append(run([python,'-I','-B','tools/package.py','--rid',rid,'--commit',context['sourceCommit'],'--work','artifacts/build','--out','artifacts/delivery','--dotnet',str(entry)],checkout,env,proof,'native-package',120,deadline))
    archives=list((checkout/'artifacts/delivery').iterdir());need(len(archives)==1 and archives[0].stat().st_size<=104857600,'ONE_APP_ARCHIVE')
    package=safe_extract(archives[0],checkout/'artifacts/extracted with spaces')
    records.append(run([python,'-I','-B','tools/check_package.py','--package',str(package),'--work','artifacts/package checks with spaces','--commit',context['sourceCommit']],checkout,env,proof,'original-22-extracted-checks',90,deadline))
    # Original compatibility literals/oracles are retained; own CI control adapter
    # is an explicit source/input attachment, never the historical local proof.
    control=route['compatibilityControlBinding'];need(sha(Path(control['path']))==control['sha256'],'CI_COMPATIBILITY_CONTROL')
    records.append(run([python,'-I','-B','tools/check_tech_refresh.py','--old-package',route['oldPublicPackage'],'--old-archive',route['oldPublicArchive'],'--new-package',str(package),'--commit',context['sourceCommit'],'--work',str(root/'compatibility'),'--control',control['path'],'--control-sha256',control['sha256']],checkout,env,proof,'unchanged-literal-compatibility',90,deadline))
    # Redistributed graph/notices/audit and both RID final gates remain independent.
    return {'state':'PRODUCT_STAGES_EXITED_TERMINAL_PROOF_PENDING','records':records,'runtimeArtifactBytes':archives[0].stat().st_size,'SDKArtifactOrCacheUpload':False,'normalInput':receipt}


def input_graphs(route,context,root,proof,deadline,normal,normal_context,normal_directory):
    """Original allocated phase1/2 only; real own capped Linux SDK, no restore."""
    need(context['rid']=='linux-x64','INPUT_GRAPH_QUALIFIED_LINUX_ONLY')
    checkout=Path(context['checkout']);env=dict(os.environ)
    for key in ('DOTNET_STARTUP_HOOKS','DOTNET_ADDITIONAL_DEPS','MSBuildSDKsPath','DirectoryBuildPropsPath','DirectoryBuildTargetsPath'):
        need(not env.get(key),'INPUT_GRAPH_AMBIENT_OVERRIDE')
    env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_GENERATE_ASPNET_CERTIFICATE='false',DOTNET_NOLOGO='1',DOTNET_EnableDiagnostics='0',DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='true',MSBuildEnableWorkloadResolver='false',MSBUILDDISABLENODEREUSE='1',DOTNET_CLI_USE_MSBUILD_SERVER='0',DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER='1',UseSharedCompilation='false',DOTNET_MULTILEVEL_LOOKUP='0',DOTNET_PROCESSOR_COUNT='2')
    for key,name in [('DOTNET_CLI_HOME','home'),('NUGET_PACKAGES','packages'),('NUGET_HTTP_CACHE_PATH','http'),('NUGET_PLUGINS_CACHE_PATH','plugins'),('NUGET_SCRATCH','scratch'),('TEMP','temp'),('TMP','temp')]:
        path=root/name;path.mkdir(exist_ok=True);env[key]=str(path)
    records=[]
    with stage_alarm(150,deadline,normal,normal_context):
        sdk,receipt=normal.transport('linux-x64',normal_directory,normal_context)
        need(sdk==normal_directory/'sdk','OWN_FRESH_NORMAL_RESULT_PATH');validate_normal_receipt(receipt,context,normal_context)
        records.extend(native_prerequisites(sdk,checkout,env,proof,deadline))
    env.update(DOTNET_ROOT=str(sdk),DOTNET_ROOT_X64=str(sdk),DOTNET_HOST_PATH=str(sdk/'dotnet'),PATH=str(sdk)+os.pathsep+'/usr/bin:/bin')
    begin=time.monotonic();end=min(deadline,begin+100)
    work=root/'input-curation';work.mkdir();config=work/'NuGet.Config';config.write_text('<configuration><packageSources><clear /></packageSources><auditSources><clear /></auditSources></configuration>\n',encoding='utf-8')
    archive=work/'source.zip'
    subprocess.run(['/usr/bin/git','-C',str(checkout),'archive','--format=zip','--output='+str(archive),context['sourceCommit']],check=True,timeout=min(10,max(.1,end-time.monotonic())))
    with zipfile.ZipFile(archive) as z:
        members=z.infolist();payload_paths([x.filename for x in members]);need(len(members)<=256 and sum(x.file_size for x in members)<=33554432,'INPUT_GRAPH_SOURCE_BOUND')
        for mode in ('portable','linux-x64','win-x64'):
            source=work/mode/'source';source.mkdir(parents=True);(work/mode/'evidence').mkdir()
            for item in members:
                need((item.external_attr>>16)&0o170000!=0o120000,'INPUT_GRAPH_SOURCE_LINK')
                target=source/item.filename
                if item.is_dir():target.mkdir(parents=True,exist_ok=True)
                else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
    plan=json.loads((checkout/'tools/ci/input-graph-plan.json').read_bytes());commands=plan['commands']
    need(plan['schema']=='frl01-finite-input-graph-plan/v1' and len(commands)==6 and [x['id'] for x in commands]==['linux-x64-evaluate','portable-evaluate','win-x64-evaluate','linux-x64-restore-graph','portable-restore-graph','win-x64-restore-graph'],'INPUT_GRAPH_FINITE_COMMANDS')
    products={}
    for item in commands:
        need(item['maxSeconds']==(4 if item['phase']==1 else 6),'INPUT_GRAPH_FIXED_TIMEOUT')
        replace=lambda value:value.replace('<OWN_ACCEPTED_SDK>',str(sdk)).replace('<OWN_WORK>',str(root)).replace('<APPROVED_LOCAL_ONLY_NUGET_CONFIG>',str(config))
        argv=[replace(x) for x in item['argv']];need(argv[0]==str(sdk/'dotnet') and argv[1]=='msbuild' and all('<' not in x for x in argv),'INPUT_GRAPH_FIXED_ARGV')
        normal.inspect_sdk('linux-x64',sdk,normal_context)
        records.append(run(argv,checkout,env,proof,item['id'],item['maxSeconds'],end))
        path=proof/(item['id']+'.stdout') if item['phase']==1 else Path(replace(item['output']))
        need(path.is_file() and not path.is_symlink() and path.stat().st_size<=1048576,'INPUT_GRAPH_OUTPUT_BOUND')
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        if item['phase']==1:
            props=value['Properties'];need(props['TargetFramework']=='net11.0' and props['LangVersion']=='15.0' and props['RuntimeFrameworkVersion']=='11.0.0','INPUT_GRAPH_TARGET_IDENTITY')
        else:need(type(value.get('projects')) is dict and 1<=len(value['projects'])<=2,'INPUT_GRAPH_PROJECT_BOUND')
        products[item['id']]={'bytes':path.stat().st_size,'sha256':sha(path),'value':value}
    result={'schema':'frl01-actual-sdk-input-graphs/v1','state':'ACTUAL_SDK_GRAPHS_OBSERVED_NOT_CURATED_LOCKS_NOT_PRODUCT_ADMITTED','sourceCommit':context['sourceCommit'],'sourceTree':context['sourceTree'],'hostRID':'linux-x64','dataOnlyTargetRIDs':['portable','linux-x64','win-x64'],'commands':records,'graphs':products,'elapsedWithinOriginal100SecondsSlot':time.monotonic()-begin,'normalInput':receipt,'packageAcquisitions':0,'restores':0,'builds':0,'tests':0,'WindowsNativeExecutions':0}
    raw=json.dumps(result,separators=(',',':')).encode();need(len(raw)<=2097152,'INPUT_GRAPH_PROOF_BOUND');(proof/'input-graphs.json').write_bytes(raw)
    return result


def sdk_environment(root):
    # Runtime-private NuGet roots retain the accepted86dc null-path repair.
    forbidden=('DOTNET_STARTUP_HOOKS','DOTNET_ADDITIONAL_DEPS','CORECLR_ENABLE_PROFILING','CORECLR_PROFILER','MSBuildSDKsPath','DirectoryBuildPropsPath','DirectoryBuildTargetsPath','NUGET_PLUGIN_PATHS')
    need(not any(os.environ.get(k) for k in forbidden),'OWN_SDK_AMBIENT_OVERRIDE')
    allowed=('SystemRoot','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','LANG','LC_ALL','USER','LOGNAME')
    env={k:os.environ[k] for k in allowed if k in os.environ}
    env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_GENERATE_ASPNET_CERTIFICATE='false',DOTNET_NOLOGO='1',DOTNET_EnableDiagnostics='0',DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='true',MSBuildEnableWorkloadResolver='false',MSBUILDDISABLENODEREUSE='1',DOTNET_CLI_USE_MSBUILD_SERVER='0',DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER='1',UseSharedCompilation='false',DOTNET_MULTILEVEL_LOOKUP='0',DOTNET_PROCESSOR_COUNT='2',PYTHONDONTWRITEBYTECODE='1')
    for key,name in [('HOME','home'),('USERPROFILE','home'),('DOTNET_CLI_HOME','home'),('NUGET_PACKAGES','packages'),('NUGET_HTTP_CACHE_PATH','http'),('NUGET_PLUGINS_CACHE_PATH','plugins'),('NUGET_SCRATCH','scratch'),('TEMP','temp'),('TMP','temp'),('TMPDIR','temp'),('NUGET_COMMON_APPLICATION_DATA','program-data')]:
        path=root/name;path.mkdir(exist_ok=True);env[key]=str(path)
    if os.name=='nt':
        for key,name in [('PROGRAMFILES(X86)','program-files-x86'),('PROGRAMFILES','program-files'),('PROGRAMDATA','program-data'),('APPDATA','app-data'),('LOCALAPPDATA','local-app-data')]:
            path=root/name;path.mkdir(exist_ok=True);env[key]=str(path)
        env['PATH']='C:/Windows/System32;C:/Windows;C:/Program Files/Git/cmd'
    else:env['PATH']='/usr/bin:/bin'
    return env


def windows_native_prerequisites(sdk,checkout,env,proof,deadline):
    # Same existing publisher/import method as accepted qualification; own files,
    # actual host and own caps. No new SDK qualification or policy setter.
    import importlib.util
    path=checkout/'tools/qualification_input_guard.py';need(sha(path)=='7420b08d78d3b1476be41385d179a42212a2a7e1a965a8d8ea3b67bb14da7925','OWN_NATIVE_GUARD_SOURCE')
    spec=importlib.util.spec_from_file_location('own_native_input_guard',path);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    names=['dotnet.exe','host/fxr/11.0.0/hostfxr.dll','shared/Microsoft.NETCore.App/11.0.0/hostpolicy.dll','shared/Microsoft.NETCore.App/11.0.0/coreclr.dll','shared/Microsoft.NETCore.App/11.0.0/clrjit.dll'];system=Path(os.environ['SystemRoot'])/'System32';imports=[]
    for name in names:
        path=sdk/name;need(guard.machine(path)==('PE',0x8664),'OWN_NATIVE_PE_AMD64')
        for lib in guard.pe_imports(path):
            if lib.lower().startswith(('api-ms-','ext-ms-')):continue
            resolved=path.parent/lib
            if not resolved.is_file():resolved=system/lib
            need(resolved.is_file(),'OWN_NATIVE_IMPORT_MISSING');imports.append({'file':name,'import':lib,'resolvedName':resolved.name,'sha256':sha(resolved)})
    paths=','.join("'"+str(sdk/name).replace("'","''")+"'" for name in names)
    script="$ErrorActionPreference='Stop'; $r=@("+paths+") | ForEach-Object { $s=Get-AuthenticodeSignature -LiteralPath $_; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Microsoft Corporation' -or $null -eq $s.TimeStamperCertificate) { throw 'SDK_MICROSOFT_SIGNATURE_REQUIRED' }; [pscustomobject]@{name=[IO.Path]::GetFileName($_);status=[string]$s.Status;signer=$s.SignerCertificate.Subject;thumbprint=$s.SignerCertificate.Thumbprint;timestamp=$s.TimeStamperCertificate.Thumbprint} }; ConvertTo-Json -InputObject @($r) -Compress"
    record=run([str(system/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',script],checkout,env,proof,'own-windows-native-publisher',60,deadline)
    rows=json.loads((proof/'own-windows-native-publisher.stdout').read_text(encoding='utf-8-sig'));need(len(rows)==5 and all(x['status']=='Valid' and x['timestamp'] for x in rows),'OWN_NATIVE_PUBLISHER_REQUIRED')
    raw=json.dumps({'state':'OWN_CURRENT_SDK_PE_IMPORTS_AND_MICROSOFT_TIMESTAMPED_PUBLISHERS_OBSERVED','imports':imports,'publishers':rows,'record':record},indent=2).encode();need(len(raw)<=1048576,'OWN_NATIVE_PROOF_BOUND');(proof/'windows-native-prerequisites.json').write_bytes(raw)
    return [record]


def input_only(route,context,root,proof,deadline,normal,normal_context,normal_directory):
    need(context['rid']=='win-x64','OWN_WINDOWS_INPUT_ONLY_SCOPE');env=sdk_environment(root)
    with stage_alarm(150,deadline,normal,normal_context):
        sdk,receipt=normal.transport('win-x64',normal_directory,normal_context);validate_normal_receipt(receipt,context,normal_context)
        records=native_prerequisites(sdk,Path(context['checkout']),env,proof,deadline)
    value={'schema':'frl01-current-consumer-input-only/v1','state':'OWN_CURRENT_WINDOWS_INPUT_AND_NATIVE_PREREQUISITES_OBSERVED_NO_SDK_TARGET','sourceCommit':context['sourceCommit'],'sourceTree':context['sourceTree'],'normalInput':receipt,'records':records,'SDKExecutions':0,'NugetPackageAdmission':False,'productAdmission':False}
    raw=json.dumps(value,separators=(',',':')).encode();need(len(raw)<=2097152,'OWN_INPUT_ONLY_PROOF_BOUND');(proof/'input-only.json').write_bytes(raw);return value
