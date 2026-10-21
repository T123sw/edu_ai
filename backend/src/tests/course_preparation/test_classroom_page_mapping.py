"""Authored native timeline bindings replace independent per-page LLM mapping.

Historical renderer page-count validation remains for archived material.
"""
from copy import deepcopy
import json

from tests.course_preparation.test_openmaic_native_integration import native_scene


def test_native_semantic_position_uses_finished_project_timing(tmp_path):
    from tests.hyperframes.native_workflow_fixtures import Runner
    from app.integrations.hyperframes.workflow_import import timeline_from_project
    (tmp_path/'REQUEST.json').write_text('{}')
    receipt=Runner(object(),tmp_path,lambda:None).run('native fixture')
    timeline=timeline_from_project(receipt['project_directory'],title='T',duration=2.75)
    assert timeline['segments'][0]['start']==0
    assert timeline['segments'][0]['end']==2.75
    assert timeline['segments'][0]['id']=='01-concept'


def test_historical_native_classrooms_can_have_more_than_24_pages():
    from app.course_preparation.native_render_checks import check_native_render
    content = native_scene('interactive', {'html': '<button>观察</button>'})
    first = content['scenes'][0]
    content['scenes'] = [{**deepcopy(first), 'id': f's{i}', 'order': i,
        'actions': [{'id': f'a{i}', 'type': 'speech', 'text': '观察'}]} for i in range(30)]
    assert check_native_render(content)['passed']
