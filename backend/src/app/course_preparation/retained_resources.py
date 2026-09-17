"""Read exact retained resources for review without submitting generation jobs."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import MaterialVersion,User
from .tool_registry import digest


def read_retained(repository,context,checkpoint):
    nodes=set(checkpoint.get('retained_node_ids',[]))
    if not nodes:return []
    result=[]
    with Session(repository.engine) as db:
        user=db.get(User,context.owner_user_id)
        for node in checkpoint['target_snapshot']['manifest']['nodes']:
            if node['node_id'] not in nodes:continue
            for resource in node['resources']:
                row=db.scalar(select(MaterialVersion).where(MaterialVersion.course_id==checkpoint['target_snapshot']['manifest']['course_id'],MaterialVersion.material_type==resource['resource_type'],MaterialVersion.material_id==resource['resource_id'],MaterialVersion.version==resource['version']))
                if row is None or row.payload.get('content_hash')!=resource['content_sha256']:raise ValueError('RETAINED_RESOURCE_CHANGED')
                if user is None or (row.payload.get('owner_user_id')!=user.username and row.payload.get('visibility')!='course'):raise PermissionError('RETAINED_RESOURCE_UNAVAILABLE')
                artifact=row.payload.get('preparation_artifact') or {'content':row.payload['content'],'title':row.payload['title']}
                if row.payload.get('content')!=artifact.get('content'):raise ValueError('RETAINED_RESOURCE_BODY_CHANGED')
                actual=digest(artifact) if row.payload.get('preparation_artifact') else digest({'content':row.payload.get('content'),'title':row.payload.get('title'),'artifact_type':resource['resource_type']})
                if actual!=resource['content_sha256']:raise ValueError('RETAINED_RESOURCE_BODY_CHANGED')
                spec={'node_id':node['node_id'],'objectives':[o['text'] for o in node['objectives']]}
                result.append({'artifact_id':'retained:'+resource['resource_id'],'resource_type':resource['resource_type'],
                    'resource_id':resource['resource_id'],'resource_version':resource['version'],'status':'draft','spec':spec,
                    'spec_digest':digest(spec),'content':artifact,'content_digest':digest(artifact)})
    return result
