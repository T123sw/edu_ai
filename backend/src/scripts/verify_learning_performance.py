"""Single-client API latency on synthetic data; not a production load benchmark."""
import json,os,platform,time,math,shutil
from pathlib import Path
from uuid import uuid4
for flag in ('LEARNING_BROWSER_AGENT','LEARNING_BROWSER_ENRICHMENT','LEARNING_BROWSER_PREPARATION'):
    os.environ[flag]='1'
from tests.self_learning import browser_app as fixture
from fastapi.testclient import TestClient
from sqlalchemy import text

def stats(samples):
    values=sorted(samples)
    return {'samples':len(values),'p50_ms':round(values[math.ceil(len(values)*.5)-1],3),
        'p95_ms':round(values[math.ceil(len(values)*.95)-1],3),'max_ms':round(max(values),3)}
report={'environment':{'python':platform.python_version(),'platform':platform.platform(),'cpu_count':os.cpu_count(),
    'cpu_model':next((v.split(':',1)[1].strip() for v in Path('/proc/cpuinfo').read_text().splitlines() if v.startswith('model name')),''),
    'concurrent_clients':1,'transport':'in-process ASGI TestClient; excludes network/proxy','dataset':'isolated fixture, 3 nodes, 4 report resources'},'api':{}}
with fixture.engine.connect() as db:report['environment']['postgres']=db.scalar(text('select version()'))
try:
    with TestClient(fixture.app,headers={'Authorization':'Bearer alice'}) as client:
        url='/api/self-learning/courses/learning-fixture'
        assert client.get(url).status_code==200
        read=[];write=[];stream=str(uuid4())
        for i in range(30):
            start=time.perf_counter();response=client.get(url);read.append((time.perf_counter()-start)*1000)
            assert response.status_code==200,response.text
            event={'event_id':str(uuid4()),'type':'reading_position_set','occurred_at':'2026-09-17T00:00:00Z',
                'resource_ref':{'course_id':'learning-fixture','material_type':'report','material_id':'a-core','version':1},
                'payload':{'stream_id':stream,'sequence':i+1,'locator':{'kind':'document','scroll_top':i*50}}}
            start=time.perf_counter();response=client.post(url+'/topics/a/events',json=event);write.append((time.perf_counter()-start)*1000)
            assert response.status_code==200,response.text
        report['api']={'room_read':stats(read),'position_event_write':stats(write),'position_events_sent':30}
        report['status']='passed'
finally:
    shutil.rmtree(fixture.root,ignore_errors=True)
    destination=Path(__file__).resolve().parents[3]/'docs/acceptance/artifacts/learning-agent-p6/performance.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
