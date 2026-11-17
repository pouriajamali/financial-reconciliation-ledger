"""Project01 typed CI host handshake. Source-only candidate; not an SDK qualifier.
Producer facts are immutable historical evidence. Each current consumer supplies
its own host/instance/image/kernel proof; job IDs are recorded, never equated.
"""
import hashlib, json, os, platform, re
from pathlib import Path

HOSTS = {'GitHubHostedWindowsServer2025x64': ('win-x64', 'win25'),
         'GitHubHostedUbuntu24.04x64': ('linux-x64', 'ubuntu24')}
DESIGN = '9b3e0f376c5381b623f6a0f007bf6a6bb44f3dcbd1c2e4654de949a1eb97eec8'
HOST_IMAGES = {'GitHubHostedWindowsServer2025x64': frozenset(('win25', 'win25-vs2026')),
               'GitHubHostedUbuntu24.04x64': frozenset(('ubuntu24',))}


def need(ok, code):
    if not ok: raise RuntimeError(code)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1048576), b''): h.update(data)
    return h.hexdigest()

def read(path):
    need(path.is_absolute() and path.is_file() and path.stat().st_size <= 2097152, 'BOUND_DOCUMENT')
    for item in [path, *path.parents]:
        need(not item.is_symlink() and not (getattr(item.lstat(), 'st_file_attributes', 0) & 0x400), 'NO_LINK')
    def unique(pairs):
        value = {}
        for k,v in pairs:
            need(k not in value, 'DUPLICATE_KEY'); value[k] = v
        return value
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)

def bound(value):
    need(set(value)=={'path','sha256'} and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'HASH_BINDING')
    path = Path(value['path']); result = read(path)
    need(digest(path)==value['sha256'] and not result.get('fixtureOnly', False), 'REAL_BOUND_INPUT')
    return result

INTERFACE_SHA='63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c'
INTERFACE_ID='urn:pouria:dotnet11-host-qualification:v1'
IDENTITY_RULE='QUALIFIED_ON_IS_HISTORICAL_PRODUCER_INSTANCE_CURRENT_CONSUMER_JOB_MAY_DIFFER'

def schema_value(v,s):
    # Pure stdlib evaluator for the frozen producer schema vocabulary; no local schema fork.
    if 'type' in s:
        kinds=s['type'] if isinstance(s['type'],list) else [s['type']]
        types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'null':type(None)}
        need(any(type(v) is types.get(k) if k!='number' else type(v) in (int,float) for k in kinds),'SHARED_SCHEMA_TYPE')
    if 'const' in s:need(type(v) is type(s['const']) and v==s['const'],'SHARED_SCHEMA_CONST')
    if 'enum' in s:need(v in s['enum'],'SHARED_SCHEMA_ENUM')
    if isinstance(v,dict):
        props=s.get('properties',{});need(all(k in v for k in s.get('required',[])),'SHARED_SCHEMA_REQUIRED')
        if s.get('additionalProperties') is False:need(set(v)<=set(props),'SHARED_SCHEMA_EXTRA')
        for k,x in v.items():
            if k in props:schema_value(x,props[k])
    if isinstance(v,list):
        need(s.get('minItems',0)<=len(v)<=s.get('maxItems',100000),'SHARED_SCHEMA_ITEMS')
        prefix=s.get('prefixItems',[])
        for i,x in enumerate(v):
            sub=prefix[i] if i<len(prefix) else s.get('items',{})
            need(sub is not False,'SHARED_SCHEMA_EXTRA_ITEM')
            if isinstance(sub,dict):schema_value(x,sub)
    if isinstance(v,str):
        need(s.get('minLength',0)<=len(v)<=s.get('maxLength',100000),'SHARED_SCHEMA_LENGTH')
        if 'pattern' in s:need(re.fullmatch(s['pattern'],v) is not None,'SHARED_SCHEMA_PATTERN')
    if type(v) in (int,float):need(s.get('minimum',float('-inf'))<=v<=s.get('maximum',float('inf')) and v>s.get('exclusiveMinimum',float('-inf')),'SHARED_SCHEMA_RANGE')

def shared_schema(admission):
    interface=admission['producerHostFactInterface']
    need(interface['schemaId']==INTERFACE_ID and interface['consumerDefinition']=='#/$defs/consumerAdmission' and interface['schemaBinding']['sha256']==INTERFACE_SHA,'SOLE_FROZEN_PRODUCER_INTERFACE')
    value=bound(interface['schemaBinding']);need(value['$id']==INTERFACE_ID,'SHARED_SCHEMA_ID');return value

