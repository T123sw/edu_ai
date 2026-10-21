import json
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.chat.runtime.model_registry import build_default_gateway
from app.chat.harness.reviewed_resource import review_content
from app.chat.harness.numeric_checks import verify_calculations
source=json.loads((ROOT/'docs/acceptance/2026-10-19-transformer-generation-watch/numeric-spotcheck-source.json').read_text())
content={'title':'自注意力计算复核','questions':source['questions']}
start=time.monotonic()
review,feedback=review_content('quiz',content,{'title':content['title'],'audience':'初学者'},build_default_gateway())
evidence=[{'question_index':q.question_index,'checks':verify_calculations(content['questions'][q.question_index],q.calculation_checks)[0]} for q in review.question_checks]
result={'seconds':time.monotonic()-start,'feedback':feedback,'review':review.model_dump(),'numeric_evidence':evidence}
(ROOT/'docs/acceptance/2026-10-19-adaptive-video-concurrency/live-numeric-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'seconds':result['seconds'],'rejected':bool(feedback),'claims':sum(len(q.calculation_checks) for q in review.question_checks),'computed_failures':sum(c['status']=='fail' for q in evidence for c in q['checks'])},ensure_ascii=False))
assert feedback,'Known erroneous quiz must not pass'
