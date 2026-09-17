"""Authorized exact versions and bounded excerpts; never silently use latest."""
import hashlib
import json
from fastapi import HTTPException
from .contracts import ResourceRef


def exact_material(learning, owner, ref: ResourceRef):
    current = learning.material(ref.course_id, ref.material_type, ref.material_id, owner)
    if current.get('version') == ref.version:
        return current
    if getattr(learning, 'prepared_courses', None) and learning.prepared_courses.lookup(owner, ref.course_id):
        return learning.prepared_courses.material(owner, ref.course_id, ref.material_type, ref.material_id, ref.version)
    if learning.manager._material_uses_postgres():
        old = learning.manager._material_repository().get_version(ref.course_id, ref.material_type, ref.material_id, ref.version)
    else:
        old = current.get('revision_history', {}).get(str(ref.version))
    if not old or old.get('version') != ref.version:
        raise HTTPException(409, '指定资料版本不可读取，请重新打开可用版本')
    if not learning.manager._material_owner_matches(old, owner):
        raise HTTPException(404, '资料不存在或无权访问')
    return old


def material_text(material):
    content = material.get('content')
    if isinstance(content, str):
        return content
    return json.dumps({k: material[k] for k in ('title', 'content', 'questions', 'scenes') if k in material}, ensure_ascii=False)


def excerpt(material, *, selected_text='', locator=None, query='', max_chars=4000):
    text = material_text(material)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    quality, offset = 'approximate', 0
    resolved = None
    if locator and locator.get('kind') == 'classroom':
        scene = next((s for s in material.get('scenes', []) if s.get('id') == locator.get('scene_id')), None)
        if scene:
            text = json.dumps(scene, ensure_ascii=False)
            quality, resolved = 'exact', locator
    elif selected_text and text.count(selected_text) == 1:
        offset = max(0, text.index(selected_text) - min(500, max_chars // 4))
        quality = 'exact'
        resolved = {'kind': 'document', 'offset': text.index(selected_text), 'content_hash': content_hash}
    elif locator and locator.get('kind') == 'document' and locator.get('content_hash') == content_hash and locator.get('offset') is not None and locator['offset'] < len(text):
        offset, quality, resolved = locator['offset'], 'exact', locator
    elif query and query.casefold() in text.casefold():
        offset = max(0, text.casefold().index(query.casefold()) - 300)
    # Pixel positions have no reliable mapping to source characters.
    return {'excerpt': text[offset:offset + max_chars], 'resolved_locator': resolved,
            'location_quality': quality, 'content_hash': content_hash, 'truncated': len(text) - offset > max_chars}
