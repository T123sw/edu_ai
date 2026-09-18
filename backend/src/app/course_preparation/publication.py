"""Explicit publication copies verified content in one SQL transaction."""
from copy import deepcopy
import time
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User,Course,CourseMembership,PreparedCoursePointer,PreparedManifestVersion,MaterialVersion
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.services.material_publication_service import MaterialPublicationService
from .publication_models import PublishedPreparationManifest as Public,PublishedPreparationPointer as Pointer
from .tool_registry import digest
from .manifest import CourseManifest

class PreparedPublication:
    def __init__(self,engine):self.engine=engine

    @staticmethod
    def current(db,course,version=None):
        pointer=db.get(Pointer,course)
        if pointer is None:return None
        row=db.get(Public,(course,version or pointer.version))
        if row and digest(row.payload)!=row.content_digest:raise ValueError('PUBLISHED_MANIFEST_CORRUPTED')
        return row

    def publish(self,owner,course):
        with Session(self.engine) as db,db.begin():
            user=db.scalar(select(User).where(User.username==owner,User.is_disabled.is_(False)))
            lock=db.scalar(select(Course).where(Course.course_id==course).with_for_update())
            member=db.get(CourseMembership,(course,user.user_id)) if user else None
            if lock is None or user is None or user.role not in ('teacher','admin') or member is None or member.role!='owner':raise PermissionError('PUBLICATION_NOT_AUTHORIZED')
            source_pointer=db.get(PreparedCoursePointer,(user.user_id,course))
            source=db.get(PreparedManifestVersion,(user.user_id,course,source_pointer.version)) if source_pointer else None
            if source is None or digest(source.payload)!=source.content_digest:raise ValueError('SOURCE_MANIFEST_UNAVAILABLE')
            previous=self.current(db,course)
            if previous and previous.source_digest==source.content_digest:return previous.payload
            manifest=deepcopy(source.payload);version=(previous.version if previous else 0)+1
            manifest.update(space='course',manifest_id='published_'+digest(course)[:32],version=version)
            materials=PostgresMaterialRepository(self.engine);mapping={}
            for node in manifest['nodes']:
                for resource in node['resources']:
                    old_id=resource['resource_id'];raw=db.scalar(select(MaterialVersion).where(MaterialVersion.course_id==course,MaterialVersion.material_type==resource['resource_type'],MaterialVersion.material_id==old_id,MaterialVersion.version==resource['version']))
                    if raw is None or raw.payload.get('owner_user_id')!=owner or raw.payload.get('content_hash')!=resource['content_sha256']:raise PermissionError('PUBLICATION_SOURCE_UNREADABLE')
                    if (digest(raw.payload.get('preparation_artifact'))!=resource['content_sha256']
                            or raw.payload.get('content')!=raw.payload['preparation_artifact'].get('content')):
                        raise ValueError('PUBLICATION_SOURCE_CONTENT_CHANGED')
                    shared_id='shared_'+digest([course,old_id])[:32]
                    existing=db.scalar(select(MaterialVersion).where(MaterialVersion.course_id==course,MaterialVersion.material_type==resource['resource_type'],MaterialVersion.material_id==shared_id,MaterialVersion.version==resource['version']))
                    if existing:
                        payload=existing.payload
                        actual=digest({'content':payload.get('content'),'title':payload.get('title'),'artifact_type':resource['resource_type']})
                        if actual!=payload.get('content_hash'):raise ValueError('PUBLISHED_RESOURCE_CORRUPTED')
                    else:
                        payload=MaterialPublicationService(None)._snapshot_payload(source=raw.payload,material_type=resource['resource_type'],owner_user_id=owner,published_paths=[])
                        # Prepared bodies have already passed the native validator;
                        # keep DSL identifiers/order while excluding draft audit data.
                        payload['content']=deepcopy(raw.payload['content'])
                        if resource['resource_type'] in ('quiz','classroom'):
                            from app.chat.harness.reviewed_resource import validate_resource
                            validate_resource(resource['resource_type'],payload['content'])
                        if resource['resource_type']=='classroom':payload.update(payload['content'])
                        if resource['resource_type']=='quiz':payload['questions']=payload['content']['questions']
                        payload.update(course_id=course,material_type=resource['resource_type'],material_id=shared_id,version=resource['version'],visibility='course',owner_user_id=owner,learning_course_resource=True)
                        payload['content_hash']=digest({'content':payload.get('content'),'title':payload.get('title'),'artifact_type':resource['resource_type']})
                        materials.upsert(payload,session=db)
                    resource.update(resource_id=shared_id,content_sha256=payload['content_hash']);mapping[old_id]=shared_id
                for check in node['checks']:check['resource_id']=mapping[check['resource_id']]
            manifest=CourseManifest.model_validate(manifest).model_dump(mode='json')
            db.add(Public(course_id=course,version=version,source_owner_user_id=user.user_id,source_digest=source.content_digest,payload=manifest,content_digest=digest(manifest),created_at=time.time()))
            pointer=db.get(Pointer,course)
            if pointer:pointer.version=version
            else:db.add(Pointer(course_id=course,version=version))
            return manifest
