import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.database.models import (CoursePreparationRecord,CoursePreparationAttemptRecord,PreparationExecution,
    MaterialVersion,PreparedManifestVersion)
from app.chat.harness.numeric_checks import CalculationCheck, verify_calculations
root=ROOT/'docs/acceptance/2026-10-19-adaptive-video-concurrency'
minimal = (root/'quiz-minimal-revision.json').exists()
request=json.loads((root/('quiz-minimal-revision.json' if minimal else 'quiz-exact-revision.json')).read_text());pid=request['receipt']['preparation_id']
course='learn-65488c25779346448e1dcbe0b809d73e';rid='resource_471ae3cd827344574d74384701f842c1'
with Session(create_engine(os.environ['DATABASE_URL'])) as s:
    prep=s.get(CoursePreparationRecord,pid)
    attempt=s.get(CoursePreparationAttemptRecord,(pid,prep.current_attempt_no))
    run=s.get(PreparationExecution,(pid,prep.current_attempt_no))
    operator = json.loads((root/'operator-correction.json').read_text()) if (root/'operator-correction.json').exists() else None
    if attempt.status!='succeeded' and operator is None:
        print(json.dumps({'status':attempt.status,'stage':attempt.stage}));sys.exit(2)
    result_ref = {'manifest_version':operator['manifest_version']} if operator else run.result_ref
    material=s.scalar(select(MaterialVersion).where(MaterialVersion.course_id==course,
        MaterialVersion.material_id==rid).order_by(MaterialVersion.version.desc()))
    current=material.payload;old=json.loads((root/'quiz-original.json').read_text())
    questions=current['content']['questions'];qs={q['id']:q for q in questions}
    mismatches=[key+'.'+field for key,changes in request.get('replacements', {}).items() for field,value in changes.items() if qs[key][field]!=value]
    # Recompute all full-precision vectors supplied in the exact replacement.
    claims=[('q6-hand-calc-weights','softmax([1/sqrt(2),0,1/sqrt(2)])','[0.4011120926797859,0.1977758146404282,0.4011120926797859]'),
            ('q6-hand-calc-weights','softmax([1/sqrt(2),1/sqrt(2),sqrt(2)])','[0.2482550782577231,0.2482550782577231,0.5034898434845538]'),
            ('q6-hand-calc-weights','softmax([1,0,1])','[0.4223187982515182,0.15536240349696362,0.4223187982515182]'),
            ('q7-hand-calc-output','weighted_sum(softmax([1/sqrt(2),0,1/sqrt(2)]),[[1,0],[0,1],[1,1]])','[0.8022241853595718,0.5988879073202141]'),
            ('q7-hand-calc-output','weighted_sum(softmax([1/sqrt(2),1/sqrt(2),sqrt(2)]),[[1,0],[0,1],[1,1]])','[0.7517449217422769,0.7517449217422769]'),
            ('q7-hand-calc-output','weighted_sum(softmax([1,0,1]),[[1,0],[0,1],[1,1]])','[0.8446375965030364,0.5776812017484818]')]
    evidence=[];errors=[]
    for key,expression,claimed in claims:
        check=CalculationCheck(source_field='explanation',excerpt=qs[key]['explanation'],expression=expression,claimed=claimed,decimal_places=16)
        rows, feedback=verify_calculations(qs[key],[check]);evidence.extend(rows);errors.extend(feedback)
    original_manifest=s.get(PreparedManifestVersion,('teacher',course,21)).payload
    latest=s.get(PreparedManifestVersion,('teacher',course,result_ref['manifest_version'])).payload
    other_resources=lambda m:{r['resource_id']:r for n in m['nodes'] for r in n['resources'] if r['resource_id']!=rid}
    report={'status':'succeeded','method':'authorized_targeted_numeric_data_repair' if operator else 'preparation_revision','preparation_id':None if operator else pid,'resource_version':material.version,
        'manifest_version':result_ref['manifest_version'],'exact_replacements_match':None if minimal else not mismatches,'mismatches':mismatches,
        'same_question_ids':[q['id'] for q in old['content']['questions']]==[q['id'] for q in questions],
        'changed_questions':[q['id'] for q in old['content']['questions'] if q!=qs[q['id']]],
        'other_resources_unchanged':other_resources(original_manifest)==other_resources(latest),
        'route_version_unchanged':original_manifest['route_version']==latest['route_version'],
        'original_objective_bindings_restored':old['preparation_artifact']['generation_state']['preparation']['objective_bindings']==current['preparation_artifact']['generation_state']['preparation']['objective_bindings'],
        'obsolete_intermediate_values_absent':not any(value in qs[key]['explanation'] for key in ('q6-hand-calc-weights','q7-hand-calc-output') for value in ('0.40110905','0.19778190','2.02811383','5.05622766','8.16947804')),
        'numeric_errors':errors,'numeric_evidence':evidence}
    (root/'quiz-final.json').write_text(json.dumps(current,ensure_ascii=False,indent=2,default=str))
    (root/'quiz-final-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='numeric_evidence'},ensure_ascii=False))
    assert not mismatches and not errors and report['same_question_ids'] and report['other_resources_unchanged'] and report['route_version_unchanged'] and report['obsolete_intermediate_values_absent'] and report['original_objective_bindings_restored']
