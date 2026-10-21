"""Read-only receipt audit; no content review or model invocation."""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend/src'))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(ROOT / '.env')
engine = create_engine(os.environ['DATABASE_URL'], connect_args={
    'options': '-c default_transaction_read_only=on -c statement_timeout=10000'})
state = json.loads((OUT / 'latest.json').read_text())
artifacts = {a['id']: a for a in state['artifacts']}
with engine.connect() as connection:
    rows = [dict(r) for r in connection.execute(text(
        'select action_id,action_key,kind,status,created_at,payload,consumed,receipt '
        'from preparation_actions where preparation_id=:id order by created_at'),
        {'id': state['preparation_id']}).mappings()]
(OUT / 'actions.json').write_text(json.dumps(rows, ensure_ascii=False, default=str, indent=2))
resources, failed, recoveries = defaultdict(list), [], []
for row in rows:
    key = row['action_key'].split(':')
    artifact = artifacts.get(key[1]) if key[0] == 'child' and len(key) > 1 else None
    model = (row['receipt'] or {}).get('model_response') or {}
    response = model.get('response') or {}
    record = {'action_id': row['action_id'], 'at': str(row['created_at']), 'status': row['status'],
              'phase': model.get('phase') or ('native_video' if artifact and artifact['type'] == 'classroom' else None),
              'protocol_attempt': model.get('protocol_recovery_attempt'), 'usage': response.get('usage'),
              'finish_reasons': [c.get('finish_reason') for c in response.get('choices', [])]}
    if artifact and row['kind'] == 'model_completion':
        resources[artifact['id']].append(record)
    if row['status'] == 'failed':
        failed.append({**record, 'kind': row['kind'], 'artifact': artifact, 'receipt': row['receipt']})
    if model.get('protocol_recovery_attempt', 0):
        recoveries.append({**record, 'node': artifact['node'] if artifact else None,
                           'resource_type': artifact['type'] if artifact else None})
quizzes = []
for artifact in artifacts.values():
    if artifact['type'] != 'quiz':
        continue
    path = OUT / artifact['id'] / 'content.json'
    content = json.loads(path.read_text()) if path.exists() else {}
    receipt = (content.get('generation_state') or {}).get('resource_review') or {}
    quizzes.append({'node': artifact['node'], 'status': artifact['status'],
                    'questions': len((content.get('content') or {}).get('questions', [])),
                    'receipt': receipt, 'model_calls': resources[artifact['id']]})
audit = {'at': datetime.now(timezone.utc).isoformat(),
         'action_counts': dict(Counter(r['status'] for r in rows)),
         'protocol_recoveries': recoveries, 'failed_actions': failed,
         'resource_model_calls': dict(resources), 'quizzes': quizzes}
(OUT / 'action-audit.json').write_text(json.dumps(audit, ensure_ascii=False, default=str, indent=2))
print(json.dumps({'action_counts': audit['action_counts'], 'failed_actions': len(failed),
                  'protocol_recoveries': len(recoveries), 'quizzes': [
                      {'node': q['node'], 'questions': q['questions'],
                       'model_calls': len(q['model_calls']),
                       'phases': [r['phase'] for r in q['model_calls']]} for q in quizzes]}, ensure_ascii=False))
