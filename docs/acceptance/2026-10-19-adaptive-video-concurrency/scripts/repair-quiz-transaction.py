"""Audited, versioned data repair; never rewrite historical versions or task status."""
import copy,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.database.models import (Material,MaterialVersion,PreparedManifestVersion,PreparedCoursePointer,
    AppStateRecord,CourseMembership,User,PreparationArtifact)
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.course_preparation.manifest import CourseManifest
from app.course_preparation.tool_registry import digest as value_digest
from app.chat.harness.reviewed_resource import review_content,verified_resource,digest,validate_resource
from app.chat.harness.numeric_checks import verify_calculations
from app.chat.runtime.model_registry import build_default_gateway

OUT=ROOT/'docs/acceptance/2026-10-19-adaptive-video-concurrency'
OWNER='teacher';COURSE='learn-65488c25779346448e1dcbe0b809d73e';RID='resource_471ae3cd827344574d74384701f842c1'
AUDIT='numeric_correction_transformer_n2_20261019'
engine=create_engine(os.environ['DATABASE_URL'])
with Session(engine) as session:
    existing=session.get(AppStateRecord,('prepared_resource_corrections',AUDIT))
    if existing:
        (OUT/'operator-correction.json').write_text(json.dumps(existing.payload,ensure_ascii=False,indent=2))
        print(json.dumps(existing.payload,ensure_ascii=False));sys.exit()
    pointer=session.get(PreparedCoursePointer,(OWNER,COURSE))
    assert pointer.version==22,'Base manifest changed'
    base_manifest=session.get(PreparedManifestVersion,(OWNER,COURSE,22))
    manifest=copy.deepcopy(base_manifest.payload)
    source_preparation=base_manifest.preparation_id
    row=session.scalar(select(MaterialVersion).where(MaterialVersion.course_id==COURSE,
        MaterialVersion.material_id==RID,MaterialVersion.version==2))
    old=copy.deepcopy(row.payload)
    source=session.scalar(select(PreparationArtifact).where(PreparationArtifact.resource_id==RID,
        PreparationArtifact.resource_version==2,PreparationArtifact.status=='draft'))
    spec=copy.deepcopy(source.spec)
artifact=copy.deepcopy(old['preparation_artifact'])
content=artifact['content']
replacements=json.loads((OUT/'quiz-exact-revision.json').read_text())['replacements']
replacements['q6-hand-calc-weights']['explanation']=replacements['q6-hand-calc-weights']['explanation'].replace(
    '第二行与第一行对称', '第二行权重约为 [0.1977758146404282,0.4011120926797859,0.4011120926797859]，即第一行的前两个分量互换')
for question in content['questions']:
    if question['id'] in replacements:question.update(replacements[question['id']])
validate_resource('quiz',content)
metadata=artifact['generation_state'].get('preparation')
original=json.loads((OUT/'quiz-original.json').read_text())
metadata['objective_bindings']=copy.deepcopy(original['preparation_artifact']['generation_state']['preparation']['objective_bindings'])
review_spec={'title':artifact['title'],'teaching_context':spec.get('teaching_context'),
    'requirements':(spec.get('teaching_context') or {}).get('requirements',[]),
    'requirement_ids':(spec.get('teaching_context') or {}).get('requirement_ids',[]),
    **({'preparation':metadata} if metadata else {})}
cache=OUT/'corrected-quiz-review.json'
if cache.exists():
    saved=json.loads(cache.read_text())
    assert saved['candidate_digest']==value_digest(content),'Review candidate changed'
    from app.chat.harness.reviewed_resource import PreparationQuizReview,BoundQuizReview,review_feedback
    schema=PreparationQuizReview if metadata else BoundQuizReview
    review=schema.model_validate(saved['review']);feedback=review_feedback('quiz',content,review)
else:
    started=time.monotonic()
    class RecordedGateway:
        def __init__(self, gateway): self.gateway=gateway
        def __getattr__(self, name): return getattr(self.gateway,name)
        def with_response_schema(self, schema):
            method=getattr(self.gateway,'with_response_schema',None)
            return RecordedGateway(method(schema)) if callable(method) else self
        def chat(self, *args, **kwargs):
            raw=self.gateway.chat(*args,**kwargs)
            index=len(list(OUT.glob('operator-review-raw-*.json')))+1
            (OUT/f'operator-review-raw-{index}.json').write_text(json.dumps({'raw':raw},ensure_ascii=False,indent=2))
            return raw
    review,feedback=review_content('quiz',content,review_spec,RecordedGateway(build_default_gateway()))
    cache.write_text(json.dumps({'candidate_digest':value_digest(content),'review':review.model_dump(),
        'feedback':feedback,'seconds':time.monotonic()-started},ensure_ascii=False,indent=2))
