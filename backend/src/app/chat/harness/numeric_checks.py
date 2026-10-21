"""Bounded arithmetic verification of source-bound claims; never execute code.

The model identifies claims and expressions, this module computes them. Coverage
is explicit: an empty list is not evidence that all mathematics was verified.
"""
import ast
from decimal import Decimal
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class CalculationCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_field: Literal['stem', 'answer', 'explanation']
    excerpt: str = Field(default='', max_length=4000)
    start_segment: StrictInt | None = Field(default=None, ge=0)
    end_segment: StrictInt | None = Field(default=None, ge=0)
    expression: str = Field(min_length=1, max_length=4000)
    claimed: str = Field(min_length=1, max_length=4000)
    decimal_places: int = Field(ge=0, le=20)


def source_segments(text):
    return [part for part in re.findall(r'.*?(?:[。！？；\n]+|$)', text or '', re.S) if part]


def bind_calculation_sources(content, review):
    for question in review.question_checks:
        if not 0 <= question.question_index < len(content['questions']):
            raise ValueError('numeric_question_index_out_of_range')
        source = content['questions'][question.question_index]
        for check in question.calculation_checks:
            if check.start_segment is None and check.end_segment is None:
                continue  # Read historical literal-bound receipts.
            segments = source_segments(source.get(check.source_field))
            if (check.start_segment is None or check.end_segment is None or
                    not 0 <= check.start_segment <= check.end_segment < len(segments)):
                raise ValueError(f'numeric_source_span_invalid: question_index={question.question_index}, source_field={check.source_field}')
            excerpt = ''.join(segments[check.start_segment:check.end_segment + 1])
            if len(excerpt) > 4000:
                raise ValueError('numeric_source_span_too_large')
            check.excerpt = excerpt
    return review


def softmax(values):
    if not isinstance(values, list) or not values or any(isinstance(v, list) for v in values):
        raise ValueError('softmax expects one nonempty vector')
    exponentials = [math.exp(v - max(values)) for v in values]
    return [v / sum(exponentials) for v in exponentials]


def transpose(matrix):
    if not matrix or not all(isinstance(row, list) and len(row) == len(matrix[0]) for row in matrix):
        raise ValueError('expected rectangular matrix')
    return [list(row) for row in zip(*matrix)]


def matmul(left, right):
    columns = transpose(right)
    if not left or any(not isinstance(row, list) or len(row) != len(right) for row in left):
        raise ValueError('matrix dimensions do not match')
    return [[sum(x * y for x, y in zip(row, col)) for col in columns] for row in left]


def _binary(left, right, operation):
    if isinstance(left, list) or isinstance(right, list):
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                raise ValueError('shape mismatch')
            return [_binary(a, b, operation) for a, b in zip(left, right)]
        return [_binary(a, right, operation) for a in left] if isinstance(left, list) else [_binary(left, b, operation) for b in right]
    if not math.isfinite(left) or not math.isfinite(right):
        raise ValueError('nonfinite input')
    return operation(left, right)


