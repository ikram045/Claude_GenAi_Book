from parse_response import ModelResponse, parse

VALID = '{"answer": "42", "confidence": 0.87, "sources": [{"doc": "a.pdf", "page": 3}]}'


def test_parses_valid():
    r = parse(VALID)
    assert isinstance(r, ModelResponse)
    assert r.answer == "42"
    assert r.confidence == 0.87
    assert r.sources[0].doc == "a.pdf"


def test_coerces_numeric_strings():
    raw = '{"answer": "42", "confidence": "0.5", "sources": [{"doc": "a.pdf", "page": "3"}]}'
    r = parse(raw)
    assert r is not None
    assert r.confidence == 0.5
    assert r.sources[0].page == 3


def test_rejects_confidence_above_one():
    raw = '{"answer": "x", "confidence": 1.5, "sources": [{"doc": "a.pdf", "page": 1}]}'
    assert parse(raw) is None


def test_rejects_negative_confidence():
    raw = '{"answer": "x", "confidence": -0.1, "sources": [{"doc": "a.pdf", "page": 1}]}'
    assert parse(raw) is None


def test_rejects_empty_sources():
    raw = '{"answer": "x", "confidence": 0.5, "sources": []}'
    assert parse(raw) is None


def test_rejects_page_zero():
    raw = '{"answer": "x", "confidence": 0.5, "sources": [{"doc": "a.pdf", "page": 0}]}'
    assert parse(raw) is None


def test_rejects_missing_field():
    assert parse('{"answer": "x", "confidence": 0.5}') is None


def test_rejects_broken_json():
    assert parse("not json at all {{{") is None


def test_rejects_wrong_type():
    raw = '{"answer": "x", "confidence": "high", "sources": [{"doc": "a.pdf", "page": 1}]}'
    assert parse(raw) is None
