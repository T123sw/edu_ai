"""Resolve generated mappings against native bodies before trusting an LLM review."""
import math
import re
from .tool_registry import digest


def preparation_metadata(artifact):
    return artifact.get('content', {}).get('generation_state', {}).get('preparation', {})


def content_locations(kind, body):
    """Stable IDs only; ordinal pages and invented scene/question aliases are invalid."""
    locations = {'section_id': set(), 'question_id': set(), 'scene_id': set(), 'action_id': set()}
    if kind == 'report':
        if isinstance(body, str):
            # Ignore headings in code samples; explicit HTML anchors are also native locators.
            text = re.sub(r'(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$', '', body)
            locations['section_id'].update(re.findall(r'(?m)^#{1,6}\s+(.+?)\s*#*\s*$', text))
            locations['section_id'].update(re.findall(r'<(?:a|h[1-6])\b[^>]*\bid=["\']([^"\']+)', text))
        elif isinstance(body, dict):
            locations['section_id'].update(str(s['id']) for s in body.get('sections', []) if s.get('id'))
    elif kind == 'quiz' and isinstance(body, dict):
        locations['question_id'].update(str(q['id']) for q in body.get('questions', []) if q.get('id'))
    elif kind == 'classroom' and isinstance(body, dict):
        for scene in body.get('scenes', []):
            if scene.get('id'): locations['scene_id'].add(str(scene['id']))
            locations['question_id'].update(str(q['id']) for q in scene.get('content',{}).get('questions',[]) if q.get('id'))
            for action in scene.get('actions', []):
                if action.get('id'): locations['action_id'].add(str(action['id']))
    return locations


def resolve_locator(kind, body, locator):
    if not isinstance(locator, dict) or not locator or set(locator) - {'section_id','question_id','scene_id','action_id'}:
        raise ValueError('INVALID_CONTENT_LOCATOR')
    locations = content_locations(kind, body)
    if any(not value or str(value) not in locations[key] for key, value in locator.items()):
        raise ValueError('CONTENT_LOCATOR_NOT_FOUND')
    if 'action_id' in locator:
        if 'scene_id' not in locator:
            raise ValueError('ACTION_REQUIRES_SCENE')
        scene = next(s for s in body['scenes'] if str(s.get('id')) == str(locator['scene_id']))
        if not any(str(a.get('id')) == str(locator['action_id']) for a in scene.get('actions', [])):
            raise ValueError('ACTION_SCENE_MISMATCH')
    if kind == 'classroom' and 'question_id' in locator:
        if 'scene_id' not in locator: raise ValueError('CLASSROOM_QUESTION_REQUIRES_SCENE')
        scene = next(s for s in body['scenes'] if str(s.get('id')) == str(locator['scene_id']))
        if not any(str(q.get('id')) == str(locator['question_id']) for q in scene.get('content',{}).get('questions', [])):
            raise ValueError('QUESTION_SCENE_MISMATCH')
    return locator


