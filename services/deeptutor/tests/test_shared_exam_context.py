"""A shared graph preamble must be reconciled together with a dependent question."""
import pytest
from deeptutor.tools.question import question_extractor as extractor


def test_shared_prefix_reconciliation_reads_the_following_question(monkeypatch,tmp_path):
    calls=[]
    def extract(window,*args):
        calls.append(window)
        question={'question_number':'41','question_type':'short_answer','question_text':'Use graph G to run BFS.',
                  'source_start_line':4,'source_end_line':4,'images':['graph.jpg']}
        if len(calls)>1:
            assert '[L4] 41. Run BFS' in window
            assert '[L1] Given graph G' in window
            question['source_start_line']=1
        return {'questions':[question],'incomplete_questions':[1] if len(calls)==1 else []}
    monkeypatch.setattr(extractor,'_extract_question_window',extract)
    result=extractor.extract_questions_with_llm('Given graph G, answer the following questions.\n![](graph.jpg)\n\n41. Run BFS\n',[],tmp_path,'','','offline')
    assert len(calls)==2
    assert len(result)==1 and result[0]['question_number']=='41'
    assert '![](graph.jpg)' in result[0]['source_text']


def test_shared_prefix_must_be_accounted_for_not_silently_discarded(monkeypatch,tmp_path):
    def extract(*args):
        return {'questions':[{'question_number':'41','question_type':'short_answer','question_text':'Run BFS',
                              'source_start_line':4,'source_end_line':4}], 'incomplete_questions':[1]}
    monkeypatch.setattr(extractor,'_extract_question_window',extract)
    with pytest.raises(ValueError,match='unresolved partial'):
        extractor.extract_questions_with_llm('Unresolved source\n![](graph.jpg)\n\n41. Run BFS\n',[],tmp_path,'','','offline')

@pytest.mark.parametrize('repair',[True,False])
def test_shared_preamble_cannot_collapse_independent_questions(monkeypatch,tmp_path,repair):
    calls=[]
    def extract(window,*args):
        calls.append(window)
        questions=[{'question_number':'41','question_type':'short_answer','question_text':'BFS','source_start_line':1,'source_end_line':2},
                   {'question_number':'42','question_type':'short_answer','question_text':'DFS','source_start_line':3 if repair and len(calls)>1 else 1,'source_end_line':3}]
        return {'questions':questions,'incomplete_questions':[]}
    monkeypatch.setattr(extractor,'_extract_question_window',extract)
    if repair:
        result=extractor.extract_questions_with_llm('Given graph G\n41. BFS\n42. DFS\n',[],tmp_path,'','','offline')
        assert [q['question_number'] for q in result]==['41','42']
    else:
        with pytest.raises(ValueError,match='share a start anchor'):
            extractor.extract_questions_with_llm('Given graph G\n41. BFS\n42. DFS\n',[],tmp_path,'','','offline')
    assert len(calls)==2
    assert 'share a start anchor' in calls[1]