def calculate(expression):
    if len(expression) > 4000:
        raise ValueError('expression too large')
    tree = ast.parse(expression, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 512:
        raise ValueError('expression too complex')
    def visit(node, depth=0):
        if depth > 24:
            raise ValueError('expression too deep')
        rec = lambda child: visit(child, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError('number out of bounds')
            return value
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= 64:
            return [rec(child) for child in node.elts]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return _binary(0, rec(node.operand), (lambda a, b: -b) if isinstance(node.op, ast.USub) else (lambda a, b: b))
        if isinstance(node, ast.BinOp):
            operations = {ast.Add: lambda a,b:a+b, ast.Sub:lambda a,b:a-b,
                          ast.Mult:lambda a,b:a*b, ast.Div:lambda a,b:a/b}
            if type(node.op) in operations:
                return _binary(rec(node.left), rec(node.right), operations[type(node.op)])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            functions = {'softmax':softmax, 'matmul':matmul, 'transpose':transpose,
                         'sqrt':math.sqrt, 'exp':math.exp, 'log':math.log, 'sum':sum,
                         'weighted_sum':lambda weights, values:matmul([weights], values)[0]}
            if node.func.id in functions:
                return functions[node.func.id](*[rec(arg) for arg in node.args])
        raise ValueError('unsupported arithmetic; only numbers, vectors, matrices and approved functions are allowed')
    value = visit(tree.body)
    def finite(v):
        if isinstance(v, list):
            for item in v: finite(item)
        elif not math.isfinite(v):
            raise ValueError('nonfinite result')
    finite(value)
    return value


def matches(actual, claimed, places):
    if isinstance(actual, list) or isinstance(claimed, list):
        return (isinstance(actual, list) and isinstance(claimed, list) and len(actual) == len(claimed)
                and all(matches(a,b,places) for a,b in zip(actual, claimed)))
    # Compare against full precision, not a previously rounded intermediate.
    return abs(actual - claimed) <= .5 * 10 ** (-places) + 4 * max(math.ulp(actual), math.ulp(claimed))


def verify_calculations(question, checks):
    evidence, errors = [], []
    for check in checks:
        row = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        if not row['excerpt'] or row['excerpt'] not in str(question.get(row['source_field']) or ''):
            raise ValueError('numeric_claim_excerpt_mismatch')
        try:
            actual = calculate(row['expression'])
            literal = ast.parse(row['claimed'], mode='eval')
            if any(not isinstance(node, (ast.Expression, ast.Constant, ast.List, ast.Tuple, ast.UnaryOp, ast.UAdd, ast.USub, ast.Load)) for node in ast.walk(literal)):
                raise ValueError('claimed must contain literal numbers, not computed expressions')
            claimed = calculate(row['claimed'])
            numbers = r'(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])'
            literal_numbers = [Decimal(v) for v in re.findall(numbers, row['claimed'])]
            if len(literal_numbers) != sum(isinstance(node, ast.Constant) for node in ast.walk(literal)):
                raise ValueError('claimed must use ordinary decimal notation')
            source_numbers = {Decimal(v) for v in re.findall(numbers, row['excerpt'].replace('−', '-'))}
            if any(value not in source_numbers for value in literal_numbers):
                raise ValueError('claimed numbers must occur in the quoted source; do not substitute a corrected value')
            displayed_places = max((max(0, -value.as_tuple().exponent) for value in literal_numbers), default=0)
            places = max(row['decimal_places'], min(20, displayed_places))
            passed = matches(actual, claimed, places)
            evidence.append({**row, 'computed':actual, 'status':'pass' if passed else 'fail'})
            if not passed:
                errors.append(f"数值不符：{row['excerpt']}；{row['expression']} = {actual}，原文声称 {claimed}")
        except (ValueError, SyntaxError, TypeError, ArithmeticError, RecursionError) as exc:
            evidence.append({**row, 'status':'unverified', 'reason':str(exc)})
            errors.append(f"数值断言无法复算：{row['excerpt']}；请提供受支持的算式或明确其验证限制")
    # Exact, self-contained softmax claims also get checked without relying on
    # the reviewer's extraction. This is deliberately a narrow grammar.
    pattern = re.compile(r'(?:softmax\s*\(\s*\[([^\]]+)\]\s*\)\s*(?:≈|=|为|得到)\s*\[([^\]]+)\]|'
                         r'对\s*([\d.,，、\s-]+)\s*做\s*softmax\s*会得到\s*([\d.、，,\s-]+))', re.I)
    for field in ('answer', 'explanation'):
        source = str(question.get(field) or '')
        for match in pattern.finditer(source):
            if re.search(r'(?:错误(?:示例|写法)?|误写(?:为)?|不能写成|并非|不是)[：:\s“\"「]*$', source[max(0, match.start()-24):match.start()]):
                continue
            left, right = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
            try:
                inputs = [float(x) for x in re.split(r'[,，、]\s*', left.strip())]
                parts = re.split(r'[,，、]\s*', right.strip().rstrip('，,、'))
                claimed = [float(x) for x in parts]
                if len(inputs) != len(claimed) or len(inputs) > 64: continue
                places = min(len(x.strip().partition('.')[2]) for x in parts)
                actual = softmax(inputs)
                passed = matches(actual, claimed, places)
                evidence.append({'source_field':field, 'excerpt':match.group(), 'computed':actual,
                                 'status':'pass' if passed else 'fail', 'method':'literal_softmax'})
                if not passed: errors.append(f'解析中的 softmax 数值错误：{match.group()}；复算为 {actual}')
            except (ValueError, ArithmeticError):
                continue
    return evidence, errors
