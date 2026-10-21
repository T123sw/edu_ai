"""Only brief handoff and durable native-artifact import belong to the host."""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import shutil

from .contracts import safe_path
from .projects import ProjectStore
from .runtime import RUNTIME
from .workflow_agent import NativeWorkflowAgent
from .workflow_audio import audio_provider
from .workflow_import import import_project
from .build_info import runtime_info


def legacy_creation_brief(payload):
    request = payload.model_dump(mode='json') if hasattr(payload,'model_dump') else vars(payload)
    teaching = request.get('teaching_context') or {}
    if hasattr(teaching,'model_dump'): teaching=teaching.model_dump(mode='json')
    brief = {'title':request.get('title'), 'request':teaching.get('request_goal') or request.get('focus') or request.get('subject'),
        'audience':request.get('audience'), 'language':teaching.get('language'),
        'requested_video_minutes':teaching.get('resource_target_minutes') or request.get('duration_minutes'),
        'requirements':deepcopy(teaching.get('requirements',[])), 'exclusions':deepcopy(teaching.get('exclusions',[])),
        'sources':request.get('research_context',''), 'uploaded_text':request.get('pdf_content'),
        'requested_changes':teaching.get('requested_changes') or request.get('revision_feedback'),
        'original_content':request.get('original_content')}
    media_options = request.get('classroom_options') or {}
    if hasattr(media_options, 'model_dump'): media_options = media_options.model_dump(exclude_none=True)
    media_options = {k:v for k,v in media_options.items() if v is not None}
    if media_options: brief['media_requirements'] = deepcopy(media_options)
    for key in ('prior_knowledge', 'desired_outcomes', 'source_policy', 'depth', 'requirement_ids'):
        if teaching.get(key): brief[key] = deepcopy(teaching[key])
    objectives = teaching.get('objectives') or request.get('objectives')
    if objectives: brief['topic_objectives'] = deepcopy(objectives)
    return brief


def creation_brief(payload):
    brief = legacy_creation_brief(payload)
    request = payload.model_dump(mode='json') if hasattr(payload, 'model_dump') else vars(payload)
    teaching = request.get('teaching_context') or {}
    if hasattr(teaching, 'model_dump'): teaching = teaching.model_dump(mode='json')
    brief['teaching_context'] = deepcopy(teaching)
    brief['course_visual_contract'] = {'version':'teaching-readable-v1',
        'font_family':'Noto Sans SC', 'canvas':[1920,1080],
        'body_min_px':32, 'diagram_label_min_px':28, 'title_min_px':48,
        'background':'#0f172a', 'foreground':'#f8fafc', 'accent':'#38bdf8',
        'instruction':'Use these defaults consistently across this course; explicit user style and existing revision design take precedence. Split dense diagrams into steps instead of shrinking labels.'}
    for key in ('node_id', 'learning_activities', 'self_check', 'node_budget_minutes', 'prerequisites',
                'effective_preferences', 'assumptions', 'limitations'):
        if key in teaching: brief[key] = deepcopy(teaching[key])
    preferences = request.get('video_preferences') or teaching.get('video_preferences')
    if hasattr(preferences, 'model_dump'): preferences = preferences.model_dump(exclude_none=True)
    if preferences: brief['video_preferences'] = deepcopy(preferences)
    for key in ('scene_count', 'teaching_style'):
        if request.get(key) is not None:
            brief.setdefault('media_requirements', {})[key] = request[key]
    brief['language'] = teaching.get('language') or request.get('language')
    original_brief = (request.get('original_files') or {}).get('BRIEF.md')
    if original_brief: brief['original_native_brief'] = original_brief
    return brief


