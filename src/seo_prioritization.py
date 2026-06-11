"""
Priorisation SEO complémentaire pour SILO.

Ce module reste volontairement isolé du pipeline NLP : il analyse les données
GSC pour identifier les pages cibles avec le meilleur potentiel de gain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class PrioritizationConfig:
    """Paramètres métier pour qualifier les pages cibles prioritaires."""

    position_min: float = 5.0
    position_max: float = 20.0
    impressions_percentile: float = 80.0
    min_impressions: int = 100


def normalize_gsc_columns(gsc_data: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise les colonnes GSC sans modifier le DataFrame d'origine.

    SILO travaille avec Page/Query/Clicks, tandis que d'autres exports peuvent
    utiliser URL/Requete/Clics. Cette fonction accepte les deux familles.
    """
    column_aliases = {
        "URL": "Page",
        "Url": "Page",
        "page": "Page",
        "Query": "Query",
        "Requete": "Query",
        "Requête": "Query",
        "requete": "Query",
        "Impressions": "Impressions",
        "impressions": "Impressions",
        "Clicks": "Clicks",
        "Clics": "Clicks",
        "clicks": "Clicks",
        "Position": "Position",
        "position": "Position",
        "CTR": "CTR",
        "ctr": "CTR",
    }

    normalized = gsc_data.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    normalized = normalized.rename(columns={column: column_aliases.get(column, column) for column in normalized.columns})

    required_columns = {"Page", "Query", "Impressions", "Clicks", "Position"}
    missing_columns = sorted(required_columns - set(normalized.columns))
    if missing_columns:
        raise ValueError(f"Colonnes GSC manquantes pour la priorisation : {', '.join(missing_columns)}")

    normalized["Page"] = normalized["Page"].astype(str).str.strip()
    normalized["Query"] = normalized["Query"].astype(str).str.strip()

    for column in ("Impressions", "Clicks", "Position"):
        normalized[column] = (
            normalized[column]
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace("%", "", regex=False)
        )
        if column == "Position":
            normalized[column] = normalized[column].str.replace(",", ".", regex=False)
        else:
            normalized[column] = normalized[column].str.replace(",", "", regex=False)
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=["Page", "Query", "Impressions", "Clicks", "Position"])
    normalized = normalized[normalized["Page"].str.len() > 0]
    normalized = normalized[normalized["Query"].str.len() > 0]

    return normalized


def build_page_priority(gsc_data: pd.DataFrame) -> pd.DataFrame:
    """
    Agrège la GSC query-level en priorités par page.

    Le score combine volume, position moyenne et clics. Il ne remplace pas le
    score SILO : il sert à expliquer quelles cibles méritent le plus d'attention.
    """
    normalized = normalize_gsc_columns(gsc_data)
    if normalized.empty:
        return pd.DataFrame(
            columns=[
                "Page",
                "Top_Query",
                "Impressions",
                "Clicks",
                "Position",
                "Query_Count",
                "Opportunity_Score",
            ]
        )

    sorted_queries = normalized.sort_values(["Page", "Clicks", "Impressions", "Position"], ascending=[True, False, False, True])
    top_queries = sorted_queries.drop_duplicates(subset=["Page"], keep="first")[["Page", "Query"]]
    top_queries = top_queries.rename(columns={"Query": "Top_Query"})

    grouped = (
        normalized.groupby("Page", as_index=False)
        .agg(
            Impressions=("Impressions", "sum"),
            Clicks=("Clicks", "sum"),
            Position=("Position", "mean"),
            Query_Count=("Query", "nunique"),
        )
        .merge(top_queries, on="Page", how="left")
    )

    grouped["Potential_Gap"] = grouped["Position"].clip(lower=1.0)
    grouped["Opportunity_Score"] = (
        (grouped["Impressions"] / grouped["Potential_Gap"])
        * (1 + grouped["Query_Count"] / 10)
        * (1 + grouped["Clicks"] / grouped["Impressions"].replace(0, pd.NA).fillna(1))
    )

    return grouped.sort_values("Opportunity_Score", ascending=False).reset_index(drop=True)


def identify_priority_targets(
    gsc_data: pd.DataFrame,
    config: Optional[PrioritizationConfig] = None,
) -> pd.DataFrame:
    """
    Filtre les pages cibles à potentiel selon les seuils SEO.

    Par défaut, on cible les positions 5 à 20 avec un volume d'impressions élevé,
    ce qui correspond aux pages proches du gain mais pas encore dominantes.
    """
    selected_config = config or PrioritizationConfig()
    page_priority = build_page_priority(gsc_data)
    if page_priority.empty:
        return page_priority

    position_mask = page_priority["Position"].between(
        selected_config.position_min,
        selected_config.position_max,
        inclusive="both",
    )
    eligible_pages = page_priority[position_mask].copy()
    if eligible_pages.empty:
        return eligible_pages

    percentile_threshold = eligible_pages["Impressions"].quantile(selected_config.impressions_percentile / 100)
    impression_threshold = max(float(percentile_threshold), float(selected_config.min_impressions))

    priority_targets = eligible_pages[eligible_pages["Impressions"] >= impression_threshold].copy()
    return priority_targets.sort_values("Opportunity_Score", ascending=False).reset_index(drop=True)


def summarize_priority_overlap(opportunities: pd.DataFrame, priority_targets: pd.DataFrame) -> Dict[str, int]:
    """
    Résume la couverture des cibles prioritaires par les opportunités SILO.
    """
    if opportunities.empty or priority_targets.empty:
        return {
            "priority_targets": int(len(priority_targets)),
            "covered_targets": 0,
            "uncovered_targets": int(len(priority_targets)),
        }

    covered_targets = set(opportunities.get("Target_URL", pd.Series(dtype=str)).dropna().astype(str))
    priority_pages = set(priority_targets["Page"].dropna().astype(str))
    covered_priority_pages = priority_pages & covered_targets

    return {
        "priority_targets": int(len(priority_pages)),
        "covered_targets": int(len(covered_priority_pages)),
        "uncovered_targets": int(len(priority_pages - covered_priority_pages)),
    }
