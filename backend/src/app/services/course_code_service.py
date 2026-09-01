"""Human-friendly, non-sequential course join codes."""

from __future__ import annotations

import secrets
import hashlib
from collections.abc import Callable


COURSE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
COURSE_CODE_LENGTH = 8


class CourseCodeError(ValueError):
    pass


def normalize_course_code(value: object) -> str:
    normalized = str(value or "").strip().upper().replace("-", "").replace(" ", "")
    if len(normalized) != COURSE_CODE_LENGTH:
        raise CourseCodeError("课程码必须为 8 位")
    if any(char not in COURSE_CODE_ALPHABET for char in normalized):
        raise CourseCodeError("课程码包含无效字符")
    return normalized


def _random_code() -> str:
    return "".join(secrets.choice(COURSE_CODE_ALPHABET) for _ in range(COURSE_CODE_LENGTH))


def deterministic_course_code(course_id: str, *, salt: int = 0) -> str:
    digest = hashlib.sha256(f"{course_id}:edu-ai-course-code-v1:{salt}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    chars: list[str] = []
    for _ in range(COURSE_CODE_LENGTH):
        value, index = divmod(value, len(COURSE_CODE_ALPHABET))
        chars.append(COURSE_CODE_ALPHABET[index])
    return "".join(chars)


def generate_course_code(exists: Callable[[str], bool], *, max_attempts: int = 64) -> str:
    for _ in range(max_attempts):
        candidate = _random_code()
        if not exists(candidate):
            return candidate
    raise CourseCodeError("暂时无法生成唯一课程码，请稍后重试")
