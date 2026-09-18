"""Server-issued passage handles avoid asking a model to retype source typography."""
import re


def passages(content):
    result=[]; offset=0
    while offset<len(content):
        end=min(offset+240,len(content))
        if end<len(content):
            boundaries=[m.end() for m in re.finditer(r'\n\n|[。！？.!?]\s',content[offset:end]) if m.end()>=60]
            if boundaries: end=offset+boundaries[-1]
        text=content[offset:end]
        if len(text.strip())>=8: result.append(text)
        elif result and len(result[-1])+len(text)<=400: result[-1]+=text
        offset=end
    return result


def span_registry(state):
    return {f'q{i+1}_{j+1}':{'source_id':e.source_id,'quote':quote}
            for i,e in enumerate(state.evidence) for j,quote in enumerate(passages(e.content))}


def evidence_context(state):
    return [{**e.model_dump(mode='json',exclude={'content'}),'passages':[
        {'citation_ref':f'q{i+1}_{j+1}','text':quote} for j,quote in enumerate(passages(e.content))]}
        for i,e in enumerate(state.evidence)]
