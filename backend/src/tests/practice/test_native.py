import asyncio
import json
from types import SimpleNamespace

import pytest

from app.practice.native import generate_native, load_native, postprocess_native
from app.practice.native_runtime import wrap_native_html


def plan():
    return {'concept_name':'快速排序', 'subject':'计算机', 'concept_overview':'观察分区',
            'mastery_points':'理解比较和交换', 'design_idea':'逐步操作',
            'steps':[{'title':'选择基准','instruction':'点击下一步','question':'基准在哪？'}]}


def test_calls_real_upstream_generators_and_never_shares_generated_html():
    calls=[]
    science={key:['有效约束'] for key in ['core_formulas','mechanism','constraints','forbidden_errors']}
    html='<!DOCTYPE html><html><head></head><body>原生实验</body></html>'
    async def complete(owner,prompt,**kwargs):
        index=len(calls)%4
        calls.append((owner,prompt))
        return [json.dumps(science),html,html,'{"metadata":{"title":"快速排序"}}'][index]
    for owner in ['alice','bob']:
        context=SimpleNamespace(owner_user_id=owner,is_cancel_requested=lambda:False,progress=lambda *_:None)
        result=asyncio.run(generate_native(plan(),context,complete))
        assert result['html']==html
        assert result['generation_info']['stages_completed']==2
        assert [call['stage'] for call in result['native_calls']]==['science','interaction','polish','metadata']
    assert len(calls)==8
    assert '左右双栏布局' in calls[1][1]
    assert '布局优化和视觉润色' in calls[2][1]
    assert '当前HTML' in calls[2][1] and html in calls[2][1]
    assert '25000' not in calls[1][1]
    assert load_native().generation.HeavyGenerator.__module__.startswith('_edu_maic_native.')


def test_scientific_model_failure_does_not_generate_placeholder():
    calls=[]
    async def complete(*args,**kwargs):
        calls.append(args)
        return '{}'
    context=SimpleNamespace(owner_user_id='alice',is_cancel_requested=lambda:False,progress=lambda *_:None)
    with pytest.raises(ValueError,match='完整约束'):
        asyncio.run(generate_native(plan(),context,complete))
    assert len(calls)==1


def test_cancellation_stops_native_pipeline():
    async def complete(*args,**kwargs):
        raise AssertionError('cancelled work must not call model')
    context=SimpleNamespace(owner_user_id='alice',is_cancel_requested=lambda:True,progress=lambda *_:None)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(generate_native(plan(),context,complete))


def test_native_assets_preserve_layout_and_formula_processing():
    source=r'''<!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script>
<style>.chart{height:280px}</style></head><body class="p-6"><p>\(x^2\)</p></body></html>'''
    html=wrap_native_html(postprocess_native(source))
    assert 'src="https://' not in html
    assert '<body class="p-6">' in html
    assert '.chart{height:280px}' in html
    assert 'renderMathInElement' in html
    assert 'data:font/woff2;base64,' in html
    assert "connect-src 'none'" in html
    assert 'trust: false' in html
    assert html.index('Content-Security-Policy') < html.index('<script>')


def test_unknown_native_dependency_is_not_silently_delivered():
    with pytest.raises(ValueError,match='未打包的脚本'):
        wrap_native_html('<html><head><script src="https://unavailable.invalid/lib.js"></script></head><body></body></html>')
