from __future__ import annotations

import pytest

from app.services.course_code_service import (
    CourseCodeError,
    generate_course_code,
    normalize_course_code,
)


def test_normalize_course_code_accepts_human_formatting() -> None:
    assert normalize_course_code(" abcd-2345 ") == "ABCD2345"


@pytest.mark.parametrize("value", ["", "ABC", "ABCDO234", "ABCD-1234", "ABCDEFGH!"])
def test_normalize_course_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(CourseCodeError):
        normalize_course_code(value)


def test_generate_course_code_retries_collisions(monkeypatch) -> None:
    values = iter(["ABCD2345", "WXYZ6789"])
    monkeypatch.setattr(
        "app.services.course_code_service._random_code",
        lambda: next(values),
    )

    assert generate_course_code(lambda code: code == "ABCD2345") == "WXYZ6789"
