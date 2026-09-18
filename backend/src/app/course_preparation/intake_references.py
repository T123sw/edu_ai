"""Server-owned intake quotes; IDs bind the document version, chunk and text."""
from copy import deepcopy
import hashlib
import json
from .evidence_spans import passages


def reference_id(document, offset, quote):
    value = [document['document_id'], document.get('version'), document.get('source_hash'), offset, quote]
    return 'ip_' + hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()[:24]


def document_passages(document, offset, content):
    return [{'source_ref': reference_id(document, offset, quote), 'text': quote}
            for quote in passages(content)]


def with_references(documents):
    """Also upgrade historical checkpoints without re-reading or reinterpreting them."""
    result = deepcopy(documents)
    for document in result:
        for part in document['parts']:
            for point in part['relevant_points']:
                point['source_ref'] = reference_id(document, part.get('offset', 0), point['source_quote'])
    return result


def resolve_requirements(brief, documents):
    registry = {point['source_ref']: (document['document_id'], point['source_quote'])
                for document in with_references(documents) for part in document['parts']
                for point in part['relevant_points']}
    requirements = []
    for item in brief.requirements:
        if item.source_ref:
            entry = registry.get(item.source_ref)
            if entry is None:
                raise ValueError(f'{item.requirement_id}: 未知 source_ref={item.source_ref}；请选择 input_documents 要点的 source_ref')
            document_id, quote = entry
            if item.source_document_id and item.source_document_id != document_id:
                raise ValueError(f'{item.requirement_id}: source_ref 不属于 source_document_id={item.source_document_id}')
            item = item.model_copy(update={'source_document_id': document_id, 'source_quote': quote})
        requirements.append(item)
    return brief.model_copy(update={'requirements': tuple(requirements)})
