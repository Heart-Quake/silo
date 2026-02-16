
import pytest
import re
import pandas as pd
from unittest.mock import MagicMock
from src.silo_linker import process_single_file
# Access the module to set global worker mocks
import src.silo_linker as silo_module

class MockNLPMatcher:
    def _lemmatize_text(self, text):
        return [t.lower() for t in text.split()]
    
    def find_matches_optimized(self, p_lemmes, p_doc, k_lemmes, p_text):
        # Always return a match for "seo" if present, just for testing logic
        if "seo" in p_text.lower():
            return [(0, 3, "SEO")]
        return []

class MockNLP:
    def __call__(self, text):
        return MagicMock()

@pytest.fixture
def setup_worker_mocks():
    # Setup global mocks for the worker environment
    silo_module.worker_matcher = MockNLPMatcher()
    silo_module.worker_nlp = MockNLP()
    yield
    # Cleanup
    silo_module.worker_matcher = None
    silo_module.worker_nlp = None

def test_anti_cannibalization_prevents_duplicate_link(setup_worker_mocks):
    """
    Verify that if a Source Page ALLREADY links to Target Page, 
    we successfully filter out any new opportunity for that Target Page.
    """
    
    source_url = "https://example.com/source"
    target_url = "https://example.com/target"
    
    # HTML contains a link to the target already
    # AND a paragraph with valid keywords for that target
    html_content = f"""
    <html>
        <body>
            <main>
                <p>Nous faisons du SEO de qualité.</p>
                <a href="{target_url}">Lien existant vers target</a>
            </main>
        </body>
    </html>
    """
    
    # Setup configuration
    keywords_dict = {
        target_url: ["seo"]
    }
    
    # Regex pre-filter will find "seo"
    regex_patterns = {
        target_url: re.compile(r"(?i)(seo)")
    }
    
    keyword_patterns = {
        "seo": ["seo"]
    }
    
    gsc_data = pd.DataFrame() # Score calc might fail or return 0, but we care about list empty
    
    # Run process
    opportunities = process_single_file(
        args=(source_url, html_content),
        keywords_dict=keywords_dict,
        keyword_patterns=keyword_patterns,
        regex_patterns=regex_patterns,
        gsc_data=gsc_data
    )
    
    # Assertions
    # Should be EMPTY because the link exists
    assert len(opportunities) == 0, "Should handle anti-cannibalization (link exists)"
    
    
def test_anti_cannibalization_allows_new_link(setup_worker_mocks):
    """
    Verify that if a Source Page DOES NOT link to Target Page, 
    we allow the opportunity.
    """
    
    source_url = "https://example.com/source"
    target_url = "https://example.com/target"
    other_url = "https://example.com/other"
    
    # HTML contains link to OTHER only
    html_content = f"""
    <html>
        <body>
            <main>
                <p>Nous faisons du SEO de qualité.</p>
                <a href="{other_url}">Lien vers autre</a>
            </main>
        </body>
    </html>
    """
    
    # Setup configuration matches above
    keywords_dict = {
        target_url: ["seo"]
    }
    regex_patterns = {
        target_url: re.compile(r"(?i)(seo)")
    }
    keyword_patterns = {"seo": ["seo"]}
    gsc_data = pd.DataFrame({'Page': [target_url], 'Query': ['seo'], 'Clicks': [100], 'Position': [1]})

    
    # Run process
    opportunities = process_single_file(
        args=(source_url, html_content),
        keywords_dict=keywords_dict,
        keyword_patterns=keyword_patterns,
        regex_patterns=regex_patterns,
        gsc_data=gsc_data
    )
    
    # Assertions
    # Should HAVE opportunity
    assert len(opportunities) > 0, "Should find opportunity when no link exists"
    assert opportunities[0]['Target_URL'] == target_url

