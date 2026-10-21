from tests.course_preparation.legacy_classroom_fixtures import TeachingScript,native_classroom
from app.artifact_revision.adapters import validate


def test_metered_classroom_script_maps_to_native_playback_contract():
    script=TeachingScript(slides=[{'title':'工具调用的职责','points':['模型选择工具和参数','服务端执行后回传结果'],
        'narration':'模型根据工具描述选择调用，服务端检查权限、参数和预算后执行，将真实结果回传给模型。'*3},
        {'title':'面试检查','points':['解释一次工具调用失败的恢复方式'],
         'narration':'请说明如果写入已经执行，但回执在网络中丢失时，你如何避免重复写入。应先按幂等键查询实际结果，确认不存在才允许再提交。'*2}])
    content=native_classroom(script,'面试课堂','resource-1')
    validate('classroom',content)
    assert content['scenes'][0]['stageId']==content['stage']['id']
    assert content['scenes'][0]['content']['canvas']['viewportSize']==1000
    assert all(s['actions'][0]['type']=='speech' and s['actions'][0]['text'] for s in content['scenes'])
    assert all('audioUrl' not in s['actions'][0] for s in content['scenes'])
