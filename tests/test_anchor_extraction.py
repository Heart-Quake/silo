"""
Tests de distinction entre ancre, extrait court et contexte.
"""
from src.silo_linker import (
    _extract_anchor_context_static,
    _extract_anchor_text_static,
    _extract_suggested_anchor_static,
)


def test_extract_suggested_anchor_returns_exact_match_text():
    paragraph = "Le maillage interne permet de renforcer une page stratégique."
    start = paragraph.index("maillage interne")
    end = start + len("maillage interne")

    anchor = _extract_suggested_anchor_static(paragraph, (start, end, "maillage interne"), "fallback")

    assert anchor == "maillage interne"


def test_extract_suggested_anchor_keeps_real_text_variant():
    paragraph = "Les chevaux de course sont rapides."
    start = paragraph.index("chevaux de course")
    end = start + len("chevaux de course")

    anchor = _extract_suggested_anchor_static(paragraph, (start, end, "chevaux de course"), "cheval de course")

    assert anchor == "chevaux de course"


def test_extract_suggested_anchor_falls_back_to_keyword_when_match_is_invalid():
    paragraph = "Le maillage interne permet de renforcer une page stratégique."

    anchor = _extract_suggested_anchor_static(paragraph, (1000, 2000, ""), "maillage interne")

    assert anchor == "maillage interne"


def test_extract_anchor_context_keeps_surrounding_text():
    paragraph = "Le maillage interne permet de renforcer une page stratégique."
    start = paragraph.index("maillage interne")
    end = start + len("maillage interne")

    context = _extract_anchor_context_static(paragraph, (start, end, "maillage interne"))

    assert "maillage interne" in context
    assert len(context) > len("maillage interne")


def test_legacy_extract_anchor_text_now_returns_exact_anchor():
    paragraph = "Le maillage interne permet de renforcer une page stratégique."
    start = paragraph.index("maillage interne")
    end = start + len("maillage interne")

    anchor = _extract_anchor_text_static(paragraph, (start, end, "maillage interne"))

    assert anchor == "maillage interne"
