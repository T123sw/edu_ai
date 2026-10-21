"""Validate the native DSL supported by our existing OpenMAIC player/exporter."""
import base64
import re

from app.services.classroom_validation import validate_stage
from .classroom_render_checks import ClassroomFailure, _number

ACTIONS = {'speech', 'spotlight', 'laser', 'play_video', 'widget_highlight',
           'widget_setState', 'widget_annotation', 'widget_reveal'}
ELEMENTS = {'text', 'shape', 'image', 'line', 'chart', 'table', 'latex', 'video', 'audio'}


def _media(source, kind):
    if not isinstance(source, str): return False
    # Native preparations currently embed provider-produced bytes. Arbitrary
    # URLs/placeholders cannot masquerade as verified generated media.
    if not re.match(r'^data:' + kind + r'/[a-zA-Z0-9.+-]+;base64,', source): return False
    try:
        return bool(base64.b64decode(source.split(',', 1)[1], validate=True))
    except (ValueError, TypeError): return False


def check_native_render(content):
    scenes = content.get('scenes', [])
    stage = content.get('stage', {})
    issues = validate_stage(stage, scenes)
    invalid = []
    if not scenes: issues.append('invalid native scene count')
    actions_seen = set()
    for index, scene in enumerate(scenes):
        before = len(issues)
        sid = scene.get('id')
        kind, body = scene.get('type'), scene.get('content', {})
        if kind not in ('slide', 'quiz', 'interactive') or body.get('type') != kind:
            issues.append(f'{sid}: disabled or mismatched scene type')
        if scene.get('stageId') != stage.get('id') or scene.get('order') != index:
            issues.append(f'{sid}: scene identity/order mismatch')
        if kind == 'slide':
            canvas = body.get('canvas', {})
            width, ratio = canvas.get('viewportSize'), canvas.get('viewportRatio')
            if not _number(width) or not _number(ratio) or width <= 0 or ratio <= 0:
                issues.append(f'{sid}: invalid canvas size')
            else:
                elements = canvas.get('elements', [])
                if not elements: issues.append(f'{sid}: empty slide')
                for el in elements:
                    label = f"{sid}/{el.get('id')}"
                    typ = el.get('type')
                    if typ not in ELEMENTS: issues.append(label + ': unsupported element')
                    x, y = el.get('left'), el.get('top')
                    if typ == 'line':
                        points = [el.get('start'), el.get('end')]
                        if not all(isinstance(p, list) and len(p) == 2 and all(_number(v) for v in p) for p in points):
                            issues.append(label + ': invalid line geometry')
                        elif not all(_number(v) for v in (x, y)) or any(not (-1 <= x+p[0] <= width+1 and -1 <= y+p[1] <= width*ratio+1) for p in points):
                            issues.append(label + ': line outside canvas')
                    else:
                        w, h = el.get('width'), el.get('height')
                        if (not all(_number(v) for v in (x, y, w, h)) or min(w, h) <= 0
                                or x < -1 or y < -1 or x+w > width+1 or y+h > width*ratio+1):
                            issues.append(label + ': invalid bounds')
                    if typ == 'text' and not re.sub('<[^>]*>', '', el.get('content', '')).strip():
                        issues.append(label + ': empty text')
                    if typ == 'shape' and (not el.get('path') or not el.get('viewBox')):
                        issues.append(label + ': missing shape geometry')
                    if typ in ('image', 'video', 'audio') and not _media(el.get('src'), typ):
                        issues.append(label + ': missing/unverified media')
                    if typ == 'latex' and not el.get('latex'):
                        issues.append(label + ': missing formula')
        elif kind == 'interactive':
            if not isinstance(body.get('html'), str) or not body['html'].strip():
                issues.append(f'{sid}: interactive HTML missing')
            elif re.search(r'\bloadPyodide\s*\(', body['html']) and not re.search(r'<script[^>]+src=[\"\'][^\"\']*pyodide', body['html'], re.I):
                issues.append(f'{sid}: Python runtime loader missing; use a self-contained JS simulation or load Pyodide explicitly')
        elif kind == 'quiz':
            questions = body.get('questions', [])
            seen = set()
            if not questions: issues.append(f'{sid}: empty quiz')
            for question in questions:
                qid, qtype = question.get('id'), question.get('type')
                if (not qid or qid in seen or not question.get('question')
                        or not question.get('analysis') or qtype not in ('single', 'multiple', 'short_answer')):
                    issues.append(f'{sid}: invalid quiz')
                seen.add(qid)
                if qtype in ('single', 'multiple'):
                    values = [o.get('value') for o in question.get('options', [])]
                    answers = question.get('answer', [])
                    if (len(values) < 2 or len(values) != len(set(values)) or not answers
                            or not set(answers) <= set(values) or qtype == 'single' and len(answers) != 1):
                        issues.append(f'{sid}/{qid}: invalid answers')
        for action in scene.get('actions', []):
            aid, atype = action.get('id'), action.get('type')
            if aid in actions_seen: issues.append(f'{sid}: duplicate action')
            actions_seen.add(aid)
            if atype not in ACTIONS: issues.append(f'{sid}/{aid}: disabled action')
            if isinstance(atype, str) and atype.startswith('widget_') and kind != 'interactive': issues.append(f'{sid}/{aid}: widget action outside interactive scene')
            if atype == 'speech' and kind == 'quiz' and action.get('text') not in {q.get('question') for q in body.get('questions', [])}:
                issues.append(f'{sid}/{aid}: quiz narration must read only the question before submission')
            if atype == 'speech' and action.get('audioUrl'): issues.append(f'{sid}/{aid}: pre-generated audio requires a verified TTS receipt')
            if atype == 'speech' and not action.get('text', '').strip(): issues.append(f'{sid}/{aid}: empty narration')
        if len(issues) > before: invalid.append(sid)
    return {'schema_version': 1, 'passed': not issues, 'issues': issues, 'invalid_scene_ids': invalid,
            'browser_layout': 'not_checked', 'audio_listening': 'not_checked'}


def require_native_renderable(content):
    report = check_native_render(content)
    if not report['passed']:
        raise ClassroomFailure('CLASSROOM_RENDER_INVALID', '; '.join(report['issues'])[:2000])
    return report
