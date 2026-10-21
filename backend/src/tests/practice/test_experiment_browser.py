import pytest
from app.practice.service import validate_html
from app.practice.native_runtime import wrap_native_html
from tests.practice.experiment_fixtures import artifact
@pytest.mark.parametrize('name',['quicksort','friction','probability'])
def test_actual_sandbox_adapter_cases_and_resizing(name):
    data=artifact(name);result=validate_html(data['html'],experiment=data['experiment']['spec'])
    assert result['ok'],result
    assert [case['verdict'] for case in result['checks']]==['pass','fail']
def test_nonfunctional_generated_page_is_rejected():
    data=artifact('quicksort');html=wrap_native_html('<!doctype html><html><head></head><body>假的交互页面<script>EduExperiment.register({apply(s,c){return s},render(){}})</script></body></html>',experiment=data['experiment'])
    result=validate_html(html,experiment=data['experiment']['spec'])
    assert not result['ok']
