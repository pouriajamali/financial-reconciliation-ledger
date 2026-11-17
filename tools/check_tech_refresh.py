"""Bounded synthetic old/new comparison. Requires a separately admitted control phase.

Source preparation is not execution approval. No SDK acquisition, extraction,
wrapper bootstrap, control receipt generation or generic sandbox claim lives here.
The future reviewed allocation must bind the exact control/interface before use.
"""
import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import zipfile
import tarfile
from pathlib import Path, PurePosixPath

OLD_COMMIT = '68aaecf26e9cd87190445f936c6df660d67e6bc5'
OLD_ARCHIVES = {
    'win-x64': 'dc5948c50f21be0f660766df1206ad6d394e120831fece8de0e46b174ac41b4e',
    'linux-x64': '636ee6fb634a685fbfe7e625768acfb73a88393676d91f49e4efd42b55ddc71b',
}
VERSIONS = {'old': '0.1.0-preview.2', 'new': '0.1.0-preview.3'}
DETAIL_FIELDS = ['schema', 'summarySha256', 'bookId', 'statementSha256',
                 'snapshotReceiptListSha256', 'throughSequence', 'issues']
ISSUE_FIELDS = ['code', 'requestId', 'statementRowIndex', 'entrySequence',
                'expectedAmountMinor', 'actualAmountMinor', 'firstStatementRowIndex']
SEVEN = [
    ('WRONG_AMOUNT', 'DEMO_A', 1, 1, 123456789012, 123456789011, None),
    ('UNEXPECTED_REQUEST_ID', 'X', 2, None, None, 1, None),
    ('DUPLICATE_REQUEST_ID', 'X', 3, None, None, 2, 2),
    ('UNEXPECTED_REQUEST_ID', 'X', 3, None, None, 2, None),
    ('DUPLICATE_REQUEST_ID', 'DEMO_A', 4, 1, 123456789012, 123456789010, 1),
    ('WRONG_AMOUNT', 'DEMO_A', 4, 1, 123456789012, 123456789010, None),
    ('MISSING_REQUEST_ID', 'DEMO_B', None, 2, 1000, None, None),
]

def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate metadata key')
        result[key] = value
    return result


def decode(raw):
    require(len(raw) <= 2 * 1024 * 1024 and not raw.startswith(b'\xef\xbb\xbf'), 'JSON framing/cap')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(RuntimeError('Non-finite JSON')))


def regular(path):
    require(path.is_absolute(), 'Absolute paths required')
    for ancestor in [path, *path.parents]:
        if ancestor.exists():
            require(not ancestor.is_symlink() and not (getattr(ancestor.lstat(), 'st_file_attributes', 0) & 0x400), 'Link/reparse path')
    require(path.is_file(), 'Regular file required')
    return path


def read_json(path):
    regular(path)
    require(path.stat().st_size <= 2 * 1024 * 1024, 'Metadata cap')
    return decode(path.read_bytes())


def binding(value):
    require(set(value) == {'path', 'sha256'}, 'Exact identity binding required')
    path = regular(Path(value['path']))
    require(path.stat().st_size <= 2 * 1024 * 1024, 'Control binding byte cap')
    require(re.fullmatch('[0-9a-f]{64}', value['sha256']) and sha(path) == value['sha256'], 'Binding hash mismatch')
    return path


