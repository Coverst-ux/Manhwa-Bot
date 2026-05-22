import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.Tracking import AddManhwaComick

def test_whole_number():
    assert AddManhwaComick.format_chapter_number(10.0) == "10"

def test_decimal_number():
    assert AddManhwaComick.format_chapter_number(10.5) == "10.5"

def test_zero():
    assert AddManhwaComick.format_chapter_number(0.0) == "0"

def test_large_number():
    assert AddManhwaComick.format_chapter_number(999.0) == "999"

def test_invalid_input():
    assert AddManhwaComick.format_chapter_number(None) == "None"