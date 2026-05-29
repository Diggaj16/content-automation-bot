# tests/agents/creation/test_finance_flags.py
"""Tests for finance_flags.detect_finance_flags."""
from app.agents.creation.finance_flags import detect_finance_flags


def test_detects_investment_advice():
    text = "You should buy HDFC Bank stocks right now."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "investment_advice" for f in flags)


def test_detects_financial_figure_rupee():
    text = "The company raised ₹500 crore in Series A funding."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "financial_figure" for f in flags)


def test_detects_financial_figure_percentage():
    text = "The stock dropped 12.5% after the quarterly results."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "financial_figure" for f in flags)


def test_detects_regulatory_claim():
    text = "This fund is SEBI approved and regulated."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "regulatory_claim" for f in flags)


def test_no_investment_advice_flag_for_clean_text():
    text = "The Indian economy grew in the last quarter according to government data."
    flags = detect_finance_flags(text)
    assert not any(f.flag_type == "investment_advice" for f in flags)


def test_returns_empty_list_for_empty_text():
    flags = detect_finance_flags("")
    assert flags == []


def test_flag_has_required_fields():
    text = "SEBI announced new regulations for mutual funds yesterday."
    flags = detect_finance_flags(text)
    for flag in flags:
        assert flag.context != ""
        assert flag.content != ""
        assert flag.flag_type in ("investment_advice", "financial_figure", "regulatory_claim", "company_name")


def test_does_not_raise_on_any_input():
    flags = detect_finance_flags("normal text without financial patterns")
    assert isinstance(flags, list)
