import pytest

from cogs.Tracking import AddManhwaComick


@pytest.mark.parametrize("chapter, expected", [
    (10.0, "10"),
    (10.5, "10.5"),
    (0.0, "0"),
    (999.0, "999"),
    ("12", "12"),
    ("12.5", "12.5"),
])
def test_format_chapter_number(chapter, expected):
    assert AddManhwaComick.format_chapter_number(chapter) == expected


def test_format_chapter_number_handles_none_without_crashing():
    assert AddManhwaComick.format_chapter_number(None) == "None"