def validate_artifact(artifact):
    """v1 remains readable; v2 cannot impersonate it with a legacy review receipt."""
    spec = artifact['spec']
    if spec.get('schema_version', 1) < 2:
        return
    if digest(spec) != artifact['spec_digest'] or digest(artifact['content']) != artifact['content_digest']:
        raise ValueError('ARTIFACT_DIGEST_MISMATCH')
    context = spec.get('teaching_context')
    meta = preparation_metadata(artifact)
    if not context or meta.get('schema_version') != 1:
        raise ValueError('PREPARATION_ALIGNMENT_MISSING')
    if (meta.get('spec_digest') != artifact['spec_digest']
            or meta.get('teaching_context_digest') != digest(context)):
        raise ValueError('PREPARATION_ALIGNMENT_STALE')
    if context.get('node_id') != spec['node_id'] or set(context.get('objective_ids', [])) != set(spec['objective_ids']):
        raise ValueError('ALIGNMENT_NODE_MISMATCH')
    body = artifact['content']['content']
    if artifact['resource_type'] == 'classroom':
        render = meta.get('render_checks', {})
        if render.get('passed') is not True or render.get('issues'):
            raise ValueError('CLASSROOM_RENDER_UNVERIFIED')
    objectives = set(spec['objective_ids'])
    requirements = {r['requirement_id'] for r in context.get('requirements', [])}
    bindings = meta.get('objective_bindings', [])
    if not bindings:
        raise ValueError('OBJECTIVE_BINDINGS_MISSING')
    for binding in bindings:
        if binding.get('objective_id') not in objectives or binding.get('role') not in ('explanation','practice','check'):
            raise ValueError('OBJECTIVE_BINDING_INVALID')
        resolve_locator(artifact['resource_type'], body, binding.get('locator'))
    for applied in meta.get('applied_requirements', []):
        if applied.get('requirement_id') not in requirements or not str(applied.get('explanation', '')).strip():
            raise ValueError('APPLIED_REQUIREMENT_INVALID')
        resolve_locator(artifact['resource_type'], body, applied.get('locator'))
    if 'requirement_ids' not in context and {a['requirement_id'] for a in meta.get('applied_requirements', [])} != requirements:
        raise ValueError('APPLIED_REQUIREMENT_COVERAGE_MISSING')
    duration = meta.get('duration', {})
    basis, value = duration.get('basis'), duration.get('value_minutes')
    if basis not in ('unknown','estimated','measured'):
        raise ValueError('DURATION_BASIS_INVALID')
    if basis == 'unknown':
        if value is not None: raise ValueError('UNKNOWN_DURATION_HAS_VALUE')
    elif (isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value)
          or value <= 0 or not str(duration.get('method', '')).strip()):
        raise ValueError('DURATION_EVIDENCE_MISSING')


def node_requirement_issues(artifacts, nodes):
    """Aggregate real locations over a node's resources, not over unrelated nodes."""
    issues = []
    for node in nodes:
        rows = [a for a in artifacts if a['spec']['node_id'] == node['node_key']]
        scoped = [a for a in rows if 'requirement_ids' in (a['spec'].get('teaching_context') or {})]
        if not scoped:
            continue  # Historical unscoped contexts keep per-resource checks.
        expected = set(node.get('requirement_ids', []))
        for row in scoped:
            context = row['spec']['teaching_context']
            expected.update(context['requirement_ids'])
            if not set(context['requirement_ids']) <= {r['requirement_id'] for r in context['requirements']}:
                raise ValueError('REQUIREMENT_REFERENCE_INVALID')
        covered = set()
        for row in rows:
            validate_artifact(row)
            covered.update(r['requirement_id'] for r in preparation_metadata(row).get('applied_requirements', []))
        missing = expected - covered
        if missing:
            # Repair one explanatory resource, preserving other valid resources.
            target = next((a for a in scoped if a['resource_type'] == 'report'), scoped[0])
            issues.append({'artifact_ids': [target['artifact_id']],
                           'reason': 'NODE_REQUIREMENT_COVERAGE_MISSING:' + ','.join(sorted(missing))})
    return issues


def node_objective_issues(artifacts, nodes):
    """Route missing deliverable checks to a real resource repair before manifest construction."""
    issues = []
    for node in nodes:
        rows = [a for a in artifacts if a['spec']['node_id'] == node['node_key']]
        if not any(a['spec'].get('schema_version', 1) >= 2 for a in rows):
            continue  # Historical manifests retain their existing validation.
        expected = {node['node_key'] + ':o' + str(i + 1) for i, _ in enumerate(node['objectives'])}
        covered = {oid for a in rows if a['spec'].get('required', True) for oid in resource_objectives(a)}
        checked = {oid for a in rows for check in resource_checks(a, node['node_key']) for oid in check['objective_ids']}
        missing_content, missing_checks = expected - covered, expected - checked
        if missing_content or missing_checks:
            preferred = 'quiz' if missing_checks else 'report'
            target = next((a for a in rows if a['resource_type'] == preferred),
                          next((a for a in rows if a['resource_type'] == 'report'), rows[0]))
            issues.append({'artifact_ids': [target['artifact_id']], 'reason':
                'NODE_OBJECTIVE_COVERAGE_MISSING: 内容=' + ','.join(sorted(missing_content))
                + '; 学习检查=' + ','.join(sorted(missing_checks))
                + '。补齐这些目标对应的真实题目或报告自测及 practice/check 映射；已有题目只缺角色映射时仅修正映射，'
                  '保留正确正文和稳定ID。不能把课堂场景伪装为习题或报告位置，也不能机械绑定无关目标。'})
    return issues


