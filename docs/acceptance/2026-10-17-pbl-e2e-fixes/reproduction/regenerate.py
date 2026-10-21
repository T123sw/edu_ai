import asyncio,json,sys,copy
from pathlib import Path
sys.path.insert(0,'/home/zxqs_ep/Edu_AI/scripts/pbl')
from isolated import configure
configure(live_model=True)
from app.pbl.project_generator import generate_project_phase
from app.pbl.project_validation import check_project
from app.pbl.project_schemas import STARTER_FILES,hash_files,validate_planned_checks
root=Path('/tmp/pbl-fixes-20261017');old=Path('/tmp/pbl-matrix-20261017')
sem=asyncio.Semaphore(2)
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
async def model(name,phase,data):
 async with sem:
  p=root/name;p.mkdir(exist_ok=True)
  n=len(list(p.glob('input*.json')))+1;save(p/f'input-{n:03}.json',{'phase':phase,'data':data})
  result=await generate_project_phase('fixes-validation',{},phase,data)
  save(p/f'output-{n:03}.json',result)
  return result
async def checks_case(name):
 source=old/('matrix_'+name);private=json.loads((source/'private.json').read_text())['candidate_private'];plan=private['plan']
 checks=[];previous=STARTER_FILES
 for index,item in enumerate(private['completed']):
  candidate=item['candidate'];step=plan['steps'][index];files=candidate['referenceFiles']
  report=await asyncio.to_thread(check_project,files,checks) if checks else {'skipped':True}
  assert report.get('passed',True),report
  data={'topic':json.loads((source/'detail.json').read_text())['artifact']['topic'],'plan':plan,'step':step,'requiredChecks':[c for c in plan['checks'] if c['id'] in step['newCheckIds']],'previousFiles':previous,'previousChecks':checks,'previousCheckReport':report,'referenceFiles':files,'referenceHash':hash_files(files),'unit':candidate['unit'],'issues':[],'priorCandidate':None}
  for attempt in range(3):
   try:
    result=await model(name,'repair_checks' if attempt else 'build_checks',data)
    validate_planned_checks(plan,result['checks'])
    report=await asyncio.to_thread(check_project,files,checks+result['checks'])
    save(root/name/f'baseline-{index}-{attempt}.json',report)
    if not report['passed']:raise ValueError(str([x for x in report['results'] if x['status']=='failed']))
    checks+=result['checks'];previous=files
    print(name,index,report['passed'],flush=True);break
   except (ValueError,KeyError) as exc:
    data['issues']=[str(exc)];data['priorCandidate']=getattr(exc,'raw',locals().get('result'))
  else:return {'case':name,'passed':False,'issues':data['issues']}
 save(root/name/'checks.json',checks)
 return {'case':name,'passed':True,'checks':len(checks)}
async def repair_old():
 name='old-regression';checkpoint=json.loads((old/'matrix_shop_b/private.json').read_text())['checkpoint'];plan=checkpoint['plan'];step=plan['steps'][3]
 checks=[c for item in checkpoint['completed'] for c in item['candidate']['checks']];previous=checkpoint['completed'][-1]['candidate']['referenceFiles']
 data={'topic':json.loads((old/'matrix_shop_b/input-001.json').read_text())['data']['topic'],'plan':plan,'step':step,'requiredChecks':[c for c in plan['checks'] if c['id'] in step['newCheckIds']],'previousFiles':previous,'previousChecks':checks,'previousCheckReport':checkpoint['previousCheckReport'],'issues':checkpoint['issues'],'priorCandidate':checkpoint['lastCandidate']}
 for attempt in range(3):
  result=await model(name,'repair_step',data)
  report=await asyncio.to_thread(check_project,result['referenceFiles'],checks);save(root/name/f'regression-{attempt}.json',report)
  print(name,attempt,'previous',report['passed'],flush=True)
  data['previousCheckReport']=report
  if report['passed']:
   acceptance=await model(name,'repair_checks',{**data,**result,'previousCheckReport':report})
   report=await asyncio.to_thread(check_project,result['referenceFiles'],checks+acceptance['checks']);save(root/name/f'cumulative-{attempt}.json',report)
   if report['passed']:break
  data['issues']=[str([x for x in report['results'] if x['status']=='failed'])]
  data['priorCandidate']={**result,**({'checks':acceptance['checks']} if report.get('passed') is not None and 'acceptance' in locals() else {})}
 return {'case':name,'passed':report['passed']}
async def main():
 results=await asyncio.gather(*(checks_case(n) for n in ('score','form','shop_a')),repair_old(),return_exceptions=True)
 save(root/'regenerate-coverage-results.json',[{'error':str(r)} if isinstance(r,Exception) else r for r in results])
 print('DONE',results,flush=True)
asyncio.run(main())
