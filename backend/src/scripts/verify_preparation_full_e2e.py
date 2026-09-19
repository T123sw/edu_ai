"""Real HTTP -> durable workers -> PostgreSQL -> exact learning versions.

No runner invocation, model substitution, automatic migration or mock fallback.
Exit 0 means automated checks passed; 1 failed; 2 preflight/scenario not_run.
"""
import argparse
import io
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from scripts.preparation_validation_common import (
    database_identity, digest, git_identity, local_http, write_json,
)

CASES = Path(__file__).with_name('preparation_cases') / 'scenarios.json'
STAGES = {'normalize', 'ingest', 'research_scope', 'plan', 'research_nodes', 'produce', 'review', 'commit'}
TERMINAL = {'succeeded', 'failed', 'canceled'}


def fixture_bytes(name):
    from docx import Document
    doc = Document()
    if name == 'fractions':
        paragraphs = [
            '分数加法：分母表示整体被等分的份数，分子表示取了几份。',
            '一张披萨等分4份，先吃1份再吃2份，共吃3份：1/4+2/4=3/4。同分母相加只加分子，分母不变。',
            '异分母先通分。1/2=2/4，所以1/2+1/4=2/4+1/4=3/4。可以用相同大小的整体画图验证。',
            '不能把分母直接相加：1/2+1/2=1，而不是2/4。练习：1/3+1/3=2/3；1/2+1/3=3/6+2/6=5/6。',
            '学习先修是整数加法和等分。目标是解释同分母加法并完成异分母通分计算。自测要解释为何整体大小必须相同。',
        ]
    else:
        paragraphs = [
            '最小工具调用：模型选择工具，程序校验和执行。仅手工追踪伪代码，不包含任何真实供应商SDK、鉴权或API实现。',
            '工具add(a,b)只接受两个数字，返回a+b。模型发出name、arguments、call_id；程序校验已注册工具名和参数，执行后把结果与同一call_id回传模型。',
            '成功例：12加30，name=add，a=12，b=30；参数合法，执行结果42。日志包括用户问题、工具参数、执行结果及最终回答。',
            '失败例：add(a=12)缺少b；返回INVALID_ARGUMENT，message=b is required；不执行add，不把失败当作0或编造成功结果。',
            '伪代码：name不是add则UNKNOWN_TOOL；a或b不是数字则INVALID_ARGUMENT；否则返回a+b。禁止执行模型任意代码。',
            '节点1先用12加30的例子解释模型与程序职责；节点2追踪成功和失败分支。自测：谁执行工具？参数缺失时为什么不能相加？',
            '真实API程序还需要官方SDK、安装、鉴权及具体接口版本；附件没有这些内容，不能用本材料证明已经实现真实API。',
        ]
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def assert_harness_receipts(actions):
    completions = [a for a in actions if a['kind'] == 'model_completion' and a['status'] == 'completed']
    if not completions:
        raise AssertionError('NO_REAL_MODEL_COMPLETIONS')
    for action in completions:
        receipt = action.get('receipt') or {}
        response = receipt.get('model_response') or {}
        skill = response.get('skill') or {}
        assert response.get('runtime') == 'deepseek-harness', 'COMPLETION_BYPASSED_HARNESS'
        assert response.get('phase'), 'COMPLETION_PHASE_MISSING'
        assert response.get('spec_digest'), 'COMPLETION_SPEC_DIGEST_MISSING'
        assert skill.get('name') and len(skill.get('sha256', '')) == 64 and skill.get('loaded') is True, 'SKILL_LOAD_RECEIPT_MISSING'
        assert (receipt.get('usage') or {}).get('reported_by_provider') is True, 'REAL_USAGE_MISSING'
        assert (response.get('response') or {}).get('model') or response.get('model'), 'MODEL_IDENTITY_MISSING'
    return len(completions)


