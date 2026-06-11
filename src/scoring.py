"""
Scoring qualite pour les opportunites SILO.

Ce module reste pur et testable : il ne lit aucun fichier et ne depend pas de
Streamlit. Il enrichit les opportunites brutes avec des signaux SEO,
editoriaux et techniques.
"""
import math
import re
from typing import Any, Dict, Iterable, Optional, Set, Tuple
from urllib.parse import urlparse

import pandas as pd


OUTPUT_COLUMNS = [
    "Priority",
    "Final_Score",
    "Risk_Level",
    "Priority_Target",
    "Keyword_GSC",
    "Suggested_Anchor",
    "Anchor_Context",
    "Source_URL",
    "Target_URL",
    "Source_Type",
    "Target_Type",
    "Clicks",
    "Impressions",
    "Position",
    "SEO_Potential_Score",
    "Editorial_Fit_Score",
    "Decision_Reason",
]

DEBUG_COLUMNS = [
    "Score",
    "Technical_Status",
    "Technical_Reason",
    "Technical_Confidence",
    "Context_Snippet",
    "XPath",
    "Similarity_Type",
]


def normalize_url(url: Any) -> str:
    """Normalise legerement une URL pour matcher crawl, GSC et HTML."""
    normalized = str(url or "").strip()
    if normalized.endswith("/index.html"):
        normalized = normalized[:-len("/index.html")]
    if normalized.endswith("/index.php"):
        normalized = normalized[:-len("/index.php")]
    return normalized


def classify_page_type(url: Any) -> str:
    """Classe une URL dans une typologie SEO simple et stable."""
    parsed = urlparse(str(url or ""))
    path = parsed.path.lower()
    query = parsed.query.lower()

    if any(token in path for token in ["/simulateur", "/calculateur", "/outil", "/devis", "/demande-simulation", "/comparateur"]):
        return "tool"
    if any(token in path for token in ["/creche/", "/agence", "/magasin", "/boutique", "/etablissement", "/local"]):
        return "local"
    if "utm_source=gmb" in query or "/gmb" in path:
        return "local"
    if any(token in path for token in ["/blog", "/guide", "/conseils", "/actualite", "/ressource", "/article"]):
        return "editorial"
    if any(token in path for token in ["/service", "/solution", "/offre", "/produit", "/mutuelle", "/credit", "/assurance", "/prevoyance"]):
        return "business"
    if path in {"", "/"}:
        return "business"
    return "other"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convertit une valeur en float sans lever d'exception."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def clamp_score(value: float) -> int:
    """Contraint un score entre 0 et 100."""
    return int(round(max(0.0, min(100.0, value))))


def is_indexability_value_indexable(value: Any) -> bool:
    """Interprete les valeurs Screaming Frog d'indexabilite."""
    if value is None or str(value).strip() == "":
        return True
    normalized = str(value).strip().lower()
    return normalized in {"indexable", "indexable url", "yes", "oui"}


def assess_technical_metadata(url: Any, metadata: Optional[Dict[str, Any]]) -> Tuple[str, int, str]:
    """
    Retourne le statut technique, la confiance et une raison courte.

    Le crawl devient source de verite lorsqu'il existe. Sans crawl, on ne bloque
    pas l'opportunite, mais la confiance technique est plus faible.
    """
    if not metadata:
        return "Unknown", 70, "Crawl absent ou URL non trouvee dans le crawl"

    status_code = safe_float(metadata.get("status_code"), default=0.0)
    if int(status_code) != 200:
        return "Excluded", 0, f"Code HTTP {int(status_code) if status_code else 'inconnu'}"

    if not is_indexability_value_indexable(metadata.get("indexability")):
        return "Excluded", 0, f"Indexability={metadata.get('indexability')}"

    meta_robots = str(metadata.get("meta_robots") or "").lower()
    if "noindex" in meta_robots:
        return "Excluded", 0, "Meta robots noindex"

    canonical = str(metadata.get("canonical") or "").strip()
    if canonical:
        canonical_lower = canonical.lower()
        if canonical_lower in {"self referencing", "self-referencing", "self canonical", "self"}:
            pass
        elif canonical.startswith(("http://", "https://", "/")):
            normalized_url = normalize_url(url).rstrip("/")
            normalized_canonical = normalize_url(canonical).rstrip("/")
            if normalized_canonical and normalized_canonical != normalized_url:
                return "Excluded", 0, "Canonical differente"
        elif "canonicalis" in canonical_lower or "non self" in canonical_lower:
            return "Excluded", 0, "Canonical differente"

    return "Eligible", 100, "200 + indexable"


