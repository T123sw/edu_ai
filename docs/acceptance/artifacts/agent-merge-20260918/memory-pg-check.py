import os,subprocess
from uuid import uuid4
from sqlalchemy import create_engine,text
from app.database import Base
schema='merge_memory_'+uuid4().hex
url='postgresql+psycopg://zxqs_ep@127.0.0.1:55439/postgres'
admin=create_engine(url)
with admin.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
try:
 names=['agent_memory_items','user_profile_facts','conversation_episodes','agent_memory_audit_events','agent_memory_epochs','agent_memory_suppressions','agent_memory_dependencies','agent_memory_changes']
 Base.metadata.create_all(engine,tables=[Base.metadata.tables[n] for n in names])
 result=subprocess.run(['python','-m','pytest','--import-mode=importlib','tests/chat/memory/test_memory_postgres_integration.py','-q','-ra'],env={**os.environ,'AGENT_MEMORY_TEST_DATABASE_URL':url+'?options=-csearch_path%3D'+schema})
 if result.returncode:raise RuntimeError('PostgreSQL shared memory test failed')
finally:
 engine.dispose()
 with admin.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
 admin.dispose()
