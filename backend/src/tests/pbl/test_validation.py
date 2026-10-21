import json
from pathlib import Path
from app.pbl.contracts import normalize_candidate
from app.pbl.validation import validate_candidate

def test_python_to_shared_browser_runtime():
    candidate=normalize_candidate(json.loads((Path(__file__).parent/'fixtures/candidate.json').read_text()))
    report=validate_candidate(candidate)
    assert report['passed'] and report['templateVersion']=='js-function-v1'
    assert len(report['caseResults'])==len(candidate.testCases)
    assert all(c['status']=='passed' for c in report['caseResults'])
