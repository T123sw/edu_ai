# PostgreSQL Foundation Phase 1

## Goal

Introduce a reversible PostgreSQL foundation without changing the existing JSON stores' runtime authority.

## Included

- Docker Compose PostgreSQL 17 local deployment.
- Optional `DATABASE_URL`; the application remains functional when unset.
- SQLAlchemy core identity/course models.
- Alembic baseline migration for users, courses, objectives, and memberships.
- Database connectivity health endpoint.
- Focused model, transaction, and route tests.

## Explicitly deferred

- Importing JSON data.
- Dual writes.
- Switching any production read path.
- Deleting or rewriting existing JSON files.
- Moving documents, media, Chroma vectors, or generated artifacts.

## Completion gate

1. Existing tests remain green without `DATABASE_URL`.
2. PostgreSQL container becomes healthy.
3. `alembic upgrade head` creates the four baseline tables.
4. `alembic downgrade base` and re-upgrade work on a disposable database.
5. Existing JSON course data remains byte-for-byte untouched by migration commands.
