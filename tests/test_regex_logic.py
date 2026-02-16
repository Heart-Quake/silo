import re
from src.silo_linker import SILOLinker

def test_regex_compilation():
    # Mock SILOLinker (we just need the method, which is an instance method but uses no state)
    # Actually it uses no self state so we can call it if we instantiate or refactor.
    # It is an instance method in the refactored code.
    
    linker = SILOLinker("gsc.csv", "test.zip")
    
    keywords_dict = {
        "url1": ["seo", "backlinks", "audit technique"],
        "url2": ["marketing", "inbound"]
    }
    
    patterns = linker._compile_regex_patterns(keywords_dict)
    
    assert len(patterns) == 2
    assert "url1" in patterns
    assert "url2" in patterns
    
    # Test matching
    p1 = patterns["url1"]
    assert p1.search("un audit technique complet")
    assert p1.search("faire du seo")
    assert not p1.search("faire du marketing") # Should be false for url1 pattern
    
    # Test case insensitivity
    assert p1.search("SEO")

    print("\n✅ Regex Compilation Logic Verified")

if __name__ == "__main__":
    test_regex_compilation()