def is_indexable_crawl_metadata(url: Any, metadata: Optional[Dict[str, Any]]) -> bool:
    """Indique si une URL est eligible au maillage selon les metadonnees crawl."""
    status, _confidence, _reason = assess_technical_metadata(url, metadata)
    return status == "Eligible"


def position_opportunity_score(position: Any) -> int:
    """Score le potentiel lie a la position moyenne GSC."""
    pos = safe_float(position, default=100.0)
    if pos <= 0:
        return 0
    if pos <= 3:
        return 35
    if pos <= 10:
        return clamp_score(100 - ((pos - 4) * 5))
    if pos <= 20:
        return clamp_score(70 - ((pos - 10) * 4))
    if pos <= 50:
        return clamp_score(30 - (pos - 20))
    return 0


def normalized_log_score(value: Any, max_log_value: float) -> int:
    """Normalise une metrique de volume avec une echelle logarithmique."""
    numeric_value = max(0.0, safe_float(value))
    if max_log_value <= 0:
        return 0
    return clamp_score((math.log1p(numeric_value) / max_log_value) * 100)


def calculate_editorial_fit(row: pd.Series) -> int:
    """Score la qualite editoriale de l'ancre et de son contexte."""
    anchor = str(row.get("Suggested_Anchor") or "").strip()
    keyword = str(row.get("Keyword_GSC") or "").strip()
    context = str(row.get("Anchor_Context") or row.get("Context_Snippet") or "").strip()
    legacy_score = safe_float(row.get("Score"), default=0.0)

    anchor_words = [word for word in re.split(r"\s+", anchor) if word]
    if 2 <= len(anchor_words) <= 8:
        anchor_length_score = 100
    elif len(anchor_words) in {1, 9, 10}:
        anchor_length_score = 70
    elif anchor_words:
        anchor_length_score = 35
    else:
        anchor_length_score = 0

    context_length = len(context)
    if context_length >= 80:
        context_score = 100
    elif context_length >= 40:
        context_score = 75
    elif context_length >= 20:
        context_score = 45
    else:
        context_score = 20

    anchor_lower = anchor.lower()
    keyword_lower = keyword.lower()
    if anchor_lower and keyword_lower and (anchor_lower in keyword_lower or keyword_lower in anchor_lower):
        keyword_relation_score = 100
    else:
        anchor_tokens = {token for token in re.findall(r"\w+", anchor_lower) if len(token) > 2}
        keyword_tokens = {token for token in re.findall(r"\w+", keyword_lower) if len(token) > 2}
        overlap = anchor_tokens & keyword_tokens
        denominator = max(1, min(len(anchor_tokens), len(keyword_tokens)))
        keyword_relation_score = 70 if len(overlap) / denominator >= 0.5 else 35

    editorial_score = (
        legacy_score * 0.30
        + anchor_length_score * 0.25
        + context_score * 0.25
        + keyword_relation_score * 0.20
    )
    return clamp_score(editorial_score)


def _lookup_metadata(crawl_metadata: Dict[str, Dict[str, Any]], url: Any) -> Optional[Dict[str, Any]]:
    normalized = normalize_url(url)
    return crawl_metadata.get(normalized) or crawl_metadata.get(normalized.rstrip("/"))


def _has_query_parameters(url: Any) -> bool:
    parsed = urlparse(str(url or ""))
    return bool(parsed.query)


def _risk_rank(risk_level: str) -> int:
    return {"Low": 0, "Medium": 1, "High": 2}.get(risk_level, 0)


def _highest_risk(current: str, candidate: str) -> str:
    return candidate if _risk_rank(candidate) > _risk_rank(current) else current


