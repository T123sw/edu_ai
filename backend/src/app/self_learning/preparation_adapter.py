"""Explicit learning requests hand off to the durable preparation service once."""
import re
from uuid import uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User
from app.course_preparation.schemas import PreparationRequest
from .contracts import ResourceRef
from .progress_repository import digest
from .resource_reader import exact_material


def requests_saved_work(question):
    if any(term in question for term in ('不要生成','无需生成','不要保存','不需要保存','只解释','仅解释')): return False
    return any(term in question for term in ('保存','生成一份','补充资料','修订资料','修改这份','调整学习路径','调整课程','创建课程'))


class PreparationAdapter:
    def __init__(self,learning,service=None): self.learning,self.service=learning,service

    def submit(self,turn,operation,goal,*,resource_ref=None,resource_type='report',changes=()):
        if not requests_saved_work(turn['request']['question']): raise HTTPException(422,'当前原话没有要求保存或修改学习资料')
        markers={'create_course':('创建课程','新课程','新建课程'),
                 'adjust_course':('调整学习路径','调整课程','调整路线'),
                 'revise_resource':('修订','修改这份','改写','更新这份')}
        if operation in markers and not any(word in turn['request']['question'] for word in markers[operation]):
            raise HTTPException(422,'本轮没有明确要求此类修改，请确认目标操作')
        self.learning.require(turn['course_id'],turn['owner'])
        prepared=self.learning.prepared_courses
        if prepared is None: raise HTTPException(503,'课程准备尚未启用')
        manifest=prepared.manifest(turn['owner'],turn['course_id'])
        if manifest is None and operation!='create_course': raise HTTPException(409,'当前课程尚无可修订的版本清单')
        with Session(prepared.engine) as db:
            user=db.scalar(select(User).where(User.username==turn['owner'],User.is_disabled.is_(False)))
            if user is None: raise HTTPException(403,'用户不可用')
            owner_id=user.user_id
        service=self.service
        if service is None:
            try:
                from app.course_preparation.application import application
                service=application().service
            except RuntimeError as exc: raise HTTPException(503,'课程准备暂不可用') from exc
        request_id=uuid5(NAMESPACE_URL,'learning-preparation:'+turn['turn_id'])
        if getattr(service,'repository',None):
            with Session(service.repository.engine) as db:
                previous=service.repository._request_record(db,owner_id,request_id)
                previous_id=previous.preparation_id if previous else None
            if previous_id:
                return service.get(owner_id,previous_id)
        target=None
        if operation!='create_course':
            target={'course_id':turn['course_id'],'base_manifest_version':manifest['version']}
            if operation in ('supplement_node','revise_resource'): target['node_id']=turn['topic_id']
            if operation=='revise_resource':
                current=ResourceRef.model_validate(turn['request']['reading_context']['resource_ref'])
                ref=ResourceRef.model_validate(resource_ref) if resource_ref else current
                if ref!=current: raise HTTPException(422,'请在目标资料中明确发起修订，避免选错资料')
                exact_material(self.learning,turn['owner'],ref)
                target.update(resource_id=ref.material_id,base_resource_version=ref.version)
            if operation=='adjust_course': target['base_route_version']=manifest['route_version']
        # Preserve the original command as the authoritative requirement text.
        # Model paraphrases must not drop constraints or become fabricated quotes.
        goal = turn['request']['question']
        data={'operation':operation,'goal':goal,'target':target,'origin':{'conversation_id':turn['session_id'],'message_id':turn['turn_id']+':user'},
            'overrides':{'required_resource_types':[resource_type]},'requested_changes':list(changes) if operation=='adjust_course' else [],'source_policy':{'mode':'open'}}
        # Bind only to the durable original turn and complete command, never a model call ID.
        data['request_id']=request_id
        request=PreparationRequest.model_validate(data)
        return service.submit(owner_id,request)
