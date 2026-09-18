from app.course_preparation.citation_locator import locate_quote


def test_markdown_quote_maps_back_to_verbatim_original_span():
    source = 'This exception is derived from [`RuntimeError`](#RuntimeError). It is raised when the limit is exceeded.'
    quote = 'This exception is derived from `RuntimeError`.'
    resolved = locate_quote(source, quote)
    assert resolved == 'This exception is derived from [`RuntimeError`](#RuntimeError).'
    assert resolved in source


def test_no_paraphrase_or_changed_operator_can_be_resolved():
    assert locate_quote('This function returns x * y.', 'This function returns xy.') is None
    assert locate_quote('This returns x ** y ** z.', 'This returns x y z.') is None
    assert locate_quote('This function stops eventually.', 'This function never stops.') is None


def test_whitespace_only_differences_preserve_original_newlines():
    assert locate_quote('The function\nreturns its result.', 'The function returns its result.') == 'The function\nreturns its result.'


def test_ambiguous_normalized_match_is_not_accepted():
    assert locate_quote('The `base case` stops it. The `base case` stops it.', 'The base case stops it.') is None


def test_emphasis_is_presentation_but_omitted_explanations_are_not():
    from app.course_preparation.citation_locator import locate_quote
    source='The model **does not execute** the tool. It only *decides* which tool.'
    assert locate_quote(source,'model does not execute the tool')=='model **does not execute** the tool'
    assert locate_quote(source,'only decides which tool')=='only *decides* which tool'
    assert locate_quote('the description (a concrete example) and schema','the description and schema') is None
    assert locate_quote('a * b * c is multiplication','a b c is multiplication') is None