def enrich_opportunities_dataframe(
    opportunities: pd.DataFrame,
    crawl_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    priority_target_urls: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Ajoute les colonnes de qualite SEO, editoriale et technique."""
    if opportunities is None:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    if opportunities.empty:
        enriched_empty = opportunities.copy()
        for column in OUTPUT_COLUMNS:
            if column not in enriched_empty.columns:
                enriched_empty[column] = pd.Series(dtype="object")
        return enriched_empty

    enriched = opportunities.copy()
    metadata_by_url = crawl_metadata or {}
    priority_urls = _normalize_url_set(priority_target_urls or [])

    for column, default_value in {
        "Suggested_Anchor": "",
        "Anchor_Context": "",
        "Context_Snippet": "",
        "Clicks": 0,
        "Impressions": 0,
        "Position": 100,
        "Score": 0,
    }.items():
        if column not in enriched.columns:
            enriched[column] = default_value

    max_impression_log = math.log1p(max(0.0, safe_float(enriched["Impressions"].max(), default=0.0)))
    max_click_log = math.log1p(max(0.0, safe_float(enriched["Clicks"].max(), default=0.0)))
    source_counts = enriched.groupby("Source_URL")["Target_URL"].transform("count") if "Source_URL" in enriched else pd.Series(1, index=enriched.index)
    anchor_counts = _build_anchor_counts(enriched)

    rows = []
    for index, row in enriched.iterrows():
        target_url = row.get("Target_URL")
        source_url = row.get("Source_URL")
        normalized_target = normalize_url(target_url)
        normalized_source = normalize_url(source_url)
        is_priority_target = normalized_target in priority_urls or normalized_target.rstrip("/") in priority_urls

        target_metadata = _lookup_metadata(metadata_by_url, target_url)
        source_metadata = _lookup_metadata(metadata_by_url, source_url)
        target_status, target_confidence, target_reason = assess_technical_metadata(target_url, target_metadata)
        source_status, source_confidence, source_reason = assess_technical_metadata(source_url, source_metadata)
        technical_confidence = min(target_confidence, source_confidence)
        technical_status = "Eligible" if target_status == "Eligible" and source_status == "Eligible" else "Unknown"
        if target_status == "Excluded" or source_status == "Excluded":
            technical_status = "Excluded"
        technical_reason = _merge_reasons(source_reason, target_reason)

        position_score = position_opportunity_score(row.get("Position"))
        impression_score = normalized_log_score(row.get("Impressions"), max_impression_log)
        click_score = normalized_log_score(row.get("Clicks"), max_click_log)
        priority_score = 100 if is_priority_target else 0
        seo_potential_score = clamp_score(
            position_score * 0.40
            + impression_score * 0.30
            + click_score * 0.20
            + priority_score * 0.10
        )
        editorial_fit_score = calculate_editorial_fit(row)

        risk_level, risk_reasons = assess_risk(
            row=row,
            source_opportunity_count=safe_float(source_counts.loc[index], default=1.0),
            anchor_count=anchor_counts.get(_anchor_count_key(row), 1),
            technical_status=technical_status,
            source_status=source_status,
            target_status=target_status,
        )
        risk_penalty = {"Low": 0, "Medium": 12, "High": 35}.get(risk_level, 0)

        final_score = clamp_score(
            seo_potential_score * 0.45
            + editorial_fit_score * 0.35
            + technical_confidence * 0.20
            - risk_penalty
        )
        if technical_status == "Excluded":
            final_score = 0

        enriched.at[index, "Source_Type"] = classify_page_type(source_url)
        enriched.at[index, "Target_Type"] = classify_page_type(target_url)
        enriched.at[index, "Priority_Target"] = "Yes" if is_priority_target else "No"
        enriched.at[index, "SEO_Potential_Score"] = seo_potential_score
        enriched.at[index, "Editorial_Fit_Score"] = editorial_fit_score
        enriched.at[index, "Technical_Status"] = technical_status
        enriched.at[index, "Technical_Reason"] = technical_reason
        enriched.at[index, "Technical_Confidence"] = technical_confidence
        enriched.at[index, "Risk_Level"] = risk_level
        enriched.at[index, "Final_Score"] = final_score
        enriched.at[index, "Priority"] = calculate_priority(final_score, risk_level)
        enriched.at[index, "Decision_Reason"] = build_decision_reason(
            is_priority_target=is_priority_target,
            seo_score=seo_potential_score,
            editorial_score=editorial_fit_score,
            technical_reason=technical_reason,
            risk_reasons=risk_reasons,
        )

    enriched["Final_Score"] = pd.to_numeric(enriched["Final_Score"], errors="coerce").fillna(0).astype(int)
    enriched["SEO_Potential_Score"] = pd.to_numeric(enriched["SEO_Potential_Score"], errors="coerce").fillna(0).astype(int)
    enriched["Editorial_Fit_Score"] = pd.to_numeric(enriched["Editorial_Fit_Score"], errors="coerce").fillna(0).astype(int)
    enriched["Score"] = enriched["Final_Score"]
    return enriched


def _normalize_url_set(urls: Iterable[str]) -> Set[str]:
    normalized_urls = set()
    for url in urls:
        normalized = normalize_url(url)
        if normalized:
            normalized_urls.add(normalized)
            normalized_urls.add(normalized.rstrip("/"))
    return normalized_urls


def _build_anchor_counts(dataframe: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    if "Target_URL" not in dataframe.columns or "Suggested_Anchor" not in dataframe.columns:
        return {}
    counts = dataframe.groupby(["Target_URL", "Suggested_Anchor"]).size()
    return {tuple(key): int(value) for key, value in counts.items()}


def _anchor_count_key(row: pd.Series) -> Tuple[str, str]:
    return (str(row.get("Target_URL") or ""), str(row.get("Suggested_Anchor") or ""))


def _merge_reasons(source_reason: str, target_reason: str) -> str:
    if source_reason == target_reason:
        return target_reason
    return f"Source: {source_reason}; Cible: {target_reason}"


def assess_risk(
    row: pd.Series,
    source_opportunity_count: float,
    anchor_count: int,
    technical_status: str,
    source_status: str,
    target_status: str,
) -> Tuple[str, Set[str]]:
    """Detecte les risques principaux pour une opportunite."""
    risk_level = "Low"
    reasons = set()

    if technical_status == "Excluded":
        risk_level = _highest_risk(risk_level, "High")
        reasons.add("source ou cible non indexable")

    source_url = normalize_url(row.get("Source_URL")).rstrip("/")
    target_url = normalize_url(row.get("Target_URL")).rstrip("/")
    if source_url and target_url and source_url == target_url:
        risk_level = _highest_risk(risk_level, "High")
        reasons.add("auto-lien source cible")

    if _has_query_parameters(row.get("Target_URL")):
        risk_level = _highest_risk(risk_level, "Medium")
        reasons.add("URL cible avec parametres")

    if anchor_count > 3:
        risk_level = _highest_risk(risk_level, "Medium")
        reasons.add("ancre repetee vers la meme cible")

    if source_opportunity_count > 5:
        risk_level = _highest_risk(risk_level, "Medium")
        reasons.add("nombre eleve de liens proposes sur la source")

    if source_status == "Unknown" or target_status == "Unknown":
        reasons.add("crawl absent ou incomplet")

    return risk_level, reasons


def calculate_priority(final_score: Any, risk_level: str) -> str:
    """Transforme le score final en priorite operationnelle."""
    score = safe_float(final_score)
    if risk_level == "High":
        return "Low"
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def build_decision_reason(
    is_priority_target: bool,
    seo_score: int,
    editorial_score: int,
    technical_reason: str,
    risk_reasons: Set[str],
) -> str:
    """Produit une justification courte exploitable dans l'export."""
    reasons = []
    if is_priority_target:
        reasons.append("cible prioritaire GSC")
    if seo_score >= 70:
        reasons.append("fort potentiel SEO")
    elif seo_score >= 45:
        reasons.append("potentiel SEO moyen")
    else:
        reasons.append("potentiel SEO faible")

    if editorial_score >= 70:
        reasons.append("ancre et contexte solides")
    elif editorial_score >= 45:
        reasons.append("contexte editorial acceptable")
    else:
        reasons.append("contexte editorial faible")

    if technical_reason:
        reasons.append(technical_reason)
    if risk_reasons:
        reasons.append("risque: " + ", ".join(sorted(risk_reasons)))

    return "; ".join(reasons)