def assert_outcome(case, public, evidence):
    assert public['status'] == case['expected_business_status'], 'UNEXPECTED_BUSINESS_STATUS'
    if public['status'] == 'failed':
        assert public.get('error_code') == case['expected_error_code'], 'WRONG_BUSINESS_FAILURE'
        assert not public.get('result_ref') and not evidence['manifests'], 'FAILED_TASK_DELIVERED_COURSE'
        assert evidence['checkpoint'].get('research_blocker'), 'RESEARCH_GAP_DETAILS_MISSING'
    else:
        assert (public.get('result_ref') or {}).get('course_ready') is True, 'COURSE_NOT_COMMITTED'
        assert evidence['manifests'], 'MANIFEST_MISSING'
        assert STAGES <= set(evidence['stages']), 'STAGE_EVIDENCE_INCOMPLETE'
        manifest = evidence['manifests'][-1]
        assert len(manifest['nodes']) == 2, 'EXPECTED_TWO_NODES'
        for node in manifest['nodes']:
            for resource in node['resources']:
                assert any(a['resource_id'] == resource['resource_id'] and a['resource_version'] == resource['version'] and a['status'] in ('draft', 'committed') for a in evidence['artifacts']), 'COMMITTED_ARTIFACT_MISSING'
            assert {'report', 'quiz', 'classroom'} <= {r['resource_type'] for r in node['resources'] if r['required']}, 'REQUIRED_RESOURCE_MISSING'
    assert_harness_receipts(evidence['actions'])


def collect_evidence(engine, owner, preparation_id):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.database.models import (CoursePreparationRecord, PreparationExecution, PreparationAction,
        PreparationArtifact, PreparationBudget, PreparedManifestVersion, CoursePreparationEventRecord)
    with Session(engine) as session:
        prep = session.get(CoursePreparationRecord, preparation_id)
        if prep is None or prep.owner_user_id != owner:
            raise AssertionError('HTTP_DATABASE_OR_OWNER_MISMATCH')
        executions = list(session.scalars(select(PreparationExecution).where(PreparationExecution.preparation_id == preparation_id).order_by(PreparationExecution.attempt_no)))
        actions = list(session.scalars(select(PreparationAction).where(PreparationAction.preparation_id == preparation_id).order_by(PreparationAction.created_at)))
        artifacts = list(session.scalars(select(PreparationArtifact).where(PreparationArtifact.preparation_id == preparation_id)))
        budget = session.get(PreparationBudget, preparation_id)
        manifests = list(session.scalars(select(PreparedManifestVersion).where(PreparedManifestVersion.preparation_id == preparation_id).order_by(PreparedManifestVersion.version)))
        events = list(session.scalars(select(CoursePreparationEventRecord).where(CoursePreparationEventRecord.preparation_id == preparation_id).order_by(CoursePreparationEventRecord.sequence)))
        event_rows = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in events]
        stages = {row.get('stage') for row in event_rows}
        for row in event_rows:
            stages.add((row.get('payload') or {}).get('stage'))
        return {
            'checkpoint': executions[-1].checkpoint if executions else {},
            'attempts': [{'attempt_no': r.attempt_no, 'error_code': r.error_code, 'worker_id': r.worker_id} for r in executions],
            'stages': sorted(s for s in stages if s), 'events': event_rows,
            'actions': [{k: getattr(a, k) for k in ('action_id', 'kind', 'status', 'payload', 'receipt', 'reserved', 'consumed')} for a in actions],
            'artifacts': [{k: getattr(a, k) for k in ('artifact_id', 'resource_id', 'resource_version', 'resource_type', 'status', 'spec', 'spec_digest', 'content', 'content_digest', 'error_code')} for a in artifacts],
            'manifests': [m.payload for m in manifests],
            'budget': {'limits': budget.limits, 'reserved': budget.reserved, 'consumed': budget.consumed} if budget else None,
        }


