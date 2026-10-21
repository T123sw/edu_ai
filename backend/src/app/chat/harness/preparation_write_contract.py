"""Compile preparation write/repair contracts before asking the model to submit.

The wire format is a tool argument object, never an untyped JSON string. Cross-
field references are checked before acknowledgement; content correctness still
belongs to the independent reviewer.
"""
from copy import deepcopy

from app.artifact_revision.adapters import apply_edits, validate
from .preparation_content import preparation_metadata, report_sections


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties, 'additionalProperties': False,
            'required': list(properties) if required is None else required}


def text():
    return {'type': 'string', 'minLength': 1, 'pattern': r'\S'}


def array(items, **limits):
    return {'type': 'array', 'items': items, **limits}


def identifier(allowed=None):
    return {**text(), **({'enum': list(allowed)} if allowed else {})}


def quiz_schema():
    variants = []
    for kind in ('single_choice', 'multiple_choice', 'true_false', 'short_answer'):
        fields = {'id': text(), 'type': {'const': kind}, 'stem': text(),
                  'answer': text(), 'explanation': text(),
                  'difficulty': {'type': 'string', 'enum': ['easy', 'medium', 'hard']}}
        required = list(fields)
        if kind in ('single_choice', 'multiple_choice'):
            fields['options'] = array(text(), minItems=2, maxItems=26, uniqueItems=True)
            fields['answer'] = {'type': 'string', 'pattern':
                r'^[A-Z]$' if kind == 'single_choice' else r'^[A-Z](?:,[A-Z])*$'}
            required.append('options')
        else:
            # Existing native non-choice questions can serialize options=[].
            fields['options'] = array(text(), maxItems=0)
        variants.append(obj(fields, required))
    return obj({'title': text(), 'questions': array({'oneOf': variants}, minItems=1)})


def metadata_schema(kind, context, question_ids=None):
    key = 'question_id' if kind == 'quiz' else 'section_id'
    locator = obj({key: identifier(question_ids)})
    requirements = [r['requirement_id'] for r in context.get('requirements', [])]
    objectives = context['objective_ids']
    fields = {
        'applied_requirements': array(obj({
            'requirement_id': identifier(requirements), 'locator': locator, 'explanation': text(),
        }), **({} if requirements else {'maxItems': 0})),
        'objective_bindings': array(obj({
            'objective_id': identifier(objectives), 'locator': locator,
            'role': {'type': 'string', 'enum': ['practice', 'check'] if kind == 'quiz'
                     else ['explanation', 'practice', 'check']},
        }), minItems=1),
    }
    if kind == 'quiz':
        fields['question_time_estimates'] = array(obj({
            'question_id': identifier(question_ids),
            'thinking_seconds': {'type': 'number', 'exclusiveMinimum': 0},
            'reason': {**text(), 'minLength': 5},
        }), minItems=1)
    return fields


def edit_schema(kind, previous, allow_delete):
    paths = []
    if kind == 'report':
        paths.append([])
    else:
        if isinstance(previous.get('title'), str):
            paths.append(['title'])
        for index, question in enumerate(previous['questions']):
            for key in ('stem', 'answer', 'explanation', 'difficulty'):
                if isinstance(question.get(key), str):
                    paths.append(['questions', index, key])
            paths.extend(['questions', index, 'options', option]
                         for option in range(len(question.get('options') or [])))
    replacement = obj({
        'op': {'const': 'replace'}, 'path': {'enum': paths},
        'before': text(), 'after': {'type': 'string'},
    }, ['path', 'before', 'after'])
    variants = [replacement]
    if kind == 'quiz' and allow_delete:
        variants.extend(obj({
            'op': {'const': 'delete'}, 'path': {'const': ['questions', index]},
            'before': {'const': question}, 'after': {'type': 'null'},
        }) for index, question in enumerate(previous['questions']))
    return array({'oneOf': variants}, maxItems=100)


class PreparationWriteContract:
    def __init__(self, kind, context, spec_digest, *, previous=None, patch=False, allow_delete=False):
        if kind not in {'quiz', 'report'}:
            raise ValueError('unsupported_preparation_write_contract')
        if patch and previous is None:
            raise ValueError('repair_requires_previous_content')
        self.kind, self.context, self.spec_digest = kind, deepcopy(context), spec_digest
        self.previous, self.patch, self.allow_delete = deepcopy(previous), patch, allow_delete
        question_ids = ([q['id'] for q in previous['questions']]
                        if kind == 'quiz' and previous is not None else None)
        fields = metadata_schema(kind, self.context, question_ids)
        if patch:
            fields['edits'] = edit_schema(kind, self.previous, allow_delete)
        else:
            fields['content'] = quiz_schema() if kind == 'quiz' else text()
        self.schema = obj(fields)
        self.schema['description'] = (
            f'{kind} {"局部修订" if patch else "完整生成"}提交契约。'
            '字段直接置于工具参数顶层；不添加 value 包装，不返回 JSON 字符串。'
            '只提交当前资源。结构正确后还需独立内容审阅。')

    def validate_submission(self, arguments):
        """Pure cross-field validation, called before the model session ends."""
        content = (apply_edits(self.previous, arguments['edits'])
                   if self.patch and arguments['edits'] else
                   deepcopy(self.previous) if self.patch else arguments['content'])
        validate(self.kind, content)
        if self.kind == 'quiz':
            from .reviewed_resource import validate_resource
            validate_resource('quiz', content)
            ids = [q['id'] for q in content['questions']]
            estimates = arguments['question_time_estimates']
            if len(estimates) != len(ids) or {e['question_id'] for e in estimates} != set(ids):
                raise ValueError('question_time_estimates must cover each question_id exactly once')
            for q in content['questions']:
                if 'difficulty' in q and q['difficulty'] not in ('easy', 'medium', 'hard'):
                    raise ValueError('difficulty must be easy, medium or hard')
                if q['type'] in ('single_choice', 'multiple_choice'):
                    letters = q['answer'].split(',')
                    if len(letters) != len(set(letters)):
                        raise ValueError('choice answer contains duplicate letters')
            if self.previous is not None:
                old_ids = [q['id'] for q in self.previous['questions']]
                expected = [key for key in old_ids if key in ids] if self.allow_delete else old_ids
                if not ids or ids != expected:
                    raise ValueError('quiz_repair_changed_question_identity')
        elif self.previous is not None:
            if list(report_sections(content)) != list(report_sections(self.previous)):
                raise ValueError('report_repair_changed_section_identity')
        preparation_metadata(self.kind, content, arguments, self.context, self.spec_digest)


def bind_write_contract(writer, kind, context, spec_digest, **options):
    """Legacy workbench and test gateways retain their existing contracts."""
    if context is None or kind not in {'quiz', 'report'}:
        return writer
    contract = PreparationWriteContract(kind, context, spec_digest, **options)
    bind = getattr(writer, 'with_response_schema', None)
    if not callable(bind):
        if getattr(writer, 'preparation_harness', False):
            raise RuntimeError('PREPARATION_WRITE_SCHEMA_REQUIRED')
        return writer
    return bind(contract.schema, validator=contract.validate_submission)
