import os,subprocess,json
from uuid import uuid4
from sqlalchemy import create_engine,text,inspect
root='/home/zxqs_ep/Edu_AI-agent-merge-20260918/backend/src'
admin=create_engine('postgresql+psycopg://zxqs_ep@127.0.0.1:55439/postgres',isolation_level='AUTOCOMMIT')
name='edu_merge_check_'+uuid4().hex[:12]
with admin.connect() as c:c.execute(text('CREATE DATABASE '+name))
url='postgresql+psycopg://zxqs_ep@127.0.0.1:55439/'+name
try:
 env={**os.environ,'DATABASE_URL':url,'PYTHONPATH':root}
 def upgrade(rev):subprocess.run(['python','-m','alembic','upgrade',rev],cwd=root,env=env,check=True)
 upgrade('20260917_0029')
 engine=create_engine(url)
 with engine.begin() as c:
  c.execute(text("INSERT INTO learning_memory_epochs (owner,epoch) VALUES ('merge-sentinel',17)"))
 before=set(inspect(engine).get_table_names())
 upgrade('head')
 after=set(inspect(engine).get_table_names())
 with engine.connect() as c:
  assert c.scalar(text("SELECT epoch FROM learning_memory_epochs WHERE owner='merge-sentinel'"))==17
  assert c.scalar(text('SELECT version_num FROM alembic_version'))=='20260918_0036'
 assert before<=after
 assert {'prepared_course_pointers','prepared_manifest_versions','preparation_course_notifications','course_production_runs','learning_checks'}<=after
 print(json.dumps({'status':'passed','upgrade_from':'20260917_0029','upgrade_to':'20260918_0036','original_tables':len(before),'added_tables':sorted(after-before),'existing_learning_row_preserved':True}))
 engine.dispose()
finally:
 with admin.connect() as c:c.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
 admin.dispose()
