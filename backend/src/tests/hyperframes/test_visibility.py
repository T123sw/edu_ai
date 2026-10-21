import json
import pytest
from app.integrations.hyperframes.visibility import write_visibility_assertions

TIMELINE = {'duration': 40, 'segments': [{'id': 's1', 'end': 17}, {'id': 's2', 'end': 40}]}


def test_preserves_native_assertions_and_verifies_both_teaching_segments(tmp_path):
    (tmp_path/'index.html').write_text('<html/>')
    authored = {'kind': 'before', 'a': '#first', 'b': '#second'}
    (tmp_path/'index.motion.json').write_text(json.dumps({'version': 1, 'assertions': [authored]}))
    result = write_visibility_assertions(tmp_path, {'s1': ['#first'], 's2': ['#second']}, TIMELINE)
    assert result['assertions'] == [authored,
        {'kind': 'appearsBy', 'selector': '#first', 'bySec': 17},
        {'kind': 'appearsBy', 'selector': '#second', 'bySec': 40}]
    assert json.loads((tmp_path/'index.motion.json').read_text()) == result


@pytest.mark.parametrize('targets', [None, {}, {'s1': ['#first']}, {'s1': ['body'], 's2': ['#second']}])
def test_missing_or_ambiguous_teaching_targets_are_repairable(tmp_path, targets):
    with pytest.raises(ValueError): write_visibility_assertions(tmp_path, targets, TIMELINE)
