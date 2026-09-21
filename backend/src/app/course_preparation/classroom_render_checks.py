"""Deterministic checks, not a substitute for browser layout/audio acceptance."""
from __future__ import annotations

import copy
import hashlib
import math
import re

from app.services.classroom_validation import validate_stage


try:
    from .generation_failures import GenerationFailure as _GenerationFailure
except ModuleNotFoundError as exc:
    if exc.name != 'app.course_preparation.generation_failures':
        raise

    class _GenerationFailure(ValueError):
        # Contract-only baseline before F is integrated. Once present, E uses
        # F's exact exception/schema so the handler preserves recovery details.
        def __init__(self, detail):
            self.detail, self.code = detail, detail['code']
            super().__init__(detail['message'])


class ClassroomFailure(_GenerationFailure):
    """Concrete E failure with F's structured recovery semantics."""
    def __init__(self, code, message, *, category='render', phase='classroom_write', retry_scope='content'):
        super().__init__({'code': code, 'message': message, 'category': category,
                         'phase': phase, 'retry_scope': retry_scope,
                         'artifact_id': None, 'content_digest': None})


def narration_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def invalidate_stale_audio(content, receipts):
    """Keep audio only with a matching final text/URL and verified receipt.

    Receipt production and permissioned URL probing belong to the media tool.
    This function never makes network calls or treats a URL as proof of playback.
    """
    result = copy.deepcopy(content)
    retained = []
    for scene in result.get('scenes', []):
        for action in scene.get('actions', []):
            if action.get('type') != 'speech':
                continue
            receipt = receipts.get(action['id'], {})
            seconds = receipt.get('duration_seconds')
            valid = (action.get('audioUrl') and receipt.get('audio_url') == action['audioUrl']
                     and receipt.get('narration_digest') == narration_digest(action.get('text', ''))
                     and receipt.get('url_verified') is True
                     and isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
                     and math.isfinite(seconds) and seconds > 0)
            if valid:
                retained.append(receipt)
            else:
                for key in ('audioUrl', 'audioDuration', 'duration', 'wordTimestamps'):
                    action.pop(key, None)
    return result, retained


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_classroom_render(content, *, media_receipts=None):
    """Check E's controlled renderer subset; reject unsupported injected content."""
    issues = validate_stage(content.get('stage', {}), content.get('scenes', []))
    stage_id = content.get('stage', {}).get('id')
    scenes = content.get('scenes', [])
    scene_ids = {s.get('id') for s in scenes}
    all_actions = set()
    invalid_scene_ids = []
    if not scenes:
        issues.append('CLASSROOM_EMPTY')
    for index, scene in enumerate(scenes):
        scene_issue_start = len(issues)
        sid = scene.get('id')
        body = scene.get('content', {})
        kind = scene.get('type')
        if scene.get('stageId') != stage_id or scene.get('order') != index:
            issues.append(f'{sid}: scene identity/order mismatch')
        if kind not in ('slide', 'quiz') or body.get('type') != kind:
            issues.append(f'{sid}: unsupported/mismatched scene type')
        elements = body.get('canvas', {}).get('elements', [])
        element_ids = {e.get('id') for e in elements}
        if kind == 'slide':
            canvas = body.get('canvas', {})
            width, ratio = canvas.get('viewportSize'), canvas.get('viewportRatio')
            if not _number(width) or not _number(ratio) or width <= 0 or ratio <= 0:
                issues.append(f'{sid}: invalid canvas dimensions')
                invalid_scene_ids.append(sid)
                continue
            height = width * ratio
            if not elements:
                issues.append(f'{sid}: empty canvas')
            for element in elements:
                eid = element.get('id')
                x, y, w, h = (element.get(k) for k in ('left', 'top', 'width', 'height'))
                if not all(_number(v) for v in (x, y, w, h)) or min(w, h) <= 0 or min(x, y) < 0 or x + w > width or y + h > height:
                    issues.append(f'{sid}/{eid}: element outside canvas or invalid bounds')
                kind_e = element.get('type')
                if kind_e not in ('text', 'shape', 'image'):
                    issues.append(f'{sid}/{eid}: unsupported element')
                if kind_e == 'text':
                    markup = element.get('content', '')
                    sizes = re.findall(r'font-size\s*:\s*([\d.]+)px', markup)
                    if not re.sub('<[^>]*>', '', markup).strip() or not sizes or any(float(size) < 18 for size in sizes):
                        issues.append(f'{sid}/{eid}: missing text or base font below 18px')
                if kind_e == 'shape' and (not element.get('path') or not element.get('viewBox')):
                    issues.append(f'{sid}/{eid}: missing shape geometry')
                if kind_e == 'image':
                    receipt = (media_receipts or {}).get(eid, {})
                    if not element.get('src') or receipt.get('url_verified') is not True or receipt.get('url') != element['src'] or not receipt.get('source'):
                        issues.append(f'{sid}/{eid}: image missing or unverified')
                link = element.get('link') or {}
                if link.get('type') == 'slide' and link.get('target') not in scene_ids:
                    issues.append(f'{sid}/{eid}: dangling scene link')
        if kind == 'quiz':
            questions = body.get('questions', [])
            seen = set()
            if not questions:
                issues.append(f'{sid}: quiz has no questions')
            for q in questions:
                options = q.get('options', [])
                values = [o.get('value') for o in options]
                if (not q.get('id') or q['id'] in seen or q.get('type') != 'single'
                        or not q.get('question') or not q.get('analysis') or len(values) < 2
                        or len(values) != len(set(values)) or len(q.get('answer', [])) != 1
                        or not set(q.get('answer', [])) <= set(values)):
                    issues.append(f'{sid}: invalid quiz/answer reference')
                seen.add(q.get('id'))
            from .classroom_storyboard import quiz_narration
            allowed_speech = {text for q in questions for text in (
                quiz_narration(q.get('question', '')),
                q.get('question', '') + '。请选择答案，提交后查看解析。')}
        for action in scene.get('actions', []):
            aid = action.get('id')
            if aid in all_actions:
                issues.append(f'{sid}: duplicate action across scenes')
            all_actions.add(aid)
            if action.get('type') not in ('speech', 'spotlight', 'laser'):
                issues.append(f'{sid}/{aid}: unsupported action')
            if action.get('elementId') and action['elementId'] not in element_ids:
                issues.append(f'{sid}/{aid}: dangling element action')
            if action.get('sceneId') and action['sceneId'] not in scene_ids:
                issues.append(f'{sid}/{aid}: dangling scene action')
            if action.get('type') == 'speech':
                if not action.get('text', '').strip():
                    issues.append(f'{sid}/{aid}: empty speech')
                if kind == 'quiz' and action.get('text') not in allowed_speech:
                    issues.append(f'{sid}/{aid}: quiz speech must contain only the question')
                if action.get('audioUrl'):
                    receipt = (media_receipts or {}).get(aid, {})
                    clean, _ = invalidate_stale_audio({'scenes': [{'actions': [action]}]}, {aid: receipt})
                    if not clean['scenes'][0]['actions'][0].get('audioUrl'):
                        issues.append(f'{sid}/{aid}: audio missing/stale/unverified')
        if len(issues) > scene_issue_start:
            invalid_scene_ids.append(sid)
    return {'schema_version': 1, 'passed': not issues, 'issues': issues,
            'invalid_scene_ids': invalid_scene_ids,
            'browser_layout': 'not_checked', 'audio_listening': 'not_checked'}


def require_renderable(content, **kwargs):
    report = check_classroom_render(content, **kwargs)
    if report['issues']:
        raise ClassroomFailure('CLASSROOM_RENDER_INVALID', '; '.join(report['issues'])[:2000])
    return report
