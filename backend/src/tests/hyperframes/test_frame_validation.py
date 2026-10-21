import pytest
from app.integrations.hyperframes.frame_validation import validate_frame_html


def test_digit_id_used_as_selector_fails_without_browser():
    with pytest.raises(ValueError, match='id_requires_css_escape'):
        validate_frame_html('<div id="07-title"></div><script>gsap.to("#07-title", {})</script>')
    validate_frame_html('<div id="frame07-title"></div><script>gsap.to("#frame07-title", {})</script>')
    validate_frame_html('<div id="07-title"></div><script>document.getElementById("07-title")</script>')


def test_incremental_repair_can_preserve_existing_errors_without_adding_new_ones():
    before = '<i id="07-a"></i><i id="07-b"></i><style>#07-a,#07-b{}</style>'
    after = before.replace('07-a', 'frame07-a')
    validate_frame_html(after, before=before)
    with pytest.raises(ValueError):
        validate_frame_html(after+'<i id="08-c"></i><style>#08-c{}</style>', before=before)
