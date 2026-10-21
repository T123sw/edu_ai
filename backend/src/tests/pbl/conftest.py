import json
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from app.pbl.db_models import PblExercise,PblWorkspace,PblRun,PblTutorTurn
from app.pbl.repository import PblRepository
from app.pbl.contracts import normalize_candidate,public_artifact,hash_code
from app.pbl.schemas import TEMPLATE_VERSION

@pytest.fixture
def engine(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'pbl.db'),connect_args={'check_same_thread':False})
    for model in (PblExercise,PblWorkspace,PblRun,PblTutorTurn): model.__table__.create(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def repository(engine): return PblRepository(engine=engine)

@pytest.fixture
def candidate():
    return normalize_candidate(json.loads((Path(__file__).parent/'fixtures/candidate.json').read_text()))

@pytest.fixture
def validation_report(): return {'passed':True,'templateVersion':TEMPLATE_VERSION,'caseResults':[]}

@pytest.fixture
def exercise(repository): return repository.create_or_get('alice',str(uuid4()),'快速排序')

@pytest.fixture
def ready_exercise(repository,exercise,candidate,validation_report):
    artifact=public_artifact(candidate,exercise_id=exercise.id,artifact_version=1,validation_summary=validation_report)
    repository.publish('alice',exercise.id,exercise.current_job_id,artifact,candidate.model_dump(mode='json'),validation_report)
    return repository.get_owned('alice',exercise.id)

@pytest.fixture
def patch():
    return {'artifactVersion':1,'expectedRevision':0,'mutationId':str(uuid4()),
        'files':{'/src/algorithm.js':'new code'},'activeTaskId':'implement-sort','customInputText':'[]'}

@pytest.fixture
def run(ready_exercise,candidate):
    return {'runId':str(uuid4()),'exerciseId':ready_exercise.id,'artifactVersion':1,
        'templateVersion':TEMPLATE_VERSION,'taskId':'implement-sort','code':candidate.referenceSolution,
        'codeHash':hash_code(candidate.referenceSolution),'mode':'check','cases':[c.model_dump() for c in candidate.testCases],
        'status':'passed','results':[{'caseId':c.id,'status':'passed','actual':c.expected,'expected':c.expected,
            'inputAfter':c.input,'returnedSameReference':False} for c in candidate.testCases],
        'durationMs':12,'evidenceSource':'browser_reported'}
