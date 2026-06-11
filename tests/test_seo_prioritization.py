"""
Tests de la priorisation SEO ajoutée à SILO.

Ces tests ne chargent pas spaCy : ils protègent la fusion sans ralentir le
pipeline sémantique existant.
"""
import pandas as pd
import pytest

from src.seo_prioritization import (
    PrioritizationConfig,
    build_page_priority,
    identify_priority_targets,
    normalize_gsc_columns,
    summarize_priority_overlap,
)


def test_normalize_gsc_columns_accepts_silo_and_french_names():
    raw_data = pd.DataFrame(
        {
            "URL": ["https://example.com/a"],
            "Requête": ["maillage interne"],
            "Impressions": ["1,200"],
            "Clics": ["42"],
            "Position": ["8,5"],
        }
    )

    normalized = normalize_gsc_columns(raw_data)

    assert list(normalized.columns) == ["Page", "Query", "Impressions", "Clicks", "Position"]
    assert normalized.loc[0, "Page"] == "https://example.com/a"
    assert normalized.loc[0, "Query"] == "maillage interne"
    assert normalized.loc[0, "Impressions"] == 1200
    assert normalized.loc[0, "Clicks"] == 42
    assert normalized.loc[0, "Position"] == 8.5


def test_normalize_gsc_columns_rejects_missing_required_columns():
    raw_data = pd.DataFrame({"Page": ["https://example.com/a"], "Query": ["seo"]})

    with pytest.raises(ValueError, match="Colonnes GSC manquantes"):
        normalize_gsc_columns(raw_data)


def test_build_page_priority_aggregates_query_level_data():
    raw_data = pd.DataFrame(
        {
            "Page": ["https://example.com/a", "https://example.com/a", "https://example.com/b"],
            "Query": ["seo", "audit seo", "maillage"],
            "Impressions": [1000, 500, 200],
            "Clicks": [50, 30, 10],
            "Position": [8.0, 10.0, 4.0],
        }
    )

    priority = build_page_priority(raw_data)
    page_a = priority[priority["Page"] == "https://example.com/a"].iloc[0]

    assert page_a["Impressions"] == 1500
    assert page_a["Clicks"] == 80
    assert page_a["Query_Count"] == 2
    assert page_a["Top_Query"] == "seo"
    assert page_a["Opportunity_Score"] > 0


def test_identify_priority_targets_applies_position_and_volume_thresholds():
    raw_data = pd.DataFrame(
        {
            "Page": [
                "https://example.com/strong-target",
                "https://example.com/too-high",
                "https://example.com/too-low-volume",
            ],
            "Query": ["seo", "marque", "longue traine"],
            "Impressions": [2000, 3000, 50],
            "Clicks": [120, 600, 1],
            "Position": [8.0, 2.0, 12.0],
        }
    )
    config = PrioritizationConfig(position_min=5, position_max=20, impressions_percentile=50, min_impressions=100)

    targets = identify_priority_targets(raw_data, config)

    assert targets["Page"].tolist() == ["https://example.com/strong-target"]


def test_summarize_priority_overlap_counts_covered_and_uncovered_targets():
    opportunities = pd.DataFrame(
        {
            "Source_URL": ["https://example.com/source"],
            "Target_URL": ["https://example.com/a"],
        }
    )
    priority_targets = pd.DataFrame(
        {
            "Page": ["https://example.com/a", "https://example.com/b"],
            "Opportunity_Score": [100.0, 80.0],
        }
    )

    summary = summarize_priority_overlap(opportunities, priority_targets)

    assert summary == {
        "priority_targets": 2,
        "covered_targets": 1,
        "uncovered_targets": 1,
    }
