"""Translate a frozen tutoring turn to the preparation service's public contract."""
import re
from uuid import uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.production_models import ProductionRun
from app.course_preparation.production_service import digest
from .contracts import ResourceRef
from .resource_reader import exact_material, material_text
from .notifications import NotificationService

class PreparationAdapter:
    def __init__(self, learning, service):
        self.learning, self.service = learning, service
        self.notifications = NotificationService(self)

    def submit(self, turn, args, packet, operation_id):
        # Persisted user message, never the model's paraphrase, authorizes the effect.
        saved = self.learning.turn_repository.get(turn['owner'], turn['turn_id'])
        if saved['request'] != turn['request']:
            raise HTTPException(409, '轮次内容不一致')
        question = saved['request']['question']
        clean = re.sub(r'“[^”]*”|「[^」]*」|"[^"]*"', '', question)
        if re.search(r'不要|不需要|别(?:生成|保存|修改)|不用|假如|假设|如果|例如', clean) or not re.search(r'保存|生成(?:并保存|一份|一道)|添加|加入|修改当前|修改这份', clean):
            raise HTTPException(422, '请先明确要保存或修改的资料')
        operation = args.get('operation')
        if operation not in {'supplement_node','revise_resource'}:
            raise HTTPException(422, '不支持的操作')
        owner,course,topic = saved['owner'],saved['course_id'],saved['topic_id']
        self.learning.require(course, owner)
        if not args.get('goal') or len(args['goal']) > 2000:
            raise HTTPException(422,'目标无效')
        types = args.get('resource_types') or ['report']
        if len(set(types)) != len(types) or set(types) - {'report','quiz'}:
            raise HTTPException(503,'所请求的资料生产器尚不可用')
        intent_hash=digest(args)
        with Session(self.service.engine) as db:
            old = db.scalar(select(ProductionRun).where(ProductionRun.owner==owner, ProductionRun.operation_id==operation_id))
            if old:
                if old.payload.get('intent_hash') != intent_hash:
                    raise HTTPException(409,'操作标识已用于其他请求')
                return self.get(owner,old.preparation_id)
        handle = args.get('resource_handle')
        if operation == 'revise_resource':
            if not re.search(r'修改|修订|改写|更新', clean):
                raise HTTPException(422,'缺少修改授权')
            if handle:
                ref = packet.get('handles',{}).get(handle)
                # A model-issued handle alone is not disambiguation by the user.
                if ref != saved['request']['reading_context']['resource_ref'] or not re.search(r'当前|这份|正在读',clean):
                    raise HTTPException(422,'请明确要修改哪份资料')
            elif re.search(r'当前|这份|正在读',clean):
                ref=saved['request']['reading_context']['resource_ref']
            else:
                raise HTTPException(422,'请明确要修改哪份资料')
        else:
            ref=saved['request']['reading_context']['resource_ref']
        from .context_builder import ContextBuilder
        ContextBuilder(self.learning).authorize(owner,course,topic,{'resource_ref':ref})
        material=exact_material(self.learning,owner,ResourceRef.model_validate(ref))
        if material.get('version') != self.learning.material(course,ref['material_type'],ref['material_id'],owner).get('version'):
            raise HTTPException(409,'请先确认当前可用资料版本')
        source={'ref':ref,'hash':digest(material),'text':material_text(material)[:9000]}
        version=self.service.baseline(owner,course)
        target={'course_id':course,'node_id':topic,'base_manifest_version':version}
        if operation=='revise_resource':
            target.update(resource_id=ref['material_id'],base_resource_version=ref['version'])
            if types != [ref['material_type']]:
                raise HTTPException(422,'修订需保持资料类型')
        request=PreparationRequest(request_id=uuid5(NAMESPACE_URL,owner+':'+operation_id), operation=operation,
            goal=question+'\n具体要求：'+args['goal'],target=target,
            origin={'conversation_id':saved['session_id'],'message_id':saved['turn_id']+':user'},
            overrides={'required_resource_types':types})
        return self.service.accept(owner,request,operation_id,source,saved['request'].get('_config_snapshot',{}),intent_hash=intent_hash)

    def get(self, owner, preparation_id):
        return self.service.get(owner,preparation_id)

    def list(self, owner, course):
        return self.service.list(owner,course)
