"""Legacy chat entry keeps requirements only; native workflow owns video design."""
from uuid import uuid4


def organize(tools, args):
    value = {'organization_id': 'org_' + uuid4().hex, 'resource_type': 'classroom',
        'subject': args.subject, 'audience': args.audience, 'requirements': args.requirements,
        'scope': args.requirements or args.subject, 'objectives': [], 'units': [],
        'evidence_ids': args.evidence_ids, 'source_policy': tools._source_policy(),
        'model_review': {'performed': False, 'reason': 'requirements_handoff'}}
    tools.session.data.setdefault('organizations', {})[value['organization_id']] = value
    tools.session.save()
    return value


def outline(tools, args, prior):
    options = args.classroom_options.model_dump(exclude_none=True)
    parts = ['# ' + args.subject + '：视频需求', args.requirements]
    if getattr(args, 'require_section_count', False):
        parts.append(f'用户指定片段数量：{args.section_count}，由原生工作流安排。')
    if args.audience: parts.append('受众：' + args.audience)
    if options.get('duration_minutes') is not None:
        parts.append(f"用户指定时长：{options['duration_minutes']:g} 分钟")
    if options.get('enable_tts') is not None:
        parts.append('配音要求：' + ('需要配音' if options['enable_tts'] else '不需要配音'))
    if options.get('include_visuals') is not None:
        parts.append('外部配图：' + ('允许使用' if options['include_visuals'] else '不需要外部配图'))
    parts.append('讲稿、分镜、视觉设计、音频编排和动画制作交给 HyperFrames 原生工作流。')
    value = {'outline_id': args.revise_outline_id or 'outline_' + uuid4().hex,
        'revision': prior['revision'] + 1 if prior else 1, 'created_request_id': tools.request.request_id,
        'resource_type': 'classroom', 'subject': args.subject, 'audience': args.audience,
        'interaction_mode': 'outline_confirmation' if getattr(args,'require_confirmation',False) else 'direct',
        'requirements': args.requirements,
        'workspace': {'scope_type': tools.request.scope_type or 'course', 'scope_id': tools.request.scope_id},
        'organization_id': args.organization_id, 'classroom_options': options,
        'quality': {'structural': 'pass', 'objective_coverage': False,
                    'coverage_method': 'requirements_handoff', 'semantic_review': 'not_performed', 'review': None},
        'chapters': [], 'markdown': '\n\n'.join(part for part in parts if part),
        'evidence_ids': args.evidence_ids, 'source_policy': tools._source_policy(),
        'status': 'awaiting_approval', 'job_id': None}
    tools.session.data['outlines'][value['outline_id']] = value
    tools.session.data['active_outline'] = value['outline_id']
    tools.session.save()
    return value
