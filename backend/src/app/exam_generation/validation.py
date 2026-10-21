"""Validate delivery against the blueprint frozen before generation, not its own count."""
from collections import Counter
import hashlib
import re

TYPES = {'choice', 'multiple_choice', 'concept', 'fill_in_blank', 'short_answer', 'written', 'coding', 'compound'}


def _matches(node, question):
    if not isinstance(node, dict) or not isinstance(question, dict):
        return False
    kind = node.get('question_type')
    if kind not in TYPES or question.get('question_id') != node.get('question_id') or question.get('question_type') != kind:
        return False
    if any(not isinstance(question.get(key), str) or not question[key].strip() for key in ('question', 'correct_answer', 'explanation')):
        return False
    options = question.get('options')
    if kind in {'choice', 'multiple_choice'}:
        keys = node.get('option_keys')
        if not isinstance(keys, list) or len(keys) < 2 or len(set(keys)) != len(keys):
            return False
        if not isinstance(options, dict) or set(options) != set(keys) or any(not isinstance(v, str) or not v.strip() for v in options.values()):
            return False
        if kind == 'choice' and question['correct_answer'] not in options:
            return False
        if kind == 'multiple_choice':
            answers = question.get('correct_answers')
            if not isinstance(answers, list) or any(not isinstance(a, str) for a in answers) or len(answers) < 1 or len(set(answers)) != len(answers) or not set(answers) <= set(keys):
                return False
    elif options:
        return False
    if kind == 'concept' and question['correct_answer'] not in {'true', 'false'}:
        return False
    if kind == 'fill_in_blank':
        blanks = node.get('blank_count')
        if type(blanks) is not int or blanks < 1 or len(re.findall(r'(?<!_)____(?!_)', question['question'])) != blanks:
            return False
        if blanks > 1:
            answers = question.get('blank_answers')
            if not isinstance(answers, list) or len(answers) != blanks or any(not isinstance(a, str) or not a.strip() for a in answers):
                return False
    nodes, children = node.get('children') or [], question.get('children') or []
    if not isinstance(nodes, list) or not isinstance(children, list) or len(nodes) != len(children):
        return False
    if (kind == 'compound') != bool(nodes):
        return False
    ids = [n.get('question_id') for n in nodes if isinstance(n, dict)]
    if len(ids) != len(nodes) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        return False
    return all(_matches(n, q) for n, q in zip(nodes, children))


def complete_result(record):
    result = record.get('result') or {}
    summary = (result.get('metadata') or {}).get('summary') or {}
    count, results = summary.get('completed'), summary.get('results')
    if summary.get('success') is not True or summary.get('failed') != 0:
        return False
    if type(count) is not int or count < 1 or not isinstance(results, list) or count != len(results):
        return False
    request = record['request']
    if request['mode'] != 'mimic':
        if count != request['num_questions']:
            return False
        targets = request.get('per_type_counts')
        if targets and Counter((r.get('qa_pair') or {}).get('question_type') for r in results) != Counter(targets):
            return False
        return True
    blueprint = record.get('blueprint')
    if not isinstance(blueprint, dict) or blueprint.get('version') != 1 or summary.get('blueprint') != blueprint:
        return False
    nodes = blueprint.get('questions')
    if not isinstance(nodes, list) or count != len(nodes) or count != summary.get('template_count'):
        return False
    ids = [n.get('question_id') for n in nodes if isinstance(n, dict)]
    if len(ids) != count or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != count:
        return False
    templates = [s for s in (record.get('parsed_sources') or []) if s.get('role') == 'template']
    if len(templates) != 1:
        return False
    source_hash = hashlib.sha256(templates[0]['content'].encode()).hexdigest()
    for node, item in zip(nodes, results):
        if node.get('source_hash') != source_hash or not isinstance(item, dict):
            return False
        if node.get('source_document_id') and node['source_document_id'] != templates[0].get('document_id'):
            return False
        if node.get('source_original_hash') and node['source_original_hash'] != templates[0].get('source_hash'):
            return False
        metadata = item.get('metadata') or {}
        passed = (metadata.get('structure_passed') is True
                  if metadata.get('validation_mode') == 'structure_only'
                  else metadata.get('review_passed') is True)
        if metadata.get('issues') or not passed or metadata.get('blueprint_id') != node['question_id']:
            return False
        if not _matches(node, item.get('qa_pair')):
            return False
    return True