if feedback:
    print(json.dumps({'status':'review_rejected','feedback':feedback},ensure_ascii=False));sys.exit(3)
numeric=[{'question_index':q.question_index,'checks':verify_calculations(content['questions'][q.question_index],q.calculation_checks)[0]} for q in review.question_checks]
audit={'decision':'pass','method':'model_review','resource_type':'quiz','content_sha256':digest('quiz',content),
    'checks':review.model_dump()['checks'],'suggestions':review.suggestions,'question_checks':review.model_dump()['question_checks'],
    'option_binding_version':1,'numeric_verification':{'version':1,'coverage':'source_bound_claims_and_literal_softmax','questions':numeric},
    'revision_provenance':{'method':'authorized_targeted_numeric_data_repair','audit_id':AUDIT,'base_resource_version':2}}
if metadata:
    audit.update(preparation_sha256=value_digest(metadata),preparation_checks=review.model_dump()['preparation_checks'])
artifact['generation_state']['resource_review']=audit
assert verified_resource(artifact,'quiz'),'Fresh review receipt must pass normal verification'
new_digest=value_digest(artifact)
updated=copy.deepcopy(old)
updated.update(content=content,questions=content['questions'],generation_state=artifact['generation_state'],
    preparation_artifact=artifact,version=3,content_hash=new_digest,updated_at=datetime.now(timezone.utc).isoformat(),
    numeric_correction_audit_id=AUDIT)
old_questions={q['id']:q for q in old['content']['questions']}
assert [q['id'] for q in content['questions']]==list(old_questions)
assert {q['id'] for q in content['questions'] if q!=old_questions[q['id']]}==set(replacements)
for q in content['questions']:
    if q['id'] in replacements:
        assert {k:v for k,v in q.items() if k not in ('answer','explanation')}=={k:v for k,v in old_questions[q['id']].items() if k not in ('answer','explanation')}
for node in manifest['nodes']:
    for resource in node['resources']:
        if resource['resource_id']==RID:resource.update(version=3,content_sha256=new_digest)
    for check in node['checks']:
        if check['resource_id']==RID:check['resource_version']=3
manifest['version']=23
# The originating preparation remains the lineage. The new correction has an
# explicit, separately persisted quality/audit record, not a fabricated task.
manifest['quality_report_id']=AUDIT
manifest=CourseManifest.model_validate(manifest).model_dump(mode='json')
record={'method':'authorized_targeted_numeric_data_repair','actor':OWNER,'course_id':COURSE,'resource_id':RID,
    'base_resource_version':2,'resource_version':3,'base_manifest_version':22,'manifest_version':23,
    'base_content_digest':old['content_hash'],'content_digest':new_digest,
    'source_preparation_id':source_preparation,'review_digest':value_digest(audit),
    'changed_fields':['q6.answer','q6.explanation','q7.answer','q7.explanation'],
    'restored_original_objective_bindings':True,
    'numeric_checks':sum(len(q['checks']) for q in numeric),'at':datetime.now(timezone.utc).isoformat()}
# Prepare durable files before the only mutation, for review and recovery.
(OUT/'operator-candidate.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2))
with Session(engine) as session,session.begin():
    pointer=session.scalar(select(PreparedCoursePointer).where(PreparedCoursePointer.owner_user_id==OWNER,
        PreparedCoursePointer.course_id==COURSE).with_for_update())
    material=session.scalar(select(Material).where(Material.course_id==COURSE,Material.material_id==RID,
        Material.material_type=='quiz').with_for_update())
    user=session.get(User,OWNER)
    assert user and not user.is_disabled and session.get(CourseMembership,(COURSE,OWNER))
    assert pointer.version==22 and material.version==2 and material.content_hash==old['content_hash'],'Base changed; no repair published'
    assert session.get(AppStateRecord,('prepared_resource_corrections',AUDIT)) is None
    assert session.get(PreparedManifestVersion,(OWNER,COURSE,23)) is None
    assert session.scalar(select(MaterialVersion).where(MaterialVersion.course_id==COURSE,MaterialVersion.material_id==RID,MaterialVersion.version==3)) is None
    PostgresMaterialRepository(engine).upsert(updated,session=session)
    session.add(AppStateRecord(namespace='prepared_resource_corrections',record_key=AUDIT,owner_user_id=OWNER,payload=record))
    session.add(PreparedManifestVersion(owner_user_id=OWNER,course_id=COURSE,version=23,
        manifest_id=manifest['manifest_id'],preparation_id=source_preparation,payload=manifest,content_digest=value_digest(manifest)))
    pointer.version=23
(OUT/'operator-correction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({'status':'published',**record},ensure_ascii=False))
