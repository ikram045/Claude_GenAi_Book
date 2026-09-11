from word_frequency import top_words


def test_basic():
    assert top_words("the cat and the dog and the cat", n=2) == [("cat", 2), ("dog", 1)]


def test_case_insensitive():
    result = dict(top_words("Cat cat CAT", n=1))
    assert result == {"cat": 3}


def test_strips_punctuation():
    result = dict(top_words("cat, cat. cat!", n=1))
    assert result == {"cat": 3}


def test_ignores_stopwords():
    words = [w for w, _ in top_words("the the the dog", n=5)]
    assert "the" not in words
    assert "dog" in words


def test_empty_text():
    assert top_words("", n=3) == []


def test_n_larger_than_vocabulary():
    assert len(top_words("cat dog", n=10)) == 2
