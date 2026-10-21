import copy
import json
from pathlib import Path
import pytest
from app.pbl.contracts import normalize_candidate, public_artifact, hash_code
from app.pbl.schemas import TEMPLATE_VERSION

@pytest.fixture
def candidate_payload():
    return json.loads((Path(__file__).parent/'fixtures/candidate.json').read_text())

def test_publication_whitelist_and_trusted_cases(candidate_payload):
    c=normalize_candidate(candidate_payload)
    assert len(c.testCases)==9
    p=public_artifact(c,exercise_id='pbl_test',artifact_version=1,validation_summary={'passed':True,'templateVersion':TEMPLATE_VERSION})
    assert 'referenceSolution' not in p.model_dump()
    assert candidate_payload['referenceSolution'] not in p.model_dump_json()
    assert len(p.tasks)==1 and set(p.tasks[0].testCaseIds)=={x.id for x in c.testCases}

@pytest.mark.parametrize('mutation',[
 lambda p:p.update(owner='alice'),lambda p:p['contract'].update(exportName='sort'),
 lambda p:p['testCases'][0].update(expected=[9]),lambda p:p['testCases'][0].update(input=[True]),
 lambda p:p['testCases'][0].update(input=[float('inf')]),
 lambda p:p['testCases'].append(copy.deepcopy(p['testCases'][0])),
 lambda p:p['tasks'].append(copy.deepcopy(p['tasks'][0])),
])
def test_invalid_candidate_rejected(candidate_payload,mutation):
    mutation(candidate_payload)
    with pytest.raises(ValueError):normalize_candidate(candidate_payload)

def test_no_publish_without_validation(candidate_payload):
    with pytest.raises(ValueError):public_artifact(normalize_candidate(candidate_payload),exercise_id='x',artifact_version=1,validation_summary={})

def test_code_hash_fixture():
    fixture=json.loads((Path(__file__).parents[4]/'frontend/src/pbl/fixtures/code-hash.json').read_text())
    for row in fixture: assert hash_code(row['code'])==row['hash']
