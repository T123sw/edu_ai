import asyncio
import json
from unittest.mock import AsyncMock
import httpx
import pytest
from deeptutor.agents.question.calculation_check import Calculator,check_calculations,check_choice_calculations
from deeptutor.agents.question.algorithm_checks import linear_probe,dijkstra,is_heap,is_topological_order
from deeptutor.agents.question.exam_retry import model_call_with_retry


def test_named_computations_use_actual_values_not_claimed_expected_values():
    evidence,issues=check_calculations([
        {'name':'delta','expression':'25-9','expected':10},
        {'expression':'delta/4','expected':4}])
    assert len(issues)==1 and evidence[1]['actual']==4
    assert check_calculations([{'name':'a','expression':'a+1','expected':2}])[1]
    assert check_calculations([{'name':'a','expression':'1+1','expected':2},{'name':'a','expression':'3','expected':3}])[1]


def test_matrix_boundaries_and_tree_membership_compute_from_actual_indices():
    c=Calculator()
    assert c.evaluate('[[i,j] for i in range(5) for j in range(5) if 4-i<=j<=5-i]') == [[0,4],[1,3],[1,4],[2,2],[2,3],[3,1],[3,2],[4,0],[4,1]]
    assert c.evaluate('len([i for i in complete_tree_subtree(2024,2) if 2*i+1>=2024 and i<1899])')==375
    assert c.evaluate('sum(i*x for i,x in enumerate([2,3,4]))')==11
    assert c.evaluate("{'x':[1,2]}['x'][1]")==2


def test_graph_single_choice_checks_every_edge_and_vertex():
    vertices=[0,1,2,3];edges=[[0,1],[0,2],[1,3],[2,3]]
    assert is_topological_order(vertices,edges,[0,1,2,3])
    assert is_topological_order(vertices,edges,[0,2,1,3])
    assert not is_topological_order(vertices,edges,[1,0,2,3])
    assert not is_topological_order(vertices,edges,[0,1,1,3])
    assert is_heap([1,3,2,8,4]) and not is_heap([1,3,2,0])
    computed,issues=check_choice_calculations({'requires_computation':True,'option_checks':{
        'A':f'is_topological_order({vertices},{edges},[0,1,2,3])',
        'B':f'is_topological_order({vertices},{edges},[0,2,1,3])'}},{'question_type':'choice','options':{'A':'first','B':'second'}})
    assert issues and all(v['actual'] for v in computed.values())


def test_hash_tombstones_do_not_stop_failed_search_and_wraparound_counts():
    value=linear_probe([0,5,10],7,5,[5])
    assert value['table']==[0,'deleted',10,None,None,None,None]
    assert value['successful_probes']==[1,3]
    assert value['unsuccessful_probes']==[4,3,2,1,1]
    assert value['asl_success']==2 and value['asl_unsuccess']==2.2
    assert linear_probe([4,9,14],5,5)['table']==[9,14,None,None,4]
    with pytest.raises(ValueError):linear_probe([1,1],5)
    with pytest.raises(ValueError):linear_probe([],100000)


def test_dijkstra_stop_convention_ties_zero_weights_and_unreachable_nodes():
    matrix=[[None,0,3,None],[None,None,2,None],[None,None,None,None],[None,None,None,None]]
    result=dijkstra(matrix,0,1)
    assert result['settled']==[1,1,0,0]
    assert result['distances']==[0,0,3,None]  # Before relaxing vertex 1.
    result=dijkstra(matrix,0)
    assert result['distances']==[0,0,2,None] and result['predecessors']==[-1,0,1,-1]
    assert dijkstra([[None,1,1],[None,None,None],[None,None,None]],0)['order']==[0,1,2]
    with pytest.raises(ValueError):dijkstra([[None,-1],[None,None]],0)


@pytest.mark.parametrize('expression',[
    'list(range(10000000))','[list(range(10000)) for i in range(1000)]',
    '[i for i in range(10000) for j in range(10000) if False]',
    "{'x':1}.update({'x':2})",'min([1,2],key=lambda x:x)',
    "__import__('os')","open('/etc/passwd')",'dijkstra([[None]],99)',
])
def test_extended_expressions_remain_bounded_and_cannot_execute_code(expression):
    assert check_calculations([{'expression':expression,'expected':0}])[1]


@pytest.mark.asyncio
async def test_transient_retry_recovers_but_exhaustion_is_bounded(monkeypatch):
    sleep=AsyncMock();monkeypatch.setattr('deeptutor.agents.question.exam_retry.asyncio.sleep',sleep)
    call=AsyncMock(side_effect=[httpx.ReadTimeout('fixture'),42]);notify=AsyncMock()
    assert await model_call_with_retry(call,notify=notify)==42
    assert call.await_count==2 and notify.await_count==1
    call=AsyncMock(side_effect=httpx.ReadTimeout('fixture'))
    with pytest.raises(httpx.ReadTimeout):await model_call_with_retry(call)
    assert call.await_count==3


