import copy

import pytest

from app.course_preparation.classroom_render_checks import check_classroom_render, invalidate_stale_audio, narration_digest
from app.course_preparation.classroom_storyboard import ClassroomStoryboard, render_storyboard
from tests.course_preparation.test_classroom_teaching_contract import board_data


def content():
    return render_storyboard(ClassroomStoryboard.model_validate(board_data()), '课堂', 'r')


def test_controlled_renderer_passes_without_claiming_browser_or_audio_acceptance():
    report = check_classroom_render(content())
    assert report == {'schema_version': 1, 'passed': True, 'issues': [], 'invalid_scene_ids': [],
                      'browser_layout': 'not_checked', 'audio_listening': 'not_checked'}


@pytest.mark.parametrize('failure', ['bounds', 'font', 'empty', 'stage', 'element', 'scene', 'type', 'nan', 'image', 'action', 'quiz_leak'])
def test_invalid_render_and_references_are_blocked(failure):
    c = content(); s = c['scenes'][0]; e = s['content']['canvas']['elements'][0]
    if failure == 'bounds': e['left'] = 999
    if failure == 'font': e['content'] = '<div style="font-size:9px">太小</div>'
    if failure == 'empty': e['content'] = ''
    if failure == 'stage': s['stageId'] = 'other'
    if failure == 'element': s['actions'][1]['elementId'] = 'missing'
    if failure == 'scene': s['actions'][0]['sceneId'] = 'missing'
    if failure == 'type': s['type'] = 'demonstration'
    if failure == 'nan': e['width'] = float('nan')
    if failure == 'image': e.update(type='image', src='/missing.png')
    if failure == 'action': s['actions'][0]['type'] = 'invented_reveal'
    if failure == 'quiz_leak': c['scenes'][-1]['actions'][0]['text'] = '答案为 B'
    assert not check_classroom_render(c)['passed']


def test_text_length_is_not_a_browser_overflow_measurement():
    c = content()
    c['scenes'][0]['content']['canvas']['elements'][0]['content'] = '<div style="font-size:30px">' + '宽' * 1000 + '</div>'
    report = check_classroom_render(c)
    assert report['passed']  # Browser must measure actual layout, not a character heuristic.
    assert report['browser_layout'] == 'not_checked'


def test_audio_is_bound_to_final_narration_and_verified_media_receipt():
    c = content(); a = c['scenes'][0]['actions'][0]
    a['audioUrl'] = '/api/media/actual.wav'
    receipts = {a['id']: {'audio_url': a['audioUrl'], 'url_verified': True,
                         'narration_digest': narration_digest(a['text']), 'duration_seconds': 5.3}}
    original = copy.deepcopy(c)
    clean, valid = invalidate_stale_audio(c, receipts)
    assert clean == c and len(valid) == 1
    assert check_classroom_render(clean, media_receipts=receipts)['passed']
    a['text'] += '修订后的新旁白'
    assert not check_classroom_render(c, media_receipts=receipts)['passed']
    clean, valid = invalidate_stale_audio(c, receipts)
    assert not valid and 'audioUrl' not in clean['scenes'][0]['actions'][0]
    assert original['scenes'][0]['actions'][0]['audioUrl']  # Immutable previous version.


@pytest.mark.parametrize('seconds', [None, 0, -1, float('nan'), float('inf'), True])
def test_unmeasured_audio_never_gets_measured_receipt(seconds):
    c = content(); a = c['scenes'][0]['actions'][0]; a['audioUrl'] = '/api/media/audio.wav'
    receipt = {'audio_url': a['audioUrl'], 'url_verified': True,
               'narration_digest': narration_digest(a['text']), 'duration_seconds': seconds}
    clean, valid = invalidate_stale_audio(c, {a['id']: receipt})
    assert not valid and 'audioUrl' not in clean['scenes'][0]['actions'][0]
