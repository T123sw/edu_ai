import json
from pathlib import Path
import pytest
from app.chat.harness.numeric_checks import CalculationCheck, calculate, verify_calculations, matches


def test_softmax_and_matrix_computation_use_full_precision():
    assert calculate('softmax([1,0,1])') == pytest.approx([.4223187982515182,.15536240349696362,.4223187982515182])
    value = calculate('matmul([[1,0],[0,1],[1,1]], transpose([[1,0],[0,1],[1,1]]))/sqrt(2)')
    assert value[2] == pytest.approx([.7071067811865475,.7071067811865475,1.414213562373095])
    assert not matches(calculate('softmax([1/sqrt(2),1/sqrt(2),2/sqrt(2)])'), [.248,.248,.504], 3)
    assert matches(calculate('softmax([1/sqrt(2),1/sqrt(2),2/sqrt(2)])'), [.248,.248,.503], 3)


@pytest.mark.parametrize('expression', ["__import__('os').system('id')", '(1).__class__', '[x for x in [1]]',
    '2**100000000', 'open("/etc/passwd")', 'exp(10000)', '1/0'])
def test_calculator_rejects_code_and_unbounded_work(expression):
    with pytest.raises((ValueError, TypeError, ArithmeticError)): calculate(expression)


def test_source_bound_claim_cannot_be_overridden_by_model_pass():
    question = {'explanation':'softmax([1,0,1]) ≈ [0.422,0.207,0.371]'}
    checks = [CalculationCheck(source_field='explanation', excerpt=question['explanation'],
        expression='softmax([1,0,1])', claimed='[0.422,0.207,0.371]', decimal_places=3)]
    evidence, errors = verify_calculations(question, checks)
    assert errors and evidence[0]['status'] == 'fail'
    checks[0].excerpt = 'fabricated quote'
    with pytest.raises(ValueError, match='excerpt_mismatch'): verify_calculations(question, checks)


def test_actual_transformer_explanation_is_rejected_even_without_model_claims():
    question = {'explanation':'注意若漏掉除以 √2，直接对 1、0、1 做 softmax 会得到 0.422、0.207、0.371，那是未缩放打分的权重。'}
    evidence, errors = verify_calculations(question, [])
    assert errors and evidence[0]['status'] == 'fail'
    question['explanation'] = question['explanation'].replace('0.422、0.207、0.371', '0.422、0.155、0.422')
    assert not verify_calculations(question, [])[1]


def test_vector_scalar_multiplication_never_repeats_a_list():
    assert calculate("[1]*100000000") == [100000000]


def test_unscaled_value_output_is_recomputed_from_full_precision():
    result = calculate('weighted_sum(softmax([1,0,1]), [[1,0],[0,1],[1,1]])')
    assert result == pytest.approx([.8446375965030364,.5776812017484818])
    assert matches(result,[.84,.58],2)
    assert not matches(result,[.79,.58],2)


def test_claim_cannot_hide_bad_digits_by_lowering_precision_or_replacing_claimed_value():
    question = {'explanation':'权重是 0.40110905'}
    check = CalculationCheck(source_field='explanation', excerpt=question['explanation'],
        expression='exp(1/sqrt(2))/(2*exp(1/sqrt(2))+1)', claimed='0.40110905',decimal_places=3)
    evidence, errors = verify_calculations(question,[check])
    assert errors and evidence[0]['status']=='fail'
    check.claimed = '0.401'
    evidence, errors = verify_calculations(question,[check])
    assert errors and evidence[0]['status']=='unverified'


def test_literal_wrong_example_is_not_mistaken_for_a_positive_claim():
    question = {'explanation':'错误示例：softmax([1,0,1]) = [0.422,0.207,0.371]。正确值另行计算。'}
    assert not verify_calculations(question,[])[1]


def test_indexed_calculation_sources_are_restored_without_model_transcription():
    from types import SimpleNamespace
    from app.chat.harness.numeric_checks import bind_calculation_sources
    content = {'questions':[{'answer':'第一行：[0.422, 0.155, 0.422]。第二行另算。'}]}
    claim = CalculationCheck(source_field='answer',start_segment=0,end_segment=0,
        expression='softmax([1,0,1])',claimed='[0.422,0.155,0.422]',decimal_places=3)
    review = SimpleNamespace(question_checks=[SimpleNamespace(question_index=0,calculation_checks=[claim])])
    bind_calculation_sources(content,review)
    assert claim.excerpt == '第一行：[0.422, 0.155, 0.422]。'
    assert not verify_calculations(content['questions'][0],[claim])[1]
    claim.end_segment = 99
    with pytest.raises(ValueError, match='numeric_source_span_invalid'):bind_calculation_sources(content,review)
