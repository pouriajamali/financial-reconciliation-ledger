"""Project01-only local controller source. Requires independent manager admission.
No generic argv executor, SDK bootstrap, service repair or self-admission route.
"""
import argparse, ctypes, hashlib, json, os, platform, secrets, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = HERE / 'PROFILE.json'
CONTRACT = '142dac81ae7f6e05f52319d3521d4825d5df028e37542b7623d16316ff7dd077'
PROTOCOL = '9120ca49a0d46673053aa0ec0cdbbc6f00731d71ea0b57ddab09e8fc3ac3ac8b'
BASE = '2a5e751b585b304bd01ec304457926e3c60a8cbc'
BRANCH = 'codex/frl-net11-maintenance-20261114'
PHASES = ('probe', 'lock', 'restore', 'rid-lock', 'rid-restore', 'tests', 'package', 'extracted', 'compatibility')


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            value.update(chunk)
    return value.hexdigest()


def ordinary(path, exists=True):
    need(path.is_absolute(), 'Absolute path required')
    for parent in [path, *path.parents]:
        if parent.exists():
            need(not parent.is_symlink() and not (getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400), 'Link/reparse input')
    need(not exists or path.is_file(), 'Actual file required')
    return path


def document(path):
    ordinary(path)
    need(path.stat().st_size <= 2097152, 'Document byte bound')
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate metadata key')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def identity(binding):
    need(set(binding) == {'path', 'sha256'}, 'Actual path/hash binding required')
    path = ordinary(Path(binding['path']))
    need(digest(path) == binding['sha256'], 'Input identity differs')
    return path


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def start_id(pid):
    if os.name != 'nt':
        value = Path(f'/proc/{pid}/stat').read_text()
        return value[value.rfind(')') + 2:].split()[19]
    from ctypes import wintypes as w
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    api.OpenProcess.restype = w.HANDLE
    api.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
    api.CloseHandle.argtypes = [w.HANDLE]
    handle = api.OpenProcess(0x1000, False, pid)
    need(handle, 'Process identity unavailable')
    values = [w.FILETIME() for _ in range(4)]
    try:
        need(api.GetProcessTimes(handle, *[ctypes.byref(v) for v in values]), 'Process start unavailable')
        return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)
    finally:
        api.CloseHandle(handle)


