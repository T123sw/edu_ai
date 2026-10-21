import asyncio,json,time,uuid,sys,os
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
engine=create_engine('postgresql+psycopg://zxqs_ep@127.0.0.1:55441/pbl_acceptance_20261017_final')
root=Path('/tmp/pbl-fixes-final-20261017')
out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-fixes')
API='http://127.0.0.1:8027'
shopping='我想用 React 做一个购物清单页面，练习状态管理和列表操作。输入商品名称，点击“添加”后加入列表，初始数量为 1，并清空输入框。空白名称不能添加，页面显示提示。每件商品都有增加、减少数量的按钮，数量最低为 1。可以切换“待购买 / 已购买”状态，也可以删除商品。支持按“全部 / 待购买 / 已购买”筛选。显示商品种类数和待购买总件数；统计基于整个清单，不受筛选影响。只在当前页面运行，不需要后端、登录或刷新后保存。我已经会基本 JSX，请按合理的功能增量拆分步骤，说明每步成果和验收要求。'
cases={
 'shop_a':shopping,
 'shop_b':shopping,
 'form':'用 React 做一个本地活动报名表，只做一个完整交互步骤。页面有姓名输入框和报名按钮。空字符串或只有空格的姓名提交后显示“请输入姓名”；合法姓名提交后显示“报名成功：”加去掉首尾空格的姓名。修改姓名时清除旧的成功或错误提示。不要联网、持久化、手机号或其他字段。',
 'layout':'用 React 做一个个人作品展示页，只需要一个页面布局步骤。页面有标题“我的作品”、简介“记录我的学习成果”，下方展示三件作品，每件含标题和一句介绍。作品标题分别是“天气卡片”“读书笔记”“像素画”。桌面标题在简介上方，作品区域在简介下方；手机页面不横向溢出。无需按钮、输入框或交互功能，不要图片或外部资源。',
 'score':'用 React 做一个双人比赛记分牌。双方名称固定为“红队”和“蓝队”，分数初始都为 0。每队各有加 1 分、减 1 分按钮，分数不能低于 0；操作一队不影响另一队。另有一个“重置比赛”按钮清空双方分数。页面显示当前状态：分数相同时“平局”，否则显示“红队领先”或“蓝队领先”。我会 JSX，请按功能增量拆分步骤，先完成页面外壳再加入交互。不要计时、后端或持久化。',
}

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

async def login(client,name):
 r=await client.post(API+'/api/auth/login',json={'username':'matrix_'+name,'password':'matrix-isolated-only'});r.raise_for_status();return r.json()

async def run(name,topic):
 case=root/('matrix_'+name);case.mkdir(exist_ok=True)
 start=time.time();events=[]
 async with httpx.AsyncClient(timeout=120) as client:
  auth=await login(client,name);save(case/'auth.json',auth)
  headers={'Authorization':'Bearer '+auth['token']}
  payload={'topic':topic,'request_id':str(uuid.uuid4())}
  response=await client.post(API+'/api/pbl',json=payload,headers=headers);response.raise_for_status();created=response.json();save(case/'created.json',created)
  again=await client.post(API+'/api/pbl',json=payload,headers=headers);assert again.json()['exerciseId']==created['exerciseId']
  identifier=created['exerciseId'];path=API+'/api/pbl/'+identifier
  print(name,'CREATED',identifier,flush=True)
  final=None
  for _ in range(600):
   response=await client.get(path,headers=headers);response.raise_for_status();detail=response.json();job=detail['job'] or {}
   state=(job.get('status'),job.get('step'),job.get('message'))
   if not events or events[-1]['state']!=list(state):
    events.append({'seconds':round(time.time()-start,2),'state':list(state)});print(name,*state,flush=True)
   if detail.get('artifact') or job.get('status') in ('failed','canceled'):
    final=detail;break
   await asyncio.sleep(2)
  assert final is not None,'generation deadline'
  save(case/'detail.json',final)
  with engine.connect() as connection:
   row=connection.execute(text('select candidate_private, checkpoint from pbl_exercises where id=:id'),{'id':identifier}).mappings().one()
   save(case/'private.json',dict(row))
  result={'case':name,'topic':topic,'exerciseId':identifier,'generationPassed':bool(final.get('artifact')),'job':final['job'],'events':events,'seconds':round(time.time()-start,2),'idempotentCreate':True}
  save(out/(name+'-generation.json'),result)
  if final.get('artifact'):
   artifact=final['artifact'];result.update(stepCount=len(artifact['tasks']),checkCount=len(artifact['checks']))
   save(out/(name+'-artifact.json'),artifact)
  save(out/(name+'-generation.json'),result)
  return result

async def main():
 results=await asyncio.gather(*(run(n,t) for n,t in cases.items()),return_exceptions=True)
 save(out/'generation-summary.json',[{'error':str(x),'type':type(x).__name__} if isinstance(x,Exception) else {k:v for k,v in x.items() if k not in ('job','events')} for x in results])
 print('COMPLETE',[(x.get('case'),x.get('generationPassed')) if isinstance(x,dict) else str(x) for x in results],flush=True)

asyncio.run(main())