def parent_start(pid):
    if os.name != 'nt':
        text = Path(f'/proc/{pid}/stat').read_text()
        return text[text.rfind(')') + 2:].split()[19]
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    require(handle, 'Parent process handle unavailable')
    values = [w.FILETIME() for _ in range(4)]
    try:
        require(kernel.GetProcessTimes(handle, *[ctypes.byref(v) for v in values]), 'Parent start unavailable')
        return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def kernel_caps(control):
    if os.name != 'nt':
        rows = Path('/proc/self/cgroup').read_text().splitlines()
        relative = [r[3:] for r in rows if r.startswith('0::')]
        require(len(relative) == 1 and relative[0] != '/', 'Owned cgroup-v2 required')
        root = Path('/sys/fs/cgroup').resolve()
        group = (root / relative[0].lstrip('/')).resolve()
        require(group.is_relative_to(root) and str(group) == control['kernel']['cgroup'], 'Actual cgroup mismatch')
        quota, period = (group / 'cpu.max').read_text().split()
        memory = (group / 'memory.max').read_text().strip()
        tasks = (group / 'pids.max').read_text().strip()
        require(quota != 'max' and 0 < int(quota) <= 2 * int(period), 'CPU hard cap missing')
        require(memory != 'max' and 0 < int(memory) <= 2147483648, 'Memory hard cap missing')
        require(tasks != 'max' and 0 < int(tasks) <= 64, 'Tasks hard cap missing')
        require(str(os.getpid()) in (group / 'cgroup.procs').read_text().split(), 'Consumer outside owned cgroup')
        return {'cgroup': str(group), 'cpu.max': [quota, period], 'memory.max': memory, 'pids.max': tasks}
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('processTime', ctypes.c_longlong), ('jobTime', ctypes.c_longlong),
                    ('flags', w.DWORD), ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t),
                    ('processes', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ['readOps', 'writeOps', 'otherOps', 'readBytes', 'writeBytes', 'otherBytes']]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('processMemory', ctypes.c_size_t),
                    ('jobMemory', ctypes.c_size_t), ('peakProcess', ctypes.c_size_t), ('peakJob', ctypes.c_size_t)]
    class CPU(ctypes.Structure):
        _fields_ = [('flags', w.DWORD), ('rate', w.DWORD)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    limit, cpu = Extended(), CPU()
    require(kernel.QueryInformationJobObject(None, 9, ctypes.byref(limit), ctypes.sizeof(limit), None), 'Job limits unavailable')
    require(kernel.QueryInformationJobObject(None, 15, ctypes.byref(cpu), ctypes.sizeof(cpu), None), 'Job CPU unavailable')
    require(limit.basic.flags & 0x2208 == 0x2208, 'Hard memory/process/kill-on-close flags missing')
    require(0 < limit.jobMemory <= 2147483648 and 0 < limit.basic.processes <= 32, 'Job limit exceeds allocation')
    count = os.cpu_count()
    require(count and cpu.flags & 5 == 5 and 0 < cpu.rate <= min(10000, 20000 // count), 'Job CPU exceeds two equivalents')
    return {'jobMemory': limit.jobMemory, 'activeProcesses': limit.basic.processes, 'cpuRate': cpu.rate, 'logicalCPUs': count}


def admitted_control(args):
    require(re.fullmatch('[0-9a-f]{40}', args.commit), 'Exact candidate commit required')
    regular(args.control)
    require(args.control.stat().st_size <= 2 * 1024 * 1024, 'Control byte cap')
    require(re.fullmatch('[0-9a-f]{64}', args.control_sha256) and sha(args.control) == args.control_sha256, 'Control identity mismatch')
    value = read_json(args.control)
    if value.get('schema') == 'frl01-local-delivery-compatibility/v1':
        # Human-authorized local execution has its own identity. Never invent CI
        # admission, hosted runner variables, or a producer's kernel evidence.
        require(value['projectId'] == '01' and value['candidateCommit'] == args.commit, 'Local compatibility subject')
        require(value['helperSha256'] == sha(Path(__file__).resolve()), 'Local helper identity')
        require(value['parent']['pid'] == os.getppid() and value['parent']['startIdentity'] == parent_start(os.getppid()), 'Local parent identity')
        binding(value['wrapper'])
        require(value['work'] == str(args.work) and not args.work.exists(), 'Fresh local compatibility work')
        require(0 < value['deadlineMonotonic'] - time.monotonic() <= 90, 'Local original compatibility deadline')
        lease_guard(value)
        return value, kernel_caps(value)
    if value.get('schema') == 'frl01-ci-compatibility-control/v1':
        import importlib.util
        path=Path(__file__).resolve().parent/'ci/ci_host_guard.py'
        require(sha(path)==value['guardSha256'],'CI guard source identity')
        spec=importlib.util.spec_from_file_location('frl01_ci_guard',path);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
        manager=read_json(binding(value['managerAdmission']));own=read_json(binding(value['ownContext']))
        guard.handshake(manager,own);held=read_json(binding(value['ownHeldProof']));guard.own_caps(held,own)
        require(value['candidateCommit']==args.commit and own['sourceCommit']==args.commit,'CI compatibility subject')
        require(value['helperSha256']==sha(Path(__file__).resolve()),'CI compatibility helper bytes')
        require(value['parent']['pid']==os.getppid() and value['parent']['startIdentity']==parent_start(os.getppid()),'CI owned parent identity')
        require(value['work']==str(args.work) and not args.work.exists(),'Fresh CI compatibility work')
        ci_scope_guard(value,own)
        return value,kernel_caps(value)
    require(False,'LOCAL_COMPATIBILITY_SDK_TARGETS_EXCLUDED')
    require(value['schema'] == 'frl-tech-refresh-control-v1' and value['status'] == 'ADMITTED_FOR_BOUND_PHASE', 'Control not admitted')
    require(value['projectId'] == '01' and value['phase'] == 'tech-refresh-compatibility' and value['candidateCommit'] == args.commit, 'Wrong control subject')
    require(value['parent']['pid'] == os.getppid() and value['parent']['startIdentity'] == parent_start(os.getppid()), 'Wrong parent process identity')
    binding(value['wrapper'])
    execution = read_json(binding(value['executionContract']))
    require(execution['projectId'] == '01' and execution['executionApproved'] is True and execution['candidateCommit'] == args.commit, 'Execution contract not admitted')
    require(execution['wrapperSha256'] == value['wrapper']['sha256'] and execution['sdkReviewSha256'] == value['sdkReview']['sha256'], 'Control review bindings differ')
    manager = read_json(binding(execution['managerAdmission']))
    require(manager['schema'] == 'frl01-local-admission-v1' and manager['projectId'] == '01' and manager['status'] == 'SDK_AND_PROFILE_ADMITTED' and manager['executionApproved'] is True, 'Actual manager input/profile admission missing')
    require(manager['completeContractSha256'] == '142dac81ae7f6e05f52319d3521d4825d5df028e37542b7623d16316ff7dd077' and manager['launcherSha256'] == value['wrapper']['sha256'], 'Wrong approved source/control contract')
    binding(value['profile'])
    require(manager['profileSha256'] == value['profile']['sha256'] and manager['sdkReview']['sha256'] == value['sdkReview']['sha256'], 'Manager profile/SDK binding mismatch')
    binding(value['sdkReview'])
    require(value['helperSha256'] == sha(Path(__file__).resolve()), 'Wrong consumer helper bytes')
    require(Path(value['work']).is_absolute() and Path(value['work']) == args.work and not args.work.exists(), 'Fresh exact control-owned work required')
    lease_guard(value)
    caps = kernel_caps(value)
    return value, caps


def ci_scope_guard(control,own):
    scope=read_json(binding(control['ciOwnership']))
    require(scope['schema']=='frl01-ci-job-ownership/v1' and scope['projectId']=='01','CI job ownership')
    require(scope['jobId']==own['jobId'] and scope['instanceIdentity']==own['instanceIdentity'],'Own current job, not producer job')
    require(scope['ownerStart']==parent_start(scope['ownerPID']),'Actual CI outer controller start')


def lease_guard(control):
    if control.get('schema')=='frl01-ci-compatibility-control/v1':
        own=read_json(binding(control['ownContext']));ci_scope_guard(control,own);return
    address = ('E:/Codex WorkSpace/Git Projects/portfolio-management/development-management-20261110/wave2-state/LOCAL-FIXTURE-LEASE.json'
               if os.name == 'nt' else '/mnt/e/Codex WorkSpace/Git Projects/portfolio-management/development-management-20261110/wave2-state/LOCAL-FIXTURE-LEASE.json')
    require(Path(control['lease']['path']) == Path(address), 'Canonical lane address required')
    lease = read_json(Path(address))
    require(lease['projectId'] == '01' and lease['randomToken'] == control['lease']['randomToken'], 'Lease ownership/token mismatch')
    owner = control['lease']['ownerPID']
    owner_start = str(control['lease']['ownerProcessStartIdentity'])
    require(lease['ownerPID'] == owner and str(lease['ownerProcessStartIdentity']) == owner_start and parent_start(owner) == owner_start, 'Outer lease controller process identity mismatch')
    require(lease['ownerOS'] == platform.system() and lease['phase'] == control['lease']['phase'] == 'compatibility', 'Lease phase/OS mismatch')


def payload_name(value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.parts and all(p not in {'.', '..'} for p in path.parts), 'Payload path escapes')
    require('\\' not in value and ':' not in value and all(ord(c) >= 32 for c in value), 'Invalid payload path')
    return value


def package(root, side, commit, rid):
    manifest = read_json(root / 'BUILD-MANIFEST.json')
    require(manifest['rid'] == rid and manifest['version'] == VERSIONS[side] and manifest['sourceCommit'] == commit, 'Package subject mismatch')
    require(manifest['selfContained'] is True and manifest['localCandidate'] is False, 'Matching native tested package required')
    require(manifest['buildHost']['os'] == platform.system(), 'Wrong native build host')
    config = read_json(root / 'ledger.runtimeconfig.json')['runtimeOptions']
    runtime = '10.0.15' if side == 'old' else '11.0.0'
    tfm = 'net10.0' if side == 'old' else 'net11.0'
    require(config['tfm'] == tfm and 'frameworks' not in config and any(x['name'] == 'Microsoft.NETCore.App' and x['version'] == runtime for x in config['includedFrameworks']), 'Wrong included runtime')
    require(len(manifest['files']) <= 1024 and sum(f['bytes'] for f in manifest['files']) <= 512 * 1024 * 1024, 'Package bound')
    declared = [payload_name(f['path']) for f in manifest['files']]
    require(len(set(x.casefold() for x in declared)) == len(declared), 'Duplicate payload')
    actual = []
    for entry in root.rglob('*'):
        require(not entry.is_symlink() and not (getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400), 'Payload link')
        if entry.is_file():
            actual.append(entry.relative_to(root).as_posix())
    require(set(actual) == set(declared) | {'BUILD-MANIFEST.json'}, 'Payload inventory differs')
    for file in manifest['files']:
        path = regular(root / file['path'])
        require(path.stat().st_size == file['bytes'] and sha(path) == file['sha256'], 'Payload bytes differ')
    require(commit.encode('ascii') in (root / 'ledger.dll').read_bytes(), 'Source revision missing')
    exe = regular(root / ('ledger.exe' if os.name == 'nt' else 'ledger'))
    return exe, manifest


def public_old_manifest(archive, rid):
    regular(archive)
    require(archive.stat().st_size <= 100 * 1024 * 1024 and sha(archive) == OLD_ARCHIVES[rid], 'Exact old public archive required')
    if rid == 'win-x64':
        with zipfile.ZipFile(archive) as source:
            names = [n for n in source.namelist() if n.endswith('/BUILD-MANIFEST.json')]
            require(len(names) == 1 and source.getinfo(names[0]).file_size <= 2 * 1024 * 1024, 'Old manifest bound')
            return source.read(names[0])
    with tarfile.open(archive, 'r:gz') as source:
        matches = [m for m in source if m.name.endswith('/BUILD-MANIFEST.json')]
        require(len(matches) == 1 and matches[0].isfile() and matches[0].size <= 2 * 1024 * 1024, 'Old manifest bound')
        stream = source.extractfile(matches[0])
        require(stream is not None, 'Old manifest missing')
        with stream:
            return stream.read(2 * 1024 * 1024 + 1)


def book_files(root):
    files = sorted(root.iterdir(), key=lambda p: p.name)
    require(0 < len(files) <= 5, 'Book file-count bound')
    require(sum(regular(p).stat().st_size for p in files) <= 48 * 1024 * 1024, 'Book byte bound')
    return {p.name: sha(p) for p in files}


def normalized_json(raw, version, build):
    require(raw.endswith(b'\n'), 'JSON final LF missing')
    value = decode(raw)
    for field, expected in [('version', version), ('toolBuild', build)]:
        require(value[field] == expected, 'Version/build identity mismatch')
        pattern = re.compile(rb'"' + field.encode('ascii') + rb'"\s*:\s*("(?:[^"\\]|\\.)*")')
        matches = list(pattern.finditer(raw))
        require(len(matches) == 1 and json.loads(matches[0].group(1).decode('ascii')) == expected, 'Metadata token not uniquely framed')
        start, end = matches[0].span(1)
        raw = raw[:start] + b'"CROSS_BUILD_METADATA"' + raw[end:]
    return raw


def validate_report(folder, expected_issues):
    summary_raw = (folder / 'summary.json').read_bytes()
    summary = decode(summary_raw)
    require(list(summary) == ['schema', 'version', 'toolBuild', 'bookId', 'declaredBookId', 'statementSha256', 'snapshotDigestSchema', 'snapshotReceiptListSha256', 'result', 'limits'], 'Summary field order')
    raw = (folder / 'discrepancies.json').read_bytes()
    value = decode(raw)
    require(raw.endswith(b'\n') and list(value) == DETAIL_FIELDS, 'Detail framing/order')
    require(value['schema'] == 'synthetic-reconciliation-discrepancies-v1' and value['summarySha256'] == hashlib.sha256(summary_raw).hexdigest(), 'Summary binding')
    require(all(value[k] == summary[k] for k in ['bookId', 'statementSha256', 'snapshotReceiptListSha256']) and value['throughSequence'] == summary['result']['snapshotSequence'], 'Snapshot binding')
    require(all(list(i) == ISSUE_FIELDS for i in value['issues']) and len(value['issues']) <= 4000, 'Issue framing/count')
    if expected_issues is not None:
        require([tuple(i.values()) for i in value['issues']] == expected_issues, 'Independent literal issue oracle')
    for code, count in [('DUPLICATE_REQUEST_ID', 'duplicates'), ('UNEXPECTED_REQUEST_ID', 'unexpected'), ('WRONG_AMOUNT', 'wrongAmount'), ('MISSING_REQUEST_ID', 'missing')]:
        require(sum(i['code'] == code for i in value['issues']) == summary['result'][count], 'Independent category count')
    return summary_raw, raw

class Calls:
    def __init__(self, work, packages, commits, control):
        self.work, self.packages, self.commits, self.control = work, packages, commits, control
        self.start = time.monotonic()
        self.records, self.builds = [], {}
        self.log_bytes = 0

    def run(self, side, name, args, expected):
        lease_guard(self.control)
        kernel_caps(self.control)
        require(len(self.records) < 60 and time.monotonic() - self.start < 600 and time.monotonic() < self.control.get('deadlineMonotonic', float('inf')), 'Invocation/phase bound')
        prefix = self.work / f'{len(self.records):02d}-{side}-{name}'
        out, err = Path(str(prefix) + '.stdout'), Path(str(prefix) + '.stderr')
        env = dict(os.environ, DOTNET_ROOT=str(self.work / 'no-installed-dotnet'),
                   DOTNET_ROOT_X64=str(self.work / 'no-installed-dotnet'), DOTNET_MULTILEVEL_LOOKUP='0')
        started = time.monotonic()
        with out.open('xb') as stdout, err.open('xb') as stderr:
            child = subprocess.Popen([str(self.packages[side]), *map(str, args)], cwd=self.work,
                                     env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                     creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
            try:
                while child.poll() is None:
                    size = out.stat().st_size + err.stat().st_size
                    require(size <= 1024 * 1024 and self.log_bytes + size <= 32 * 1024 * 1024, 'Owned IPC byte bound')
                    require(time.monotonic() - started < 30 and time.monotonic() - self.start < 600, 'Owned child/phase deadline')
                    time.sleep(0.02)
                code = child.wait(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill()  # Only this unreaped Popen child; outer admitted wrapper owns descendant cleanup.
                    child.wait(timeout=5)
        raw = out.read_bytes()
        self.log_bytes += len(raw) + err.stat().st_size
        require(len(raw) <= 1024 * 1024 and self.log_bytes <= 32 * 1024 * 1024, 'Final IPC byte bound')
        record = {'side': side, 'name': name, 'pid': child.pid, 'exit': code,
                  'stdoutSha256': sha(out), 'stderrSha256': sha(err), 'ownedChildTerminal': True}
        self.records.append(record)
        require(code == expected and err.stat().st_size == 0, 'Actual CLI exit/stderr mismatch')
        value = decode(raw)
        require(value['schema'].startswith('synthetic-') and value['version'] == VERSIONS[side], 'Actual CLI identity')
        require(value['complete'] is (expected != 1), 'Completed denial confused with incomplete failure')
        require(self.commits[side] in value['toolBuild'] and VERSIONS[side] in value['toolBuild'], 'Build revision mismatch')
        if side in self.builds:
            require(self.builds[side] == value['toolBuild'], 'CLI build changed during phase')
        self.builds[side] = value['toolBuild']
        return value, raw


def write_fixture(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, separators=(',', ':')) + '\n')


def compare_pair_outputs(items, calls):
    left = normalized_json(items['old'][1], VERSIONS['old'], calls.builds['old'])
    right = normalized_json(items['new'][1], VERSIONS['new'], calls.builds['new'])
    require(left == right, 'Cross-build CLI bytes differ outside metadata')


def compare_reports(folders, expected, calls):
    values = {side: validate_report(folder, expected) for side, folder in folders.items()}
    summaries = {side: normalized_json(raw[0], VERSIONS[side], calls.builds[side]) for side, raw in values.items()}
    require(summaries['old'] == summaries['new'], 'Cross-build summary bytes differ outside metadata')
    details, texts = {}, {}
    for side, (summary, detail) in values.items():
        actual_hash = hashlib.sha256(summary).hexdigest().encode('ascii')
        token = b'"summarySha256":"' + actual_hash + b'"'
        require(detail.count(token) == 1, 'Exact summary-hash framing missing')
        # In-memory comparison token only, never emitted as an evidence hash.
        details[side] = detail.replace(token, b'"summarySha256":"CROSS_BUILD_BINDING"', 1)
        text = (folders[side] / 'summary.txt').read_bytes()
        version = ('Version ' + VERSIONS[side] + ';').encode('ascii')
        require(text.count(version) == 1, 'Text version framing')
        texts[side] = text.replace(version, b'Version CROSS_BUILD_METADATA;', 1)
    require(details['old'] == details['new'] and texts['old'] == texts['new'], 'Report byte difference outside named metadata')


def direction(producer, work, calls):
    receiver = 'new' if producer == 'old' else 'old'
    demo = work / (producer + '-origin')
    value, _ = calls.run(producer, 'demo', ['demo', demo], 0)
    require(value['entries'] == 2 and value['preciseAmountMinor'] == 123456789012, 'Demo literal fixture differs')
    original, clone = demo / 'book', work / (producer + '-closed-book-clone')
    before = book_files(original)
    shutil.copytree(original, clone)
    require(book_files(clone) == before and book_files(original) == before, 'Quiescent clone differs')
    books = {producer: original, receiver: clone}
    expected_books = {side: book_files(book) for side, book in books.items()}
    matching = read_json(demo / 'statement-match.json')
    literal = dict(matching)
    literal['rows'] = [{'requestId': 'DEMO_A', 'amountMinor': 123456789011},
                       {'requestId': 'X', 'amountMinor': 1}, {'requestId': 'X', 'amountMinor': 2},
                       {'requestId': 'DEMO_A', 'amountMinor': 123456789010}]
    seven = work / (producer + '-seven.json')
    write_fixture(seven, literal)
    scope_value = dict(matching)
    scope_value['bookId'] = 'f' * 32 if matching['bookId'] != 'f' * 32 else 'e' * 32
    scope = work / (producer + '-scope.json')
    write_fixture(scope, scope_value)
    malformed = work / (producer + '-duplicate-key.json')
    with malformed.open('x', encoding='utf-8') as stream:
        stream.write('{"unit":"LAB",' + json.dumps(matching, separators=(',', ':'))[1:])
    conflict_value = read_json(demo / 'post.json')
    for split in conflict_value['splits']:
        if split['debit']:
            split['debit'] = 1
        if split['credit']:
            split['credit'] = 1
    conflict = work / (producer + '-conflict.json')
    write_fixture(conflict, conflict_value)
    cases = []
    for name in ['replay', 'conflict', 'match', 'seven', 'scope', 'malformed', 'collision']:
        outputs, reports = {}, {}
        for side in ['old', 'new']:
            folder = work / (producer + '-' + side + '-' + name + '-report')
            if name in {'replay', 'conflict'}:
                input_path = demo / 'post.json' if name == 'replay' else conflict
                args, exit_code = ['post', books[side], input_path], (0 if name == 'replay' else 2)
            else:
                input_path = {'match': demo / 'statement-match.json', 'seven': seven, 'scope': scope,
                              'malformed': malformed, 'collision': demo / 'statement-match.json'}[name]
                if name == 'collision':
                    folder.mkdir()
                    with (folder / 'sentinel').open('xb') as stream:
                        stream.write(b'untouched')
                args = ['reconcile', books[side], input_path, folder]
                exit_code = 0 if name == 'match' else (2 if name in {'seven', 'scope'} else 1)
            output = calls.run(side, producer + '-' + name, args, exit_code)
            outputs[side] = output
            parsed = output[0]
            if name == 'replay':
                require(parsed['result']['disposition'] == 'replayed' and
                        parsed['result']['receipt'] == value['posted']['receipt'] and
                        parsed['result']['receiptSha256'] == value['posted']['receiptSha256'], 'Saved receipt bytes/hash changed')
            if name == 'conflict':
                require(parsed['reason'] == 'REQUEST_ID_CONFLICT', 'Conflict oracle')
            if name == 'malformed':
                require(parsed['reason'] == 'JSON_DUPLICATE_KEY', 'Malformed-input oracle')
                require(not (folder / 'summary.json').exists(), 'Incomplete input has final report')
            if name == 'collision':
                require(parsed['reason'] == 'OUTPUT_EXISTS' and (folder / 'sentinel').read_bytes() == b'untouched', 'Collision oracle')
                require(not (folder / 'summary.json').exists(), 'Collision has final report')
            if name in {'match', 'seven', 'scope'}:
                require(parsed['outcome'] == ('pass' if name == 'match' else 'fail'), 'Comparison outcome oracle')
                reports[side] = folder
            require(book_files(books[side]) == expected_books[side], 'Quiescent book mutated')
        compare_pair_outputs(outputs, calls)
        if reports:
            compare_reports(reports, SEVEN if name == 'seven' else [], calls)
        cases.append({'origin': producer, 'case': name, 'outcome': 'pass'})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-package', type=Path, required=True)
    parser.add_argument('--old-archive', type=Path, required=True)
    parser.add_argument('--new-package', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--control-sha256', required=True)
    args = parser.parse_args()
    require(platform.system() in {'Windows', 'Linux'} and platform.machine().lower() in {'amd64', 'x86_64'}, 'Native x64 only')
    require(sys_flags_safe(), 'Unisolated/optimized Python invocation refused')
    control, caps = admitted_control(args)
    rid = 'win-x64' if os.name == 'nt' else 'linux-x64'
    for root in [args.old_package, args.new_package, args.work]:
        require(root.is_absolute(), 'Absolute root required')
        for parent in [root, *root.parents]:
            if parent.exists():
                require(not parent.is_symlink() and not (getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400), 'Root link/reparse')
    require(all(not args.work.is_relative_to(p) and not p.is_relative_to(args.work) for p in [args.old_package, args.new_package]), 'Work overlaps input package')
    old_manifest = public_old_manifest(args.old_archive, rid)
    extracted_manifest = regular(args.old_package / 'BUILD-MANIFEST.json')
    require(extracted_manifest.stat().st_size == len(old_manifest) and old_manifest == extracted_manifest.read_bytes(), 'Old extracted manifest not from public archive')
    commits = {'old': OLD_COMMIT, 'new': args.commit}
    packages, manifests = {}, {}
    for side, root in [('old', args.old_package), ('new', args.new_package)]:
        packages[side], manifests[side] = package(root, side, commits[side], rid)
    old_graph = read_json(args.old_package / 'DEPENDENCIES.json')['packages']
    new_graph = read_json(args.new_package / 'DEPENDENCIES.json')['packages']
    def managed(graph):
        return sorted((v['id'], v['version'], v.get('nugetContentHash'), v['license'])
                      for v in graph if not v['id'].startswith('Microsoft.NETCore.App.Runtime.'))
    require(managed(old_graph) == managed(new_graph), 'Frozen managed package identity changed')
    args.work.mkdir()  # Exact fresh parent/containment was checked before target execution.
    calls = Calls(args.work, packages, commits, control)
    try:
        cases = direction('old', args.work, calls) + direction('new', args.work, calls)
        require(len(cases) == 14 and len(calls.records) == 30, 'Case/invocation bound changed')
        result = {'schema': 'frl-tech-refresh-comparison-v1',
                  'status': 'CASES_PASSED_WRAPPER_TERMINATION_PENDING',
                  'projectId': '01', 'rid': rid, 'candidateCommit': args.commit,
                  'controlSha256': args.control_sha256, 'helperSha256': sha(Path(__file__).resolve()),
                  'kernelReadback': caps, 'oldPublicArchiveSha256': sha(args.old_archive),
                  'manifests': {side: sha(root / 'BUILD-MANIFEST.json') for side, root in [('old', args.old_package), ('new', args.new_package)]},
                  'cases': cases, 'calls': calls.records,
                  'boundary': 'Synthetic fixtures only; exact named metadata normalization; no performance/power-loss/production/security claim. Final outer-wrapper terminal containment proof is still required.'}
        with (args.work / 'receipt.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    except Exception:
        with (args.work / 'incomplete.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'schema': 'frl-tech-refresh-comparison-v1', 'status': 'INCOMPLETE',
                       'calls': calls.records, 'finalWrapperCleanupStillRequired': True}, stream, indent=2)
            stream.write('\n')
        raise
    print(json.dumps({'status': result['status'], 'cases': len(cases), 'invocations': len(calls.records)}))


def sys_flags_safe():
    import sys
    return sys.flags.isolated == 1 and sys.flags.optimize == 0


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import sys
        print(json.dumps({'status': 'INCOMPLETE', 'reason': str(error) if isinstance(error, RuntimeError) else type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
