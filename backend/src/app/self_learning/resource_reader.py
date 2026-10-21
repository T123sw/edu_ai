"""Authorized exact versions and bounded excerpts; never silently use latest."""
import hashlib
import json
from fastapi import HTTPException
from .contracts import ResourceRef
from .classroom_context import find_scene, scene_content
from .report_document import report_markdown, anchored_report
from .source_navigation import quiz_question, search_report


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
    from .hyperframes_context import native_content
    native = native_content(material)
    if native:
        return json.dumps(native, ensure_ascii=False, sort_keys=True)
    if material.get('material_type') == 'report':
        return report_markdown(material)
    content = material.get('content')
    if isinstance(content, str):
        return content
    return json.dumps({k: material[k] for k in ('title', 'content', 'questions', 'scenes') if k in material}, ensure_ascii=False, sort_keys=True)


def excerpt(material, *, selected_text='', locator=None, query='', max_chars=4000):
    from .hyperframes_context import native_content, classroom_timeline_context
    native = native_content(material)
    if native:
        context = classroom_timeline_context(material, locator)
        if query and not locator:
            matches = [s for s in native['timeline']['segments'] if query.casefold() in (s['title']+' '+s['narration']+' '+s['visual_description']).casefold()]
            if matches:
                context = classroom_timeline_context(material, {'kind':'hyperframes','seconds':matches[0]['start']})
        resolved = None
        if 'seconds' in context:
            resolved = {'kind':'hyperframes','seconds':context['seconds'],'content_hash':native['project']['digest']}
            if context.get('current_segment'):
                resolved['segment_id'] = context['current_segment']['id']
        from .hyperframes_context import compact_surroundings
        body = json.dumps(context, ensure_ascii=False)
        while len(body) > max_chars and compact_surroundings(context):
            body = json.dumps(context, ensure_ascii=False)
        truncated = bool(context.get('context_truncated')) or len(body) > max_chars
        return {'excerpt':body[:max_chars], 'resolved_locator':resolved, 'content_hash':hashlib.sha256(material_text(material).encode()).hexdigest(),
            'location_quality':context['location_quality'], 'truncated':truncated}
    text = material_text(material)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    quality, offset = 'approximate', 0
    resolved = None
    if locator and locator.get('kind') == 'quiz':
        question = quiz_question(material, locator)
        body = json.dumps({'question_number': locator['question_index'] + 1, 'question': question}, ensure_ascii=False)
        return {'excerpt': body[:max_chars], 'resolved_locator': locator, 'location_quality': 'exact',
                'content_hash': content_hash, 'truncated': len(body) > max_chars}
    if locator and locator.get('kind') == 'document' and str(locator.get('block_id', '')).startswith('report-v1:'):
        if material.get('material_type') != 'report':
            raise HTTPException(409, '段落引用不属于报告资料')
        return {**anchored_report(material, locator['block_id'], max_chars), 'content_hash': content_hash}
    if material.get('material_type') == 'report' and query and not selected_text and (locator or {}).get('offset') is None:
        found = search_report(material, query, max_chars)
        if found:
            return {**found, 'content_hash': content_hash}
        return {'excerpt': '', 'resolved_locator': None, 'location_quality': 'unresolved',
                'content_hash': content_hash, 'truncated': False, 'search_matched': False}
    if locator and locator.get('kind') == 'classroom':
        scene = find_scene(material, locator.get('scene_id'))
        text = json.dumps(scene_content(scene), ensure_ascii=False)
        quality, resolved = 'exact', {'kind': 'classroom', 'scene_id': scene['id']}
    elif material.get('scenes'):
        text = json.dumps([scene_content(scene) for scene in material['scenes']], ensure_ascii=False)
        if query and query.casefold() in text.casefold():
            offset = max(0, text.casefold().index(query.casefold()) - 300)
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