def settings(args):
    need(sys.flags.isolated == 1 and sys.flags.optimize == 0, 'Use trusted Python -I -B, optimize0')
    profile = document(PROFILE)
    rid = 'win-x64' if os.name == 'nt' else 'linux-x64'
    local = profile['windows' if os.name == 'nt' else 'linux']
    need(platform.machine().lower() in {'amd64', 'x86_64'}, 'Actual x64 host required')
    need(digest(Path(sys.executable).resolve()) == local['python']['sha256'], 'Trusted host interpreter changed')
    if os.name == 'nt':
        need(os.cpu_count() == local['hostVisibleLogicalProcessors'], 'Host CPU allocation changed')
    else:
        need(os.getuid() == local['uid'] == 1000 and os.getgid() == local['gid'] == 1000, 'Actual native UID/GID mismatch')
    admission = document(args.admission)
    need(digest(args.admission) == args.admission_sha256, 'Manager handoff identity mismatch')
    need(admission['schema'] == 'frl01-local-admission-v1' and admission['projectId'] == '01', 'Wrong owner admission')
    need(admission['completeContractSha256'] == CONTRACT and admission['profileSha256'] == digest(PROFILE), 'Reviewed contract/profile mismatch')
    need(admission['launcherSha256'] == digest(Path(__file__).resolve()) and admission['rid'] == rid, 'Source/control identity mismatch')
    need(admission['status'] in {'CONTROL_PROBE_ONLY_ADMITTED', 'SDK_AND_PROFILE_ADMITTED'}, 'No actual manager admission')
    need(args.phase == 'probe' or admission['status'] == 'SDK_AND_PROFILE_ADMITTED', 'SDK target gate closed')
    prefix = 'E:/Codex WorkSpace/Git Projects/portfolio-management/development-management-20261110/' if os.name == 'nt' else '/mnt/e/Codex WorkSpace/Git Projects/portfolio-management/development-management-20261110/'
    protocol = Path(prefix + 'wave2-state/LEASE-PROTOCOL.json')
    need(digest(protocol) == PROTOCOL, 'Canonical protocol changed')
    need('01' in document(protocol)['participants'], 'Project01 not admitted to lane')
    local['lease'] = Path(prefix + 'wave2-state/LOCAL-FIXTURE-LEASE.json')
    checkout = Path(local['checkout'])
    ordinary(checkout, exists=False)
    read = subprocess.run(['git', '--no-optional-locks', '-C', str(checkout), 'branch', '--show-current'], capture_output=True, text=True, timeout=30)
    need(read.returncode == 0 and read.stdout.strip() == BRANCH, 'Wrong isolated worktree branch')
    ancestry = subprocess.run(['git', '--no-optional-locks', '-C', str(checkout), 'merge-base', '--is-ancestor', BASE, 'HEAD'], capture_output=True, timeout=30)
    need(ancestry.returncode == 0, 'Candidate lost admitted baseline')
    head = subprocess.run(['git', '--no-optional-locks', '-C', str(checkout), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=30)
    need(head.returncode == 0 and head.stdout.strip() == args.candidate_commit, 'Actual candidate HEAD differs')
    m0_path = Path(local['outputRoot']) / 'REVIEW-PACKET.json'
    need(digest(m0_path) == profile['m0Sha256'], 'Source allowance identity changed')
    m0 = document(m0_path)
    changed = subprocess.run(['git', '--no-optional-locks', '-C', str(checkout), 'diff', '--name-only', BASE], capture_output=True, text=True, timeout=30)
    untracked = subprocess.run(['git', '--no-optional-locks', '-C', str(checkout), 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True, timeout=30)
    need(changed.returncode == 0 and untracked.returncode == 0 and set(changed.stdout.splitlines() + untracked.stdout.splitlines()) <= set(m0['allowlist']), 'Source path allowance drift')
    for name, expected in m0['baseline']['trackedFileSha256'].items():
        if name not in m0['allowlist']:
            need(digest(checkout / name) == expected, 'Protected source/test/license changed')
    if args.phase in {'lock', 'rid-lock'}:
        need(admission.get('deliberateLockTransitionApproved') is True, 'Deliberate lock transition not admitted')
    if args.phase != 'probe':
        identity(admission['sdkReview'])
        identity(admission['sdkEntry'])
        need(0 < len(admission['criticalSdkFiles']) <= 64, 'Finite consumer-critical SDK bindings required')
        for item in admission['criticalSdkFiles']:
            identity(item)
        identity(admission['nugetConfig'])
    return profile, local, admission, rid


def lease_matches(local, token, owner_pid, owner_start, phase):
    value = document(local['lease'])
    need(value['projectId'] == '01' and value['randomToken'] == token and value['ownerPID'] == owner_pid and str(value['ownerProcessStartIdentity']) == owner_start and value['phase'] == phase, 'Lane ownership mismatch')
    need(start_id(owner_pid) == owner_start, 'Lane process start changed')
    return value


def environment(local, admission):
    root = Path(local['runtimeRoot']) / 'cache'
    folders = {name: root / name for name in ['packages', 'http', 'plugins', 'cli-home', 'temp', 'scratch']}
    for folder in folders.values():
        ordinary(folder, exists=False)
        folder.mkdir(parents=True, exist_ok=True)
    value = dict(os.environ)
    for key in ['MSBuildSDKsPath', 'MSBuildProjectExtensionsPath', 'DirectoryBuildPropsPath', 'DirectoryBuildTargetsPath', 'ImportDirectoryBuildProps', 'ImportDirectoryBuildTargets']:
        need(not value.get(key), 'Inherited MSBuild override refused')
    value.update(DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_GENERATE_ASPNET_CERTIFICATE='false', DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='true', MSBuildEnableWorkloadResolver='false', DOTNET_CLI_USE_MSBUILD_SERVER='0', MSBUILDDISABLENODEREUSE='1', DOTNET_CLI_HOME=str(folders['cli-home']), NUGET_PACKAGES=str(folders['packages']), NUGET_HTTP_CACHE_PATH=str(folders['http']), NUGET_PLUGINS_CACHE_PATH=str(folders['plugins']), NUGET_SCRATCH=str(folders['scratch']), TEMP=str(folders['temp']), TMP=str(folders['temp']), PYTHONDONTWRITEBYTECODE='1')
    value['UseSharedCompilation'] = 'false'
    if admission['status'] == 'SDK_AND_PROFILE_ADMITTED':
        sdk_root = str(Path(admission['sdkEntry']['path']).parent)
        value.update(DOTNET_ROOT=sdk_root, DOTNET_ROOT_X64=sdk_root, DOTNET_MULTILEVEL_LOOKUP='0')
    return value


def owned_phase_inputs(args, local, admission):
    need(args.phase_input and args.phase_input_sha256, 'Actual own phase artifact handoff required')
    need(args.phase_input.is_relative_to(Path(local['runtimeRoot'])), 'Artifact handoff outside project output')
    need(digest(ordinary(args.phase_input)) == args.phase_input_sha256, 'Own artifact handoff differs')
    value = document(args.phase_input)
    need(value['schema'] == 'frl01-owned-phase-input/v1' and value['projectId'] == '01' and value['candidateCommit'] == args.candidate_commit, 'Wrong own artifact subject')
    prior = document(identity(value['terminalReceipt']))
    need(prior['schema'] == 'frl01-local-phase-result/v1' and prior['projectId'] == '01' and prior['terminal'] is True and prior['status'] == 'PHASE_TERMINAL', 'Actual prior terminal phase required')
    need(prior['candidateCommit'] == args.candidate_commit and prior['launcherSha256'] == admission['launcherSha256'] and prior['admissionSha256'] == args.admission_sha256, 'Prior artifact/control source differs')
    prior_root = Path(prior['work'])
    need(prior_root.is_relative_to(Path(local['runtimeRoot'])), 'Prior phase outside own runtime root')
    release = document(prior_root / 'release.json')
    need(release['releasedAfterActualTerminalProof'] is True and release['terminalReceiptSha256'] == value['terminalReceipt']['sha256'], 'Actual prior terminal release receipt missing')
    return value


def command(args, local, admission, work):
    checkout = Path(local['checkout'])
    if args.phase == 'probe':
        return [str(Path(sys.executable).resolve()), '-I', '-B', '-c', 'raise SystemExit(0)'] if os.name == 'nt' else [str(identity({'path': local['probe']['path'], 'sha256': local['probe']['sha256']}))]
    sdk = str(identity(admission['sdkEntry']))
    rid = 'win-x64' if os.name == 'nt' else 'linux-x64'
    shared = ['--disable-parallel', '--configfile', str(identity(admission['nugetConfig'])), '--packages', str(Path(local['runtimeRoot']) / 'cache/packages'), '-p:NuGetAudit=true', '-p:NuGetAuditMode=all', '-p:NuGetAuditLevel=low']
    if args.phase in {'lock', 'restore', 'rid-lock', 'rid-restore'}:
        rid_phase = args.phase.startswith('rid-')
        source = 'src/Ledger/Ledger.csproj' if rid_phase else 'tests/Ledger.Tests'
        result = [sdk, 'restore', source, '--use-lock-file' if args.phase in {'lock', 'rid-lock'} else '--locked-mode', *shared]
        if rid_phase:
            result += ['--runtime', rid]
        return result
    if args.phase == 'tests':
        return [sdk, 'run', '--project', 'tests/Ledger.Tests', '-c', 'Release', '--no-launch-profile', '--no-restore', '--', '--work', str(work / 'tests')]
    python = str(Path(sys.executable).resolve())
    if args.phase == 'package':
        return [python, '-I', '-B', str(checkout / 'tools/package.py'), '--rid', rid, '--commit', args.candidate_commit, '--work', str(work / 'build'), '--out', str(work / 'delivery'), '--dotnet', sdk]
    # Actual extracted input/control identities come from the admitted fixed phase.
    phase_inputs = owned_phase_inputs(args, local, admission)
    package = identity(phase_inputs['packageManifest']).parent
    need(package.is_relative_to(Path(local['runtimeRoot'])), 'Package outside own output scope')
    if args.phase == 'extracted':
        return [python, '-I', '-B', str(checkout / 'tools/check_package.py'), '--package', str(package), '--work', str(work / 'package-checks'), '--commit', args.candidate_commit]
    need(args.phase == 'compatibility', 'Unknown project01 phase')
    need(admission['executionApproved'] is True, 'Actual target execution admission required')
    execution = work / 'derived-execution-binding.json'
    write_new(execution, {'projectId': '01', 'executionApproved': admission['executionApproved'], 'candidateCommit': args.candidate_commit, 'wrapperSha256': digest(Path(__file__).resolve()), 'sdkReviewSha256': admission['sdkReview']['sha256'], 'managerAdmission': {'path': str(args.admission), 'sha256': args.admission_sha256}})
    control = work / 'actual-compatibility-control.json'
    lease = lease_matches(local, args.token, args.owner_pid, args.owner_start, args.phase)
    kernel = current_caps(local)
    write_new(control, {'schema': 'frl-tech-refresh-control-v1', 'status': 'ADMITTED_FOR_BOUND_PHASE', 'projectId': '01', 'phase': 'tech-refresh-compatibility', 'candidateCommit': args.candidate_commit, 'parent': {'pid': os.getpid(), 'startIdentity': start_id(os.getpid())}, 'wrapper': {'path': str(Path(__file__).resolve()), 'sha256': digest(Path(__file__).resolve())}, 'profile': {'path': str(PROFILE), 'sha256': digest(PROFILE)}, 'executionContract': {'path': str(execution), 'sha256': digest(execution)}, 'sdkReview': admission['sdkReview'], 'helperSha256': digest(checkout / 'tools/check_tech_refresh.py'), 'work': str(work / 'compatibility'), 'kernel': kernel, 'lease': {'path': str(local['lease']), 'randomToken': lease['randomToken'], 'ownerPID': lease['ownerPID'], 'ownerProcessStartIdentity': lease['ownerProcessStartIdentity'], 'phase': lease['phase']}})
    return [python, '-I', '-B', str(checkout / 'tools/check_tech_refresh.py'), '--new-package', str(package), '--old-package', str(identity(phase_inputs['oldPackageManifest']).parent), '--old-archive', str(identity(phase_inputs['oldPublicArchive'])), '--commit', args.candidate_commit, '--work', str(work / 'compatibility'), '--control', str(control), '--control-sha256', digest(control)]


def size_budget(local, work):
    total, count = 0, 0
    checkout = Path(local['checkout'])
    roots = [Path(local['outputRoot']), *[Path(x) for x in local.get('extraOutputRoots', [])], checkout / 'artifacts', checkout / 'src/Ledger/bin', checkout / 'src/Ledger/obj', checkout / 'tests/Ledger.Tests/bin', checkout / 'tests/Ledger.Tests/obj']
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue  # Owned cache/compiler temporary rename; no external path is followed.
            need(not path.is_symlink() and not (getattr(stat, 'st_file_attributes', 0) & 0x400), 'Unexpected generated link')
            count += 1
            need(count <= 60000, 'Generated file-count bound')
            if __import__('stat').S_ISREG(stat.st_mode):
                total += stat.st_size
                need(total <= 4294967296, 'Source/output byte budget')
    logs = sum(path.stat().st_size for path in work.glob('*.log'))
    need(logs <= 33554432, 'Phase log byte budget')
    return {'observedSourceAndOutputBytes': total, 'observedEntries': count, 'observedLogBytes': logs, 'diskEnforcement': 'monitored bounded stop, not filesystem quota'}

class WindowsJob:
    def __init__(self, local, create=True):
        from ctypes import wintypes as w
        self.w = w
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [('processTime', ctypes.c_longlong), ('jobTime', ctypes.c_longlong), ('flags', w.DWORD), ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t), ('processes', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ['r', 'w', 'o', 'rb', 'wb', 'ob']]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('processMemory', ctypes.c_size_t), ('jobMemory', ctypes.c_size_t), ('peakProcess', ctypes.c_size_t), ('peakJob', ctypes.c_size_t)]
        class CPU(ctypes.Structure):
            _fields_ = [('flags', w.DWORD), ('rate', w.DWORD)]
        class Accounting(ctypes.Structure):
            _fields_ = [('u', ctypes.c_longlong), ('k', ctypes.c_longlong), ('pu', ctypes.c_longlong), ('pk', ctypes.c_longlong), ('faults', w.DWORD), ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]
        self.Extended, self.CPU, self.Accounting = Extended, CPU, Accounting
        self.cpuRateCeiling = local['cpuRatePer10000']
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.ResumeThread.argtypes = [w.HANDLE]
        self.api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        self.api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        self.api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.job = None
        if not create:
            return
        self.unassignedChildTerminal = True
        self.jobName = local.get('jobName')
        if self.jobName is not None:need(self.jobName.startswith('Local\\frl01-ci-') and len(self.jobName)<=180 and all(c.isascii() and (c.isalnum() or c in '\\._-') for c in self.jobName),'Own named job identity')
        ctypes.set_last_error(0)
        self.job = self.api.CreateJobObjectW(None, self.jobName)
        created_error = ctypes.get_last_error()
        need(self.job, 'Own job creation failed')
        if created_error == 183:
            self.api.CloseHandle(self.job);self.job=None
            raise RuntimeError('OWN_NAMED_JOB_ALREADY_EXISTS')
        limits = Extended()
        limits.basic.flags = 0x2208
        limits.basic.processes = local['activeProcessLimit']
        limits.jobMemory = local['jobMemoryBytes']
        cpu = CPU(5, local['cpuRatePer10000'])
        try:
            need(self.api.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)), 'Job limit assignment failed')
            need(self.api.SetInformationJobObject(self.job, 15, ctypes.byref(cpu), ctypes.sizeof(cpu)), 'Job CPU assignment failed')
        except Exception:
            self.api.CloseHandle(self.job)
            raise

    def readback(self, current=False):
        limits, cpu, accounting = self.Extended(), self.CPU(), self.Accounting()
        handle = None if current else self.job
        for number, value in [(9, limits), (15, cpu), (1, accounting)]:
            need(self.api.QueryInformationJobObject(handle, number, ctypes.byref(value), ctypes.sizeof(value), None), 'Actual job readback failed')
        need(limits.basic.flags & 0x2208 == 0x2208 and 0 < limits.jobMemory <= 2147483648 and 0 < limits.basic.processes <= 32, 'Actual job limits differ')
        need(cpu.flags & 5 == 5 and 0 < cpu.rate <= self.cpuRateCeiling, 'Actual job CPU differs')
        return {'jobMemoryBytes': limits.jobMemory, 'peakJobMemoryBytes': limits.peakJob, 'activeProcesses': accounting.active, 'totalProcesses': accounting.total, 'processLimit': limits.basic.processes, 'cpuRatePer10000': cpu.rate, 'killOnClose': True}

    def launch(self, argv, cwd, env=None, logs=None):
        w = self.w
        class Startup(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR), ('title', w.LPWSTR), ('x', w.DWORD), ('y', w.DWORD), ('xs', w.DWORD), ('ys', w.DWORD), ('xc', w.DWORD), ('yc', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD), ('show', w.WORD), ('reserved2', w.WORD), ('reservedBytes', ctypes.POINTER(ctypes.c_byte)), ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]
        class StartupEx(ctypes.Structure):_fields_=[('startup',Startup),('attributes',ctypes.c_void_p)]
        class Process(ctypes.Structure):_fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]
        class Security(ctypes.Structure):_fields_=[('length',w.DWORD),('descriptor',ctypes.c_void_p),('inherit',w.BOOL)]
        self.api.CreateProcessW.argtypes=[w.LPCWSTR,w.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,w.BOOL,w.DWORD,ctypes.c_void_p,w.LPCWSTR,ctypes.c_void_p,ctypes.POINTER(Process)]
        self.api.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
        self.api.GetActiveProcessorCount.argtypes=[w.WORD];self.api.GetActiveProcessorCount.restype=w.DWORD
        handles=[];attribute_buffer=None;attributes_initialized=False;info=Process();startup=StartupEx();startup.startup.cb=ctypes.sizeof(StartupEx);flags=0x08000004
        try:
            if logs is not None:
                self.api.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.POINTER(Security),w.DWORD,w.DWORD,w.HANDLE];self.api.CreateFileW.restype=w.HANDLE
                self.api.InitializeProcThreadAttributeList.argtypes=[ctypes.c_void_p,w.DWORD,w.DWORD,ctypes.POINTER(ctypes.c_size_t)]
                self.api.UpdateProcThreadAttribute.argtypes=[ctypes.c_void_p,w.DWORD,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_void_p]
                self.api.DeleteProcThreadAttributeList.argtypes=[ctypes.c_void_p]
                sec=Security(ctypes.sizeof(Security),None,True)
                for path,access,creation in [('NUL',0x80000000,3),(str(logs/'worker.stdout'),0x40000000,1),(str(logs/'worker.stderr'),0x40000000,1)]:
                    handle=self.api.CreateFileW(path,access,3,ctypes.byref(sec),creation,0x80,None);need(handle not in (None,ctypes.c_void_p(-1).value),'OWN_WORKER_LOG_HANDLE');handles.append(handle)
                startup.startup.flags=0x100;startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=handles
                size=ctypes.c_size_t();self.api.InitializeProcThreadAttributeList(None,1,0,ctypes.byref(size));need(0<size.value<=65536,'OWN_HANDLE_ATTRIBUTE_BOUND');attribute_buffer=ctypes.create_string_buffer(size.value);startup.attributes=ctypes.cast(attribute_buffer,ctypes.c_void_p)
                need(self.api.InitializeProcThreadAttributeList(startup.attributes,1,0,ctypes.byref(size)),'OWN_HANDLE_ATTRIBUTE_INIT');attributes_initialized=True
                inherited=(w.HANDLE*3)(*handles);need(self.api.UpdateProcThreadAttribute(startup.attributes,0,0x20002,ctypes.byref(inherited),ctypes.sizeof(inherited),None,None),'OWN_FIXED_HANDLE_LIST');flags|=0x00080000
            else:startup.startup.cb=ctypes.sizeof(Startup)
            environment=None
            if env is not None:
                need(all(type(k) is str and type(v) is str and '=' not in k and '\0' not in k+v for k,v in env.items()),'OWN_WORKER_ENVIRONMENT')
                environment=ctypes.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items(),key=lambda x:x[0].upper()))+'\0\0');flags|=0x400
            line=ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
            need(self.api.CreateProcessW(argv[0],line,None,None,bool(handles),flags,environment,str(cwd),ctypes.byref(startup),ctypes.byref(info)),'Suspended owned child creation failed')
            self.unassignedChildTerminal=False
            try:
                need(self.api.AssignProcessToJobObject(self.job,info.process),'Suspended child job membership failed');readback=self.readback();need(readback['activeProcesses']==1,'Suspended child not sole job member')
                times=[w.FILETIME() for _ in range(4)];need(self.api.GetProcessTimes(info.process,*[ctypes.byref(v) for v in times]),'OWN_RETAINED_START_IDENTITY')
                self.beforeResume={'pid':int(info.pid),'processStartIdentity':'FILETIME:'+str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime),'jobName':self.jobName,'memoryMaxBytes':readback['jobMemoryBytes'],'tasksMax':readback['processLimit'],'cpuRate':readback['cpuRatePer10000'],'logicalHostCpu':int(self.api.GetActiveProcessorCount(0xffff)),'state':'SUSPENDED','membershipBeforeRelease':True,'retainedStartHandle':True}
                need(self.api.ResumeThread(info.thread)!=0xffffffff,'Owned child resume failed')
            except BaseException:
                killed=self.api.TerminateProcess(info.process,1);self.unassignedChildTerminal=bool(killed and self.api.WaitForSingleObject(info.process,5000)==0);self.api.CloseHandle(info.process);raise
            finally:self.api.CloseHandle(info.thread)
            self.unassignedChildTerminal=True;self.process,self.pid=info.process,info.pid
            return readback
        finally:
            if attributes_initialized:self.api.DeleteProcThreadAttributeList(startup.attributes)
            for handle in handles:self.api.CloseHandle(handle)

    def exited(self):
        return self.api.WaitForSingleObject(self.process, 0) == 0

    def terminate(self):
        need(self.api.TerminateJobObject(self.job, 1), 'Own job termination failed')
        if hasattr(self,'process'):self.api.WaitForSingleObject(self.process, 5000)

    def exit_code(self):
        result = self.w.DWORD()
        need(self.api.GetExitCodeProcess(self.process, ctypes.byref(result)), 'Actual process exit unavailable')
        return result.value

    def close(self):
        if hasattr(self, 'process'):
            self.api.CloseHandle(self.process)
        if self.job:
            self.api.CloseHandle(self.job)


