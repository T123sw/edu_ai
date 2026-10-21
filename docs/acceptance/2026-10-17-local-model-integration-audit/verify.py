import asyncio, concurrent.futures, datetime, hashlib, json, math, os, sqlite3, subprocess, time
from pathlib import Path
from urllib.parse import urlsplit
from core.config import Config
# All database connections in this verification are read-only, including imports.
os.environ['PGOPTIONS'] = '-c default_transaction_read_only=on -c statement_timeout=10000'
from sqlalchemy import event
from sqlalchemy.engine import Engine
@event.listens_for(Engine, 'before_cursor_execute')
def prevent_writes(conn, cursor, statement, parameters, context, executemany):
    if statement.lstrip().split(None,1)[0].upper() not in {'SELECT','SHOW','SET','BEGIN','ROLLBACK','COMMIT'}:
        raise RuntimeError('Audit database writes prohibited')
from app.services.runtime_config_resolver import runtime_config_resolver
from app.services.runtime_config_store import runtime_config_store
import httpx, requests
ROOT=Path('/home/zxqs_ep/Edu_AI')
OUT=ROOT/'docs/acceptance/2026-10-17-local-model-integration-audit'
results={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope':'real services via project adapters; no production business writes, no restart', 'http_calls':[]}
def safe_url(value):
    u=urlsplit(str(value)); return f'{u.scheme}://{u.hostname}' + (f':{u.port}' if u.port else '') + u.path
orig_http=httpx.Client.send
orig_async=httpx.AsyncClient.send
orig_req=requests.Session.send
def http_send(self,request,*a,**kw):
    r=orig_http(self,request,*a,**kw); results['http_calls'].append({'method':request.method,'url':safe_url(request.url),'status':r.status_code}); return r
async def async_send(self,request,*a,**kw):
    r=await orig_async(self,request,*a,**kw); results['http_calls'].append({'method':request.method,'url':safe_url(request.url),'status':r.status_code}); return r
def req_send(self,request,*a,**kw):
    r=orig_req(self,request,*a,**kw); results['http_calls'].append({'method':request.method,'url':safe_url(request.url),'status':r.status_code}); return r
httpx.Client.send=http_send; httpx.AsyncClient.send=async_send; requests.Session.send=req_send
fields=('provider_name','base_url','model','dimensions','_source','_revision_id','_local_only')
results['effective_config']={p:{k:v for k,v in runtime_config_resolver.resolve(p).items() if k in fields} for p in ('tts','embedding','pdf_parser')}
records=runtime_config_store._repository().list('runtime_config') if runtime_config_store._uses_postgres() else []
results['active_config_profiles']=[]
for rec in records:
    if rec.get('provider') not in ('tts','embedding','pdf_parser') or not rec.get('active_revision_id'): continue
    revision=next((v for v in rec.get('revisions',[]) if v['revision_id']==rec['active_revision_id']),None)
    if revision:
        value=runtime_config_store._decrypt(revision['encrypted_payload'])
        results['active_config_profiles'].append({'scope':rec.get('scope'),'provider':rec['provider'],'base_url':safe_url(value.get('base_url','')),'model':value.get('model')})
results['deployment']={k:os.getenv(k) for k in ('TTS_LOCAL_ONLY','PDF_PARSER_PROVIDER','PDF_MINERU_LOCAL_BASE_URL','VECTOR_DB_PATH','RAG_ENABLE_IMAGE_EMBEDDING')}
results['services']=subprocess.check_output(['systemctl','show','edu-ai-backend','edu-ai-tts','edu-ai-embedding','edu-ai-mineru','-p','Id','-p','ActiveState','-p','MainPID','-p','ExecMainStartTimestamp'],text=True)
for port,path in [(8001,'/health'),(8188,'/health'),(8189,'/health'),(8190,'/v1/health')]:
    r=httpx.get(f'http://127.0.0.1:{port}{path}',trust_env=False,timeout=10); results[f'health_{port}']={'status':r.status_code,'body':r.json()}
print('config_and_health',json.dumps({k:v for k,v in results.items() if k not in ('http_calls','services')},ensure_ascii=False),flush=True)

def tts():
    from app.services.classroom_narration import narration_audio
    start=time.monotonic()
    path=asyncio.run(narration_audio(action={'text':'这是十月十七日的本地模型接入验证。'},audio_dir=OUT/'audio'))
    duration=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True).strip()
    return {'ok':True,'seconds':round(time.monotonic()-start,3),'bytes':path.stat().st_size,'audio_seconds':float(duration),'artifact':str(path.relative_to(OUT))}
def embedding():
    from modules.rag_v2.rag_main.system import EmbeddingClient
    c=EmbeddingClient(Config.EMBEDDING_API_BASE,model=Config.EMBEDDING_MODEL)
    start=time.monotonic(); vectors=c.embed_documents(['快速排序通过划分区间完成排序。','归并排序采用分治策略合并有序序列。'])
    answer={'ok':len(vectors)==2 and all(len(v)==1024 and all(math.isfinite(x) for x in v) for v in vectors),'seconds':round(time.monotonic()-start,3),'api_base':c.api_base,'model':c.model,'dimensions':[len(v) for v in vectors]}
    db=Path(Config.VECTOR_DB_PATH)/'chroma.sqlite3'
    with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as conn:
        answer['index_dimensions']=conn.execute('select dimension from collections').fetchall()
        answer['index_vectors']=conn.execute('select count(*) from embeddings').fetchone()[0]
    return answer

def pdf():
    from app.integrations.pdf import get_pdf_parser
    from app.course_preparation.adapters.documents import DocumentParser
    provider=get_pdf_parser(); observed={}; real_parse=provider.parse
    def traced(*a,**kw):
        result=real_parse(*a,**kw); observed['metadata']=result.metadata; return result
    provider.parse=traced
    source=ROOT/'docs/acceptance/2026-10-17-deeptutor-migration-m3/sample-paper.pdf'
    data=source.read_bytes(); start=time.monotonic()
    parsed=DocumentParser().parse(data,filename='integration-audit-sample.pdf',deadline=time.monotonic()+120)
    provider.parse=real_parse
    (OUT/'parsed-sample.md').write_text(parsed.content)
    return {'ok':bool(parsed.content),'seconds':round(time.monotonic()-start,3),'provider':type(provider).__name__,'base_url':provider.base_url,'characters':len(parsed.content),'defects':parsed.defects,'layout_count':len(parsed.layout),'asset_count':len(parsed.assets),'metadata':observed['metadata'],'sample_sha256':hashlib.sha256(data).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(fn):name for name,fn in [('tts',tts),('embedding',embedding),('pdf',pdf)]}
    for future in concurrent.futures.as_completed(futures):
        name=futures[future]
        try: results[name]=future.result()
        except Exception as exc: results[name]={'ok':False,'exception_type':type(exc).__name__,'error':str(exc)[:500]}
        print(name,json.dumps(results[name],ensure_ascii=False),flush=True)
from app.exam_generation.snapshots import SnapshotCodec
codec=SnapshotCodec()
audit_owner='local-model-integration-readonly-audit'
exam_parser=codec.read(audit_owner,codec.capture(audit_owner))['pdf_parser']
results['exam_parser_snapshot']={k:exam_parser.get(k) for k in ('provider_name','base_url','model','_source')}
(OUT/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print('saved',OUT/'verification.json',flush=True)
