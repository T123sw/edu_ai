"""Isolated real-provider backend audit; no application deployment or production data."""
import os, sys, runpy
from pathlib import Path
from unittest.mock import patch
import dotenv
root=Path('/home/zxqs_ep/Edu_AI')
settings=dotenv.dotenv_values(root/'.env')
dotenv.load_dotenv=lambda *a,**kw:False
os.environ.update({k:v for k,v in settings.items() if v is not None})
os.environ['DATABASE_URL']='postgresql+psycopg://zxqs_ep@127.0.0.1:55439/edu_ai_agent_stage'
os.environ['COURSE_PREPARATION_ENABLED']='false'
for key in ('APP_STATE','MATERIAL','KNOWLEDGE','COURSE','COURSE_MEMBERSHIP','JOB'):
 os.environ[key+'_PERSISTENCE_MODE']='json'
out=root/'artifacts/preparation-audit-20260919'
from docx import Document
doc=Document()
paragraphs=[
 '工具调用入门课：模型选择，程序执行',
 '模型读取用户问题和已注册工具描述，可以返回工具名和参数。程序负责校验名称及参数并执行真实工具，再将工具结果交回模型生成回答。模型提出调用不代表工具已经执行。',
 '本课采用可手动追踪的伪代码，不接入任何外部模型 API，不学习 SDK 安装或鉴权。工具 add(a,b) 仅接受两个数字，执行 a+b。',
 '成功例：用户问 12 加 30。模型选择 add，参数 a=12、b=30。程序校验通过并执行，返回 42；模型根据真实返回值回答 42。日志依次记录用户问题、工具名称及参数、执行结果、最终回答。',
 '失败例：模型给出 add(a=12)，缺少 b。校验层返回 INVALID_ARGUMENT，message 为 b is required。不得运行 add，不得把错误当作 0 或编造成功结果，应要求补全参数。',
 '伪代码：如果工具名不是 add，返回 UNKNOWN_TOOL；否则检查 a 和 b 是否为数字，缺失或类型错误时返回 INVALID_ARGUMENT；仅通过检查后计算 a+b。工具请求的 call_id 与回传结果关联，成功和失败都要保留可追溯日志。',
 '检查题：谁执行工具？为什么缺少 b 时不能继续求和？成功例应得 42；失败例应记录未执行工具并提示补全 b。拓展练习：给出未知工具名 subtract，判断校验分支和错误类型。',
 '本附件足以学习和手工追踪以上最小伪代码流程，不提供实际模型 SDK 程序，不允许据此声称完成了真实 API 接入。',
]
for item in paragraphs: doc.add_paragraph(item)
source=out/'tool-calling.docx';doc.save(source)
from app.services.personal_knowledge_service import PersonalKnowledgeService
from app.services.runtime_config_resolver import runtime_config_resolver
from app.integrations.pdf.mineru_cloud import MinerUCloudProvider
personal=PersonalKnowledgeService(root_path=out/'personal')
mineru=MinerUCloudProvider(api_key=settings['PDF_MINERU_CLOUD_API_KEY'],base_url=settings.get('PDF_MINERU_CLOUD_BASE_URL'))
original_resolve=runtime_config_resolver.resolve
def resolve(provider,*args,**kwargs):
 if provider=='llm':
  return {'base_url':settings['DEEPSEEK_BASE_URL'],'api_key':settings['DEEPSEEK_API_KEY'],'model':settings.get('LLM_MODEL') or 'deepseek-v4-pro'}
 return original_resolve(provider,*args,**kwargs)
sys.argv=['smoke_preparation_stages.py','--database-url',os.environ['DATABASE_URL'],
 '--goal','我会 Python，但没有学过 Agent。请严格只依据附件，设计两个节点、合计 20 分钟的中文入门课：先理解模型与程序各自的职责，再学会追踪参数校验的成功与失败分支。先用 12 加 30 的例子，再解释原理；每个节点需要报告、习题和 AI 课堂。目标是读懂附件伪代码并手动解释日志，不要求接入真实模型 API，不学 SDK、鉴权、多 Agent 和部署。',
 '--minutes','20','--upload',str(source),'--uploaded-only','--full','--classroom','--log-dir',str(out/'full')]
with patch('app.services.personal_knowledge_service.PersonalKnowledgeService',return_value=personal),patch('app.integrations.pdf.get_pdf_parser',return_value=mineru),patch.object(runtime_config_resolver,'capture_snapshot',return_value={}),patch.object(runtime_config_resolver,'resolve',side_effect=resolve):
 runpy.run_path(str(root/'backend/src/scripts/smoke_preparation_stages.py'),run_name='__main__')
