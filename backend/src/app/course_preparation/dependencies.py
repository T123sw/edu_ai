"""Shared infrastructure identity resolution; runtime assembly follows stage capabilities."""
import os
from functools import lru_cache
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.database.models import User


@lru_cache(maxsize=1)
def engine():
    url = os.getenv('DATABASE_URL', '')
    if not url:
        raise RuntimeError('DATABASE_URL is required')
    value = create_engine(url, pool_pre_ping=True)
    if value.dialect.name != 'postgresql':
        raise RuntimeError('Preparation requires PostgreSQL')
    return value


def owner_id(username):
    with Session(engine()) as session:
        user = session.scalar(select(User).where(User.username == username, User.is_disabled.is_(False)))
        if user is None:
            raise PermissionError('active owner required')
        return user.user_id


def configured_runner():
    from .application import application
    return application().runner
