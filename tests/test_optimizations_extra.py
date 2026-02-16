import pytest
from src.nlp_matcher import NLPMatcher

def test_fuzzy_lemma_matching():
    matcher = NLPMatcher()
    
    # Test with minor variations or typos that should be caught by fuzzy
    # "optimisation" vs "optimiser" (though spaCy should catch these via lemmatization, 
    # let's test something more subtle or plural variants if not Caught)
    
    # spaCy lemmes: 
    # "SEO" -> "seo"
    # "optimisation" -> "optimisation"
    
    # Case: "référencement" vs "referencement" (accent missing)
    k1 = "référencement"
    t1 = "Le referencement est important."
    
    keyword_lemmes = matcher._lemmatize_keyword(k1)
    text_lemmes = matcher._lemmatize_text(t1)
    
    print(f"Keyword lemmes: {keyword_lemmes}")
    print(f"Text lemmes: {text_lemmes}")
    
    if keyword_lemmes and text_lemmes:
        l1 = keyword_lemmes[0]
        l2 = text_lemmes[0][0]
        import difflib
        ratio = difflib.SequenceMatcher(None, l1, l2).ratio()
        print(f"Ratio: {ratio}")

    matches = matcher.find_matches(t1, k1)
    assert len(matches) > 0, f"Should find match. Ratio was {ratio if 'ratio' in locals() else 'N/A'}"

def test_fuzzy_lemma_similarity_threshold():
    matcher_strict = NLPMatcher(min_similarity=0.99)
    matcher_loose = NLPMatcher(min_similarity=0.7)
    
    keyword = "digitalisation"
    text = "La digitalisasion du marché." # Typo: s instead of t
    
    assert len(matcher_strict.find_matches(text, keyword)) == 0
    assert len(matcher_loose.find_matches(text, keyword)) > 0

def test_multiprocessing_prep():
    # Verify we can prepare patterns in batch
    matcher = NLPMatcher()
    keywords = ["maillage interne", "seo technique", "backlinks"]
    patterns = matcher.prepare_keyword_patterns(keywords)
    assert len(patterns) == 3
    assert "maillage interne" in patterns
