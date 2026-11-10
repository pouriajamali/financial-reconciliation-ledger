"""Execute only the owned extracted apphost with fresh synthetic journal fixtures."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--commit',required=True);p.add_argument('--local-candidate',action='store_true');a=p.parse_args()
 package=a.package.resolve();work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);m=json.loads((package/'BUILD-MANIFEST.json').read_text(encoding='utf-8'))
 assert m['sourceCommit']==a.commit and m['selfContained'] and m['originalLicense']=='present' and m['rid']==('win-x64' if os.name=='nt' else 'linux-x64')
 if not a.local_candidate:assert not m['localCandidate']
 assert {f.relative_to(package).as_posix() for f in package.rglob('*') if f.is_file()}=={f['path'] for f in m['files']}|{'BUILD-MANIFEST.json'}
 for f in m['files']:
  file=package/f['path'];assert not file.is_symlink() and file.stat().st_size==f['bytes'] and sha(file)==f['sha256']
 assert a.commit.encode() in (package/'ledger.dll').read_bytes()
 for name in ['LICENSE','NOTICE.md','CONTRIBUTING.md','PROVENANCE.md','docs/CONTRACT.md','docs/CASE-STUDY.md','docs/ACCEPTED-CLARIFICATIONS.md']:assert (package/name).is_file()
 inventory=json.loads((package/'DEPENDENCIES.json').read_text(encoding='utf-8'))['packages'];assert any(d['id']=='Microsoft.Data.Sqlite' and d['version']=='10.0.15' for d in inventory)
 assert any(f.name.startswith('Microsoft.NETCore.App.Runtime') and 'THIRD-PARTY-NOTICES' in f.name.upper() for f in (package/'licenses').iterdir())
 config=json.loads((package/'ledger.runtimeconfig.json').read_text(encoding='utf-8'))['runtimeOptions'];assert 'includedFrameworks' in config and 'frameworks' not in config
 assert any(f['name']=='Microsoft.NETCore.App' and f['version']=='10.0.15' for f in config['includedFrameworks'])
 checks=['manifest-source-dependencies-licenses-document-links'];exe=package/('ledger.exe' if os.name=='nt' else 'ledger');env=dict(os.environ,DOTNET_ROOT=str(work/'no-installed-dotnet'),DOTNET_ROOT_X64=str(work/'no-installed-dotnet'),DOTNET_MULTILEVEL_LOOKUP='0')
 def run(name,args,code):
  r=subprocess.run([str(exe),*map(str,args)],cwd=work,env=env,text=True,encoding='utf-8',capture_output=True,timeout=30)
  (work/(name+'.json')).write_text(json.dumps({'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'command':[str(exe),*map(str,args)]},indent=2)+'\n',encoding='utf-8')
  assert r.returncode==code and not r.stderr,(name,r.returncode)
  if name!='version':
   decoded=json.loads(r.stdout);assert decoded['schema'].startswith('synthetic-') and decoded['version']==m['version'] and a.commit in decoded['toolBuild']
  checks.append(name);return r.stdout
 assert m['version'] in run('version',['--version'],0)
 demo=work/'demo with spaces';r=json.loads(run('demo',['demo',demo],0));assert r['complete'] and r['outcome']=='pass' and a.commit in r['toolBuild'] and r['entries']==2 and r['preciseAmountMinor']==123456789012
 assert r['posted']['receipt']==r['replayed']['receipt'] and r['rejectedConflict'] and r['rejectedUnbalanced'] and r['negative']['outcome']=='fail'
 assert sum(r['balancesDebitMinusCredit'].values())==0 and json.loads((demo/'report/summary.json').read_text(encoding='utf-8'))==r
 retryOuter=json.loads(run('exact-retry',['post',demo/'book',demo/'post.json'],0));assert a.commit in retryOuter['toolBuild'] and retryOuter['version']==m['version'];retry=retryOuter['result'];assert retry['disposition']=='replayed' and retry['receipt']==r['posted']['receipt'] and retry['receiptSha256']==r['posted']['receiptSha256']
 match=json.loads(run('matching-comparison',['reconcile',demo/'book',demo/'statement-match.json',work/'matching report'],0))['result'];assert match['outcome']=='pass' and match['snapshotSequence']==2 and match['provenance']=='UNVERIFIED' and match['freshness']=='NOT_CHECKED' and match['externalCompleteness']=='NOT_PROVEN'
 evidence=json.loads((work/'matching report/summary.json').read_text(encoding='utf-8'));assert evidence['bookId']==evidence['declaredBookId']==r['bookId'] and evidence['statementSha256']==sha(demo/'statement-match.json') and evidence['snapshotDigestSchema']=='synthetic-ledger-snapshot-v1' and len(evidence['snapshotReceiptListSha256'])==64 and a.commit in evidence['toolBuild']
 negative=json.loads(run('negative-comparison',['reconcile',demo/'book',demo/'statement-negative.json',work/'negative report'],2))['result'];assert [negative[k] for k in ['missing','unexpected','duplicates','wrongAmount']]==[1,2,1,1]
 book=work/'new book';created=json.loads(run('init',['init',book],0));assert created['complete'] and created['unit']=='LAB' and a.commit in created['toolBuild'] and created['version']==m['version']
 post=json.loads((demo/'post.json').read_text(encoding='utf-8'));post['bookId']=created['bookId'];input=work/'post-new.json';input.write_text(json.dumps(post),encoding='utf-8');assert json.loads(run('new-post',['post',book,input],0))['result']['disposition']=='posted'
 post=json.loads((demo/'post.json').read_text(encoding='utf-8'))
 for split in post['splits']:
  if split['debit']:split['debit']=1
  if split['credit']:split['credit']=1
 conflict=work/'conflict.json';conflict.write_text(json.dumps(post),encoding='utf-8');assert json.loads(run('conflict',['post',demo/'book',conflict],2))['reason']=='REQUEST_ID_CONFLICT'
 post['requestId']='UNBALANCED'
 next(s for s in post['splits'] if s['debit'])['debit']=2
 invalid=work/'unbalanced.json';invalid.write_text(json.dumps(post),encoding='utf-8');assert json.loads(run('unbalanced',['post',demo/'book',invalid],2))['reason']=='POST_UNBALANCED'
 malformed=work/'malformed.json';malformed.write_text('{',encoding='utf-8');assert not json.loads(run('malformed',['post',demo/'book',malformed],1))['complete']
 existing=work/'existing';existing.mkdir();(existing/'sentinel').write_text('untouched',encoding='utf-8');assert json.loads(run('refuse-existing',['demo',existing],1))['reason']=='OUTPUT_EXISTS' and (existing/'sentinel').read_text(encoding='utf-8')=='untouched'
 for arg in ['--host','--sql','--test-worker']:assert json.loads(run('refuse-'+arg[2:],[arg],1))['reason']=='CLI_INVALID'
 assert json.loads(run('refuse-report-overlap',['reconcile',demo/'book',demo/'statement-match.json',demo/'book/illegal report'],1))['reason']=='OUTPUT_OVERLAPS_INPUT'
 assert not (demo/'report/discrepancies.json').exists(),'Legacy demo report is unchanged'
 def details(folder):
  summary=folder/'summary.json';detail=json.loads((folder/'discrepancies.json').read_text(encoding='utf-8'));s=json.loads(summary.read_text(encoding='utf-8'))
  assert list(detail)==['schema','summarySha256','bookId','statementSha256','snapshotReceiptListSha256','throughSequence','issues']
  assert detail['schema']=='synthetic-reconciliation-discrepancies-v1' and detail['summarySha256']==sha(summary)
  assert all(detail[k]==s[k] for k in ['bookId','statementSha256','snapshotReceiptListSha256']) and detail['throughSequence']==s['result']['snapshotSequence']
  raw=(folder/'discrepancies.json').read_bytes();assert raw.endswith(b'\n') and not raw.startswith(b'\xef\xbb\xbf') and len(raw)<=2097152 and len(detail['issues'])<=4000
  fields=['code','requestId','statementRowIndex','entrySequence','expectedAmountMinor','actualAmountMinor','firstStatementRowIndex']
  assert all(list(i)==fields for i in detail['issues'])
  for code,key in [('DUPLICATE_REQUEST_ID','duplicates'),('UNEXPECTED_REQUEST_ID','unexpected'),('WRONG_AMOUNT','wrongAmount'),('MISSING_REQUEST_ID','missing')]:assert sum(i['code']==code for i in detail['issues'])==s['result'][key]
  return detail
 assert details(work/'matching report')['issues']==[] and len(details(work/'negative report')['issues'])==5
 checks.append('sidecar-binding-exact-counts-legacy-demo')
 literal=work/'seven-issue.json';frame=json.loads((demo/'statement-match.json').read_text(encoding='utf-8'))
 frame['rows']=[{'requestId':'DEMO_A','amountMinor':123456789011},{'requestId':'X','amountMinor':1},{'requestId':'X','amountMinor':2},{'requestId':'DEMO_A','amountMinor':123456789010}]
 literal.write_text(json.dumps(frame),encoding='utf-8')
 assert json.loads(run('literal-seven-issue-comparison',['reconcile',demo/'book',literal,work/'seven report'],2))['result']['wrongAmount']==2
 expected=[('WRONG_AMOUNT','DEMO_A',1,1,123456789012,123456789011,None),('UNEXPECTED_REQUEST_ID','X',2,None,None,1,None),('DUPLICATE_REQUEST_ID','X',3,None,None,2,2),('UNEXPECTED_REQUEST_ID','X',3,None,None,2,None),('DUPLICATE_REQUEST_ID','DEMO_A',4,1,123456789012,123456789010,1),('WRONG_AMOUNT','DEMO_A',4,1,123456789012,123456789010,None),('MISSING_REQUEST_ID','DEMO_B',None,2,1000,None,None)]
 assert [tuple(i.values()) for i in details(work/'seven report')['issues']]==expected
 run('repeat-seven-issue-comparison',['reconcile',demo/'book',literal,work/'seven repeated report'],2)
 for name in ['summary.json','summary.txt','discrepancies.json']:assert (work/'seven report'/name).read_bytes()==(work/'seven repeated report'/name).read_bytes()
 checks.append('literal-seven-issues-and-byte-repeat')
 frame['rows']=[{'requestId':'X','amountMinor':1} for _ in range(1000)];many=work/'2001-issues.json';many.write_text(json.dumps(frame),encoding='utf-8')
 manyresult=json.loads(run('2001-issue-comparison',['reconcile',demo/'book',many,work/'2001 report'],2))['result'];assert [manyresult[k] for k in ['duplicates','unexpected','missing','wrongAmount']]==[999,1000,2,0] and len(details(work/'2001 report')['issues'])==2001
 checks.append('full-2001-issues-no-truncation')
 assert len(checks)==22
 receipt={'status':'ACTUAL_SELF_CONTAINED_SYNTHETIC_LEDGER_PACKAGE_PASS','commit':a.commit,'rid':m['rid'],'checkCount':len(checks),'checks':checks,'manifestSha256':sha(package/'BUILD-MANIFEST.json'),'scope':'Synthetic LAB journal/reconciliation only; existing hosts, no real finance/powerloss/distributedexactlyonce/cleanOS claim'}
 (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':receipt['status'],'checks':len(checks),'rid':m['rid']}))
if __name__=='__main__':main()
