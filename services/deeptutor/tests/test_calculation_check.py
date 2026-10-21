import pytest
from deeptutor.agents.question.calculation_check import Calculator, CalculationError, check_calculations, explanation_arithmetic_issues


def test_numeric_and_algorithmic_counterexamples_are_computed():
    evidence, issues = check_calculations([
        {'expression': '2328-2000', 'expected': 276},
        {'expression': '[i for i in [399,799,800,1599,1600] if i < 1600]', 'expected': [399,799,800,1599]},
        {'expression': 'bin(1024+1)[3]', 'expected': '1'},
    ])
    assert evidence[0]['actual'] == 328
    assert evidence[1]['matches']
    assert evidence[2]['actual'] == '0'
    assert len(issues) == 2


@pytest.mark.parametrize('expression', [
    '__import__("os").system("id")', 'open("/etc/passwd")',
    '(1).__class__', '[x for x in range(100000000)]',
    '10**1000000', '"x" * 100000000',
    '[x for x in range(10000) for y in range(10000)]',
    '(lambda: 1)()', 'sqrt(-1)',
])
def test_expressions_cannot_execute_code_or_exceed_resource_bounds(expression):
    _, issues = check_calculations([{'expression': expression, 'expected': 1}])
    assert issues


def test_valid_math_and_sequence_checks():
    evidence, issues = check_calculations([
        {'expression': '(2328-2000)/82', 'expected': 4},
        {'expression': 'sum(i*i for i in range(4))', 'expected': 14},
        {'expression': 'divmod(111,30)', 'expected': [3,21]},
    ])
    assert not issues and all(x['matches'] for x in evidence)


def test_explicit_false_equalities_in_explanations_and_children():
    issues = explanation_arithmetic_issues({'explanation': '地址差为 $2328-2000=276$，每个元素占 $276 \\div 82 = 4$ 字节。',
        'children': [{'explanation': '1+2*2=6'}]})
    assert len(issues) == 3


def test_symbolic_binary_approximate_and_counterexample_not_false_rejected():
    assert not explanation_arithmetic_issues({'explanation': '1025=(10000000001)_2；ASL=17/7≈2.43。错误的做法是 2+2=5。正确计算 2328-2000=328。2^4-1=15，2^{10}-1=1023。'})


def test_data_structure_helpers_compute_from_inputs():
    checks = [
        {'expression': 'partition_hole([8,3,12,6,10,2])', 'expected':[2,3,6,8,10,12]},
        {'expression': 'partition_swap([8,3,12,6,10,2])', 'expected':[6,3,2,8,10,12]},
        {'expression': 'binary_search_trace([2,5,9,15,18],15)', 'expected':[2,3]},
        {'expression': 'complete_tree_path(14)', 'expected':[0,2,6,14]},
        {'expression': 'complete_tree_subtree(12,2)', 'expected':[2,5,6,11]},
    ]
    _, issues = check_calculations(checks)
    assert not issues


@pytest.mark.parametrize('expression', ['complete_tree_path(-1)','complete_tree_subtree(1000000,0)','complete_tree_subtree(10,-1)'])
def test_tree_helpers_are_bounded(expression):
    assert check_calculations([{'expression':expression,'expected':[]}])[1]


def test_bounded_sequence_concatenation():
    assert Calculator().evaluate('[1,2] + [3]') == [1,2,3]
    assert check_calculations([{'expression':'[i for i in range(6000)] + [i for i in range(6000)]','expected':[]}])[1]


def test_computed_choice_checks_every_option_and_rejects_multiple_winners():
    from deeptutor.agents.question.calculation_check import check_choice_calculations
    q = {'question_type':'choice','options':{'A':'2','B':'4','C':'6','D':'8'}}
    solution = {'requires_computation':True,'option_checks':{'A':'2%4==0','B':'4%4==0','C':'6%4==0','D':'8%4==0'}}
    computed, issues = check_choice_calculations(solution,q)
    assert [k for k,v in computed.items() if v['actual']] == ['B','D']
    assert issues[0].startswith('single_choice_not_unique')
    solution['option_checks']['D']='10%4==0'
    assert not check_choice_calculations(solution,q)[1]
    del solution['option_checks']['A']
    assert check_choice_calculations(solution,q)[1]


def test_choice_calculations_reject_uncomputed_boolean_and_non_boolean():
    from deeptutor.agents.question.calculation_check import check_choice_calculations
    q = {'question_type':'choice','options':{'A':'x','B':'y'}}
    solution = {'requires_computation':True,'option_checks':{'A':'True','B':'1+2'}}
    assert len(check_choice_calculations(solution,q)[1]) == 2
    assert check_choice_calculations({'requires_computation':False},q) == ({},[])


@pytest.mark.parametrize('claim', ['|V|-1=5', '|V| -1=5', 'x -1=5', '(V+E) -1=5'])
def test_symbolic_suffix_is_not_a_numeric_equality(claim):
    assert not explanation_arithmetic_issues({'explanation': claim})


def test_standalone_negative_and_numeric_errors_are_still_rejected():
    issues = explanation_arithmetic_issues({'explanation': '计算 -1=5。计算 9-4=6。'})
    assert len(issues) == 2
