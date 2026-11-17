"""Only new typed cause shape/redaction cases; no OS/native/SDK calls."""
import ast,json
from pathlib import Path
p=Path(__file__).with_name('ci_host_controller.py');tree=ast.parse(p.read_text(encoding='utf-8'));nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('need','typed_worker_cause')];ns={'Path':Path,'HERE':p.parent,'json':json};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<typed_worker_cause>','exec'),ns);f=ns['typed_worker_cause']
assert f(KeyError('hostClass'))['missingIdentifier']=='hostClass'
assert f(KeyError('https://private/?token=secret'))['missingIdentifier'] is None
assert f(ValueError('NORMAL_CURRENT_SOURCE'))['code']=='NORMAL_CURRENT_SOURCE'
assert f(TypeError('private args token=secret'))['code']=='DETAIL_REDACTED'
e=RuntimeError('UNKNOWN');e.normalInputCleanup={'state':'NO_ALLOCATION','allocationCreated':False,'private':'secret'};r=f(e);assert set(r['normalInputCleanup'])=={'state','allocationCreated'} and 'secret' not in json.dumps(r)
try:raise KeyError('bootstrap')
except KeyError as e:r=f(e);assert all(set(x)=={'module','function','line'} for x in r['frames'])
print({'newTypedCauseCases':6,'SDKOrNativeOrNetwork':0})
