"""Live HTTP -> Harness/model -> durable worker -> native resource -> readback acceptance.
Runs an isolated application and synthetic teacher/course; no production records are changed.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'backend/src'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-material', type=Path, help='Seed an isolated source document and reference it on the first turn')
    parser.add_argument('--seed-stale-draft', action='store_true', help='Seed an old report draft and send its stale reference when confirming a new plan')
    parser.add_argument('--plan-only', action='store_true', help='Verify the saved plan handoff without confirming or submitting generation')
    parser.add_argument('--retry-failed', action='store_true', help='Use the real public retry API for failed jobs')
    parser.add_argument('--resume', action='store_true', help='Reuse a failed conversation and its saved planning state')
    parser.add_argument('--recheck', action='store_true', help='Recheck previously generated artifacts without generating again')
    parser.add_argument('--wait-existing', action='store_true', help='Wait for the saved job before rechecking; never resubmit generation')
    parser.add_argument('--revision-check', action='store_true')
    parser.add_argument('--refinalize-classroom', action='store_true')
    parser.add_argument('--preview-only', action='store_true')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--direct-deepseek', action='store_true', help='Bypass shell proxies only for the configured DeepSeek endpoint during isolated acceptance')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--port', type=int, default=8012)
    parser.add_argument('--kinds', nargs='+', default=['lesson_plan', 'blog', 'quiz', 'flashcard', 'graph', 'game', 'classroom'])
    args = parser.parse_args()
    if 'report' in args.kinds and not args.plan_only:
        parser.error('Report support in this runner is limited to --plan-only; full reports use the report acceptance runner')
    if args.seed_stale_draft and not args.reference_material:
        parser.error('--seed-stale-draft requires --reference-material')
    if args.reference_material:
        args.reference_material = args.reference_material.resolve()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    from core.config import Config
    if args.direct_deepseek:
        from urllib.parse import urlsplit
        host = urlsplit(Config.DEEPSEEK_BASE_URL).hostname
        for key in ('NO_PROXY', 'no_proxy'):
            os.environ[key] = ','.join(filter(None, [os.environ.get(key), '127.0.0.1', 'localhost', host]))
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False
    for key in ('USER', 'COURSE', 'COURSE_MEMBERSHIP', 'CONVERSATION', 'JOB', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'LEARNING', 'TASK'):
        os.environ[key + '_PERSISTENCE_MODE'] = 'json'
    os.environ['PERSISTENCE_PROFILE'] = 'compatibility'
    os.environ['DATABASE_URL'] = ''
    for attr in ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'CONVERSATIONS_FILE', 'COURSE_MEMBERSHIPS_FILE', 'USER_PROFILES_FILE', 'LESSON_PLANS_FILE', 'LEARNING_DB_PATH', 'RUNTIME_CONFIG_ROOT'):
        old = getattr(Config, attr)
        value = root / attr.lower() if attr.endswith('ROOT') else root / Path(old).name
        setattr(Config, attr, value)
        os.environ[attr] = str(value)
    for key in ('TASKS_DB_PATH', 'AGENT_RUNS_DB_PATH', 'AGENT_MEMORY_DB_PATH'):
        os.environ[key] = str(root / (key.lower() + '.db'))
    (root / "storage").mkdir(exist_ok=True)
    os.chdir(root)
    from core.course_storage import storage_manager
    from core.user_storage import user_storage
    from core.auth import auth_manager
    owner, course = 'resource-e2e-admin', 'resource-e2e-course'
    if not user_storage.get_user(owner):
        user_storage.create_user(owner, uuid4().hex, role='teacher')
    user_storage.update_user(owner, role='teacher')
    storage_manager.create_course_structure(course)
    storage_manager.save_course_info(course, {'id': course, 'title': '数据结构验收课程', 'name': '数据结构验收课程', 'description': '合成测试课程', 'icon': 'school', 'color': '#2563eb', 'created_by': owner, 'owner': owner})
    from app.api.course_dependencies import get_course_membership_store
    get_course_membership_store().upsert(course, owner, 'owner', added_by=owner)
    source_material = None
    source_reference = None
    if args.reference_material:
        source_material = json.loads(args.reference_material.resolve().read_text())
        source_kind = source_material.get('material_type', 'report')
        storage_manager.save_generated_material(course, source_kind, 'source-reference',
            {'title': source_material['title'], 'content': source_material['content']},
            owner_user_id=owner, visibility='private', scope_type='course')
        source_reference = {'artifact_id': 'source-reference', 'artifact_type': source_kind,
            'source_course_id': course, 'version_id': 'v1', 'title': source_material['title']}
    if args.refinalize_classroom:
        import asyncio
        from app.services.job_store import get_job
        from app.services.classroom_service import _make_on_sidecar_succeeded
        from app.integrations.openmaic import get_openmaic_client
        item = json.loads((root / 'classroom.json').read_text())
        job = get_job(item['job']['edu_job_id'])
        metadata = (job.input_summary or {})['material_metadata']
        async def finalize():
            client = get_openmaic_client(owner_user_id=owner, use_cache=False)
            try:
                envelope = await client.poll_job(client.config.base_url.rstrip('/') + '/api/generate-classroom/' + job.sidecar_job_id)
                assert envelope['status'] == 'succeeded'
                callback = _make_on_sidecar_succeeded(active_client=client, course_storage_manager=storage_manager,
                    course_id=course, owner=owner, scope_type=job.scope_type, scope_id=job.scope_id,
                    source_job_id=job.edu_job_id, material_id=item['job']['result_ref']['material_id'], material_metadata=metadata)
                return await callback(envelope['result'])
            finally:
                await client.aclose()
        reference = asyncio.run(finalize())
        material = storage_manager.get_generated_material(course, 'classroom', reference['material_id'], owner_user_id=owner)
        from app.chat.harness.reviewed_resource import verified_resource
        assert verified_resource(material, 'classroom')
        assert not any(a.get('audioUrl') for scene in material['scenes'] for a in scene.get('actions', []))
        item.update(material=material, finalization_verified=True, no_tts_verified=True)
        (root / 'classroom.json').write_text(json.dumps(item, ensure_ascii=False, indent=2))
    import uvicorn
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    import requests
    base = f'http://127.0.0.1:{args.port}'
    headers = {'Authorization': 'Bearer ' + auth_manager.create_token(owner, 'teacher')}
    for _ in range(180):
        if server.started: break
        if not thread.is_alive(): raise RuntimeError('isolated_server_failed')
        time.sleep(1)
    assert server.started
    prompts = {
        'report': '请生成一份面向大学初学者的“数组的实现”报告，介绍连续存储、地址计算与插入删除，先给报告大纲。',
        'lesson_plan': '请生成一份面向大学初学者、15分钟的“数组随机访问”教案，包含具体课堂活动和评价。',
        'blog': '请生成一篇面向大学初学者的“数组随机访问”教学博客，约600字，包含具体地址计算实例。先给文章大纲，确认后写正文。',
        'quiz': '请生成3道面向大学初学者的“数组随机访问”单选题，每题4个选项，附正确答案与解析。',
        'flashcard': '请生成4张面向大学初学者的“数组随机访问”问答闪卡，每张正面一个问题，背面答案与解释。',
        'graph': '请生成一份面向大学初学者的“数组随机访问”思维导图，包含内存布局、地址计算和适用条件三个分支。',
        'game': '请生成面向大学初学者的“数组随机访问”拖拽配对互动游戏，包含4对概念与解释。',
        'classroom': '请生成面向大学初学者的“数组随机访问”AI课堂，3个场景，5分钟，使用文字、公式和图形讲解，无需语音或外部配图。',
    }
    results = {}
    def run(kind):
        conversation = 'resource-e2e-' + kind + '-' + uuid4().hex[:8]
        evidence = {'kind': kind, 'conversation_id': conversation, 'turns': []}
        dest = root / (kind + '.json')
        if args.resume and dest.exists():
            evidence = json.loads(dest.read_text())
            conversation = evidence['conversation_id']
            evidence['prior_error'] = evidence.pop('error', None)
            evidence.pop('passed', None)
        if args.seed_stale_draft and not args.resume:
            from types import SimpleNamespace
            from core.conversation_storage import conversation_storage
            from app.artifact_revision.service import ArtifactRevisionService
            class SeedDraftModel:
                def invoke(self, messages):
                    return SimpleNamespace(content=json.dumps({'focus': '案例', 'reason': '补充例子', 'benefit': '便于讲解',
                        'edits': [{'path': [], 'before': '原始案例', 'after': '旧稿案例'}]}, ensure_ascii=False))
            seeded = ArtifactRevisionService(storage_manager, SeedDraftModel()).run(owner_user_id=owner,
                conversation_id=conversation, course_id=course, question='修改旧报告的案例',
                operation_id='old-draft', artifact_reference=source_reference)
            assert seeded['status'] == 'preview', seeded
            conversation_storage.ensure_conversation(conversation, '旧报告修改', owner=owner)
            conversation_storage.update_state(conversation, {'pending_operation': {'id': 'old-draft',
                'kind': 'artifact_revision', 'owner': owner, 'course_id': course, 'scope_id': None, 'revision_pending': seeded['pending']}, 'latest_revision_outcome': seeded,
                'course_id': course, 'scope_type': 'course', 'scope_id': None})
        def save(): dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        def chat(question, reference=None):
            started = time.monotonic()
            submitted_at = None
            response = requests.post(base + '/api/chat/v2/stream', headers=headers,
                json={'course_id': course, 'scope_type': 'course', 'question': question,
                      'artifact_reference': reference or (source_reference if not evidence['turns'] else None),
                      'conversation_id': conversation, 'request_id': uuid4().hex, 'allow_rag': False, 'allow_web': False},
                stream=True, timeout=(15, 600))
            if response.status_code != 200:
                raise RuntimeError(f"chat_http_{response.status_code}: {response.text[:800]}")
            events, result = [], None
            for line in response.iter_lines(decode_unicode=True):
                if not line.startswith('data:'): continue
                try: event = json.loads(line[5:])
                except ValueError: continue
                events.append(event)
                if event.get('type') == 'task_submitted':
                    submitted_at = round(time.monotonic() - started, 3)
                payload = event.get('payload', event)
                if 'trace' in payload and 'message' in payload: result = payload
            response.close()
            evidence['turns'].append({'question': question, 'events': events, 'result': result,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'task_submitted_seconds': submitted_at})
            save()
            assert result and result.get('action', {}).get('name') != 'agent.failed', (kind, result)
            print(json.dumps({'kind': kind, 'stage': 'turn', 'action': result.get('action'), 'workflow': result.get('workflow')}, ensure_ascii=False), flush=True)
            return result
        try:
            first = chat(prompts[kind] + '资料使用通用知识即可，无需检索。')
            if source_reference:
                assert first.get('resource_creation_handoff') and not first.get('artifact_revision'), first
                evidence['reference_handoff_verified'] = True
            if args.plan_only:
                assert first.get('harness_outline') and not first.get('task_id'), first
                assert first['workflow']['type'] == kind and first['workflow']['status'] == 'awaiting_confirm', first
                if source_material:
                    original = storage_manager.get_generated_material(course, source_reference['artifact_type'], 'source-reference', owner_user_id=owner)
                    assert original['content'] == source_material['content']
                    evidence['source_unchanged_verified'] = True
                evidence.update(passed=True, plan_only_verified=True)
                save()
                return evidence
            if kind in {'quiz', 'flashcard', 'graph', 'game'}:
                assert first.get('task_id') and not first.get('harness_outline'), first
                assert not any(t['tool'] == 'draft_resource_outline' for t in first['trace']['tool_events'])
                submitted = first
                evidence['direct_generation_verified'] = True
            else:
                assert first.get('harness_outline') and not first.get('task_id'), first
                assert first['workflow']['type'] == kind, first['workflow']
                if kind == 'classroom':
                    outline = next(t['data'] for t in first['trace']['tool_events'] if t['tool'] == 'draft_resource_outline' and t['ok'])
                    assert outline['classroom_options'] == {'enable_tts': False, 'include_visuals': False, 'duration_minutes': 5}, outline['classroom_options']
                    assert len(outline['chapters']) == 3
                if kind == 'lesson_plan':
                    paused = chat('先不要生成，解释一下你如何检查学生学会了。')
                    assert not paused.get('task_id'), paused
                    revised = chat('请把教案课时改成12分钟，先给我修改后的教学方案。')
                    assert revised.get('harness_outline') and not revised.get('task_id'), revised
                    assert revised['harness_outline']['revision'] > first['harness_outline']['revision']
                    evidence['pause_and_revision_verified'] = True
                submitted = chat('可以' if args.seed_stale_draft else 'Go ahead with this plan.', reference=source_reference if args.seed_stale_draft else None)
                if args.seed_stale_draft:
                    assert submitted.get('resource_creation_handoff') and not submitted.get('artifact_revision'), submitted
                    evidence['stale_reference_confirmation_verified'] = True
            task = submitted.get('task_id')
            assert task, submitted
            deadline = time.monotonic() + (2100 if kind == 'classroom' else 1200)
            while time.monotonic() < deadline:
                response = requests.get(base + '/api/jobs/' + task, headers=headers, timeout=30)
                response.raise_for_status()
                job = response.json()
                if job.get('status') in {'succeeded', 'failed', 'canceled', 'partially_succeeded'}: break
                time.sleep(3)
            evidence['job'] = job
            save()
            assert job['status'] == 'succeeded', job
            reference = job['result_ref']
            mid = reference.get('material_id') or reference.get('classroom_id')
            response = requests.get(base + f'/api/courses/{course}/materials/{kind}/{mid}', headers=headers, timeout=30)
            response.raise_for_status()
            material = response.json()
            evidence['material'] = material
            from app.chat.harness.reviewed_resource import verified_resource
            assert verified_resource(material, kind), 'review_readback_failed'
            content = material.get('content') or {}
            if kind == 'quiz': assert len(content['questions']) == 3
            if kind == 'flashcard': assert len(content['cards']) == 4
            queried = chat('刚才生成的资源完成了吗？请读取它并概括内容。')
            assert not queried.get('task_id') and queried.get('verification', {}).get('decision') == 'pass', queried
            evidence['passed'] = True
            if source_material:
                original = storage_manager.get_generated_material(course, source_reference['artifact_type'], 'source-reference', owner_user_id=owner)
                assert original['content'] == source_material['content']
                evidence['source_unchanged_verified'] = True
            save()
            print(json.dumps({'kind': kind, 'passed': True, 'material_id': mid}, ensure_ascii=False), flush=True)
            return evidence
        except Exception as exc:
            evidence['passed'] = False
            evidence['error'] = str(exc)[:3000]
            save()
            print(json.dumps({'kind': kind, 'passed': False, 'error': str(exc)[:250]}, ensure_ascii=False), flush=True)
            return evidence
    # Independent conversations share the real application worker and HTTP boundary.
    if args.preview_only:
        results = {kind: json.loads((root / (kind + '.json')).read_text()).get('passed', False) for kind in args.kinds}
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, kind): kind for kind in args.kinds}
            for future in as_completed(futures):
                results[futures[future]] = future.result()['passed']
                (root / 'summary.json').write_text(json.dumps(results, indent=2))
    if args.retry_failed:
        from app.chat.harness.reviewed_resource import verified_resource
        for kind in args.kinds:
            dest = root / (kind + '.json')
            item = json.loads(dest.read_text())
            original = item['job']
            response = requests.post(base + '/api/jobs/' + original['edu_job_id'] + '/retry', headers=headers, timeout=30)
            response.raise_for_status()
            retried_id = response.json()['edu_job_id']
            deadline = time.monotonic() + (2100 if kind == 'classroom' else 1200)
            while time.monotonic() < deadline:
                response = requests.get(base + '/api/jobs/' + retried_id, headers=headers, timeout=30)
                response.raise_for_status()
                retried = response.json()
                if retried['status'] in {'succeeded', 'failed', 'canceled'}: break
                time.sleep(3)
            item.update(retry_original_job=original, job=retried)
            dest.write_text(json.dumps(item, ensure_ascii=False, indent=2))
            assert retried['status'] == 'succeeded', retried
            if kind == 'classroom':
                from app.services.job_store import get_job
                assert get_job(retried_id).sidecar_job_id == get_job(original['edu_job_id']).sidecar_job_id
            ref = retried['result_ref']
            mid = ref.get('material_id') or ref.get('classroom_id')
            response = requests.get(base + f'/api/courses/{course}/materials/{kind}/{mid}', headers=headers, timeout=30)
            response.raise_for_status()
            material = response.json()
            assert verified_resource(material, kind)
            item.update(material=material, passed=True, public_retry_verified=True)
            dest.write_text(json.dumps(item, ensure_ascii=False, indent=2))
            results[kind] = True
            print(json.dumps({'kind': kind, 'public_retry_passed': True}), flush=True)
    if args.recheck:
        from app.chat.harness.reviewed_resource import verified_resource
        for kind in args.kinds:
            dest = root / (kind + '.json')
            item = json.loads(dest.read_text())
            task = item['job']['edu_job_id']
            if args.wait_existing:
                deadline = time.monotonic() + (2100 if kind == 'classroom' else 1200)
                while time.monotonic() < deadline:
                    current = requests.get(base + '/api/jobs/' + task, headers=headers, timeout=30)
                    current.raise_for_status()
                    if current.json()['status'] not in {'queued', 'running'}: break
                    time.sleep(3)
            job_response = requests.get(base + '/api/jobs/' + task, headers=headers, timeout=30)
            job_response.raise_for_status()
            item['job'] = job_response.json()
            dest.write_text(json.dumps(item, ensure_ascii=False, indent=2))
            assert job_response.json()['status'] == 'succeeded'
            ref = job_response.json()['result_ref']
            mid = ref.get('material_id') or ref.get('classroom_id')
            material_response = requests.get(base + f'/api/courses/{course}/materials/{kind}/{mid}', headers=headers, timeout=30)
            material_response.raise_for_status()
            material = material_response.json()
            assert verified_resource(material, kind)
            response = requests.post(base + '/api/chat/v2/stream', headers=headers,
                json={'course_id': course, 'scope_type': 'course', 'conversation_id': item['conversation_id'],
                    'request_id': uuid4().hex, 'question': ('我刚才在任务列表重试了这份资源。请查询对应重试任务的真实状态并读取内容；不要重新生成。' if args.retry_failed or item.get('retry_original_job') else '请重新查询刚才这份已生成资源的真实状态，并读取实际内容后概括；不要重新生成。'),
                    'allow_rag': False, 'allow_web': False}, stream=True, timeout=(15, 600))
            response.raise_for_status()
            result = None
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data:'):
                    event = json.loads(line[5:])
                    if event.get('type') == 'result': result = event['payload']
            item['recheck_result'] = result
            dest.write_text(json.dumps(item, ensure_ascii=False, indent=2))
            assert result and not result.get('task_id') and (result.get('verification') or {}).get('decision') == 'pass', result
            item.update(passed=True, material=material, readback_recheck_verified=True)
            if kind == 'classroom' and item.get('retry_original_job'):
                from app.services.job_store import get_job
                assert get_job(task).sidecar_job_id == get_job(item['retry_original_job']['edu_job_id']).sidecar_job_id
                item['public_retry_verified'] = True
                item['reused_sidecar_verified'] = True
            dest.write_text(json.dumps(item, ensure_ascii=False, indent=2))
            results[kind] = True
            print(json.dumps({'kind': kind, 'recheck_passed': True}), flush=True)
    if args.preview or args.preview_only:
        from playwright.sync_api import sync_playwright
        from urllib.parse import urlsplit
        with sync_playwright() as browser_api:
            browser = browser_api.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            session = {'token': headers['Authorization'].removeprefix('Bearer '), 'user': {'username': owner, 'role': 'teacher'}}
            page.add_init_script('localStorage.setItem("edu-ai-auth", ' + json.dumps(json.dumps(session)) + ')')
            def forward(route):
                url = urlsplit(route.request.url)
                if url.path.startswith('/api/'):
                    response = route.fetch(url=base + url.path + ('?' + url.query if url.query else ''), timeout=120000)
                    route.fulfill(response=response)
                else:
                    route.continue_()
            page.route('**/api/**', forward)
            for kind, passed in list(results.items()):
                if not passed: continue
                item = json.loads((root / (kind + '.json')).read_text())
                ref = item['job']['result_ref']
                mid = ref.get('material_id') or ref.get('classroom_id')
                page.goto(f'http://127.0.0.1:5173/#resources?course_id={course}&material_type={kind}&material_id={mid}')
                page.wait_for_timeout(2500)
                (root / (kind + '-browser.txt')).write_text(page.locator('body').inner_text())
                page.screenshot(path=str(root / (kind + '-loading.png')), full_page=True)
                if kind == 'quiz':
                    page.locator('.resource-quiz-preview article').first.wait_for()
                    assert page.locator('.resource-quiz-preview article').count() == 3
                    page.get_by_text('查看答案与解析', exact=True).first.click()
                elif kind == 'flashcard':
                    page.locator('.resource-flashcard-grid button').first.wait_for()
                    assert page.locator('.resource-flashcard-grid button').count() == 4
                    page.locator('.resource-flashcard-grid button').first.click()
                elif kind == 'graph':
                    page.locator('.resource-mind-map__tree').wait_for()
                    nodes = page.locator('.resource-mind-map__tree').get_by_role('treeitem')
                    initial_nodes = nodes.count()
                    assert initial_nodes == 1 + len(item['material']['content']['root'].get('children', []))
                    page.locator('.resource-mind-map__toggle[aria-label^="展开"]').first.click()
                    assert nodes.count() > initial_nodes
                    page.get_by_role('button', name='复位', exact=True).click()
                    assert nodes.count() == initial_nodes
                    with page.expect_download() as downloaded:
                        page.get_by_role('button', name='导出导图', exact=True).click()
                    exported = json.loads(Path(downloaded.value.path()).read_text())
                    assert exported['root'] == item['material']['content']['root']
                    item['graph_interaction_verified'] = True
                    item['export_content_verified'] = True
                elif kind == 'game':
                    page.locator('.resource-game-preview iframe').wait_for()
                    with page.expect_popup() as popup:
                        page.get_by_role('link', name='在新窗口打开小游戏').click()
                    frame = popup.value
                    pairs = item['material']['content']['game_data']['pairs']
                    for pair in pairs:
                        card = frame.locator('.card').filter(has_text=pair['left'])
                        slot = frame.locator('.slot').filter(has_text=pair['right'])
                        card.drag_to(slot)
                    frame.get_by_role('button', name='提交校验').click()
                    from playwright.sync_api import expect
                    expect(frame.locator('#status')).to_contain_text('全部匹配正确')
                    frame.screenshot(path=str(root / 'game-interaction.png'), full_page=True)
                    frame.close()
                    item['game_interaction_verified'] = True
                elif kind == 'classroom':
                    page.get_by_role('button', name='打开课堂', exact=True).click()
                    page.get_by_test_id('classroom-core-controls').wait_for()
                    page.get_by_role('region', name='课堂舞台').wait_for()
                    page.get_by_role('button', name='下一页').click()
                    from playwright.sync_api import expect
                    expect(page.locator('.classroom-page-count')).to_have_text('2 / 3')
                    item['classroom_navigation_verified'] = True
                elif kind in {'lesson_plan', 'blog'}: page.locator('.edu-rich-preview').wait_for()
                if kind in {'quiz', 'flashcard'}:
                    with page.expect_download() as downloaded:
                        page.get_by_role('button', name='导出', exact=True).click()
                    exported = json.loads(Path(downloaded.value.path()).read_text())
                    field = 'questions' if kind == 'quiz' else 'cards'
                    assert exported[field] == item['material']['content'][field]
                    item['export_content_verified'] = True
                page.screenshot(path=str(root / (kind + '-preview.png')), full_page=True)
                item['browser_preview'] = True
                (root / (kind + '.json')).write_text(json.dumps(item, ensure_ascii=False, indent=2))
            browser.close()
    if args.revision_check:
        item = json.loads((root / 'quiz.json').read_text())
        response = requests.post(base + '/api/chat/v2/stream', headers=headers,
            json={'course_id': course, 'scope_type': 'course', 'conversation_id': item['conversation_id'],
                'request_id': uuid4().hex, 'question': '请把刚才这份习题第一题的解析改得更简洁，给我修改稿预览，先不要保存原件。',
                'allow_rag': False, 'allow_web': False}, stream=True, timeout=(15, 600))
        response.raise_for_status()
        result = None
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data:'):
                event = json.loads(line[5:])
                if event.get('type') == 'result': result = event['payload']
        (root / 'revision-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        assert result and (result.get('artifact_revision') or {}).get('status') == 'preview', result
        mid = item['job']['result_ref']['material_id']
        response = requests.get(base + f'/api/courses/{course}/materials/quiz/{mid}', headers=headers, timeout=30)
        response.raise_for_status()
        assert response.json()['content'] == item['material']['content']
        print('Model-selected revision preview verified; original content preserved.', flush=True)
    server.should_exit = True
    thread.join(timeout=20)
    summary_path = root / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary.update(results)
    summary_path.write_text(json.dumps(summary, indent=2))
    assert all(results.values()), results


if __name__ == '__main__':
    main()
