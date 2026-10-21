"""Exact-version, time-based teaching context; visual metadata is not a screenshot."""
from fastapi import HTTPException
from app.integrations.hyperframes.contracts import validate_content, resolve_position


def native_content(material):
    body = material.get('content')
    if isinstance(body, dict) and body.get('format') == 'hyperframes/v1':
        return body
    if material.get('format') == 'hyperframes/v1':
        return {k: material[k] for k in ('format', 'title', 'project', 'timeline', 'exports') if k in material}
    return None


def timeline_context(content, seconds, segment_id=None):
    try:
        resolved = resolve_position(content, seconds)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, '播放位置与指定课堂版本不符') from exc
    segment = resolved['segment']
    if segment_id is not None and (segment is None or segment['id'] != segment_id):
        raise HTTPException(409, '章节与播放时间不符，请重新定位课堂')
    segments = content['timeline']['segments']
    previous = next((s for s in reversed(segments) if s['end'] <= seconds and (segment is None or s['id'] != segment['id'])), None)
    following = next((s for s in segments if s['start'] > seconds), None)
    semantic = lambda s: {k: s[k] for k in ('id','title','start','end','narration','visual_description','objective_ids','source_ids')} if s else None
    return {'format': 'hyperframes/v1', 'seconds': seconds,
        'duration': content['timeline']['duration'],
        'location_quality': 'exact' if segment else 'timeline_gap',
        'position_source': 'client_playback_snapshot',
        'visual_evidence': 'authored_metadata_not_observed_screenshot',
        'narration_alignment': 'segment_audio_duration',
        'current_segment': semantic(segment), 'active_visual_events': resolved['events'],
        'previous_segment': semantic(previous), 'next_segment': semantic(following),
        'directory': [{k:s[k] for k in ('id','title','start','end')} for s in segments]}


def classroom_timeline_context(material, locator=None, playback=None):
    content = native_content(material)
    try:
        validate_content(content)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, '课堂时间轴无效') from exc
    locator = locator or {}
    playback = playback or {}
    position = playback.get('position')
    if locator and locator.get('kind') != 'hyperframes':
        raise HTTPException(409, '该课堂需要时间轴位置')
    if playback.get('lecture'):
        raise HTTPException(409, '原幻灯片位置不适用于该课堂')
    if locator.get('content_hash') and locator['content_hash'] != content['project']['digest']:
        raise HTTPException(409, '课堂内容版本不匹配')
    if position and locator and (position['seconds'] != locator['seconds'] or
        position.get('segment_id') and locator.get('segment_id') and position['segment_id'] != locator['segment_id']):
        raise HTTPException(409, '课堂播放快照与引用位置不一致')
    pointer = position or locator
    if not pointer:
        return {'format':'hyperframes/v1', 'location_quality':'unknown', 'current_segment':None,
            'visual_evidence':'authored_metadata_not_observed_screenshot',
            'directory':[{k:s[k] for k in ('id','title','start','end')} for s in content['timeline']['segments']]}
    result = timeline_context(content, pointer['seconds'], pointer.get('segment_id'))
    result['status'] = playback.get('status', 'idle')
    return result


def compact_surroundings(context):
    """Drop surrounding prose before any current teaching content, in place."""
    for key in ('previous_segment', 'next_segment'):
        segment = context.get(key)
        if segment and any(field in segment for field in ('narration', 'visual_description')):
            segment.pop('narration', None)
            segment.pop('visual_description', None)
            segment['prose_omitted'] = True
            context['context_truncated'] = True
            return True
    directory = context.get('directory', [])
    current = context.get('current_segment') or {}
    if len(directory) > 3:
        at = next((i for i, s in enumerate(directory) if s['id'] == current.get('id')), 0)
        context['directory_total'] = context.get('directory_total', len(directory))
        context['directory'] = directory[max(0, at-1):at+2]
        context['context_truncated'] = True
        return True
    return False
