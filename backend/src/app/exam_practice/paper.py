import hashlib
import json
import re
from fastapi import HTTPException
from app.exam_generation.validation import complete_result
from app.exam_generation.titles import paper_title

def build(record):
    if not complete_result(record):
        raise HTTPException(409, '整份试卷尚未生成完成')
    questions = [item['qa_pair'] for item in record['result']['metadata']['summary']['results']]
    version = hashlib.sha256(json.dumps(questions, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    leaves = {}
    def walk(nodes, prefix='', parents=()):
        result = []
        for i, q in enumerate(nodes):
            number = f'{prefix}.{i+1}' if prefix else str(i+1)
            public = {key: q[key] for key in ('question_id', 'question_type', 'question', 'options') if key in q}
            public.update(number=number, blank_count=len(re.findall(r'(?<!_)____(?!_)', q['question'])))
            public['children'] = walk(q.get('children') or [], number, (*parents, q['question']))
            if not public['children']:
                if q['question_id'] in leaves:
                    raise HTTPException(409, '题目标识重复，暂不能开始作答')
                leaves[q['question_id']] = {**q, 'number': number, 'parents': list(parents), 'blank_count': public['blank_count']}
            result.append(public)
        return result
    public = walk(questions)
    return {'generation_id':record['id'], 'version':version, 'title':paper_title(record['request'], record.get('sources')),
            'questions':public, 'answer_count':len(leaves), 'exam_ready':True}, leaves

def validate_answer(q, value, *, allow_empty=False):
    kind = q['question_type']
    options, blanks, text = value['option_ids'], value['blank_values'], value['text']
    if any(len(s)>4000 for s in blanks) or sum(map(len, blanks))>12000:
        raise HTTPException(422, '填空答案过长')
    if kind in {'choice','multiple_choice','concept'}:
        allowed = {'true','false'} if kind=='concept' else set(q.get('options') or {})
        if text or blanks or len(options)!=len(set(options)) or not set(options)<=allowed or (kind!='multiple_choice' and len(options)>1):
            raise HTTPException(422, '选项不属于当前题目')
        filled=bool(options)
    elif kind=='fill_in_blank':
        if options or text or len(blanks)!=q['blank_count']:
            raise HTTPException(422, '填空数量与题目不一致')
        filled=all(s.strip() for s in blanks)
    else:
        if options or blanks:
            raise HTTPException(422, '请填写文字答案')
        filled=bool(text.strip())
    if not allow_empty and not filled:
        raise HTTPException(422, '请先完成本题作答')
    return filled

def objective(q, answer):
    if q['question_type'] not in {'choice','multiple_choice','concept'}:
        return None
    expected=q.get('correct_answers') if q['question_type']=='multiple_choice' else [q['correct_answer']]
    return set(answer['option_ids'])==set(expected)
