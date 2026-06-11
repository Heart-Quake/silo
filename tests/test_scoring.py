"""
Tests du scoring qualite SILO.
"""
import pandas as pd

from src.scoring import (
    OUTPUT_COLUMNS,
    assess_technical_metadata,
    classify_page_type,
    enrich_opportunities_dataframe,
    position_opportunity_score,
)


def test_position_opportunity_score_prioritizes_positions_4_to_20():
    """Les positions proches du gain SEO doivent etre favorisees."""
    assert position_opportunity_score(6) > position_opportunity_score(2)
    assert position_opportunity_score(12) > position_opportunity_score(35)


def test_classify_page_type_detects_core_url_patterns():
    """La typologie doit couvrir les familles SEO principales."""
    assert classify_page_type("https://example.com/blog/comment-choisir") == "editorial"
    assert classify_page_type("https://example.com/creche/paris") == "local"
    assert classify_page_type("https://example.com/demande-simulation/credit") == "tool"
    assert classify_page_type("https://example.com/mutuelle-professionnelle") == "business"


def test_assess_technical_metadata_excludes_non_indexable_cases():
    """Les URLs non indexables ne doivent pas rester eligibles."""
    assert assess_technical_metadata("https://example.com/a", {"status_code": 301})[0] == "Excluded"
    assert assess_technical_metadata(
        "https://example.com/a",
        {"status_code": 200, "indexability": "Non-Indexable"},
    )[0] == "Excluded"
    assert assess_technical_metadata(
        "https://example.com/a",
        {"status_code": 200, "indexability": "Indexable", "meta_robots": "noindex,follow"},
    )[0] == "Excluded"
    assert assess_technical_metadata(
        "https://example.com/a",
        {"status_code": 200, "indexability": "Indexable", "canonical": "https://example.com/b"},
    )[0] == "Excluded"
    assert assess_technical_metadata(
        "https://example.com/a",
        {"status_code": 200, "indexability": "Indexable", "canonical": "Self Referencing"},
    )[0] == "Eligible"


def test_enrich_opportunities_dataframe_adds_quality_columns_and_priority_trace():
    """Le scoring doit ajouter les colonnes visibles/exportables."""
    opportunities = pd.DataFrame(
        {
            "Score": [50],
            "Keyword_GSC": ["formation seo"],
            "Suggested_Anchor": ["formation SEO"],
            "Anchor_Context": ["Cette formation SEO permet de structurer une strategie de contenu durable."],
            "Source_URL": ["https://example.com/blog/guide"],
            "Target_URL": ["https://example.com/services/formation-seo"],
            "Clicks": [30],
            "Impressions": [1000],
            "Position": [8.0],
        }
    )

    enriched = enrich_opportunities_dataframe(
        opportunities,
        crawl_metadata={
            "https://example.com/blog/guide": {"status_code": 200, "indexability": "Indexable"},
            "https://example.com/services/formation-seo": {"status_code": 200, "indexability": "Indexable"},
        },
        priority_target_urls={"https://example.com/services/formation-seo"},
    )

    assert all(column in enriched.columns for column in OUTPUT_COLUMNS)
    assert enriched.loc[0, "Priority_Target"] == "Yes"
    assert enriched.loc[0, "Technical_Status"] == "Eligible"
    assert enriched.loc[0, "Final_Score"] > 0
    assert "cible prioritaire GSC" in enriched.loc[0, "Decision_Reason"]


def test_output_columns_do_not_reintroduce_obsolete_fields():
    """L'export metier ne doit pas contenir les anciennes colonnes techniques."""
    obsolete_columns = {"Anchor_Text", "XPath", "Similarity_Type"}

    assert not obsolete_columns & set(OUTPUT_COLUMNS)