def linux_caps():
    rows = Path('/proc/self/cgroup').read_text().splitlines()
    found = [line[3:] for line in rows if line.startswith('0::')]
    need(len(found) == 1 and found[0] != '/', 'Owned cgroup-v2 membership required')
    root = Path('/sys/fs/cgroup').resolve()
    group = (root / found[0].lstrip('/')).resolve()
    need(group.is_relative_to(root), 'Unexpected cgroup path')
    cpu = (group / 'cpu.max').read_text().split()
    memory = (group / 'memory.max').read_text().strip()
    swap = (group / 'memory.swap.max').read_text().strip()
    tasks = (group / 'pids.max').read_text().strip()
    need(cpu[0] != 'max' and 0 < int(cpu[0]) <= 2 * int(cpu[1]), 'CPU cap not observed')
    need(memory != 'max' and 0 < int(memory) <= 2147483648 and swap == '0', 'Memory/swap cap not observed')
    need(tasks != 'max' and 0 < int(tasks) <= 64, 'Task cap not observed')
    need(str(os.getpid()) in (group / 'cgroup.procs').read_text().split(), 'Controller outside actual cgroup')
    return {'cgroup': str(group), 'cpu.max': cpu, 'memory.max': memory, 'memory.swap.max': swap, 'pids.max': tasks}