@pytest.mark.asyncio
async def test_permanent_error_and_cancellation_are_never_retried():
    for error in [ValueError('invalid question'),asyncio.CancelledError()]:
        call=AsyncMock(side_effect=error)
        with pytest.raises(type(error)):await model_call_with_retry(call)
        assert call.await_count==1


def test_safe_readonly_methods_reproduce_real_topological_and_string_checks():
    assert Calculator().evaluate('all([2,1,4,3,5,6].index(u)<[2,1,4,3,5,6].index(v) for u,v in [[1,3],[1,4],[2,4],[3,5],[4,5],[5,6]])') is True
    assert Calculator().evaluate('"aaaaa".replace("aa","b")')=='bba'
    assert Calculator().evaluate("{'x':3}.get('x')")==3
    assert check_calculations([{'expression':'[1].append(2)','expected':None}])[1]
    assert check_calculations([{'expression':'"a".replace("", "x".replace("x", "a"))','expected':'aaa'}])[0][0]['actual']=='aaa'


def test_independent_compute_only_outputs_are_actual_facts_not_predicted_assertions():
    evidence,issues=check_calculations([
        {'name':'tree','expression':'complete_tree_subtree(27,2)'},
        {'expression':'[i+1 for i in tree if 2*(i+1)>27 and i+1<25]'}],allow_compute_only=True)
    assert not issues and evidence[-1]['actual']==[14,15,24]
    assert evidence[-1]['matches'] is None
    assert check_calculations([{'expression':'1+1'}])[1]  # Explicit reviewer assertions still require expected.


def test_spatial_leaf_order_is_not_global_level_order():
    from deeptutor.agents.question.algorithm_checks import complete_tree_facts
    a=complete_tree_facts(1000,999)
    assert a['top_subtree_side']=='right' and a['leaves_to_left']==232 and a['leaves_before_by_label']==243
    b=complete_tree_facts(2024,1900,1)
    assert b['leaves_to_left']==364 and b['leaves_before_by_label']==375
    c=complete_tree_facts(27,25,1)
    assert c['leaves_to_left']==1 and c['leaves_before_by_label']==3 and c['top_subtree_height']==4


def test_tree_acceptance_requires_actual_comparison_for_every_child():
    from deeptutor.agents.question.calculation_check import check_tree_answer_assertions
    q={'children':[{'question_id':'left','correct_answer':'1'},{'question_id':'label','correct_answer':'3'}]}
    items=[{'name':'facts','expression':'complete_tree_facts(27,25,1)'},
        {'question_id':'left','expression':"facts['leaves_to_left']==1",'expected':True},
        {'question_id':'label','expression':"facts['leaves_before_by_label']==3",'expected':True}]
    evidence,issues=check_calculations(items,allow_compute_only=True)
    assert not issues and not check_tree_answer_assertions(evidence,q)
    assert check_tree_answer_assertions(evidence[:-1],q)==['tree_answer_unverified: label']
    items[-1]['expression']='3==3'
    assert check_tree_answer_assertions(check_calculations(items,allow_compute_only=True)[0],q)
    items[-1]['expression']="facts['leaves_before_by_label']==249"
    evidence,issues=check_calculations(items,allow_compute_only=True)
    assert issues and check_tree_answer_assertions(evidence,q)


def test_reviewer_cannot_silently_replace_a_wrong_candidate_number():
    from deeptutor.agents.question.calculation_check import check_tree_answer_assertions
    q={'question_id':'leaf','correct_answer':'249个'}
    items=[{'question_id':'leaf','expression':"complete_tree_facts(1000,999)['leaves_to_left']==232",'expected':True}]
    evidence,issues=check_calculations(items)
    assert not issues and check_tree_answer_assertions(evidence,q)==['tree_answer_unverified: leaf']
    q['correct_answer']='232 个'
    assert not check_tree_answer_assertions(evidence,q)


@pytest.mark.asyncio
async def test_false_candidate_comparison_is_not_repaired_into_true_assertion():
    from deeptutor.agents.question.answer_evidence import verify_tree_answers
    call=AsyncMock(return_value={'calculations':[{'question_id':'q','expression':"complete_tree_facts(1000,999)['leaves_to_left']==249",'expected':True}]})
    evidence,issues=await verify_tree_answers({'question_id':'q','correct_answer':'249'},[],call)
    assert 'candidate_tree_claim_false' in issues and call.await_count==1
    assert evidence[0]['actual'] is False


@pytest.mark.asyncio
async def test_missing_answer_evidence_gets_bounded_repair_without_changing_candidate():
    from deeptutor.agents.question.answer_evidence import verify_tree_answers
    call=AsyncMock(side_effect=[{}, {'calculations':[{'question_id':'q','expression':"complete_tree_facts(27,25,1)['leaves_before_by_label']==3",'expected':True}]}])
    question={'question_id':'q','correct_answer':'3','question':'Count labels before target.'}
    evidence,issues=await verify_tree_answers(question,[],call)
    assert not issues and evidence[0]['actual'] is True and call.await_count==2
    assert json.loads(call.await_args_list[1].args[1])['candidate']==question


