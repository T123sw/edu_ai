import pytest
from pydantic import ValidationError

from app.self_learning.contracts import ReadingContext, ResourceRef


def ref(**changes):
    return dict(course_id='course', material_type='report', material_id='same', version=1, **changes)


def test_resource_identity_includes_type_and_version():
    original = ResourceRef(**ref())
    assert original.key != ResourceRef(**{**ref(), 'material_type': 'quiz'}).key
    assert original.key != ResourceRef(**{**ref(), 'version': 2}).key


@pytest.mark.parametrize('changes', [{'version': 0}, {'version': True}, {'owner': 'someone'}, {'material_id': ' '}])
def test_invalid_or_identity_injecting_reference_rejected(changes):
    with pytest.raises(ValidationError):
        ResourceRef(**{**ref(), **changes})


def test_reading_locator_is_typed_and_selection_is_not_trusted():
    context = ReadingContext(resource_ref=ref(), locator={'kind': 'pdf', 'page': 5}, selected_text='片段')
    assert context.locator.page == 5
    assert context.location_verified is False
    with pytest.raises(ValidationError):
        ReadingContext(resource_ref=ref(), locator={'kind': 'pdf', 'seconds': 5})


@pytest.mark.parametrize('locator', [
    {'kind': 'video', 'seconds': -1},
    {'kind': 'pdf', 'page': 0},
    {'kind': 'classroom', 'scene_id': ''},
    {'kind': 'document', 'scroll_top': float('nan')},
])
def test_invalid_locator_rejected(locator):
    with pytest.raises(ValidationError):
        ReadingContext(resource_ref=ref(), locator=locator)
