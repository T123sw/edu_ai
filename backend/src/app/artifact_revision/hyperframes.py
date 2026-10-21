"""Regenerate synchronized native files/audio when a teaching draft is edited."""
from types import SimpleNamespace
from uuid import uuid4


def regenerate(service, original, edited, instruction):
    if original.get('format') != 'hyperframes/v1':
        return edited
    # A text editing model cannot choose arbitrary stored executable projects.
    if edited.get('project') != original['project'] or edited.get('exports') != original.get('exports'):
        raise ValueError('工程地址不能作为文本修改；请修改讲稿或画面说明')
    from app.integrations.hyperframes.generation import generate_classroom
    from app.course_preparation.tool_registry import digest
    from app.chat.harness.content_gateway import build_content_gateway
    gateway = build_content_gateway()
    from app.integrations.hyperframes.projects import ProjectStore
    store = ProjectStore()
    files = store.manifest(original['project'])
    text_suffixes = ('.html','.css','.svg','.js','.mjs','.cjs','.ts','.tsx','.jsx','.json','.md','.yaml','.yml','.txt','.toml','.csv','.lock')
    media_files = {name: store.file(original['project'],name).read_bytes()
        for name in files if not name.startswith('exports/')
        and (name.startswith('assets/') or not name.endswith(text_suffixes))}
    original_files = {name: store.file(original['project'],name).read_text()
        for name in files if name.endswith(text_suffixes)
        and not name.startswith(('assets/media/', 'exports/'))
        and name not in {'assets/gsap.min.js','assets/hyperframe.runtime.iife.js'}}
    payload=SimpleNamespace(title=edited['title'],original_content=edited,original_files=original_files,
        focus='按用户要求修订原课堂，保留正确内容。修改要求：'+instruction,
        research_context='',classroom_options={})
    return generate_classroom(payload,gateway=gateway,context=service,
        artifact={'resource_id':'revision_'+uuid4().hex,'spec_digest':digest(edited)},media_files=media_files)['content']
