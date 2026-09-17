"""Live P3 diagnostic on an isolated database; result is a path, never course-ready."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database-url',required=True)
    parser.add_argument('--goal',required=True)
    parser.add_argument('--minutes',type=int,default=60)
    parser.add_argument('--upload',action='append',default=[])
    parser.add_argument('--uploaded-only',action='store_true')
    parser.add_argument('--log-dir',required=True)
    args=parser.parse_args()
    if 'edu_ai_agent_stage' not in args.database_url: raise ValueError('Use the dedicated stage test database')
    from core.config import Config
    from app.database.models import User
    from app.services.personal_knowledge_service import PersonalKnowledgeService
    from app.services.runtime_config_resolver import runtime_config_resolver
    from app.course_preparation.adapters.documents import PersonalDocumentReader
    from app.course_preparation.adapters.document_store import DocumentStore
    from app.course_preparation.adapters.memory import PreparationMemory
    from app.course_preparation.authorizer import PreparationReferenceAuthorizer
    from app.course_preparation.lifecycle_repository import LifecycleRepository
    from app.course_preparation.research_factory import research_factory
    from app.course_preparation.research_stages import ResearchStages
    from app.course_preparation.node_research import review_node
    from app.course_preparation.runner import PreparationRunner
    from app.course_preparation.schemas import PreparationRequest
    from app.course_preparation.runtime_contracts import BudgetLimits
    engine=create_engine(args.database_url)
    owner='stage-smoke-'+uuid4().hex
    with Session(engine) as session,session.begin():
        session.add(User(user_id=owner,username=owner,password_hash='disabled-live-test-account',role='student'))
    personal=PersonalKnowledgeService()
    documents=DocumentStore(engine,PersonalDocumentReader(personal))
    uploads=[]
    for file in args.upload:
        path=Path(file)
        record=personal.create_document(owner_user_id=owner,filename=path.name,file_data=path.read_bytes())
        uploads.append(documents.register(owner,record['id']))
    repo=LifecycleRepository(engine,authorizer=PreparationReferenceAuthorizer(engine,documents))
    memory=PreparationMemory(repo); factory=research_factory(repo,documents,memory)
    def check_node(context,checkpoint,state,node):
        request=repo.get(owner_user_id=owner,preparation_id=context.preparation_id).request
        agent=factory(context,request,checkpoint)
        return review_node(agent.model,state,node,preferences=checkpoint.get('memory_view'))
    stages=ResearchStages(repo,factory,documents,memory=memory,node_reviewer=check_node)
    runner=PreparationRunner(repo,stages.handlers())
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal=args.goal,uploads=uploads,
        overrides={'total_minutes':args.minutes},source_policy={'mode':'uploaded_only' if args.uploaded_only else 'uploads_preferred' if uploads else 'open'})
    task=repo.submit(owner,request,config_snapshot=runtime_config_resolver.capture_snapshot(owner),
                     limits=BudgetLimits(seconds=1800,cost_micro_usd=20_000_000))
    output=Path(args.log_dir); output.mkdir(parents=True,exist_ok=False)
    def write(name,value): (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    write('request.json',request.model_dump(mode='json'))
    write('run.json',{'owner':owner,'preparation_id':task['preparation_id'],'started_at':datetime.now(timezone.utc).isoformat(),'scope':'P3 research only','course_ready':False})
    from app.database.models import PreparationExecution, PreparationAction
    from sqlalchemy import select
    for step in range(100):
        public=repo.get_public(owner,task['preparation_id'])
        if public['status'] in ('failed','canceled') or public['stage']=='produce': break
        result=runner.run_step(task['preparation_id'],worker_id=f'smoke-{step}')
        with Session(engine) as session:
            execution=session.get(PreparationExecution,(task['preparation_id'],public['attempt_no']))
            checkpoint=execution.checkpoint
        write(f'{step:03d}-{public["stage"]}.json',{'result':result,'checkpoint':checkpoint})
        print(step,public['stage'],result,flush=True)
    final=repo.get_public(owner,task['preparation_id'])
    write('final.json',final)
    events=[]
    while True:
        batch=repo.events(owner_user_id=owner,preparation_id=task['preparation_id'],after=events[-1]['sequence'] if events else 0,limit=200)
        if not batch: break
        events.extend(e.model_dump(mode='json') for e in batch)
    write('events.json',events)
    with Session(engine) as session:
        actions=session.scalars(select(PreparationAction).where(PreparationAction.preparation_id==task['preparation_id'])).all()
        write('actions.json',[{'kind':a.kind,'payload':a.payload,'status':a.status,'receipt':a.receipt,'reserved':a.reserved,'consumed':a.consumed} for a in actions])
    print(json.dumps(final,ensure_ascii=False),flush=True)
    raise SystemExit(0 if final['stage']=='produce' and final['status']=='running' else 1)

if __name__=='__main__': main()