def get_json(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        # Response text can contain configuration details: keep only method/status/path.
        raise RuntimeError(f'HTTP_{response.status_code}:{method}:{path}')
    return response.json()


def learning_readback(client, manifest, artifacts):
    course = manifest['course_id']
    room = get_json(client, 'GET', f'/api/self-learning/courses/{course}')
    results = []
    for node in manifest['nodes']:
        for resource in node['resources']:
            kind, rid, version = resource['resource_type'], resource['resource_id'], resource['version']
            material = get_json(client, 'GET', f'/api/self-learning/courses/{course}/materials/{kind}/{rid}/versions/{version}')
            assert material.get('version') == version, 'LEARNING_VERSION_MISMATCH'
            artifact = next(a for a in artifacts if a['resource_id'] == rid and a['resource_version'] == version)
            assert artifact['content_digest'] == resource['content_sha256'], 'MANIFEST_CONTENT_DIGEST_MISMATCH'
            # Persist the actual readback for semantic review, not only its existence.
            results.append({'resource_id': rid, 'version': version, 'material': material, 'readback_sha256': digest(material)})
    return {'room': room, 'resources': results}


def run_case(client, engine, owner, case, output, timeout):
    start = time.monotonic()
    payload = {'schema_version': 1, 'request_id': str(uuid4()), 'operation': 'create_course',
        'goal': case['goal'], 'source_policy': {'mode': case['source_mode']},
        'overrides': {'language': 'zh-CN', 'total_minutes': 20, 'depth': 'introductory',
                      'required_resource_types': ['report', 'quiz', 'classroom']}}
    data = fixture_bytes(case['fixture'])
    upload = get_json(client, 'POST', '/api/course-preparations/uploads', files={'file': ('source.docx', data, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    payload['uploads'] = [{k: upload[k] for k in ('document_id', 'version')}]
    write_json(output/'request.json', payload)
    accepted = get_json(client, 'POST', '/api/course-preparations', json=payload)
    pid = accepted['preparation_id']
    write_json(output/'accepted.json', accepted)
    result = {'preparation_id': pid, 'test_status': 'failed', 'input_digest': digest(payload), 'upload_sha256': __import__('hashlib').sha256(data).hexdigest()}
    observed = []
    public = None
    try:
        while True:
            public = get_json(client, 'GET', f'/api/course-preparations/{pid}')
            observed.append({'elapsed_seconds': round(time.monotonic()-start, 2), 'public': public})
            write_json(output/'public-state.json', observed)
            if public['status'] in TERMINAL:
                break
            if time.monotonic()-start >= timeout:
                # Explicitly cancel the isolated task so a timed-out test cannot accrue cost indefinitely.
                get_json(client, 'POST', f'/api/course-preparations/{pid}/cancel', json={})
                raise TimeoutError('ACCEPTANCE_TIMEOUT_CANCEL_REQUESTED')
            time.sleep(2)
        result['business_status'] = public['status']
        evidence = collect_evidence(engine, owner, pid)
        evidence['stages'] = sorted(set(evidence['stages']) | {p['public']['stage'] for p in observed})
        write_json(output/'evidence.json', evidence)
        assert_outcome(case, public, evidence)
        if public['status'] == 'succeeded':
            readback = learning_readback(client, evidence['manifests'][-1], evidence['artifacts'])
            write_json(output/'learning-readback.json', readback)
        result.update(test_status='passed', model_completions=assert_harness_receipts(evidence['actions']),
                      budget=evidence['budget'], semantic_review='not_run', browser='not_run')
    except Exception as exc:
        if public is None or public.get('status') not in TERMINAL:
            try:
                canceled = get_json(client, 'POST', f'/api/course-preparations/{pid}/cancel', json={})
                result['cleanup_status'] = canceled.get('status')
            except Exception:
                result['cleanup_status'] = 'cancel_request_failed'
        result['error'] = {'type': type(exc).__name__, 'code': str(exc) if isinstance(exc, (AssertionError, TimeoutError)) else 'SEE_PRIVATE_RUNTIME_LOG'}
        # Even failed model/contract assertions keep terminal checkpoint and cost evidence.
        try:
            failed_evidence = collect_evidence(engine, owner, pid)
            write_json(output/'evidence.json', failed_evidence)
            result['budget'] = failed_evidence['budget']
        except Exception:
            result['evidence_collection'] = 'failed'
    result['elapsed_seconds'] = round(time.monotonic()-start, 2)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--database-url-env', default='PREPARATION_TEST_DATABASE_URL')
    parser.add_argument('--scenario', required=True, choices=[c['scenario'] for c in json.loads(CASES.read_text())['cases']])
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--timeout-seconds', type=int, default=1800)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= 20 or args.timeout_seconds <= 0:
        parser.error('repeat must be 1..20 and timeout must be positive')
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    case = next(c for c in json.loads(CASES.read_text())['cases'] if c['scenario'] == args.scenario)
    ledger = {'schema_version': 1, **git_identity(), 'case_id': case['case_id'], 'scenario': args.scenario,
              'scope': 'real HTTP and durable workers; PostgreSQL read-only observer; real providers; no mock fallback',
              'expected_business_status': case.get('expected_business_status'), 'requested_runs': args.repeat,
              'runs': [], 'test_status': 'not_run', 'semantic_review': 'not_run', 'browser': 'not_run'}
    code = 2
    engine = None
    try:
        if case.get('requires_driver'):
            raise ValueError('SCENARIO_DRIVER_PENDING:' + case['requires_driver'])
        if ledger['dirty']:
            raise ValueError('COMMITTED_VALIDATION_TREE_REQUIRED')
        import dotenv
        settings = {k: v for k, v in dotenv.dotenv_values(args.env_file).items() if v is not None}
        dotenv.load_dotenv = lambda *a, **kw: False
        url = os.environ.get(args.database_url_env) or settings.get(args.database_url_env, '')
        identity = database_identity(url)
        credentials_path = settings.get('PREPARATION_TEST_CREDENTIALS_FILE', '')
        credentials = json.loads(Path(credentials_path).read_text())
        if not credentials['username'].startswith('prep-test-'):
            raise ValueError('SYNTHETIC_TEST_IDENTITY_REQUIRED')
        from sqlalchemy import create_engine, text
        engine = create_engine(url)
        with engine.connect() as connection:
            assert connection.scalar(text('select current_database()')) == identity['database']
        import httpx
        with httpx.Client(base_url=local_http(args.base_url), timeout=60, trust_env=False, follow_redirects=False) as client:
            login = get_json(client, 'POST', '/api/auth/login', json={k: credentials[k] for k in ('username', 'password')})
            client.headers['Authorization'] = 'Bearer ' + login['token']
            attestation = get_json(client, 'GET', '/api/preparation-validation/identity')
            for key in ('database', 'endpoint_digest'):
                assert attestation.get(key) == identity[key], 'SERVER_DATABASE_MISMATCH'
            assert attestation.get('code_sha') == ledger['code_sha'] and not attestation.get('dirty'), 'SERVER_CODE_MISMATCH'
            assert attestation.get('worker_started') and attestation.get('preparation_enabled'), 'SERVER_WORKERS_NOT_STARTED'
            assert attestation.get('test_identity') == credentials['username'], 'SERVER_IDENTITY_MISMATCH'
            from sqlalchemy.orm import Session
            from sqlalchemy import select
            from app.database.models import User
            with Session(engine) as session:
                owner = session.scalar(select(User.user_id).where(User.username == credentials['username'], User.is_disabled.is_(False)))
            assert owner, 'TEST_USER_NOT_IN_DATABASE'
            ledger.update(attestation=attestation, test_identity=credentials['username'])
            for index in range(args.repeat):
                try:
                    result = run_case(client, engine, owner, case, output/f'run-{index+1:02}', args.timeout_seconds)
                except Exception as exc:
                    result = {'test_status': 'failed', 'business_status': 'unknown', 'error': {'type': type(exc).__name__, 'code': 'HTTP_OR_FIXTURE_SETUP_FAILED'}}
                ledger['runs'].append(result)
                write_json(output/'ledger.json', ledger)
            successes = sum(r['test_status'] == 'passed' for r in ledger['runs'])
            ledger.update(passed=successes, failed=len(ledger['runs'])-successes, denominator=len(ledger['runs']),
                          repetition_requirement_met=args.repeat >= case.get('repeats_required', 1))
            code = 0 if successes == args.repeat and ledger['repetition_requirement_met'] else 1
            ledger['test_status'] = 'passed' if code == 0 else 'failed'
    except Exception as exc:
        ledger['preflight_error'] = {'type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, (ValueError, AssertionError)) else 'PREFLIGHT_UNAVAILABLE_CHECK_PRIVATE_CONFIGURATION'}
    finally:
        if engine is not None:
            engine.dispose()
        write_json(output/'ledger.json', ledger)
    print(json.dumps({'case_id': case['case_id'], 'test_status': ledger['test_status'], 'ledger': str(output/'ledger.json')}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
