"""Only new actual Windows image variants in the pure owner model; no SDK/host run."""
import copy,importlib.util,json
from pathlib import Path
here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('own_host_guard',here/'ci_host_guard.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
base=json.loads((here/'host_boundary_fixtures.json').read_text(encoding='utf-8'))['baselineModel']
fact=json.loads((here.parent/'sdk11-normal/accepted-windows-fact.json').read_bytes());acceptance=json.loads((here.parent/'sdk11-normal/accepted-windows-acceptance.json').read_bytes())
assert fact['qualifiedOn']['runId']=='44083510897' and fact['qualifiedOn']['imageOS']=='win25-vs2026'
for image,accepted in [('win25-vs2026',True),('win25',True),('win25-other',False),('win25-vs2026-extra',False),('ubuntu24',False)]:
 value=copy.deepcopy(base);value['fact']=fact;value['acceptance']=acceptance;route=value['route'];route['producerQualifiedOn']=fact['qualifiedOn'];route['archive']=fact['archive'];route['admittedFor']['memberManifestSha256']=fact['tree']['memberManifestSha256'];value['own']['imageOS']=image
 denied=False
 try:guard.model(fact,acceptance,route,value['own'])
 except RuntimeError:denied=True
 if denied==accepted:raise RuntimeError('NEW_WINDOWS_IMAGE_VARIANT:'+image)
print(json.dumps({'newWindowsImageCases':5,'scope':'MODEL_ONLY_REAL_FACT_INPUT_NOT_CURRENT_CONSUMER_ADMISSION','SDKLaunches':0}))
