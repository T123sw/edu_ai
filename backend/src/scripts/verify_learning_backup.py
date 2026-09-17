"""Destructive actions are limited to newly created databases on the isolated test cluster.

Dump and restore a real schema plus synthetic material files; compare every row
and file hash, then read facts/history through repositories against the restore.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from uuid import uuid4

TEST_URL=os.environ['LEARNING_TEST_DATABASE_URL']
os.environ['LEARNING_BROWSER_AGENT']='1'
os.environ['LEARNING_BROWSER_ENRICHMENT']='1'
os.environ['LEARNING_BROWSER_PREPARATION']='1'
from tests.self_learning import browser_app as fixture
from sqlalchemy import create_engine,text,inspect
from sqlalchemy.engine import make_url
from app.database import Base
from app.self_learning.migration_models import TABLES
from app.self_learning.migration import LearningMigration
from app.self_learning.progress_repository import ProgressRepository
from app.self_learning.postgres_repository import SessionRepository

url=make_url(TEST_URL)
assert url.host in {'127.0.0.1','localhost'} and url.database=='postgres'
with fixture.admin.connect() as db:
    assert db.scalar(text('show data_directory'))=='/tmp/edu-learning-p1-pg', 'refuse non-isolated PostgreSQL cluster'
restore_name='learning_restore_'+uuid4().hex
artifact=Path(__file__).resolve().parents[3]/'docs/acceptance/artifacts/learning-agent-p6/backup-restore.json'
report={'database':restore_name,'source_schema':fixture.schema,'status':'started'}
temporary=Path(tempfile.mkdtemp(prefix='learning-backup-'))
restore_engine=None
created=False

def rows(engine,schema):
    result={}
    with engine.connect() as db:
        for table in sorted(inspect(db).get_table_names(schema=schema)):
            quoted=db.dialect.identifier_preparer.quote
            values=[dict(r) for r in db.execute(text(f'SELECT * FROM {quoted(schema)}.{quoted(table)}')).mappings()]
            encoded=sorted(json.dumps(v,sort_keys=True,default=str,ensure_ascii=False) for v in values)
            result[table]={'rows':len(values),'sha256':hashlib.sha256('\n'.join(encoded).encode()).hexdigest()}
    return result

def files(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}

try:
    Base.metadata.create_all(fixture.engine,tables=[Base.metadata.tables[n] for n in TABLES])
    source={'owner':'alice','course_id':'learning-fixture','sessions':[{'topic_id':'a','session_id':'legacy-backup','turns':[
        {'turn_id':f'old-{i}','question':f'原问题{i}','answer_text':f'原回答{i}','resource_id':'a-core'} for i in range(151)]}],
        'overlay':{'progress':{'a-core':{'completed':True,'version':1},'pending:b':{'note':'保留笔记'}},'understanding':{'a':'review'}}}
    migration=LearningMigration(fixture.svc)
    scan=migration.scan(source)
    report['import']=migration.import_records(scan)
    report['reconcile']=migration.reconcile(scan)
    report['activation']=migration.activate(scan,5)
    source_path=temporary/'legacy-source.json'
    source_path.write_text(json.dumps(source,ensure_ascii=False))
    cli_url=url.set(query={'options':f'-csearch_path={fixture.schema}'}).render_as_string(hide_password=False)
    common=[sys.executable,'-m','app.database.migrate_self_learning_cli','--database-url',cli_url,'--storage-root',str(fixture.root)]
    cli_report=temporary/'scan.json'
    cli_env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
    subprocess.run(common+['--source',str(source_path),'--output',str(cli_report)],env=cli_env,check=True,capture_output=True,text=True)
    cli_results={}
    for action in ('import','reconcile'):
        output=temporary/(action+'.json')
        subprocess.run(common+[action,'--report',str(cli_report),'--output',str(output)],env=cli_env,check=True,capture_output=True,text=True)
        cli_results[action]=json.loads(output.read_text())
    assert cli_results['import']['created']==0 and cli_results['reconcile']['unexplained_differences']==[]
    report['cli']=cli_results
    before=rows(fixture.engine,fixture.schema)
    file_before=files(fixture.root)
    shutil.copytree(fixture.root,temporary/'files')
    env={**os.environ,'PGHOST':url.host,'PGPORT':str(url.port or 5432),'PGUSER':url.username or '', 'PGPASSWORD':url.password or ''}
    dump=temporary/'snapshot.dump'
    subprocess.run(['/usr/lib/postgresql/14/bin/pg_dump','--dbname','postgres','--format=custom','--schema',fixture.schema,'--file',str(dump)],env=env,check=True,capture_output=True)
    with fixture.admin.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
        db.execute(text(f'CREATE DATABASE {restore_name}'))
        created=True
    subprocess.run(['/usr/lib/postgresql/14/bin/pg_restore','--dbname',restore_name,'--exit-on-error',str(dump)],env=env,check=True,capture_output=True)
    restore_engine=create_engine(url.set(database=restore_name),connect_args={'options':f'-csearch_path={fixture.schema}'})
    after=rows(restore_engine,fixture.schema)
    assert before==after,'restored row hashes differ'
    assert file_before==files(temporary/'files'),'restored material hashes differ'
    facts=ProgressRepository(restore_engine).read('alice','learning-fixture')
    assert next(r for r in facts['resources'] if r['resource_ref']['material_id']=='a-core')['completed']
    sessions=SessionRepository(restore_engine)
    current=sessions.find('alice','learning-fixture','a')
    assert current['message_count']==303
    assert sessions.messages('alice',current['session_id'])['items'][-1]['text']=='原回答150'
    report.update(status='verified',row_hashes=after,material_files=len(file_before),dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest(),
        restored_history_messages=current['message_count'],restored_completion=True)
finally:
    if restore_engine:restore_engine.dispose()
    if created:
        with fixture.admin.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
            db.execute(text(f'DROP DATABASE {restore_name}'))
    fixture.engine.dispose()
    with fixture.admin.begin() as db:db.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
    fixture.admin.dispose()
    shutil.rmtree(temporary)
    report['temporary_backup_and_restore_removed']=True
    artifact.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'status':report['status'],'artifact':str(artifact)},ensure_ascii=False))
