from datetime import date

from resume_engine.dates import parse_date_range


def test_parse_date_range_month_year_to_present():
    result = parse_date_range("Acme Corp, Senior Engineer, 2021 - Present")
    assert result is not None
    assert result.start == date(2021, 1, 1)
    assert result.end is None
    assert result.is_current is True
    assert result.display == "2021 - Present"


def test_parse_date_range_month_year_to_month_year():
    result = parse_date_range("Jan 2018 - Mar 2021")
    assert result.start == date(2018, 1, 1)
    assert result.end == date(2021, 3, 1)
    assert result.is_current is False


def test_parse_date_range_bare_years():
    result = parse_date_range("Beta Inc, 2016-2018")
    assert result.start == date(2016, 1, 1)
    assert result.end == date(2018, 1, 1)


def test_parse_date_range_returns_none_when_no_date_range_present():
    assert parse_date_range("No dates here at all") is None


def test_parse_date_range_accepts_word_to_as_separator():
    result = parse_date_range("2021 to Present")
    assert result.is_current is True
    assert result.start == date(2021, 1, 1)


def test_parse_date_range_never_raises_on_garbage():
    # Defensive: must not raise even for adversarial input.
    assert parse_date_range("") is None
    assert parse_date_range("999999999999999999") is None
