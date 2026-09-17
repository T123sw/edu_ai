"""Pure learning projections: no model, no writes, no inference from silence."""
from .contracts import CourseView, LearningFacts, NextAction, TopicProjection, TopicView


def project_topic(topic: TopicView, facts: LearningFacts) -> TopicProjection:
    states = {s.resource_ref.key: s for s in facts.resources}
    core = [r for r in topic.resources if r.required is True]
    completed = sum(bool(states.get(r.resource_ref.key) and states[r.resource_ref.key].completed) for r in core)
    policy_known = topic.completion_policy == 'explicit' and all(r.required is not None for r in topic.resources)
    core_done = (policy_known and bool(core) and completed == len(core)
                 and set(topic.required_activity_ids) <= set(facts.completed_activity_ids))
    self_assessment = facts.self_assessments.get(topic.topic_id, 'unset')
    started = any(
        s.opened or s.reached_end or s.completed or s.locator is not None
        for r in topic.resources if (s := states.get(r.resource_ref.key)) is not None
    ) or self_assessment != 'unset' or bool(facts.open_questions.get(topic.topic_id))
    judgments, evidence_refs = [], []
    valid_refs = {r.resource_ref.key for r in topic.resources}
    from .contracts import ResourceRef
    for objective in topic.objectives:
        evidence = [e for e in facts.check_evidence if e.get('topic_id') == topic.topic_id and objective.objective_id in e.get('objective_ids', [])
                    and e.get('resource_ref') and ResourceRef.model_validate(e['resource_ref']).key in valid_refs
                    and e.get('evaluator') in {'deterministic', 'model'} and e.get('rule_version')]
        positive = {e.get('question_key', e['check_id']) for e in evidence if e['correct'] is True}
        negative = any(e['correct'] is False for e in evidence)
        rule = objective.check_rule or {}
        enough = bool(rule.get('version') and type(rule.get('min_successes')) is int and rule['min_successes'] >= 1 and len(positive) >= rule['min_successes'])
        judgment = 'mixed' if positive and negative else 'needs_review' if negative else 'evidence_supports' if enough else 'unverified'
        refs = [e['attempt_id'] for e in evidence]
        evidence_refs.extend(refs)
        judgments.append({'objective_id': objective.objective_id, 'judgment': judgment, 'evidence_refs': refs, 'rule': rule or None})
    states = {j['judgment'] for j in judgments}
    judgment = 'mixed' if 'mixed' in states or {'needs_review', 'evidence_supports'} <= states else 'needs_review' if 'needs_review' in states else 'evidence_supports' if states == {'evidence_supports'} else 'unverified'
    return TopicProjection(topic_id=topic.topic_id, judgment=judgment, evidence_refs=sorted(set(evidence_refs)), objective_judgments=judgments,
        progress='core_completed' if core_done else 'in_progress' if started else 'not_started',
        self_assessment=self_assessment, completed_core=completed,
        total_core=len(core) if policy_known and core else None, facts_revision=facts.facts_revision)


def next_actions(course: CourseView, facts: LearningFacts, topic_id: str) -> list[NextAction]:
    index = next((i for i, t in enumerate(course.topics) if t.topic_id == topic_id), None)
    if index is None:
        raise ValueError('topic does not belong to course')
    topic = course.topics[index]
    result = []
    questions = facts.open_questions.get(topic_id, [])
    if questions:
        result.append(NextAction(kind='resolve_question', topic_id=topic_id, source_ids=questions,
                                 reason='仍有未解决的问题', facts_revision=facts.facts_revision))
    states = {s.resource_ref.key: s for s in facts.resources}
    for candidate in course.topics[index:]:
        for resource in candidate.resources:
            if resource.required is False:
                continue
            state = states.get(resource.resource_ref.key)
            if state is None or not state.completed:
                result.append(NextAction(kind='continue', topic_id=candidate.topic_id,
                    resource_ref=resource.resource_ref, reason='继续阅读未标记学完的资料',
                    facts_revision=facts.facts_revision))
                return result
    result.append(NextAction(kind='review_course', topic_id=topic_id,
        reason='可回顾课程；阅读与检查事实分别保留', facts_revision=facts.facts_revision))
    return result