def generate_native(payload, *, gateway, artifact, context=None, checkpoint=None, store=None,
                    runtime=None, narrate=None, media_files=None, runner_factory=NativeWorkflowAgent):
    store = store or ProjectStore()
    brief = creation_brief(payload)
    media_files = dict(media_files or {})
    brief['assets'] = list(media_files)
    original_files = dict(getattr(payload, 'original_files', {}) or {})
    if original_files:
        brief['original_project_files'] = {k:hashlib.sha256(v.encode()).hexdigest() for k,v in original_files.items()}
    def identify(value, version):
        return hashlib.sha256(json.dumps({'brief': value, 'spec': artifact.get('spec_digest'), 'resource_id': artifact['resource_id'],
            'media': {k: hashlib.sha256(v).hexdigest() for k,v in media_files.items()}, 'pipeline': version},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    saved = checkpoint.load_generation_state() if checkpoint else None
    legacy = legacy_creation_brief(payload)
    legacy['assets'] = list(media_files)
    if original_files: legacy['original_project_files'] = brief['original_project_files']
    old_identity = identify(legacy, 'upstream-workflow-v1')
    old_workspace = store.root.parent/'workflows'/old_identity
    resume_legacy = bool(saved and saved.get('request_digest') == old_identity) or bool(list(old_workspace.glob('videos/*/BRIEF.md')))
    previous_brief = deepcopy(brief)
    previous_brief.pop('course_visual_contract', None)
    previous_identity = identify(previous_brief, 'teaching-brief-v2')
    resume_previous = (bool(saved and saved.get('request_digest') == previous_identity) or
                       bool(list((store.root.parent/'workflows'/previous_identity).glob('videos/*/BRIEF.md'))))
    identity = old_identity if resume_legacy else (previous_identity if resume_previous else identify(brief, 'teaching-brief-v2'))
    if resume_legacy: brief = legacy
    workspace = store.root.parent/'workflows'/identity
    workspace.mkdir(parents=True,exist_ok=True,mode=0o700)
    (workspace/'.host/bin').mkdir(parents=True,exist_ok=True)
    (workspace/'.host/home').mkdir(exist_ok=True)
    def guard():
        if context and context.is_cancel_requested(): raise RuntimeError('HYPERFRAMES_CANCELED')
        if callable(getattr(gateway,'guard',None)): gateway.guard()
    guard()
    lock = (workspace/'.host/worker.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        local_state = workspace/'.host/generation-state.json'
        if saved is None and local_state.exists(): saved = json.loads(local_state.read_text())
        state = deepcopy(saved['state']) if saved and saved.get('request_digest')==identity else {}
        if state.get('published'):
            for name in store.manifest(state['published']['project']): store.file(state['published']['project'],name)
            return state['published']
        def save():
            guard()
            if checkpoint: checkpoint.save_generation_state({'request_digest':identity,'state':state})
            temporary = local_state.with_suffix('.tmp')
            temporary.write_text(json.dumps({'request_digest':identity,'state':state}, ensure_ascii=False))
            temporary.replace(local_state)
        previous_runtime = state.get('runtime')
        current_runtime = runtime_info()
        history = list(state.get('runtime_history', []))
        if not history and previous_runtime:
            history.append(previous_runtime)
        if not history and (resume_legacy or resume_previous):
            history.append({'build_id':'unrecorded', 'resumed_existing':True})
        if not history or history[-1] != current_runtime:
            history.append(current_runtime)
        state['runtime_history'] = history
        state['runtime'] = {**current_runtime, 'history':history}
        (workspace/'.host/runtime.json').write_text(json.dumps(state['runtime'], indent=2))
        state['workspace_key']=identity
        save()
        (workspace/'REQUEST.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2))
        if not resume_legacy and not state.get('receipt'):
            if not state.get('teaching_brief'):
                from .teaching_brief import generate_teaching_brief
                if callable(getattr(context, 'progress', None)): context.progress(7, 'video_brief', '正在将教学安排转换为视频制作需求')
                state['teaching_brief'] = generate_teaching_brief(brief, gateway, guard=guard)
                save()
            handoff = state['teaching_brief']
            (workspace/'.host/BRIEF.md').write_text(handoff['brief_markdown'])
            (workspace/'.host/teaching-brief.json').write_text(json.dumps(handoff, ensure_ascii=False, indent=2))
        for name,body in media_files.items():
            safe_path(name)
            target=workspace/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
        for name,body in original_files.items():
            safe_path(name)
            target=workspace/'original'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
        # Pin command resolution without modifying or abbreviating upstream sources.
        cli = RUNTIME/'node_modules/hyperframes/dist/cli.js'
        gate = '/usr/bin/python3 ' + shlex.quote(str(Path(__file__).parent/'render_gate.py'))
        node = shutil.which('node')
        for name,script in {
            'hyperframes':f'#!/bin/sh\nexec {gate} {shlex.quote(node)} {shlex.quote(str(cli))} "$@"\n',
            'npx':f'#!/bin/sh\nif [ "$1" = hyperframes ]; then shift; exec {gate} {shlex.quote(node)} {shlex.quote(str(cli))} "$@"; fi\nexec {shlex.quote(shutil.which("npx"))} "$@"\n',
        }.items():
            file=workspace/'.host/bin'/name;file.write_text(script);file.chmod(0o755)
        if callable(getattr(context,'progress',None)): context.progress(10,'native_workflow','HyperFrames 正在根据需求制作视频')
        if not state.get('receipt'):
            from .teaching_brief import effective_preferences
            options=dict(getattr(payload,'classroom_options',{}) or {})
            choices = effective_preferences(brief)['explicit']
            if 'voice' in choices: options['voice'] = choices['voice']
            if state.get('teaching_brief'):
                options['enable_tts'] = state['teaching_brief']['decisions']['narration']
                options['voice_explicit'] = bool(choices.get('voice'))
            with audio_provider(workspace,guard=guard,options=options,narrate=narrate):
                runner=runner_factory(gateway,workspace,guard)
                handoff_instruction = (f'The teaching-to-video conversion is already complete: read {workspace}/.host/BRIEF.md and .host/teaching-brief.json. Adopt its native workflow and intent without a new interview or rewriting the scope. Initialize the native project first, then call prepare_project, which installs this exact BRIEF.md when absent. Do not call the faceless prepare_scene_assets pipeline for general-video. ' if state.get('teaching_brief') else '')
                receipt=runner.run(handoff_instruction+f'Read {workspace}/REQUEST.json for the complete user brief and source evidence. Execute the full installed HyperFrames native workflow. Create the project beneath {workspace}/videos/. If a previous attempt already created native files, resume those files instead of regenerating completed work. For revisions, the complete prior text project is staged under original/ and its binary assets are staged at their original relative paths; preserve unaffected native files. Preserve source text, user duration and deliverable scope. When topic_objectives are supplied, this video covers that topic within the original overall request; do not repeat the entire course. Finish the actual rendered video and return its native project directory and video path.')
            state['receipt']=receipt;save()
        receipt=state['receipt']
        project=Path(receipt['project_directory']).resolve();project.relative_to(workspace.resolve())
        video=Path(receipt['video_path']).resolve();video.relative_to(project)
        if callable(getattr(context,'progress',None)): context.progress(95,'importing','正在保存 HyperFrames 原生工程与播放时间轴')
        guard()
        events = workspace/'.host/events.jsonl'
        if events.exists():
            (project/'exports').mkdir(exist_ok=True)
            shutil.copyfile(events, project/'exports/workflow-events.jsonl')
            shutil.copyfile(workspace/'.host/runtime.json', project/'exports/runtime.json')
        if state.get('teaching_brief'):
            (project/'exports').mkdir(exist_ok=True)
            (project/'exports/teaching-brief.json').write_text(json.dumps(state['teaching_brief'], ensure_ascii=False, indent=2))
        content=import_project(project,video,title=payload.title,project_id='hf_'+artifact['resource_id'],store=store,runtime=runtime)
        state['published']=content;save()
        return content
    finally:
        lock.close()
