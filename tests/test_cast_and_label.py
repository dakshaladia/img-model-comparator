"""Unit tests for _cast_value and _make_label in routes/sweep.py."""

from routes.sweep import _cast_value, _make_label


# ── _cast_value ──────────────────────────────────────────────────────

def test_cast_integer():
    assert _cast_value("42", "integer") == 42
    assert _cast_value("0", "integer") == 0
    assert _cast_value("-1", "integer") == -1


def test_cast_number():
    assert _cast_value("3.14", "number") == 3.14
    assert _cast_value("0.0", "number") == 0.0
    assert _cast_value("100", "number") == 100.0


def test_cast_boolean():
    assert _cast_value("true", "boolean") is True
    assert _cast_value("True", "boolean") is True
    assert _cast_value("TRUE", "boolean") is True
    assert _cast_value("false", "boolean") is False
    assert _cast_value("anything", "boolean") is False


def test_cast_string():
    assert _cast_value("hello world", "string") == "hello world"
    assert _cast_value("", "string") == ""


def test_cast_unknown_type_returns_string():
    assert _cast_value("foo", "unknown") == "foo"


# ── _make_label ──────────────────────────────────────────────────────

def test_label_short():
    assert _make_label("seed", 42) == "seed=42"
    assert _make_label("cfg", 3.5) == "cfg=3.5"


def test_label_exact_60():
    # "x=" + 58 chars = 60 total
    val = "a" * 58
    label = _make_label("x", val)
    assert len(label) == 60
    assert "..." not in label


def test_label_truncated():
    val = "a" * 70
    label = _make_label("prompt", val)
    assert len(label) == 60
    assert label.endswith("...")


def test_label_prompt_long():
    long_prompt = "a very detailed scene of a cat sitting on an ornate windowsill in paris at golden hour"
    label = _make_label("prompt", long_prompt)
    assert len(label) <= 60
    assert label.endswith("...")