def model(fact, acceptance, route, own):
    need(fact['schema']=='sdk11-host-qualification/v1' and fact['outcome']=='NATIVE_HOST_QUALIFICATION_OBSERVED','FACT_STATE')
    need(fact['qualifiedOn']['repository']=='pouriajamali/data-admission-gate','SOLE_PRODUCER04')
    need(fact['toolchain']['sdk']=='11.0.100' and fact['toolchain']['runtime']=='11.0.0','SDK_RUNTIME_PIN')
    host=own['hostClass'];need(host in HOSTS,'CI_HOST_CLASS');rid,image=HOSTS[host];target=route['admittedFor']
    need(own['rid']==rid and fact['qualifiedOn']['rid']==rid and route['rid']==rid,'RID_MATCH')
    need(route['status']=='ADMITTED' and target['hostClass']==host and target['rid']==rid,'OWN_ROUTE_ADMISSION')
    need(fact['qualifiedOn']['hostClass']==host and fact['factType']==('WindowsCIServer2025RID' if rid=='win-x64' else 'LinuxCIUbuntu24RID'),'FACT_SCOPE')
    need(acceptance['runId']==int(fact['qualifiedOn']['runId']) and any(x['status']=='completed' and x['conclusion']=='success' for x in acceptance['jobs']) and route['producerQualifiedOn']==fact['qualifiedOn'],'PRODUCER_ACCEPTANCE')
    need(route['archive']==fact['archive'] and target['memberManifestSha256']==fact['tree']['memberManifestSha256'],'ARTIFACT_IDENTITY')
    need(target['sdk']==fact['toolchain']['sdk'] and target['runtime']==fact['toolchain']['runtime'],'ADMITTED_TOOLCHAIN')
    need(own['runnerEnvironment']=='github-hosted' and own['imageOS'] in HOST_IMAGES[host] and own['machine']=='x86_64','ACTUAL_HOST_IMAGE')
    need(not own['container'] and not own['wsl'] and own['actualOSAccepted'],'NO_LOCAL_CONTAINER_FALLBACK')
    need(own['sourceCommit']==route['sourceCommit'] and own['sourceTree']==route['sourceTree'] and own['dirty'] is False,'SOURCE_SUBJECT')
    need(all(own[k]==target[k] for k in ['contractSha256','sourcePinTableSha256','controllerSha256','profileSha256']),'OWN_CONTROL_IDENTITY')
    need(own['projectId']=='01' and route['projectId']=='01' and own['cpuV2'],'OWNER_CPU')
    need(all(isinstance(own[k],str) and own[k] for k in ['runId','jobId','runAttempt','runnerName','imageVersion','instanceIdentity']),'CURRENT_JOB_IDENTITY')
    need(all(isinstance(fact['qualifiedOn'][k],str) and fact['qualifiedOn'][k] for k in ['runId','job','attempt','instanceId','imageVersion']),'PRODUCER_JOB_IDENTITY')
    # Producer job='verify'/attempt/instanceId are immutable history, not consumer jobId/runAttempt/instanceIdentity.
    return {'producerQualifiedOn':fact['qualifiedOn'],'consumerObservedOn':{k:own[k] for k in ['hostClass','runId','jobId','runAttempt','runnerName','imageVersion','instanceIdentity']},'rid':rid,'SDKLaunches':0}

def handshake(admission, own):
    need(admission['schema']=='frl01-ci-consumer-admission/v1' and admission['designGateSha256']==DESIGN,'TYPED_CI_CONTRACT')
    need(admission['state']=='EXACT_SOURCE_INPUT_HOST_ROUTE_ADMITTED','EXACT_GATE_NOT_READY')
    route=admission['routes'].get(own['hostClass']);need(isinstance(route,dict),'ONE_CORRESPONDING_ROUTE')
    schema=shared_schema(admission);fact=bound(route['producerFact']);acceptance=bound(route['producerAcceptance'])
    schema_value(fact,schema)
    need(fact['source']['schemaSha256']==INTERFACE_SHA,'PRODUCER_SCHEMA_SOURCE_BINDING')
    need(own['rid']=='linux-x64','WINDOWS_NORMAL_DENIED')
    need(route['producerFact']['sha256']=='757abf2d3dde65d10cd895cfc97eaeccb7fc11e8685b94ad046e6a8ec8829007' and route['producerAcceptance']['sha256']=='0452e1f3b4f2662d57e9b273428bb37ab0c5a733551a92394ca2a4e8b9b4ac08','IMMUTABLE_REAL_PRODUCER_PAIR')
    need(route['normalCatalog']['sha256']=='686c6c778f7841e6015fa401f3892b853df80e3341fbb5d02b27c682887c1c78' and digest(Path(route['normalCatalog']['path']))==route['normalCatalog']['sha256'],'IDENTICAL_SHARED_NORMAL_CATALOG')
    result=model(fact,acceptance,route,own);result['producerFactSha256']=route['producerFact']['sha256'];result['route']=route;return result

