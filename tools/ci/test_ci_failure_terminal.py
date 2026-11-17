"""New failure-terminal negatives only; missing cgroup never implies zero."""
import ast,copy
from pathlib import Path
p=Path(__file__).with_name('ci_host_controller.py');tree=ast.parse(p.read_text(encoding='utf-8'));fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='failed_aggregate_terminal');ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<failure_terminal>','exec'),ns)
own={'jobId':'12'};held={'pid':45,'startIdentity':'67'};unit='frl01-ci-12-token'
stop={'jobId':'12','workerPID':45,'workerStartIdentity':'67','cgroup':'/system.slice/'+unit+'.service','remainingPopulationExcludingObserver':0,'causeCapturedBeforeCollection':True,'serviceResult':'exit-code','exitCode':'exited','exitStatus':'1'}
f=ns['failed_aggregate_terminal']
assert f(stop,own,held,unit,True,True,True,None)
assert f(stop,own,held,unit,True,True,False,'0')
for change in [{'causeCapturedBeforeCollection':False},{'workerStartIdentity':'other'},{'remainingPopulationExcludingObserver':1},{'exitStatus':None}]:
 bad=dict(stop,**change);assert not f(bad,own,held,unit,True,True,True,None)
assert not f(None,own,held,unit,True,True,True,None)
assert not f(stop,own,held,unit,True,False,True,None)
assert not f(stop,own,held,unit,True,True,False,None)
print({'newFailureTerminalCases':9,'SDKOrNativeOrNetwork':0})