def test_tree_explanations_are_rendered_from_true_paths_and_leaf_sets():
    from deeptutor.agents.question.tree_explanation import render_tree_explanation
    from deeptutor.agents.question.algorithm_checks import complete_tree_facts
    q={'question':'1000个结点，目标998，编号从0开始。','correct_answer':'wrong parent summary',
       'children':[{'question_id':'a','correct_answer':'S在右子树。因为错误的二进制公式。','explanation':'wrong'},
                   {'question_id':'b','correct_answer':'242个','explanation':'wrong'}]}
    facts=complete_tree_facts(1000,998)
    assert render_tree_explanation(q,[{'expression':'complete_tree_facts(1000,998)','actual':facts}])
    assert '错误' not in q['correct_answer'] and 'wrong' not in q['explanation']
    assert '500～510、767～999' in q['explanation']
    assert '242' in q['explanation'] and '231' in q['explanation']
    assert 'i−1' in q['explanation'] and '2i+1' in q['explanation']
    assert not render_tree_explanation({'question':'27个结点，目标25'},[{'expression':'complete_tree_facts(1000,998)','actual':facts}])


def test_internal_tree_target_counts_its_left_subtree_leaves():
    from deeptutor.agents.question.algorithm_checks import complete_tree_facts
    assert complete_tree_facts(7,1)['leaves_to_left']==1
    assert complete_tree_facts(7,0)['leaves_to_left']==2
    # Existing leaf cases are unchanged by the internal-node correction.
    assert complete_tree_facts(1000,999)['leaves_to_left']==232


def test_named_algorithm_arguments_are_safe_and_do_not_require_manual_rewrites():
    value=Calculator().evaluate('linear_probe([0,5,10],7,modulus=5,deleted=[5])["asl_success"]')
    assert value==2
    assert check_calculations([{'expression':'linear_probe([1],3,**{"deleted":[]})','expected':0}])[1]


def test_tree_candidate_plan_uses_actual_ancestor_subtrees():
    from deeptutor.agents.question.algorithm_checks import tree_instance_plan
    from deeptutor.agents.question.calculation_check import complete_tree_subtree
    for count,target,base in [(41,39,0),(80,72,0),(41,40,1)]:
        plan=tree_instance_plan(count,target,base)
        for subtree in plan['ancestor_subtrees']:
            nodes=[v for level in subtree['levels'] for v in level]
            assert target in nodes
            assert nodes==[i+base for i in complete_tree_subtree(count,subtree['root']-base)]
            assert subtree['count']==len(nodes) and subtree['height']==len(subtree['levels'])


def test_sort_keys_remain_inside_bounded_calculator():
    from deeptutor.agents.question.calculation_check import CalculationError
    assert Calculator().evaluate("sorted([('b',3),('a',1)],key=lambda x:x[1])")==[['a',1],['b',3]]
    assert Calculator().evaluate('true and not false') is True
    with pytest.raises(CalculationError):Calculator().evaluate("sorted([1],key=lambda x:__import__('os'))")
    with pytest.raises(CalculationError):Calculator().evaluate('(lambda x:x)(1)')


@pytest.mark.asyncio
async def test_unrelated_false_tree_computation_gets_proof_repair():
    from deeptutor.agents.question.answer_evidence import verify_tree_answers
    q={'question_id':'leaf','correct_answer':'4个'}
    call=AsyncMock(side_effect=[{'calculations':[{'question_id':'leaf','expression':'len(range(32,65))==4','expected':True}]},
        {'calculations':[{'question_id':'leaf','expression':"complete_tree_facts(65,36)['leaves_before_by_label']==4",'expected':True}]}])
    evidence,issues=await verify_tree_answers(q,[],call)
    assert not issues and call.await_count==2 and evidence[0]['actual'] is True


@pytest.mark.parametrize('expression',[
    '[data+data for i in range(1000)]',
    '[data[:] for i in range(1000)]',
    '[dijkstra(matrix,0) for i in range(1000)]',
])
def test_nested_copies_and_algorithm_traces_share_allocation_budget(expression):
    from deeptutor.agents.question.calculation_check import CalculationError
    with pytest.raises(CalculationError,match='allocation budget'):
        Calculator().evaluate(expression,{'data':list(range(5000)),'matrix':[[0 if i==j else 1 for j in range(20)] for i in range(20)]})


def test_tree_helper_index_bases_are_explicit_and_backward_compatible():
    from deeptutor.agents.question.calculation_check import complete_tree_path,complete_tree_subtree,CalculationError
    assert complete_tree_path(25,1)==[1,3,6,12,25]
    assert complete_tree_subtree(27,3,1)==[3,6,7,12,13,14,15,24,25,26,27]
    for count in range(1,65):
        for root in range(count):
            assert complete_tree_subtree(count,root+1,1)==[i+1 for i in complete_tree_subtree(count,root)]
            assert complete_tree_path(root+1,1)==[i+1 for i in complete_tree_path(root)]
    with pytest.raises(CalculationError):complete_tree_subtree(10,0,1)
