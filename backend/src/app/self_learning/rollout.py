"""Scope new interactive capabilities while keeping migrated facts authoritative."""
import json
import os
from fastapi import HTTPException


def enabled(owner,course):
    raw=os.getenv('LEARNING_V1_SCOPE_JSON','').strip()
    if not raw:return True  # Global capability switches still default to off.
    try:
        policy=json.loads(raw)
        if not isinstance(policy,dict) or set(policy)-{'users','courses'}:return False
        for key,value in policy.items():
            if not isinstance(value,list) or any(not isinstance(v,str) or not v for v in value):return False
        return ('users' not in policy or owner in policy['users']) and ('courses' not in policy or course in policy['courses'])
    except (ValueError,TypeError):return False


def require_scope(owner,course):
    if not enabled(owner,course):raise HTTPException(503,'当前用户或课程尚未启用新版学习 Agent；已有记录仍可阅读')
