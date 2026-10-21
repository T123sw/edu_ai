"""Requirements handoff to upstream HyperFrames; stable classroom envelope."""
import asyncio


def _narrate(text, directory, options):
    from app.services.classroom_narration import narration_audio
    from app.services.tts_service import SpeechService
    from app.services.runtime_config_resolver import runtime_config_resolver
    class VoiceResolver:
        def resolve(self, provider):
            profile = dict(runtime_config_resolver.resolve(provider) or {})
            if provider == 'tts' and options.get('voice_explicit') and options.get('voice'):
                profile['voice'] = options['voice']
            return profile
    return asyncio.run(narration_audio(action={'text': text, 'speed': options.get('speed')}, audio_dir=directory,
        tts=SpeechService(voice=options.get('voice'), speed=options.get('speed'), response_format='mp3', long_form=True,
                         config_resolver=VoiceResolver())))



def generate_content(payload, *, gateway, context=None, artifact, checkpoint=None, runtime=None, store=None, narrate=None, media_files=None, runner_factory=None):
    """The host hands off requirements; upstream skills own the full creation loop."""
    from .workflow import generate_native
    options = {'runner_factory':runner_factory} if runner_factory is not None else {}
    return generate_native(payload, gateway=gateway, context=context, artifact=artifact,
        checkpoint=checkpoint, runtime=runtime, store=store, narrate=narrate,
        media_files=media_files, **options)


def generate_classroom(payload, *, gateway, context, artifact, checkpoint=None, media_files=None):
    from app.course_preparation.tool_registry import digest
    from app.chat.harness.reviewed_resource import review_classroom
    content = generate_content(payload, gateway=gateway, context=context, artifact=artifact, checkpoint=checkpoint, media_files=media_files)
    teaching = getattr(payload, 'teaching_context', None)
    if hasattr(teaching, 'model_dump'): teaching = teaching.model_dump(mode='json')
    content, audit = review_classroom(content, {'spec_digest': artifact.get('spec_digest')})
    duration = {'value_minutes': content['timeline']['duration'] / 60, 'basis': 'measured', 'method': 'ffprobe native rendered video'}
    metadata = {'schema_version': 1, 'spec_digest': artifact.get('spec_digest'), 'teaching_context_digest': digest(teaching),
        'objective_bindings': [], 'applied_requirements': [], 'alignment_status': 'not_generated',
        'alignment_policy': 'optional_native_classroom_v1', 'duration': duration, 'media_duration': duration,
        'content_digest': digest(content), 'generator': 'hyperframes-native-workflow', 'render_checks': {**content['verification'], 'native': True, 'issues': []},
        'capabilities': {'narration': any(s.get('audio_path') for s in content['timeline']['segments']), 'animation': True, 'video_export': True, 'project_export': True}}
    audit.update(preparation_sha256=digest(metadata))
    return {'artifact_type': 'classroom', 'title': payload.title, 'content': content,
        'generation_state': {'resource_review': audit, 'preparation': metadata}, 'limitations': []}
