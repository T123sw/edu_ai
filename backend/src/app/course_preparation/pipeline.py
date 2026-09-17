"""Compose concrete preparation stages over existing storage, queue and generators."""
from .application import PreparationApplication
from .dependencies import engine
from .lifecycle_repository import LifecycleRepository
from .adapters.documents import PersonalDocumentReader
from .adapters.document_store import DocumentStore
from .adapters.memory import PreparationMemory
from .adapters.generation import GenerationAdapter
from .authorizer import PreparationReferenceAuthorizer
from .research_factory import research_factory
from .research_stages import ResearchStages
from .node_research import review_node
from .production_stages import ProductionStages
from .quality import QualityStages
from .delivery import DeliveryService


def build_pipeline(task_store):
    from app.services.personal_knowledge_service import PersonalKnowledgeService
    db=engine(); documents=DocumentStore(db,PersonalDocumentReader(PersonalKnowledgeService()))
    from .adapters.targets import TargetStore
    targets=TargetStore(db)
    repo=LifecycleRepository(db,authorizer=PreparationReferenceAuthorizer(db,documents,targets=targets))
    memory=PreparationMemory(repo); factory=research_factory(repo,documents,memory)
    def reviewer(context,checkpoint,state,node):
        request=repo.get(owner_user_id=context.owner_user_id,preparation_id=context.preparation_id).request
        return review_node(factory(context,request,checkpoint).model,state,node,preferences=checkpoint.get('memory_view'))
    research=ResearchStages(repo,factory,documents,memory=memory,node_reviewer=reviewer)
    generation=GenerationAdapter(repo,task_store)
    production=ProductionStages(repo,generation,memory)
    quality=QualityStages(repo,generation,memory,factory)
    delivery=DeliveryService(repo)
    app=PreparationApplication(repo,task_store,{**research.handlers(),'produce':production.produce,
        'review':quality.review,'repair':quality.repair,'commit':delivery.commit},
        capabilities=('research','report','quiz','classroom'))
    from app.services.runtime_config_resolver import runtime_config_resolver
    app.service.snapshot_factory=lambda owner:runtime_config_resolver.capture_snapshot(memory.subject(owner))
    app.documents=documents; app.delivery=delivery
    return app