def current_caps(local):
    if os.name != 'nt':
        return linux_caps()
    instance = WindowsJob(local, create=False)
    return instance.readback(current=True)


def inside(args, profile, local, admission, rid):
    work = Path(local['runtimeRoot']) / (args.phase + '-' + args.token)
    need(work.is_dir() and work.parent == Path(local['runtimeRoot']), 'Exact fresh phase work root required')
    lease_matches(local, args.token, args.owner_pid, args.owner_start, args.phase)
    caps = current_caps(local)
    write_new(work / 'kernel-before.json', caps)
    argv = command(args, local, admission, work)
    started = time.monotonic()
    stdout, stderr = work / 'target.stdout.log', work / 'target.stderr.log'
    code = None
    try:
        with stdout.open('xb') as out, stderr.open('xb') as err:
            child = subprocess.Popen(argv, cwd=local['checkout'], env=environment(local, admission), stdin=subprocess.DEVNULL, stdout=out, stderr=err)
            try:
                while child.poll() is None:
                    lease_matches(local, args.token, args.owner_pid, args.owner_start, args.phase)
                    need(time.monotonic() - started < args.seconds, 'Bound phase deadline')
                    size_budget(local, work)
                    time.sleep(0.25)
                code = child.wait(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
        budget = size_budget(local, work)
        missing = any(tag in stdout.read_bytes() or tag in stderr.read_bytes() for tag in [b'NU1900', b'NU1905'])
        write_new(work / 'inside-result.json', {'schema': 'frl01-inside-result/v1', 'status': 'EXITED' if code == 0 and not missing else 'INCOMPLETE', 'projectId': '01', 'rid': rid, 'phase': args.phase, 'ownerPID': args.owner_pid, 'controllerPID': os.getpid(), 'controllerStart': start_id(os.getpid()), 'candidateCommit': args.candidate_commit, 'argv': argv, 'targetExitCode': code, 'missingAuditInformation': missing, 'kernel': caps, 'budget': budget, 'stdoutSha256': digest(stdout), 'stderrSha256': digest(stderr), 'parentTerminalProofPending': True})
        return 0 if code == 0 and not missing else 1
    except Exception as error:
        if not (work / 'inside-result.json').exists():
            write_new(work / 'inside-result.json', {'schema': 'frl01-inside-result/v1', 'status': 'INCOMPLETE', 'error': str(error), 'projectId': '01', 'phase': args.phase, 'kernel': caps, 'parentTerminalProofPending': True})
        return 1

def linux_systemctl_readonly(env, argv, timeout, boot_id):
    need(argv[:2] == ['/usr/bin/systemctl', '--user'] and argv[2] in {'is-system-running', 'show'}, 'Read-only existing-manager query only')
    result = {'argv': argv, 'bootId': boot_id, 'timeoutSeconds': timeout,
              'atUtc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
              'completion': 'COMPLETE', 'returnCode': None}
    stdout, stderr = b'', b''
    try:
        child = subprocess.run(argv, env=env, capture_output=True, timeout=timeout)
        result['returnCode'] = child.returncode
        stdout, stderr = child.stdout or b'', child.stderr or b''
    except subprocess.TimeoutExpired as error:
        result['completion'] = 'TIMEOUT'
        stdout, stderr = error.stdout or b'', error.stderr or b''
        # Trusted subprocess.run kills and reaps its own timed-out read-only child.
    except OSError as error:
        result['completion'] = 'OS_ERROR'
        result['error'] = (type(error).__name__ + ': ' + str(error))[:256]
    for name, raw in [('stdout', stdout), ('stderr', stderr)]:
        result[name] = raw[:2048].decode('utf-8', errors='backslashreplace')
        result[name + 'Bytes'] = len(raw)
        result[name + 'RawSha256'] = hashlib.sha256(raw).hexdigest()
        result[name + 'Truncated'] = len(raw) > 2048
    result['outputLimitExceeded'] = result['stdoutTruncated'] or result['stderrTruncated']
    return result


def linux_wait_existing_user_manager(env, work, phase_started, phase_seconds):
    began = time.monotonic()
    phase_deadline = phase_started + phase_seconds
    # At most10s, inside the original envelope; preserve8s for bounded stop/readback.
    deadline = min(began + 10.0, phase_deadline - 8.0)
    record = {'schema': 'frl01-existing-user-readiness/v1', 'uid': os.getuid(),
              'ready': False, 'bootId': None, 'attempts': [], 'stopReason': 'DEADLINE_OR_ATTEMPT_BOUND',
              'maxReadinessSeconds': 10, 'phaseEnvelopeSeconds': phase_seconds,
              'phaseElapsedBeforeReadiness': began - phase_started,
              'changes': 'NONE: existing sockets/state only; no install/start/restart/linger/fallback'}
    try:
        need(record['uid'] == 1000, 'Existing UID1000 manager required')
        with Path('/proc/sys/kernel/random/boot_id').open('rb') as stream:
            raw = stream.read(129)
        boot_id = raw.decode('ascii').strip()
        need(len(raw) <= 128 and str(__import__('uuid').UUID(boot_id)) == boot_id, 'Actual boot identity unavailable')
        record['bootId'] = boot_id
        runtime = Path('/run/user/1000')
        while time.monotonic() < deadline and len(record['attempts']) < 40:
            attempt = {'elapsedSeconds': time.monotonic() - began, 'sockets': {}, 'systemctlExecuted': False}
            for name, path in [('bus', runtime / 'bus'), ('private', runtime / 'systemd/private')]:
                try:
                    status = path.lstat()
                    attempt['sockets'][name] = {'exists': True, 'isSocket': __import__('stat').S_ISSOCK(status.st_mode)}
                except FileNotFoundError:
                    attempt['sockets'][name] = {'exists': False, 'isSocket': False}
                except OSError as error:
                    attempt['sockets'][name] = {'exists': None, 'isSocket': False, 'error': (type(error).__name__ + ': ' + str(error))[:256]}
            remaining = deadline - time.monotonic() - 0.15
            if all(value['isSocket'] for value in attempt['sockets'].values()) and remaining > 0.05:
                attempt['systemctlExecuted'] = True
                actual = linux_systemctl_readonly(env, ['/usr/bin/systemctl', '--user', 'is-system-running'], min(1.0, remaining), boot_id)
                attempt['systemctl'] = actual
                record['attempts'].append(attempt)
                if actual['outputLimitExceeded']:
                    record['stopReason'] = 'READONLY_OUTPUT_LIMIT'
                    break
                if actual['completion'] == 'COMPLETE' and actual['stdout'].strip() in {'running', 'degraded'}:
                    record['ready'] = True
                    record['stopReason'] = 'EXISTING_MANAGER_READY'
                    break
            else:
                attempt['skipReason'] = 'EXISTING_SOCKET_OR_REMAINING_BUDGET_UNAVAILABLE'
                record['attempts'].append(attempt)
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        record['stopReason'] = 'READONLY_IDENTITY_OR_STATE_ERROR'
        record['error'] = (type(error).__name__ + ': ' + str(error))[:256]
    record['elapsedSeconds'] = time.monotonic() - began
    record['phaseElapsedAtReadinessEnd'] = time.monotonic() - phase_started
    if time.monotonic() > deadline:
        record['ready'] = False
        record['stopReason'] = 'READINESS_BUDGET_EXPIRED'
    need(len(json.dumps(record).encode('utf-8')) <= 2097152, 'Readiness evidence byte bound')
    write_new(work / 'existing-user-readiness.json', record)
    return record


def top(args, profile, local, admission, rid):
    runtime = Path(local['runtimeRoot'])
    ordinary(runtime, exists=False)
    runtime.mkdir(parents=True, exist_ok=True)
    ledger = HERE / 'phase-ledger.jsonl'
    records = []
    if ledger.exists():
        need(ledger.stat().st_size <= 2097152, 'Own ledger bound')
        records = [json.loads(line) for line in ledger.read_text().splitlines()]
    need(len(records) < 128, 'Finite phase allocation exhausted')
    used = sum(row['elapsedSeconds'] for row in records)
    own = sum(row['elapsedSeconds'] for row in records if row['rid'] == rid)
    seconds = int(min(profile['phases'][args.phase], 2400 - own, 4800 - used))
    need(seconds >= 10, 'Remaining approved wall allocation exhausted')
    token, owner_pid = secrets.token_hex(16), os.getpid()
    owner_start = start_id(owner_pid)
    work = runtime / (args.phase + '-' + token)
    need(not work.exists(), 'Fresh phase destination required')
    work.mkdir()
    holder = {'projectId': '01', 'randomToken': token, 'ownerOS': platform.system(), 'ownerPID': owner_pid, 'ownerProcessStartIdentity': owner_start, 'phase': args.phase, 'startedAtUtc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), 'receiptDirectory': str(work)}
    try:
        write_new(local['lease'], holder)
    except FileExistsError:
        write_new(work / 'busy.json', {'status': 'HOLD_BUSY', 'canonicalLeaseUntouched': True})
        return 3
    started = time.monotonic()
    terminal, code, info, failure = False, None, {}, None
    job = client = None
    try:
        argv = [str(Path(sys.executable).resolve()), '-I', '-B', str(Path(__file__).resolve()), '--inside', '--phase', args.phase, '--admission', str(args.admission), '--admission-sha256', args.admission_sha256, '--candidate-commit', args.candidate_commit, '--token', token, '--owner-pid', str(owner_pid), '--owner-start', owner_start, '--seconds', str(max(1, seconds - 5))]
        if args.phase_input:
            argv += ['--phase-input', str(args.phase_input), '--phase-input-sha256', args.phase_input_sha256]
        write_new(work / 'launch-plan.json', {'projectId': '01', 'rid': rid, 'phase': args.phase, 'controllerArgv': argv, 'admissionSha256': args.admission_sha256, 'launcherSha256': digest(Path(__file__).resolve()), 'profileSha256': digest(PROFILE), 'candidateCommit': args.candidate_commit, 'actualAllocationSeconds': seconds, 'holder': holder})
        if os.name == 'nt':
            job = WindowsJob(local)
            info['suspendedJobMembership'] = job.launch(argv, Path(local['checkout']))
            while not job.exited():
                need(time.monotonic() - started < seconds, 'Controller deadline')
                size_budget(local, work)
                time.sleep(0.25)
            code = job.exit_code()
            info['terminalJob'] = job.readback()
            terminal = info['terminalJob']['activeProcesses'] == 0
        else:
            unit = 'frl01-' + args.phase + '-' + token[:16]
            env = dict(os.environ, XDG_RUNTIME_DIR='/run/user/1000', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
            remaining = lambda reserve=0.0: max(0.0, seconds - (time.monotonic() - started) - reserve)
            readiness = linux_wait_existing_user_manager(env, work, started, seconds)
            info['readiness'] = {'path': str(work / 'existing-user-readiness.json'), 'sha256': digest(work / 'existing-user-readiness.json'), 'ready': readiness['ready']}
            need(readiness['ready'], 'Same-invocation user bus unready; bounded evidence retained')
            need(remaining(8.0) > 0.05, 'Original phase budget exhausted before unit query')
            previous = linux_systemctl_readonly(env, ['/usr/bin/systemctl', '--user', 'show', unit, '--property=LoadState', '--value'], min(2.0, remaining(8.0)), readiness['bootId'])
            write_new(work / 'unit-load-state-query.json', previous)
            need(previous['completion'] == 'COMPLETE' and not previous['outputLimitExceeded'] and previous['stdout'].strip() in {'', 'not-found'}, 'Transient unit name exists or readback incomplete')
            runtime_seconds = min(max(1, seconds - 10), int(remaining(7.0)))
            need(runtime_seconds >= 1, 'Original phase budget exhausted before unit launch')
            linux_argv = list(argv)
            linux_argv[linux_argv.index('--seconds') + 1] = str(min(max(1, seconds - 5), runtime_seconds))
            cmd = ['/usr/bin/systemd-run', '--user', '--unit=' + unit, '--wait', '--pipe', '--collect', '--quiet', '--property=Type=exec', '--property=KillMode=control-group', '--property=SendSIGKILL=yes', '--property=CPUQuota=200%', '--property=MemoryMax=2147483648', '--property=MemorySwapMax=0', '--property=TasksMax=64', '--property=RuntimeMaxSec=' + str(runtime_seconds), '--property=TimeoutStopSec=5', '--working-directory=' + local['checkout'], *linux_argv]
            with (work / 'unit.stdout.log').open('xb') as out, (work / 'unit.stderr.log').open('xb') as err:
                client = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
                while client.poll() is None:
                    need(time.monotonic() - started < seconds, 'Controller deadline')
                    size_budget(local, work)
                    time.sleep(0.25)
                code = client.wait(timeout=5)
            inside_file = work / 'inside-result.json'
            kernel_file = work / 'kernel-before.json'
            need(kernel_file.is_file(), 'No actual owned kernel membership receipt')
            kernel_observed = document(kernel_file)
            group = Path(kernel_observed['cgroup'])
            need(group.is_relative_to(Path('/sys/fs/cgroup')) and unit in str(group), 'Owned unit/cgroup subject mismatch')
            procs = (group / 'cgroup.procs').read_text().split() if group.exists() else []
            need(remaining() > 0.05, 'Original phase budget exhausted before terminal state query')
            state = linux_systemctl_readonly(env, ['/usr/bin/systemctl', '--user', 'show', unit, '--property=ActiveState', '--property=SubState', '--property=LoadState'], min(2.0, remaining()), readiness['bootId'])
            write_new(work / 'unit-terminal-state-query.json', state)
            terminal = not procs and state['completion'] == 'COMPLETE' and not state['outputLimitExceeded'] and ('ActiveState=inactive' in state['stdout'] or 'ActiveState=failed' in state['stdout'] or 'LoadState=not-found' in state['stdout'])
            info['terminalUnit'] = {'unit': unit, 'cgroup': str(group), 'remainingProcesses': procs, 'readback': state['stdout'], 'systemctlResult': state, 'clientExit': code}
        inner = document(work / 'inside-result.json')
        need(terminal, 'Owned descendants not proven terminal')
        need(inner['status'] == 'EXITED' and code == 0, 'Phase incomplete or failed; retain real evidence')
    except Exception as error:
        failure = str(error)
        if job is not None:
            try:
                if hasattr(job, 'process'):
                    job.terminate()
                info['terminalJob'] = job.readback()
                terminal = info['terminalJob']['activeProcesses'] == 0 and job.unassignedChildTerminal
            except Exception:
                terminal = False
        if job is None and client is None:
            terminal = True
            info['noTargetCreated'] = True
        # Linux RuntimeMaxSec/KillMode bounds the exact owned unit. Unknown membership is HOLD;
        # no host-wide kill, service repair, guessed stale reset or competing lease.
    finally:
        elapsed = time.monotonic() - started
        result = {'schema': 'frl01-local-phase-result/v1', 'projectId': '01', 'rid': rid, 'phase': args.phase, 'status': 'PHASE_TERMINAL' if failure is None and terminal else 'HOLD_INCOMPLETE', 'candidateCommit': args.candidate_commit, 'launcherSha256': digest(Path(__file__).resolve()), 'profileSha256': digest(PROFILE), 'admissionSha256': args.admission_sha256, 'elapsedSeconds': elapsed, 'exitCode': code, 'terminal': terminal, 'kernelTerminalReadback': info, 'failure': failure, 'work': str(work), 'leaseReleasePendingAtReceipt': True}
        write_new(work / 'terminal-result.json', result)
        with ledger.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps({'rid': rid, 'phase': args.phase, 'elapsedSeconds': elapsed, 'terminalReceipt': str(work / 'terminal-result.json'), 'sha256': digest(work / 'terminal-result.json')}) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        if terminal:
            lease_matches(local, token, owner_pid, owner_start, args.phase)
            local['lease'].unlink()  # Exact own token/start identity, after durable terminal proof only.
            write_new(work / 'release.json', {'projectId': '01', 'randomToken': token, 'ownerPID': owner_pid, 'ownerProcessStartIdentity': owner_start, 'releasedAfterActualTerminalProof': True, 'terminalReceiptSha256': digest(work / 'terminal-result.json')})
        if job is not None:
            job.close()
    print(json.dumps({'status': result['status'], 'terminal': terminal, 'leaseReleased': terminal, 'receipt': str(work / 'terminal-result.json'), 'sha256': digest(work / 'terminal-result.json')}))
    return 0 if result['status'] == 'PHASE_TERMINAL' else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--admission-sha256', required=True)
    parser.add_argument('--candidate-commit', required=True)
    parser.add_argument('--phase-input', type=Path)
    parser.add_argument('--phase-input-sha256')
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--token')
    parser.add_argument('--owner-pid', type=int)
    parser.add_argument('--owner-start')
    parser.add_argument('--seconds', type=int)
    args = parser.parse_args()
    need(args.phase == 'probe', 'LOCAL_SDK_ROUTES_EXCLUDED_UNQUALIFIED_OR_SUPPORT_UNKNOWN')
    profile, local, admission, rid = settings(args)
    if args.inside:
        need(args.token and len(args.token) == 32 and args.owner_pid and args.owner_start and args.seconds and 0 < args.seconds <= profile['phases'][args.phase], 'Bound inner invocation required')
        return inside(args, profile, local, admission, rid)
    need(not any([args.token, args.owner_pid, args.owner_start, args.seconds]), 'Caller cannot set ownership/deadline')
    return top(args, profile, local, admission, rid)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'HOLD', 'reason': str(error) if isinstance(error, RuntimeError) else type(error).__name__}), file=sys.stderr)
        raise SystemExit(3)
