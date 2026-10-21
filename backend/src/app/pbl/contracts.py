"""Compatibility contracts for existing v1 artifacts; not used to plan new projects."""
import hashlib
import json
from .schemas import GeneratedExerciseCandidate, ExerciseArtifact, TEMPLATE_VERSION

BASE_CASES = [
 ('mixed','普通乱序',[4,1,3,2]), ('duplicates','重复元素',[3,1,3,2]),
 ('negative','负数与零',[0,-2,5,-1]), ('empty','空数组',[]), ('single','单元素',[7]),
 ('sorted','已排序',[1,2,3]), ('reversed','逆序',[3,2,1]),
 ('numeric','数值顺序',[10,2,1]), ('decimal','小数',[1.5,-0.5,0]),
]

def hash_code(code: str) -> str:
    payload=json.dumps([['/src/algorithm.js',code]],ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def normalize_candidate(payload: dict) -> GeneratedExerciseCandidate:
    candidate=GeneratedExerciseCandidate.model_validate(payload)
    ids=[c.id for c in candidate.testCases]
    if len(set(ids))!=len(ids): raise ValueError('用例编号重复')
    for case in [*candidate.testCases, *candidate.tasks[0].examples]:
        if case.expected != sorted(case.input): raise ValueError('预期结果不是输入的数值升序排列')
    cases=[c.model_dump() for c in candidate.testCases]
    for name,label,values in BASE_CASES:
        if not any(c['input']==values for c in cases):
            identifier='base-'+name
            while identifier in ids: identifier='base-'+identifier
            ids.append(identifier)
            cases.append(dict(id=identifier,label=label,input=values,expected=sorted(values)))
    return GeneratedExerciseCandidate.model_validate({**candidate.model_dump(),'testCases':cases})

def public_artifact(candidate: GeneratedExerciseCandidate, *, exercise_id: str, artifact_version: int,
                    validation_summary: dict, topic: str = '快速排序') -> ExerciseArtifact:
    if not validation_summary.get('passed') or validation_summary.get('templateVersion')!=TEMPLATE_VERSION:
        raise ValueError('材料尚未通过当前模板验证')
    # Deliberately enumerate fields; candidate-private data never crosses this boundary.
    return ExerciseArtifact(exerciseId=exercise_id,artifactVersion=artifact_version,topic=topic,
        title=candidate.title,summary=candidate.summary,contract=candidate.contract,
        tasks=[{**t.model_dump(),'testCaseIds':[c.id for c in candidate.testCases]} for t in candidate.tasks],
        starterCode=candidate.starterCode,testCases=candidate.testCases,
        validationSummary={'passed':True,'templateVersion':TEMPLATE_VERSION})
