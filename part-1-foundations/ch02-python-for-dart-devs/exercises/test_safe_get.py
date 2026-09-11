import pytest

from safe_get import safe_get_eafp, safe_get_lbyl

IMPLS = [safe_get_lbyl, safe_get_eafp]
DATA = {"user": {"profile": {"name": "Ada", "age": 36}, "tags": ["x"]}, "count": 0}


@pytest.mark.parametrize("fn", IMPLS)
def test_simple_path(fn):
    assert fn(DATA, "count") == 0


@pytest.mark.parametrize("fn", IMPLS)
def test_nested_path(fn):
    assert fn(DATA, "user.profile.name") == "Ada"


@pytest.mark.parametrize("fn", IMPLS)
def test_missing_leaf(fn):
    assert fn(DATA, "user.profile.email", "none") == "none"


@pytest.mark.parametrize("fn", IMPLS)
def test_missing_branch(fn):
    assert fn(DATA, "user.settings.theme", "dark") == "dark"


@pytest.mark.parametrize("fn", IMPLS)
def test_path_through_non_dict(fn):
    """'tags' is a list — descending into it must not crash."""
    assert fn(DATA, "user.tags.name", "safe") == "safe"


@pytest.mark.parametrize("fn", IMPLS)
def test_falsy_value_is_returned_not_default(fn):
    """A real 0 must come back as 0, not as the default. Gotcha #4."""
    assert fn(DATA, "count", "MISSING") == 0
