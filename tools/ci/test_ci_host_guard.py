"""New SDK0 pure model boundary additions; never a real host qualification."""
import copy,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frl01_ci_guard',HERE/'ci_host_guard.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
def main():
    data=json.loads((HERE/'host_boundary_fixtures.json').read_text(encoding='utf-8'))
    if data['fixtureOnly'] is not True or len(data['cases'])!=26:raise RuntimeError('FIXTURE_SCOPE')
    results=[]
    for case in data['cases']:
        value=copy.deepcopy(data['baselineModel'])
        if case['mutation']:
            path,replacement=case['mutation'];parts=path.split('.');target=value
            for key in parts[:-1]:target=target[key]
            target[parts[-1]]=replacement
        denied=False
        try:guard.model(value['fact'],value['acceptance'],value['route'],value['own'])
        except RuntimeError:denied=True
        expected=case['expect']=='DENY_MODEL_ONLY'
        if denied!=expected:raise RuntimeError('NEW_BOUNDARY_ORACLE_'+case['id'])
        results.append(case['id'])
    print(json.dumps({'newCases':len(results),'SDKLaunches':0,'scope':'MODEL_ONLY_NOT_HOST_OR_SDK_QUALIFICATION'}))
if __name__=='__main__':main()