def resource_objectives(artifact):
    meta = preparation_metadata(artifact)
    if artifact['spec'].get('schema_version', 1) >= 2:
        validate_artifact(artifact)
        return list(dict.fromkeys(b['objective_id'] for b in meta['objective_bindings']))
    return list(artifact['spec'].get('objective_ids', []))


def resource_checks(artifact, node_id):
    """No classroom locator is disguised as a question or a made-up page."""
    body = artifact['content']['content']
    meta = preparation_metadata(artifact)
    bindings = meta.get('objective_bindings', [])
    if artifact['spec'].get('schema_version', 1) < 2 and not bindings:
        # Legacy report self checks are retained only if the section actually exists.
        if artifact['resource_type'] == 'report' and '学习检查' in content_locations('report', body)['section_id']:
            bindings = [{'objective_id': oid, 'role':'check', 'locator':{'section_id':'学习检查'}}
                        for oid in artifact['spec'].get('objective_ids', [])]
    grouped = {}
    for binding in bindings:
        if binding.get('role') not in ('check','practice'): continue
        locator = binding['locator']
        resolve_locator(artifact['resource_type'], body, locator)
        if set(locator) not in ({'question_id'}, {'section_id'}): continue
        key = digest(locator)
        entry = grouped.setdefault(key, {'locator':locator, 'objectives':[]})
        if binding['objective_id'] not in entry['objectives']: entry['objectives'].append(binding['objective_id'])
    return [{'check_id':node_id+':check:'+digest([artifact['resource_id'], entry['locator']])[:24],
             'objective_ids':entry['objectives'], 'mode':'practice' if 'question_id' in entry['locator'] else 'self_check',
             'resource_id':artifact['resource_id'], 'resource_version':artifact['resource_version'],
             'locator':entry['locator']} for entry in grouped.values()]


def validate_manifest_locations(manifest, artifacts):
    by_id = {a['resource_id']: a for a in artifacts}
    for node in manifest.nodes:
        for check in node.checks:
            artifact = by_id.get(check.resource_id)
            if artifact is not None:
                if artifact['resource_version'] != check.resource_version:
                    raise ValueError('CHECK_RESOURCE_VERSION_MISMATCH')
                resolve_locator(artifact['resource_type'], artifact['content']['content'],
                                check.locator.model_dump(exclude_none=True))


def duration_summary(artifacts, nodes, *, hard_limit=None):
    """Node budgets are constraints, never an observed resource duration."""
    resources = []
    for artifact in artifacts:
        duration = preparation_metadata(artifact).get('duration') or {'basis':'unknown','value_minutes':None,'method':''}
        resources.append({'artifact_id':artifact['artifact_id'], 'node_id':artifact['spec']['node_id'],
                          'required':artifact['spec'].get('required', True), **duration})
    required = [r for r in resources if r['required']]
    unknown = [r['artifact_id'] for r in required if r['basis']=='unknown']
    known = sum(r['value_minutes'] for r in required if r['basis']!='unknown')
    result = {'node_budget_minutes':{n['node_key']:n.get('minutes') for n in nodes},
              'resources':resources, 'required_known_minutes':known, 'unknown_artifact_ids':unknown,
              'interaction_minutes':None, 'interaction_basis':'included in resource estimates when documented; otherwise unknown'}
    if hard_limit is not None and (unknown or known > hard_limit):
        raise ValueError('HARD_DURATION_UNVERIFIED' if unknown else 'HARD_DURATION_EXCEEDED')
    for node in nodes:
        estimated = sum(r['value_minutes'] for r in required if r['node_id']==node['node_key'] and r['basis']!='unknown')
        if node.get('minutes') and estimated > node['minutes']:
            raise ValueError('NODE_DURATION_EXCEEDED:'+node['node_key'])
    return result
