"""New own retained-Windows snapshot/CPU proof cases; fixture only."""
import ast,copy,hashlib
from pathlib import Path
tree=ast.parse(Path(__file__).with_name('ci_host_controller.py').read_text(encoding='utf-8'));nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('need','validate_windows_held_cpu')];ns={'hashlib':hashlib};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<own_windows_retained_cpu>','exec'),ns)
mask=(1<<0)|(1<<9)|(1<<13)|(1<<19)|(1<<20)|(1<<23);code=bytes.fromhex('5389c889d10fa241890041895804418948084189500c5bc3')
before={'pid':23,'processStartIdentity':'FILETIME:456','jobName':'Local\\frl01-ci-fixture','memoryMaxBytes':2147483648,'tasksMax':32,'cpuRate':5000,'logicalHostCpu':4};held={'pid':23,'startIdentity':'456','kernel':dict(before),'cpu':{'processorCount':2,'evidenceSha256':'a'*64}}
cpu={'codeHex':code.hex(),'codeSha256':hashlib.sha256(code).hexdigest(),'processors':[{'processor':0,'leaf1Ecx':mask,'extendedEcx':1},{'processor':1,'leaf1Ecx':mask,'extendedEcx':1}]}
assert ns['validate_windows_held_cpu'](held,before,cpu,'a'*64)=='a'*64
cases=[('pid',None),('start',None),('cap',None),('bit',None),('duplicate',None),('hash',None),('code',None)]
for name,_ in cases:
 h,b,c=copy.deepcopy(held),copy.deepcopy(before),copy.deepcopy(cpu);digest='a'*64
 if name=='pid':b['pid']=24
 elif name=='start':b['processStartIdentity']='FILETIME:other'
 elif name=='cap':h['kernel']['tasksMax']=64
 elif name=='bit':c['processors'][1]['leaf1Ecx']=0
 elif name=='duplicate':c['processors'][1]['processor']=0
 elif name=='hash':digest='b'*64
 elif name=='code':c['codeSha256']='b'*64
 try:ns['validate_windows_held_cpu'](h,b,c,digest)
 except RuntimeError:pass
 else:raise AssertionError('boundary accepted:'+name)
print({'newOwnWindowsProofCases':8,'fixtureOnly':True,'SDKOrNativeOrNetwork':0})