def consumer_record(admission,own,held_sha256):
    # Derived evidence only after externally admitted route plus actual own held proof.
    # Does not promote pending manager admission or producer qualification.
    hand=handshake(admission,own);route=hand['route']
    value={'schema':'sdk11-consumer-host-admission/v1','state':'ADMITTED_EXACT_SUPPORTED_HOST_CLASS','projectId':'01','producerFactSha256':hand['producerFactSha256'],'admittedFor':route['admittedFor'],'currentExecution':{'runId':own['runId'],'job':own['jobKey'],'attempt':own['runAttempt'],'instanceId':own['runnerName'],'ownCapsEvidenceSha256':held_sha256},'identityRule':IDENTITY_RULE}
    schema_value(value,shared_schema(admission)['$defs']['consumerAdmission']);return value

def observe_machine(host_class):
    need(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted', 'REAL_HOSTED_JOB_REQUIRED')
    need(host_class in HOSTS and platform.machine().lower() in {'amd64','x86_64'}, 'X64_SUPPORTED_CLASS')
    result={'hostClass':host_class,'rid':HOSTS[host_class][0],'runnerEnvironment':os.environ['RUNNER_ENVIRONMENT'],'machine':'x86_64',
            'imageOS':os.environ.get('ImageOS',''),'imageVersion':os.environ.get('ImageVersion',''),
            'runId':os.environ.get('GITHUB_RUN_ID',''),'runAttempt':os.environ.get('GITHUB_RUN_ATTEMPT',''),
            'runnerName':os.environ.get('RUNNER_NAME',''),'container':Path('/.dockerenv').exists() or bool(os.environ.get('container')),
            'wsl':'microsoft' in platform.release().lower() or bool(os.environ.get('WSL_DISTRO_NAME'))}
    if os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
            values={k:winreg.QueryValueEx(key,k)[0] for k in ['ProductName','CurrentBuildNumber','UBR','InstallationType']}
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\ProductOptions') as key:
            values['ProductType']=winreg.QueryValueEx(key,'ProductType')[0]
        result['actualOS']=values
        result['actualOSAccepted']=host_class=='GitHubHostedWindowsServer2025x64' and values['ProductType'] in {'ServerNT','LanmanNT'} and str(values['CurrentBuildNumber'])=='26100' and values['InstallationType'] in {'Server','Server Core'}
        # Actual x86-64-v2 CPUID observation is a required same-job attachment,
        # not inferred from label, Producer or a local Windows probe.
    else:
        values=dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        result['actualOS']=values;result['uid']=os.getuid();result['gid']=os.getgid()
        result['actualOSAccepted']=host_class=='GitHubHostedUbuntu24.04x64' and values.get('ID','').strip('"')=='ubuntu' and values.get('VERSION_ID','').strip('"')=='24.04' and os.getuid()>0 and os.getgid()>0
    need(not result['wsl'] and not result['container'] and result['actualOSAccepted'], 'LOCAL_OR_WRONG_OS_EXCLUDED')
    return result

def own_caps(held, own):
    need(held['jobId']==own['jobId'] and held['instanceIdentity']==own['instanceIdentity'] and held['projectId']=='01', 'OWN_KERNEL_SUBJECT')
    need(held['childHeld'] and held['membershipObservedBeforeRelease'] and held['sdkLaunchesBeforeRelease']==0, 'HELD_CHILD_REQUIRED')
    caps=held['limits'];need(caps['memoryBytes']<=2147483648 and caps['memoryBytes']>0 and 0<caps['cpuEquivalent']<=2, 'OWN_CAPS_NOT_PRODUCER_CAPS')
    if own['rid']=='win-x64':need(0<caps['processLimit']<=32 and caps['killOnClose'] and caps['suspendedBeforeAssignment'], 'WIN_JOB')
    else:need(0<caps['tasksMax']<=64 and caps['swapBytes']==0 and held['workerUid']==own['uid'] and held['workerGid']==own['gid'] and held['workerUid']>0, 'LINUX_NONROOT_CGROUP')
    return True
