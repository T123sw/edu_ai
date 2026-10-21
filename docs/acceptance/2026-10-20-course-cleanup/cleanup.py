"""Explicit course-only reset authorized on 2026-10-20; default is inventory."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from sqlalchemy import create_engine, MetaData, select, or_, tuple_, delete, text
from core.course_storage import CourseStorageManager

OUT = Path(__file__).resolve().parent
engine = create_engine(os.environ['DATABASE_URL'])
meta = MetaData()
meta.reflect(engine)
tables = meta.tables
storage = CourseStorageManager().root_path.resolve()
apply = '--apply' in sys.argv

def personal(key):
    return not key or key.startswith(('personal:', 'personal-studio-'))

def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()

def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values(): yield from walk(item)
    elif isinstance(value, list):
        for item in value: yield from walk(item)
    elif isinstance(value, str):
        yield value

with engine.connect() as conn:
    course_ids = set()
    for table in tables.values():
        if 'course_id' in table.c:
            course_ids.update(v for v in conn.execute(select(table.c.course_id).distinct()).scalars()
                              if not personal(v))
    course_ids.update(p.name for p in (storage / 'courses').iterdir()
                      if p.is_dir() and not personal(p.name))
    prep_ids = set(conn.execute(select(tables['course_preparations'].c.preparation_id)).scalars())
    course_ids.update('learn-' + key.removeprefix('prep_') for key in prep_ids)
    predicates = {}
    for name, table in tables.items():
        if 'course_id' in table.c:
            predicates[name] = table.c.course_id.in_(sorted(course_ids))
        if name.startswith(('course_preparation', 'preparation_')) or name in (
            'course_research_runs', 'course_production_runs', 'prepared_manifest_versions',
            'prepared_course_pointers'):
            predicates[name] = text('true')
    dt = tables['durable_tasks']
    predicates['durable_tasks'] = or_(predicates['durable_tasks'],
        dt.c.workflow_type.in_(['preparation_step', 'preparation_resource']))

    def propagate():
        for table in meta.sorted_tables:
            for fk in table.foreign_key_constraints:
                parent = fk.referred_table.name
                if parent in predicates:
                    condition = tuple_(*[e.parent for e in fk.elements]).in_(
                        select(*[e.column for e in fk.elements]).where(predicates[parent]))
                    predicates[table.name] = or_(predicates[table.name], condition) if table.name in predicates else condition
    propagate()

    refs = set(course_ids) | prep_ids
    for name, key in [('durable_tasks', 'task_id'), ('jobs', 'edu_job_id'),
                      ('conversations', 'conversation_id'), ('preparation_artifacts', 'artifact_id')]:
        refs.update(conn.execute(select(tables[name].c[key]).where(predicates[name])).scalars())
    path_markers = ['/courses/' + key + '/' for key in course_ids]
    long_refs = {v for v in refs if v and len(v) >= 20}
    def linked(value):
        for item in walk(value):
            if isinstance(item, str):
                if item in refs: return True
                normalized = item.replace('\\', '/')
                if any(marker in normalized for marker in path_markers): return True
                if long_refs.intersection(re.findall(r'[A-Za-z0-9_-]{20,}', item)): return True
        return False

    extra = {}
    scan = {
        'app_state_records': ~tables['app_state_records'].c.namespace.like('exam%')
                            & (tables['app_state_records'].c.namespace != 'runtime_config'),
        'runtime_index_entries': text('true'),
        'learning_progress_outbox': text('true'),
        'agent_memory_dependencies': text('true'),
    }
    for name, where in scan.items():
        table = tables[name]
        keys = []
        for row in conn.execute(select(table).where(where)).mappings():
            value = dict(row)
            namespace = value.get('namespace', '')
            forced = namespace == 'course_metadata' or namespace.startswith(('self_learning:', 'course_usage:'))
            if forced or linked(value):
                keys.append(tuple(value[c.name] for c in table.primary_key))
        if keys:
            extra[name] = keys
            condition = tuple_(*table.primary_key).in_(keys)
            predicates[name] = or_(predicates[name], condition) if name in predicates else condition
    propagate()

    selected = {}
    counts_before = {}
    for name, condition in predicates.items():
        table = tables[name]
        keys = [tuple(row) for row in conn.execute(select(*table.primary_key).where(condition))]
        if keys: selected[name] = keys
        counts_before[name] = conn.execute(select(text('count(*)')).select_from(table)).scalar_one()
    active = conn.execute(select(dt.c.task_id, dt.c.status).where(
        predicates['durable_tasks'], dt.c.status.in_(['queued','running','pending','retrying','leased']))).all()
    assert not active, f'Course tasks still active: {active}'
    assert not conn.execute(text("select 1 from course_preparation_attempts where status not in ('succeeded','failed','canceled') limit 1")).first()

    removed_projects, kept_projects, workspaces = set(), set(), set()
    for name in ['materials', 'material_versions', 'preparation_artifacts', 'durable_tasks']:
        table = tables[name]
        json_cols = [c for c in table.c if str(c.type) in ('JSON', 'JSONB')]
        if not json_cols: continue
        for remove in [True, False]:
            where = predicates[name] if remove else ~predicates[name]
            # NULL course_id belongs to the preserved side unless prep workflow.
            if not remove:
                where = ~tuple_(*table.primary_key).in_(selected.get(name, []))
            for row in conn.execute(select(*json_cols).where(where)):
                for value in row:
                    for item in walk(value):
                        if isinstance(item, dict):
                            project = item.get('project')
                            if isinstance(project, dict) and isinstance(project.get('id'), str) and project.get('digest'):
                                (removed_projects if remove else kept_projects).add(project['id'])
                            if remove and isinstance(item.get('workspace_key'), str):
                                workspaces.add(item['workspace_key'])
                        elif remove and '/hyperframes/workflows/' in item:
                            match = re.search(r'/hyperframes/workflows/([a-f0-9]{64})(?:/|$)', item)
                            if match: workspaces.add(match[1])
    filesystem = [storage / 'courses' / key for key in sorted(course_ids)
                  if (storage / 'courses' / key).exists()]
    filesystem += [storage / 'hyperframes/projects' / key for key in sorted(removed_projects - kept_projects)]
    filesystem += [storage / 'hyperframes/workflows' / key for key in sorted(workspaces)]
    filesystem = [p for p in filesystem if p.exists()]
    for p in filesystem:
        assert p.resolve().is_relative_to(storage) and p.resolve() != storage
        assert not p.is_symlink()
    preserved = {
        'users': fingerprint([dict(r) for r in conn.execute(select(tables['users']).order_by(tables['users'].c.user_id)).mappings()]),
        'runtime_config': fingerprint([dict(r) for r in conn.execute(select(tables['app_state_records']).where(tables['app_state_records'].c.namespace == 'runtime_config')).mappings()]),
    }
    summary = {'started_at': datetime.now(timezone.utc).isoformat(), 'apply': apply,
        'course_count': counts_before['courses'], 'preparation_count': counts_before['course_preparations'],
        'course_ids_including_orphans': sorted(course_ids), 'rows_selected': {k:len(v) for k,v in selected.items()},
        'filesystem': [str(p) for p in filesystem], 'preserved_fingerprints': preserved,
        'scope': 'All courses, course-bound records and preparations; preserve accounts/config/personal libraries/standalone exams, practice and PBL.'}
    (OUT / ('before.json' if apply else 'plan.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('course_ids_including_orphans','preserved_fingerprints','filesystem')},ensure_ascii=False),flush=True)
    print('file_directories_selected',len(filesystem),flush=True)
    if not apply: sys.exit(0)

    # Detach all selected relational rows in one atomic transaction. No CASCADE
    # truncation, no schema/user/config reset, and no deletion of new unrelated rows.
    conn.rollback()
    with conn.begin():
        conn.execute(text("SET LOCAL lock_timeout='10s'"))
        for table in reversed(meta.sorted_tables):
            keys = selected.get(table.name, [])
            for start in range(0, len(keys), 500):
                conn.execute(delete(table).where(tuple_(*table.primary_key).in_(keys[start:start+500])))
        for name, keys in selected.items():
            table = tables[name]
            for start in range(0,len(keys),500):
                assert not conn.execute(select(*table.primary_key).where(tuple_(*table.primary_key).in_(keys[start:start+500])).limit(1)).first()
        assert conn.execute(select(text('count(*)')).select_from(tables['courses'])).scalar_one() == 0
    summary['database_deleted'] = True
    (OUT / 'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

    # Delete vector chunks for the same physical course paths; shared/private
    # documents outside those course directories are retained.
    import chromadb
    from chromadb.config import Settings
    from core.config import Config
    client = chromadb.PersistentClient(path=str(Config.VECTOR_DB_PATH),settings=Settings(anonymized_telemetry=False))
    vector_deleted = {}
    for collection in client.list_collections():
        collection = client.get_collection(collection.name)
        ids = []
        for offset in range(0,collection.count(),1000):
            page = collection.get(limit=1000,offset=offset,include=['metadatas'])
            ids += [key for key, info in zip(page['ids'],page['metadatas']) if linked(info or {})]
        for start in range(0,len(ids),500): collection.delete(ids=ids[start:start+500])
        vector_deleted[collection.name] = len(ids)
    summary['vector_chunks_deleted'] = vector_deleted
    for p in filesystem:
        shutil.rmtree(p)
    summary['filesystem_deleted'] = True
    assert preserved['users'] == fingerprint([dict(r) for r in conn.execute(select(tables['users']).order_by(tables['users'].c.user_id)).mappings()])
    assert preserved['runtime_config'] == fingerprint([dict(r) for r in conn.execute(select(tables['app_state_records']).where(tables['app_state_records'].c.namespace == 'runtime_config')).mappings()])
    summary['accounts_config_unchanged'] = True
    summary['completed_at'] = datetime.now(timezone.utc).isoformat()
    (OUT/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'cleaned','courses_remaining':0,'vector_chunks_deleted':vector_deleted,'directories_deleted':len(filesystem)},ensure_ascii=False))
