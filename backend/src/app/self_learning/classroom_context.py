"""Semantic slide data from the authorized version, plus untrusted playback pointers.

No screenshots: image labels are metadata, never visual observations.
"""
import re
from html.parser import HTMLParser
from fastapi import HTTPException


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'br', 'li', 'tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value):
    parser = _PlainText()
    parser.feed(value if isinstance(value, str) else '')
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def narration_sentences(text):
    # Keep in sync with frontend/src/classroom/narrationSentences.ts.
    return [part.strip() for part in re.findall(r'[^。！？!?\n]+[。！？!?]*(?:[”’」』])?|[^\n]+', text) if part.strip()]


def semantic_element(element):
    kind = element.get('type')
    result = {k: element[k] for k in ('id', 'type', 'name', 'groupId') if k in element}
    if kind == 'text':
        result['text'] = plain_text(element.get('content'))
    elif kind == 'shape':
        result['text'] = plain_text((element.get('text') or {}).get('content'))
    elif kind == 'latex':
        result['latex'] = element.get('latex', '')
    elif kind == 'code':
        result.update(language=element.get('language'), file_name=element.get('fileName'),
                      lines=[{k: line[k] for k in ('id', 'content') if k in line} for line in element.get('lines', [])])
    elif kind == 'table':
        result['rows'] = [[{'text': plain_text(cell.get('text', '')),
                            **{k: cell[k] for k in ('rowspan', 'colspan') if k in cell}}
                           for cell in row] for row in element.get('data', [])]
    elif kind == 'chart':
        result.update(chart_type=element.get('chartType'),
                      data={k: v for k, v in (element.get('data') or {}).items() if k in ('labels', 'legends', 'series')})
    elif kind in ('image', 'video', 'audio'):
        result.update(description=element.get('alt') or element.get('description') or element.get('name') or '',
                      visual_content_available=False)
    elif kind == 'line':
        result['description'] = '连接线（未解析视觉关系）'
    return result


def scene_content(scene):
    content = scene.get('content') or {}
    canvas = content.get('canvas') or {}
    result = {'scene_id': scene['id'], 'title': scene.get('title', ''),
              'type': content.get('type') or scene.get('type'),
              'narration': [{'action_id': a['id'], 'text': a.get('text', '')}
                            for a in scene.get('actions', []) if a.get('type') == 'speech'],
              'visual_content_available': False}
    if result['type'] == 'slide':
        result['elements'] = [semantic_element(e) for e in canvas.get('elements', [])]
        if canvas.get('script'):
            result['speaker_notes'] = canvas['script']
    elif result['type'] == 'quiz':
        result['questions'] = [{k: q[k] for k in ('id', 'type', 'question', 'options') if k in q}
                               for q in content.get('questions', [])]
    else:
        result['description'] = '互动页面；仅提供标题和讲稿，未读取实时操作状态。'
    return result


def find_scene(material, scene_id):
    scene = next((s for s in material.get('scenes', []) if s.get('id') == scene_id), None)
    if scene is None:
        raise HTTPException(409, '指定课堂页不存在，请重新打开课件')
    return scene


def classroom_context(material, locator, playback=None):
    from .hyperframes_context import native_content, classroom_timeline_context
    if native_content(material):
        return classroom_timeline_context(material, locator, playback)
    directory = [{'scene_id': s['id'], 'page': i + 1, 'title': s.get('title', ''), 'type': s.get('type')}
                 for i, s in enumerate(material.get('scenes', []))]
    result = {'title': material.get('title', ''), 'directory': directory,
              'viewed_page': None, 'playback_status': 'unknown', 'lecture_position': None,
              'visual_content_available': False}
    if not locator or locator.get('kind') != 'classroom':
        result['location_quality'] = 'unknown'
        return result
    viewed = find_scene(material, locator['scene_id'])
    result['viewed_page'] = scene_content(viewed)
    result['location_quality'] = 'exact'
    if not playback:
        return result
    result['playback_status'] = playback['status']
    position = playback.get('lecture')
    if not position:
        return result
    scene = find_scene(material, position['scene_id'])
    actions = {a['id']: a for a in scene.get('actions', [])}
    action = actions.get(position['action_id'])
    if action is None:
        raise HTTPException(409, '讲解动作不属于指定课堂页')
    elements = {e['id']: e for e in (scene.get('content', {}).get('canvas') or {}).get('elements', [])}
    ids = position.get('highlighted_element_ids', [])
    if any(eid not in elements for eid in ids):
        raise HTTPException(409, '强调对象不属于指定课堂页')
    lecture = {'scene_id': scene['id'], 'title': scene.get('title', ''),
               'same_as_viewed_page': scene['id'] == viewed['id'],
               'action_id': action['id'], 'action_type': action['type'],
               'highlighted_elements': [semantic_element(elements[eid]) for eid in ids],
               'position_source': 'client_playback_snapshot'}
    speech_id = position.get('speech_action_id')
    index = position.get('sentence_index')
    if speech_id:
        speech = actions.get(speech_id)
        if not speech or speech.get('type') != 'speech':
            raise HTTPException(409, '讲稿动作不属于指定课堂页')
        sentences = narration_sentences(speech.get('text', ''))
        if index is not None and index >= len(sentences):
            raise HTTPException(409, '讲稿句子位置已失效')
        lecture.update(speech_action_id=speech_id, sentence_index=index,
                       sentence_alignment=position.get('sentence_alignment'),
                       speech_completed=position.get('speech_completed', False),
                       current_sentence=sentences[index] if index is not None else None,
                       speech_text=speech.get('text', ''))
    elif index is not None:
        raise HTTPException(409, '句子位置缺少对应讲稿')
    result['lecture_position'] = lecture
    return result
