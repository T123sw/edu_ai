import json, tempfile
from types import SimpleNamespace as N
from unittest.mock import patch
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.agent_tools.context import ToolExecutionContext
from app.chat.runtime.agent_tools.executor import execute_tool
from app.chat.runtime.nodes.executor import executor_node, _emit_compiled_report_result
from app.chat.runtime.graph.routes import route_after_executor
from app.chat.runtime.agent_tools.handlers.verification import handle_verify_task
from app.chat.runtime.verification.plan_verifier import verify_plan_execution

cap=N(allow_rag=False,allow_web=False,allow_image_search=False,selected_doc_ids=[],source_mode='none')
rows=[]
for q in ['不要生成报告，只解释报告的结构','请生成十道递归练习题，不要报告','解释一下学生学习进度的定义','写一篇递归教学博客','生成递归教案']:
    req=N(question=q,owner='audit',course_id='audit',conversation_id='audit',actor_role='teacher',workspace_context=None)
    c=extract_task_contract(req,cap,{})
    rows.append(dict(question=q,intent=c.intent,resources=c.resource_types,actions=[s.internal_action for s in compile_plan(c).steps]))
print('INTENT',json.dumps(rows,ensure_ascii=False))
# The same pure compiled QA step used after successful retrieval.
req=N(question='什么是递归',owner='audit',course_id='audit',conversation_id='audit',actor_role='teacher',workspace_context=None)
c=extract_task_contract(req,cap,{})
plan=compile_plan(c).to_dict()
class G:
    def stream_chat_with_tools(self,*a,**kw):
        yield {'type':'text_delta','content':'递归是函数调用自身。'}
ctx=ToolExecutionContext(capability=cap,max_steps=6,request=req)
events=[]
state=dict(messages=[{'role':'user','content':req.question}],task_contract=c.model_dump(mode='json'),current_plan=plan,plan_mode='strict',plan_step_index=0,tool_exchange=[],retrieval_sources=[])
rt=dict(ctx=ctx,t_start=__import__('time').perf_counter(),timeout_seconds=40,agent_gateway=G(),tool_schemas=[],request=req,conv_id='audit')
with patch('app.chat.runtime.nodes.executor.get_config',return_value={'configurable':{'runtime':rt}}),patch('app.chat.runtime.nodes.executor.get_stream_writer',return_value=events.append):
    updates=executor_node(state)
print('QA_TERMINATION',json.dumps(dict(route=route_after_executor({**state,**updates}),plan_actions=[s['internal_action'] for s in plan['steps']],executed_tools=ctx.trace['agent_steps'],result_types=[e['type'] for e in events]),ensure_ascii=False))
# Transient provider failure followed by success, exact same legitimate retry args.
calls=[]
def flaky(name,args,ctx):
    calls.append(1)
    return {'ok':False,'error':'transient_provider_error','summary':'temporary','payload':{}} if len(calls)==1 else {'ok':True,'summary':'recovered','payload':{}}
ctx2=ToolExecutionContext(capability=N(allow_rag=True),max_steps=6,request=req)
with patch('app.chat.runtime.agent_tools.executor.get_tool_handler',return_value=flaky):
    a=execute_tool('rag_search',{'query':'递归'},ctx2)
    b=execute_tool('rag_search',{'query':'递归'},ctx2)
print('RETRY_CACHE',json.dumps(dict(provider_calls=len(calls),first_ok=a['ok'],second_ok=b['ok'],trace_count=len(ctx2.trace['agent_steps']))))
# Failed execution's verification tool still reports ok and terminal node completes.
ctx.current_plan={'steps':[{'expected_tools':['rag_search']},{'internal_action':'report_result','user_title':'汇报结果'}]}
ctx.trace={'agent_steps':[{'tool':'rag_search','ok':False,'error':'timeout'}]}
v=handle_verify_task('verify_task',{},ctx)
s2={**state,'current_plan':ctx.current_plan,'plan_step_index':1,'pending_tasks':[]}
ev=[]
_emit_compiled_report_result(ev.append,s2,rt,ctx)
final=next(e['payload'] for e in ev if e['type']=='result')
print('VERIFICATION',json.dumps(dict(tool_ok=v['ok'],decision=ctx.verification_report['decision'],repair=ctx.verification_report['repair_directive']['action'],action=final['action'],message=final['message']['content']),ensure_ascii=False))
# Retried successfully tool remains counted as a failed execution.
p={'steps':[{'expected_tools':['rag_search']}]}
v=verify_plan_execution(p,{'agent_steps':[{'tool':'rag_search','ok':False},{'tool':'rag_search','ok':True,'evidence_count':1}]})
print('RECOVERED_AUDIT',json.dumps(dict(decision=v.decision,failed_tools=v.execution_audit.failed_tools)))
old={'active_draft_outline':{'subject':'链表','resource_type':'report','outline_markdown':'# 链表大纲'}}
req.question='生成递归教案'
c=extract_task_contract(req,cap,old)
p=compile_plan(c,old)
print('STALE_OUTLINE',json.dumps(dict(topic=c.topic,resources=c.resource_types,confirmation_policy=c.confirmation_policy,actions=[s.internal_action for s in p.steps],outline_subject=old['active_draft_outline']['subject']),ensure_ascii=False))
req.question='生成十二道递归练习题，难度高，只要选择题'
c=extract_task_contract(req,cap,{})
print('CONSTRAINTS',json.dumps(dict(question=req.question,constraints=c.constraints),ensure_ascii=False))
