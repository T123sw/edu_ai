"""Bounded structured context; optional history never displaces hard constraints."""
import hashlib
import json
from pathlib import Path
from .research_agent import ResearchError
from .intake_skill import INTAKE_PHASES, load_intake_skill

PROMPTS = Path(__file__).parent/'prompts'


def encoded_size(value):
    # UTF-8 bytes provide a conservative token ceiling without provider tokenizer drift.
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


def context_packet(context, tools, *, max_tokens, output_tokens=6000, native_skill=False):
    context=dict(context)
    skill = load_intake_skill() if context['phase'] in INTAKE_PHASES else None
    role_file={'input_document':'intake-role.md','intent':'intake-role.md','route_adjustment':'route-adjustment.md','review':'path-review.md','research_nodes':'node-research.md','course_review':'course-review.md'}.get(context['phase'],'research-role.md')
    role=(PROMPTS/role_file).read_text()
    if skill and not native_skill:
        role += '\n' + skill['body']
    context['trace']=list(context.get('trace',()))[-6:]
    if context['phase']=='review':
        context.pop('trace',None); context.pop('review',None)
    # Planning needs exact quotations and provenance, not unrelated page prose.
    if context['phase'] in ('plan','review','done') and context.get('summary'):
        quoted={}
        for finding in context['summary']['findings']:
            for cite in finding['citations']:
                quoted.setdefault(cite['source_id'],[]).append(cite['quote'])
        context['evidence']=[{**{k:v for k,v in e.items() if k != 'passages'},'content':'\n'.join(quoted[e['source_id']]),'context_view':'verified_citation_spans'}
            for e in context.get('evidence',[]) if e['source_id'] in quoted]
        context.pop('candidates',None)
    def messages():
        return [{'role':'system','content':role},{'role':'user','content':json.dumps(context,ensure_ascii=False)}]
    # Count schema, protocol framing and response capacity as well as prose.
    size=encoded_size({'messages':messages(),'tools':tools})+512+(encoded_size(skill['text']) if skill and native_skill else 0)
    if size+output_tokens>max_tokens:
        context.pop('trace',None)
        size=encoded_size({'messages':messages(),'tools':tools})+512+(encoded_size(skill['text']) if skill and native_skill else 0)
    if size+output_tokens>max_tokens:
        raise ResearchError('CONTEXT_BUDGET_EXCEEDED','硬约束与必要证据超过窗口，不能静默丢弃')
    return {**({'skill':skill,'skill_name':skill['name'],'skill_sha256':skill['sha256']} if skill else {}), 'messages':messages(),'input_token_upper_bound':size,
        'role_version':role_file+':'+hashlib.sha256(role.encode()).hexdigest(),
        'tool_set_digest':hashlib.sha256(json.dumps(tools,sort_keys=True).encode()).hexdigest()}
