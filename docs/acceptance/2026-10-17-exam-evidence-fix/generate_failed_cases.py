import os,json,sys,time,asyncio,base64
from pathlib import Path
from dataclasses import asdict
ROOT=Path('/home/zxqs_ep/Edu_AI');WORK=ROOT/'.runtime/exam-quality-v7';OUT=Path(os.environ.get('EXAM_CASE_OUT',str(ROOT/'docs/acceptance/2026-10-17-exam-evidence-fix')));OUT.mkdir(parents=True,exist_ok=True)
os.environ['DEEPTUTOR_HOME']=str(WORK/'modelrun')
from deeptutor.services.setup.init import DEFAULT_MAIN_SETTINGS,DEFAULT_AGENTS_SETTINGS
import yaml
settings=WORK/'modelrun/data/user/settings';settings.mkdir(parents=True,exist_ok=True)
for name,defaults in [('main.yaml',DEFAULT_MAIN_SETTINGS),('agents.yaml',DEFAULT_AGENTS_SETTINGS)]:
 if not (settings/name).exists():(settings/name).write_text(yaml.safe_dump(defaults,allow_unicode=True))
from deeptutor.services.config.runtime_settings import ensure_runtime_settings_files
ensure_runtime_settings_files()
from edu_deeptutor.runtime import model_scope
from deeptutor.agents.question.pipeline import QuestionPipeline,QuizTemplate,QuizPlan,build_openai_client
from deeptutor.core.context import UnifiedContext,Attachment
from deeptutor.runtime.stream_bus import StreamBus
models=json.load(sys.stdin)
if os.getenv('EXAM_TEXT_REASONING'):models['llm']['reasoning_effort']=os.environ['EXAM_TEXT_REASONING']
r=json.loads((ROOT/'.runtime/exam-real-paper-e2e/examgen_cee3918f6e261eafdd101822d15e2df0-record.json').read_text())
original_step=QuestionPipeline._run_labeled_step
traces={}
async def trace_step(self,**kwargs):
 result=await original_step(self,**kwargs);ordinal=self._case_ordinal;traces.setdefault(ordinal,[]).append({'label':kwargs.get('iter_meta',{}).get('label'),'model':self.model,'text':result.text});(WORK/f'trace-{ordinal}.json').write_text(json.dumps(traces[ordinal],ensure_ascii=False));return result
QuestionPipeline._run_labeled_step=trace_step
original_repair=QuestionPipeline._repair_quiz_payload
async def trace_repair(self,**kwargs):
 if not getattr(self,'_edu_text_stage',False):
  p=WORK/f'repair-input-{self._case_ordinal}.json';p.write_text(json.dumps({'issues':kwargs['issues'],'payload':kwargs['payload']},ensure_ascii=False))
 return await original_repair(self,**kwargs)
QuestionPipeline._repair_quiz_payload=trace_repair
requirements=r['request']['requirement'];rows=[];gate=asyncio.Semaphore(2)
async def one(ordinal):
 async with gate:
  node=r['blueprint']['questions'][ordinal-1]
  assets=[Attachment(type='image',filename=name,mime_type='image/jpeg',base64=r['parsed_sources'][0]['images'][name]) for name in node.get('images',[])]
  template=QuizTemplate(node['question_id'],node['concept'],node['question_type'],'medium',source='mimic',reference_question=node['reference_question'],blueprint=node,source_images=assets)
  with model_scope(models['vision_llm'],[],text_model=models['llm']):
   pipeline=QuestionPipeline(language='zh');pipeline._tool_list_text=lambda _: '- none';pipeline._use_native_tools=lambda _:False
   pipeline._case_ordinal=ordinal
   client=build_openai_client(pipeline.client_config)
   start=time.monotonic()
   try:
    pair=await pipeline._quiz_one(template=template,question_number=ordinal,total_questions=32,exploration_trace='',plan=QuizPlan('',[template]),previous_pairs=[],image_attachments=[],context=UnifiedContext(user_message=requirements),stream=StreamBus(),client=client)
    data=asdict(pair);(WORK/f'question-{ordinal}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));entry={'ordinal':ordinal,'passed':pair.metadata.get('review_passed'), 'issues':pair.metadata.get('issues',[]),'seconds':round(time.monotonic()-start,2)}
   except Exception as e:entry={'ordinal':ordinal,'passed':False,'error_type':type(e).__name__,'seconds':round(time.monotonic()-start,2)}
   rows.append(entry);(OUT/('tree-generation.json' if os.getenv('EXAM_CASE_ORDINALS') else 'seven-cases.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(entry,ensure_ascii=False),flush=True)
async def main():await asyncio.gather(*(one(i) for i in ([int(x) for x in os.environ['EXAM_CASE_ORDINALS'].split(',')] if os.getenv('EXAM_CASE_ORDINALS') else [12,14,26,27,29,30,32])))
asyncio.run(main())
