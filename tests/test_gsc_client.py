"""
Tests du client Google Search Console.

Les tests évitent tout appel réseau et toute authentification réelle.
"""
from src.gsc_client import build_dimension_filters, rows_to_dataframe


def test_rows_to_dataframe_converts_search_analytics_rows_to_silo_format():
    rows = [
        {
            "keys": ["https://example.com/page", "maillage interne"],
            "clicks": 12,
            "impressions": 340,
            "position": 7.4,
        }
    ]

    dataframe = rows_to_dataframe(rows)

    assert dataframe.to_dict("records") == [
        {
            "Page": "https://example.com/page",
            "Query": "maillage interne",
            "Impressions": 340,
            "Clicks": 12,
            "Position": 7.4,
        }
    ]


def test_rows_to_dataframe_drops_incomplete_rows():
    rows = [
        {"keys": ["https://example.com/page", ""], "clicks": 1, "impressions": 10, "position": 2.0},
        {"keys": ["", "seo"], "clicks": 1, "impressions": 10, "position": 2.0},
        {"keys": ["https://example.com/valid", "seo"], "clicks": 1, "impressions": 10, "position": 2.0},
    ]

    dataframe = rows_to_dataframe(rows)

    assert dataframe["Page"].tolist() == ["https://example.com/valid"]
    assert dataframe["Query"].tolist() == ["seo"]


def test_build_dimension_filters_normalizes_country_and_device():
    filters = build_dimension_filters(country="FR", device="mobile")

    assert filters == [
        {"dimension": "country", "operator": "equals", "expression": "fra"},
        {"dimension": "device", "operator": "equals", "expression": "MOBILE"},
    ]


def test_build_dimension_filters_ignores_empty_device():
    filters = build_dimension_filters(country="", device="Tous")

    assert filters == []
