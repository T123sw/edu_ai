"""Authenticated bridge from legacy username callers to committed preparation data."""
import os
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database.models import User, Course, CourseMembership, PreparedCoursePointer, PreparedManifestVersion
from app.course_preparation.delivery import DeliveryService
from app.persistence.postgres_material_repository import PostgresMaterialRepository


class PreparedCourses:
    def __init__(self, engine):
        self.engine = engine
        self.delivery = DeliveryService(SimpleNamespace(engine=engine))
        self.materials = PostgresMaterialRepository(engine)

    def identity(self, session, username):
        user = session.scalar(select(User).where(User.username == username, User.is_disabled.is_(False)))
        if user is None:
            raise HTTPException(404, '课堂不存在或无权访问')
        return user

    def lookup(self, username, course_id):
        with Session(self.engine) as session:
            user = self.identity(session, username)
            pointer = session.get(PreparedCoursePointer, (user.user_id, course_id))
            if pointer is None:
                return None
            member = session.get(CourseMembership, (course_id, user.user_id))
            course = session.get(Course, course_id)
            if member is None or course is None:
                raise HTTPException(404, '课堂不存在或无权访问')
            info = {**(course.raw_payload or {}), 'id': course_id, 'title': course.title,
                    'description': course.description, 'created_by': user.username if member.role == 'owner' else course.created_by}
            return info, SimpleNamespace(course_id=course_id, user_id=username, role=member.role)

    def list(self, username):
        with Session(self.engine) as session:
            user = self.identity(session, username)
            return list(session.scalars(select(PreparedCoursePointer.course_id).join(CourseMembership,
                (CourseMembership.course_id == PreparedCoursePointer.course_id) &
                (CourseMembership.user_id == PreparedCoursePointer.owner_user_id)).where(
                PreparedCoursePointer.owner_user_id == user.user_id)))

    def manifest(self, username, course_id, ref=None):
        if self.lookup(username, course_id) is None:
            return None
        with Session(self.engine) as session:
            owner = self.identity(session, username).user_id
        try:
            value = self.delivery.read(owner, course_id, ref.version if ref else None)
        except (PermissionError, LookupError) as exc:
            raise HTTPException(409, '课程版本不可访问') from exc
        if ref and value['manifest_id'] != ref.manifest_id:
            raise HTTPException(409, '课程版本引用不匹配')
        return value

    def material(self, username, course_id, kind, material_id, version=None):
        if self.lookup(username, course_id) is None:
            raise HTTPException(404, '课堂不存在或无权访问')
        value = self.materials.get_version(course_id, kind, material_id, version) if version else self.materials.get(course_id, kind, material_id)
        if not value or value.get('owner_user_id') != username:
            raise HTTPException(404, '资料不存在或无权访问')
        return value

    def historical_topic(self, username, course_id, topic_id, ref=None):
        if self.lookup(username, course_id) is None:
            return None
        from app.course_preparation.tool_registry import digest
        with Session(self.engine) as session:
            owner=self.identity(session,username).user_id
            rows=session.scalars(select(PreparedManifestVersion).where(
                PreparedManifestVersion.owner_user_id==owner,PreparedManifestVersion.course_id==course_id
            ).order_by(PreparedManifestVersion.version.desc()))
            for row in rows:
                if digest(row.payload)!=row.content_digest: raise HTTPException(409,'历史课程版本校验失败')
                node=next((n for n in row.payload['nodes'] if n['node_id']==topic_id),None)
                if node and (ref is None or any(r['resource_id']==ref.material_id and r['resource_type']==ref.material_type and r['version']==ref.version for r in node['resources'])):
                    return node
        return None


def configured_prepared_courses():
    if os.getenv('COURSE_PREPARATION_ENABLED', '').lower() not in {'true', '1', 'yes'}:
        return None
    from app.course_preparation.dependencies import engine
    return PreparedCourses(engine())
