import json
import pytest
from fastapi import HTTPException
from app.self_learning.rollout import enabled,require_scope


def test_scope_selects_user_and_course_without_changing_global_switches(monkeypatch):
    monkeypatch.setenv('LEARNING_V1_SCOPE_JSON',json.dumps({'users':['alice'],'courses':['course']}))
    assert enabled('alice','course')
    assert not enabled('bob','course') and not enabled('alice','other')
    with pytest.raises(HTTPException):require_scope('bob','course')
    monkeypatch.setenv('LEARNING_V1_SCOPE_JSON','malformed')
    assert not enabled('alice','course')
    monkeypatch.setenv('LEARNING_V1_SCOPE_JSON','{"users":[]}')
    assert not enabled('alice','course')
