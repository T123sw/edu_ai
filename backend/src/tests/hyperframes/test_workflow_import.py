import json

from app.integrations.hyperframes.workflow_import import timeline_from_project


def test_narration_uses_native_voice_metadata_instead_of_background_music(tmp_path):
    (tmp_path/'STORYBOARD.md').write_text('## Frame 1 — 截距\n- duration: 3s\n- src: compositions/frame.html\n')
    (tmp_path/'SCRIPT.md').write_text('## Intercept (Frame 1)\n\n    截距变大，直线上移。\n')
    (tmp_path/'audio_meta.json').write_text(json.dumps({'voices':[{'frame':1,'path':'assets/voice.mp3','duration_s':3}]}))
    (tmp_path/'index.html').write_text('<div data-composition-src="compositions/frame.html" data-start="0" data-duration="3"></div><audio src="assets/music.mp3" data-start="0" data-duration="3"></audio><audio src="assets/voice.mp3" data-start="0" data-duration="3"></audio>')
    segment=timeline_from_project(tmp_path,title='截距',duration=3)['segments'][0]
    assert segment['audio_path']=='assets/voice.mp3'
    assert segment['narration']=='截距变大，直线上移。'


def test_native_silent_general_video_requires_no_platform_script(tmp_path):
    (tmp_path/'index.html').write_text('<div data-composition-id="main" data-duration="4"></div>')
    timeline=timeline_from_project(tmp_path,title='无声示意',duration=4)
    assert timeline['duration']==4
    assert timeline['segments'][0]['narration']==''
    assert 'audio_path' not in timeline['segments'][0]


def test_general_video_joins_native_voice_ids_to_real_scene_positions(tmp_path):
    (tmp_path/'audio_request.json').write_text(json.dumps({'lines': [
        {'id': 'compare', 'text': '比较这两个相邻元素。'}, {'id': 'swap', 'text': '逆序时交换。'}]}))
    (tmp_path/'audio_meta.json').write_text(json.dumps({'voices': [
        {'id':'compare','path':'assets/a.mp3','duration_s':3}, {'id':'swap','path':'assets/b.mp3','duration_s':4}]}))
    (tmp_path/'index.html').write_text('''<div data-composition-id="compare" data-composition-src="compare.html" data-start="0" data-duration="3"></div>
        <div data-composition-id="swap" data-composition-src="swap.html" data-start="3" data-duration="4"></div>
        <audio src="assets/a.mp3" data-start="0" data-duration="3"></audio><audio src="assets/b.mp3" data-start="3" data-duration="4"></audio>''')
    segments = timeline_from_project(tmp_path, title='比较与交换', duration=7)['segments']
    assert [(s['id'],s['start'],s['end'],s['narration'],s['audio_path']) for s in segments] == [
        ('compare',0,3,'比较这两个相邻元素。','assets/a.mp3'),('swap',3,7,'逆序时交换。','assets/b.mp3')]


def test_continuous_composition_uses_native_subtitle_timestamps(tmp_path):
    (tmp_path/'index.html').write_text('<div data-composition-id="main" data-duration="12"></div>')
    (tmp_path/'captions.srt').write_text('1\n00:00:01,000 --> 00:00:04,000\n先比较。\n\n2\n00:00:05,000 --> 00:00:09,000\n再交换。\n')
    segments = timeline_from_project(tmp_path,title='排序',duration=12)['segments']
    assert [(s['start'],s['end'],s['narration']) for s in segments] == [(1,4,'先比较。'),(5,9,'再交换。')]
