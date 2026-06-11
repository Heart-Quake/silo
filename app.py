"""
Application Streamlit pour SILO (Semantic Internal Link Optimizer).
Interface "Wizard" guidée pour une expérience utilisateur simplifiée.
"""
import hashlib
import json
import traceback
import streamlit as st
import pandas as pd
import tempfile
import os
import shutil
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

# --- CONFIGURATION ---
st.set_page_config(
    page_title="SILO - Maillage Interne",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Imports (afficher l'erreur clairement si échec sur Streamlit Cloud)
try:
    from src.data_loader import DataLoader
    from src.gsc_client import GSCClient, dependencies_available, find_client_secret_path
    from src.parser import ContentParser
    from src.nlp_matcher import NLPMatcher
    from src.seo_prioritization import PrioritizationConfig, identify_priority_targets, summarize_priority_overlap
    from src.silo_linker import SILOLinker
    from src.scoring import DEBUG_COLUMNS, OUTPUT_COLUMNS, enrich_opportunities_dataframe
    import spacy
except Exception as e:
    st.error("Erreur au chargement des modules")
    st.code(traceback.format_exc())
    st.stop()

# --- STYLE CSS (Minimalist / Zen) ---
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .step-header {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #333;
    }
    .block-container {
        padding-top: 5rem;
        max_width: 1000px;
    }
</style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if 'step' not in st.session_state:
    st.session_state.step = 1  # 1: Upload, 2: Analysis, 3: Review, 4: Export
if 'nlp_model' not in st.session_state:
    st.session_state.nlp_model = None
if 'opportunities_df' not in st.session_state:
    st.session_state.opportunities_df = None
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0
if 'gsc_sites' not in st.session_state:
    st.session_state.gsc_sites = []
if 'gsc_import_df' not in st.session_state:
    st.session_state.gsc_import_df = None
if 'gsc_import_meta' not in st.session_state:
    st.session_state.gsc_import_meta = None
if 'crawl_csv_path' not in st.session_state:
    st.session_state.crawl_csv_path = None

EXPORT_COLUMNS = OUTPUT_COLUMNS
REVIEW_COLUMNS = ["Keep"] + EXPORT_COLUMNS
ADVANCED_REVIEW_COLUMNS = REVIEW_COLUMNS + DEBUG_COLUMNS

# --- SIDEBAR & INIT ---
with st.sidebar:
    st.title("🔗 SILO")
    st.caption("Optimisation Sémantique de Maillage Interne")
    
    st.markdown("---")
    
    # Progress du Wizard
    steps = {
        1: "📂 Import Données",
        2: "🚀 Analyse",
        3: "✅ Validation",
        4: "💾 Export"
    }
    
    current_step = st.session_state.step
    for step_num, step_name in steps.items():
        if step_num == current_step:
            st.markdown(f"**👉 {step_name}**")
        elif step_num < current_step:
            st.markdown(f"✅ ~~{step_name}~~")
        else:
            st.markdown(f"⬜ {step_name}")
            
    st.markdown("---")
    
    # Mode Avancé (Toggle)
    zen_mode = not st.checkbox("🔧 Mode Avancé (Debug)", value=False, help="Affiche les outils de test techniques")
    
    # Chargement du modèle NLP (Lazy load)
    if st.session_state.nlp_model is None:
        with st.spinner("Initialisation du moteur NLP..."):
            try:
                # Charger un modèle léger sans NER/parser
                st.session_state.nlp_model = spacy.load("fr_core_news_md", disable=["ner", "parser"])
            except Exception as e:
                st.error(f"Erreur NLP: {e}")

# --- HELPER FUNCTIONS ---
def reset_pipeline():
    st.session_state.step = 1
    st.session_state.opportunities_df = None
    st.session_state.final_df = None
    st.session_state.priority_target_urls = set()
    st.session_state.run_cache_signature = None
    st.session_state.run_cache_key = None
    st.rerun()


def persist_uploaded_file(uploaded_file, suffix: str) -> str:
    """Sauvegarde un upload Streamlit sur disque sans dupliquer son contenu en session."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        uploaded_file.seek(0)
        shutil.copyfileobj(uploaded_file, temp_file)
    finally:
        temp_file.close()
        uploaded_file.seek(0)
    return temp_file.name


def persist_html_zip(uploaded_file) -> str:
    """Sauvegarde et valide l'archive HTML avant de lancer le pipeline."""
    zip_path = persist_uploaded_file(uploaded_file, ".zip")
    if not zipfile.is_zipfile(zip_path):
        Path(zip_path).unlink(missing_ok=True)
        raise ValueError("L'archive HTML importée n'est pas un fichier ZIP valide.")
    return zip_path


def persist_gsc_dataframe(dataframe: pd.DataFrame) -> str:
    """Sauvegarde les données GSC en CSV temporaire pour conserver le pipeline existant."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
    dataframe.to_csv(temp_file.name, index=False)
    temp_file.close()
    return temp_file.name


def get_gsc_cache_dir() -> Path:
    """Retourne le dossier local de cache GSC."""
    cache_dir = Path(".runtime") / "gsc_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def build_gsc_cache_key(
    site_url: str,
    start_date: date,
    end_date: date,
    country: Optional[str],
    device: Optional[str],
    max_rows: int,
) -> str:
    """Construit une clé stable pour les paramètres de requête GSC."""
    payload = {
        "site_url": site_url,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "country": (country or "").strip().lower(),
        "device": device or "Tous",
        "max_rows": int(max_rows),
        "dimensions": ["page", "query"],
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def get_gsc_cache_paths(cache_key: str) -> Tuple[Path, Path]:
    """Retourne les chemins CSV et métadonnées pour une clé de cache GSC."""
    cache_dir = get_gsc_cache_dir()
    return cache_dir / f"{cache_key}.csv", cache_dir / f"{cache_key}.json"


def load_gsc_cache(cache_key: str):
    """Charge un cache GSC local s'il existe."""
    csv_path, meta_path = get_gsc_cache_paths(cache_key)
    if not csv_path.exists() or not meta_path.exists():
        return None, None
    dataframe = pd.read_csv(csv_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    return dataframe, metadata


def save_gsc_cache(cache_key: str, dataframe: pd.DataFrame, metadata: dict) -> Path:
    """Sauvegarde un cache GSC local."""
    csv_path, meta_path = get_gsc_cache_paths(cache_key)
    dataframe.to_csv(csv_path, index=False)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path


def clear_gsc_cache() -> int:
    """Supprime les caches GSC locaux."""
    cache_dir = get_gsc_cache_dir()
    deleted_count = 0
    for path in cache_dir.glob("*"):
        if path.is_file() and path.suffix in {".csv", ".json"}:
            path.unlink()
            deleted_count += 1
    return deleted_count


def get_run_cache_dir() -> Path:
    """Retourne le dossier local de cache des analyses SILO."""
    cache_dir = Path(".runtime") / "run_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def hash_file(file_path: Optional[str]) -> str:
    """Calcule un hash stable d'un fichier, sans le charger entierement en RAM."""
    if not file_path or not os.path.exists(file_path):
        return ""
    digest = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_cache_key(
    gsc_file_path: str,
    html_zip_path: str,
    html_prefix: str,
    crawl_csv_path: Optional[str],
) -> str:
    """Construit une cle stable pour les imports et les parametres d'analyse."""
    payload = {
        "gsc_hash": hash_file(gsc_file_path),
        "html_hash": hash_file(html_zip_path),
        "crawl_hash": hash_file(crawl_csv_path),
        "html_prefix": html_prefix,
        "pipeline": "silo-quality-v1",
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def build_run_cache_signature(
    gsc_file_path: str,
    html_zip_path: str,
    html_prefix: str,
    crawl_csv_path: Optional[str],
) -> str:
    """Construit une signature legere pour eviter de rehasher les gros fichiers."""
    def file_signature(file_path: Optional[str]) -> dict:
        if not file_path or not os.path.exists(file_path):
            return {"path": "", "size": 0, "mtime": 0}
        stat = os.stat(file_path)
        return {
            "path": str(file_path),
            "size": int(stat.st_size),
            "mtime": int(stat.st_mtime),
        }

    payload = {
        "gsc": file_signature(gsc_file_path),
        "html": file_signature(html_zip_path),
        "crawl": file_signature(crawl_csv_path),
        "html_prefix": html_prefix,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def get_or_build_run_cache_key(
    gsc_file_path: str,
    html_zip_path: str,
    html_prefix: str,
    crawl_csv_path: Optional[str],
) -> str:
    """Retourne la cle de cache d'analyse sans rehasher inutilement les imports."""
    signature = build_run_cache_signature(gsc_file_path, html_zip_path, html_prefix, crawl_csv_path)
    if (
        st.session_state.get("run_cache_signature") == signature
        and st.session_state.get("run_cache_key")
    ):
        return st.session_state.run_cache_key

    cache_key = build_run_cache_key(gsc_file_path, html_zip_path, html_prefix, crawl_csv_path)
    st.session_state.run_cache_signature = signature
    st.session_state.run_cache_key = cache_key
    return cache_key


def get_run_cache_paths(cache_key: str) -> Tuple[Path, Path]:
    """Retourne les chemins CSV et metadonnees du cache d'analyse."""
    cache_dir = get_run_cache_dir()
    return cache_dir / f"{cache_key}.csv", cache_dir / f"{cache_key}.json"


def load_run_cache(cache_key: str):
    """Charge un resultat d'analyse SILO s'il existe."""
    csv_path, meta_path = get_run_cache_paths(cache_key)
    if not csv_path.exists() or not meta_path.exists():
        return None, None
    dataframe = pd.read_csv(csv_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    return dataframe, metadata


def save_run_cache(cache_key: str, dataframe: pd.DataFrame, metadata: dict) -> Path:
    """Sauvegarde un resultat d'analyse SILO."""
    csv_path, meta_path = get_run_cache_paths(cache_key)
    dataframe.to_csv(csv_path, index=False)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path


def clear_run_cache() -> int:
    """Supprime les caches d'analyse SILO."""
    cache_dir = get_run_cache_dir()
    deleted_count = 0
    for path in cache_dir.glob("*"):
        if path.is_file() and path.suffix in {".csv", ".json"}:
            path.unlink()
            deleted_count += 1
    return deleted_count


def load_session_crawl_metadata() -> dict:
    """Charge les metadonnees crawl associees a la session courante."""
    if st.session_state.get("crawl_metadata") is not None:
        return st.session_state.crawl_metadata
    crawl_csv_path = st.session_state.get("crawl_csv_path")
    if not crawl_csv_path:
        st.session_state.crawl_metadata = {}
        return {}
    try:
        loader = DataLoader(
            st.session_state.get("gsc_file_path", ""),
            st.session_state.get("html_zip_path", ""),
            html_prefix=st.session_state.get("html_prefix", "rendu_"),
            crawl_csv_path=crawl_csv_path,
        )
        st.session_state.crawl_metadata = loader.load_crawl_metadata() or {}
    except Exception:
        st.session_state.crawl_metadata = {}
    return st.session_state.crawl_metadata


def normalize_opportunities_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Garantit les colonnes métier utilisées par le tableau et l'export."""
    normalized = dataframe.copy()
    if "Suggested_Anchor" not in normalized.columns:
        normalized["Suggested_Anchor"] = normalized.get("Keyword_GSC", "")
    if "Anchor_Context" not in normalized.columns:
        normalized["Anchor_Context"] = normalized.get("Context_Snippet", "")
    priority_target_urls = st.session_state.get("priority_target_urls")
    return enrich_opportunities_dataframe(
        normalized,
        crawl_metadata=load_session_crawl_metadata(),
        priority_target_urls=priority_target_urls,
    )


def build_export_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Construit le même dataset que le tableau de validation, sans les colonnes de contrôle."""
    normalized = normalize_opportunities_dataframe(dataframe)
    export_columns = [column for column in EXPORT_COLUMNS if column in normalized.columns]
    if "Keep" not in normalized.columns:
        normalized["Keep"] = True
    selected_rows = normalized[normalized["Keep"] == True].copy()
    return selected_rows[export_columns]


def render_gsc_direct_import():
    """Affiche le connecteur Search Console et retourne True si des données sont prêtes."""
    st.info("Connexion directe à Google Search Console")

    client_secret_path = find_client_secret_path()
    if client_secret_path:
        st.caption(f"Client OAuth détecté : `{client_secret_path}`")
    else:
        st.warning(
            "Aucun `client_secret.json` détecté. Placez-le dans `.runtime/client_secret.json`, "
            "`config/client_secret.json`, ou configurez `SILO_GSC_CLIENT_SECRET_PATH`."
        )

    if not dependencies_available():
        st.warning(
            "Dépendances Google manquantes. Installez `google-auth`, `google-auth-oauthlib` "
            "et `google-api-python-client`, puis relancez SILO."
        )
        return False

    client = GSCClient()
    auth_col, disconnect_col = st.columns([2, 1])
    with auth_col:
        if st.button("Connecter / rafraîchir les propriétés GSC", type="secondary", use_container_width=True):
            try:
                st.session_state.gsc_sites = client.list_sites()
                if st.session_state.gsc_sites:
                    st.success(f"{len(st.session_state.gsc_sites)} propriété(s) détectée(s).")
                else:
                    st.warning("Connexion réussie, mais aucune propriété GSC accessible n'a été trouvée.")
            except Exception:
                st.error("Connexion GSC impossible.")
                st.code(traceback.format_exc())

    with disconnect_col:
        if st.button("Déconnecter GSC", use_container_width=True):
            client.disconnect()
            st.session_state.gsc_sites = []
            st.session_state.gsc_import_df = None
            st.session_state.gsc_import_meta = None
            st.success("Token GSC local supprimé.")

    sites = st.session_state.get("gsc_sites", [])
    if not sites and client.is_connected():
        try:
            sites = client.list_sites()
            st.session_state.gsc_sites = sites
        except Exception:
            sites = []

    if not sites:
        return st.session_state.gsc_import_df is not None

    selected_site = st.selectbox("Propriété Search Console", sites)
    period = st.selectbox("Période", ["28 derniers jours", "90 derniers jours", "7 derniers jours", "Personnalisée"])

    today = date.today()
    default_end = today - timedelta(days=3)
    if period == "7 derniers jours":
        start_date = default_end - timedelta(days=6)
        end_date = default_end
    elif period == "90 derniers jours":
        start_date = default_end - timedelta(days=89)
        end_date = default_end
    elif period == "Personnalisée":
        date_col_1, date_col_2 = st.columns(2)
        with date_col_1:
            start_date = st.date_input("Date de début", value=default_end - timedelta(days=27))
        with date_col_2:
            end_date = st.date_input("Date de fin", value=default_end)
    else:
        start_date = default_end - timedelta(days=27)
        end_date = default_end

    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        country = st.text_input("Pays optionnel", value="", placeholder="fr/fra, be/bel, ch/che...")
    with filter_col_2:
        device = st.selectbox("Device", ["Tous", "DESKTOP", "MOBILE", "TABLET"])
    with filter_col_3:
        max_rows = st.number_input("Lignes max", min_value=1000, max_value=250000, value=100000, step=1000)

    cache_key = build_gsc_cache_key(
        selected_site,
        start_date,
        end_date,
        country or None,
        device,
        int(max_rows),
    )
    cached_dataframe, cached_metadata = load_gsc_cache(cache_key)
    force_refresh = st.checkbox(
        "Forcer une nouvelle requête GSC",
        value=False,
        help="À activer seulement si tu veux ignorer le cache local pour ces paramètres.",
    )

    cache_col_1, cache_col_2 = st.columns([3, 1])
    with cache_col_1:
        if cached_dataframe is not None:
            st.info(
                f"Cache GSC disponible pour ces paramètres : "
                f"{len(cached_dataframe):,} ligne(s)."
            )
        else:
            st.caption("Aucun cache GSC local pour ces paramètres.")
    with cache_col_2:
        if st.button("Vider cache GSC", type="secondary", use_container_width=True):
            deleted_count = clear_gsc_cache()
            st.success(f"{deleted_count} fichier(s) de cache supprimé(s).")
            st.rerun()

    if st.button("Importer les données GSC", type="primary", use_container_width=True):
        try:
            if cached_dataframe is not None and not force_refresh:
                dataframe = cached_dataframe
                metadata = cached_metadata or {}
                st.info("Données GSC chargées depuis le cache local.")
            else:
                with st.spinner("Récupération des données Search Console..."):
                    dataframe = client.fetch_search_analytics(
                        site_url=selected_site,
                        start_date=start_date,
                        end_date=end_date,
                        country=country or None,
                        device=device,
                        max_rows=int(max_rows),
                    )
                metadata = {
                    "site": selected_site,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "country": country or "",
                    "device": device,
                    "max_rows": int(max_rows),
                    "rows": len(dataframe),
                    "cache_key": cache_key,
                }
                save_gsc_cache(cache_key, dataframe, metadata)
            if dataframe.empty:
                st.warning("Aucune donnée GSC retournée pour ces paramètres.")
            else:
                st.session_state.gsc_import_df = dataframe
                cache_csv_path, _ = get_gsc_cache_paths(cache_key)
                st.session_state.gsc_file_path = str(cache_csv_path) if cache_csv_path.exists() else persist_gsc_dataframe(dataframe)
                st.session_state.gsc_import_meta = {
                    "site": metadata.get("site", selected_site),
                    "start_date": metadata.get("start_date", start_date.isoformat()),
                    "end_date": metadata.get("end_date", end_date.isoformat()),
                    "country": metadata.get("country", country or ""),
                    "device": metadata.get("device", device),
                    "max_rows": metadata.get("max_rows", int(max_rows)),
                    "rows": len(dataframe),
                    "cache_key": cache_key,
                }
                st.success(f"{len(dataframe):,} ligne(s) GSC importée(s).")
        except Exception:
            st.error("Import GSC impossible.")
            st.code(traceback.format_exc())

    if st.session_state.gsc_import_df is not None:
        meta = st.session_state.gsc_import_meta or {}
        st.success(
            f"Données prêtes : {meta.get('rows', len(st.session_state.gsc_import_df)):,} ligne(s), "
            f"{meta.get('site', selected_site)}"
        )
        if meta.get("cache_key"):
            st.caption(f"Cache GSC : `{meta.get('cache_key')}`")
        st.dataframe(st.session_state.gsc_import_df.head(20), use_container_width=True, hide_index=True)
        return True

    return False


def render_priority_targets_panel(opportunities_df: pd.DataFrame):
    """Affiche la priorisation SEO et retourne les cibles et l'etat du filtre."""
    with st.expander("🎯 Priorisation SEO des cibles", expanded=False):
        st.caption(
            "Ces critères identifient les pages cibles à fort potentiel. "
            "Activez le filtre pour limiter la liste d'opportunités à ces cibles."
        )

        gsc_file_path = st.session_state.get("gsc_file_path")
        if not gsc_file_path:
            st.info("Fichier GSC introuvable dans la session. Relancez une analyse pour afficher cette priorisation.")
            return set(), False

        col_config_1, col_config_2, col_config_3, col_config_4 = st.columns(4)
        with col_config_1:
            position_min = st.number_input("Position min", min_value=1.0, max_value=100.0, value=5.0, step=1.0)
        with col_config_2:
            position_max = st.number_input("Position max", min_value=1.0, max_value=100.0, value=20.0, step=1.0)
        with col_config_3:
            impressions_percentile = st.slider("Percentile impressions", 50, 95, 80, 5)
        with col_config_4:
            min_impressions = st.number_input("Impressions min", min_value=0, value=100, step=50)

        apply_priority_filter = st.checkbox(
            "Appliquer ces critères à la liste d'opportunités",
            value=True,
            help="Filtre le tableau principal pour ne garder que les opportunités vers les cibles prioritaires.",
        )

        try:
            gsc_data = DataLoader(gsc_file_path, "").load_gsc_data()
            config = PrioritizationConfig(
                position_min=position_min,
                position_max=position_max,
                impressions_percentile=float(impressions_percentile),
                min_impressions=int(min_impressions),
            )
            priority_targets = identify_priority_targets(gsc_data, config)
            coverage = summarize_priority_overlap(opportunities_df, priority_targets)
        except Exception:
            st.warning("Impossible de calculer la priorisation SEO avec le fichier GSC actuel.")
            st.code(traceback.format_exc())
            return set(), False

        metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
        metric_col_1.metric("Cibles prioritaires", coverage["priority_targets"])
        metric_col_2.metric("Déjà couvertes par SILO", coverage["covered_targets"])
        metric_col_3.metric("Sans opportunité trouvée", coverage["uncovered_targets"])

        if priority_targets.empty:
            st.info("Aucune cible prioritaire ne correspond aux seuils actuels.")
            return set(), apply_priority_filter

        display_columns = [
            "Page",
            "Top_Query",
            "Impressions",
            "Clicks",
            "Position",
            "Query_Count",
            "Opportunity_Score",
        ]
        display_df = priority_targets[display_columns].copy()
        display_df["Position"] = display_df["Position"].round(1)
        display_df["Opportunity_Score"] = display_df["Opportunity_Score"].round(1)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Page": st.column_config.LinkColumn("Page cible"),
                "Top_Query": "Requête principale",
                "Impressions": st.column_config.NumberColumn("Impressions", format="%d"),
                "Clicks": st.column_config.NumberColumn("Clics", format="%d"),
                "Position": st.column_config.NumberColumn("Position", format="%.1f"),
                "Query_Count": st.column_config.NumberColumn("Nb requêtes", format="%d"),
                "Opportunity_Score": st.column_config.NumberColumn("Score potentiel", format="%.1f"),
            },
        )

        priority_pages = set()
        for page_url in priority_targets["Page"].dropna().astype(str):
            normalized_url = DataLoader.normalize_url_for_matching(page_url)
            priority_pages.add(normalized_url)
            priority_pages.add(normalized_url.rstrip('/'))
        return priority_pages, apply_priority_filter

    return set(), False

# --- STEPS RENDERING ---

def render_upload_step():
    st.markdown('<div class="step-header">📂 Étape 1 : Importez vos données</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("1️⃣ **Données GSC (Demande)**")
        gsc_source = st.radio(
            "Source des données GSC",
            ["Connexion Search Console", "Import CSV"],
            horizontal=True,
            key="gsc_source",
        )
        gsc_file = None
        gsc_ready = False

        if gsc_source == "Connexion Search Console":
            gsc_ready = render_gsc_direct_import()
        else:
            gsc_file = st.file_uploader("Fichier CSV Google Search Console", type=['csv'])
            if gsc_file:
                st.success("Fichier GSC prêt")
                gsc_ready = True
        
    with col2:
        st.info("2️⃣ **Contenu HTML (Offre)**")
        html_file = st.file_uploader("Archive ZIP des rendus HTML", type=['zip'])
        html_prefix = st.selectbox(
            "Préfixe des fichiers",
            ["rendu_", "original_"],
            index=0,
            help="Choisissez le préfixe correspondant aux fichiers HTML dans l'archive.",
        )
        crawl_file = st.file_uploader(
            "Export crawl Screaming Frog Internal HTML (optionnel)",
            type=['csv'],
            help="CSV avec les colonnes Address, Status Code et idéalement Indexability.",
        )

    # Bouton Demo (toujours utile pour tester)
    if st.button("🔄 Charger Données de Démo (Test)", type="secondary"):
        if os.path.exists("data/input/demo_gsc.csv") and os.path.exists("data/input/demo_html.zip"):
            st.session_state.gsc_file_path = "data/input/demo_gsc.csv"
            st.session_state.html_zip_path = "data/input/demo_html.zip"
            st.session_state.crawl_csv_path = None
            st.session_state.html_prefix = "rendu_"
            st.session_state.crawl_metadata = {}
            st.session_state.final_df = None
            st.session_state.run_cache_signature = None
            st.session_state.run_cache_key = None
            st.session_state.step = 2
            st.rerun()
        else:
            st.error("Données de démo introuvables.")

    if gsc_ready and html_file:
        if st.button("Suivant ➡", type="primary"):
            try:
                if gsc_source == "Import CSV":
                    st.session_state.gsc_file_path = persist_uploaded_file(gsc_file, ".csv")

                st.session_state.html_zip_path = persist_html_zip(html_file)
                st.session_state.crawl_csv_path = persist_uploaded_file(crawl_file, ".csv") if crawl_file else None
                st.session_state.html_prefix = html_prefix
                st.session_state.crawl_metadata = None
                st.session_state.final_df = None
                st.session_state.run_cache_signature = None
                st.session_state.run_cache_key = None
                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                st.error(f"Import impossible : {e}")

def render_analysis_step():
    st.markdown('<div class="step-header">🚀 Étape 2 : Analyse Sémantique</div>', unsafe_allow_html=True)
    
    st.write("Le pipeline SILO croise vos données GSC avec le contenu de vos pages.")

    gsc_path = st.session_state.get("gsc_file_path")
    zip_path = st.session_state.get("html_zip_path")
    html_prefix = st.session_state.get("html_prefix", "rendu_")
    crawl_csv_path = st.session_state.get("crawl_csv_path")
    run_cache_key = None
    cached_run = None
    force_run_refresh = False

    if gsc_path and zip_path and os.path.exists(gsc_path) and os.path.exists(zip_path):
        run_cache_key = get_or_build_run_cache_key(gsc_path, zip_path, html_prefix, crawl_csv_path)
        cached_run, cached_run_meta = load_run_cache(run_cache_key)
        cache_col_1, cache_col_2, cache_col_3 = st.columns([3, 2, 1])
        with cache_col_1:
            if cached_run is not None:
                st.info(f"Cache analyse disponible : {len(cached_run):,} opportunité(s).")
            else:
                st.caption("Aucun cache d'analyse pour ces imports.")
        with cache_col_2:
            force_run_refresh = st.checkbox(
                "Forcer une analyse complète",
                value=False,
                help="Ignore le cache d'analyse HTML/GSC pour recalculer toutes les opportunités.",
            )
        with cache_col_3:
            if st.button("Vider cache analyse", type="secondary", use_container_width=True):
                deleted_count = clear_run_cache()
                st.success(f"{deleted_count} fichier(s) de cache supprimé(s).")
                st.rerun()

    nav_col, action_col = st.columns([1, 4])
    with nav_col:
        if st.button("⬅ Retour à l'import", type="secondary"):
            st.session_state.step = 1
            st.rerun()
    with action_col:
        start_btn = st.button("Lancer l'analyse", type="primary")
    
    if start_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            if not zip_path or not os.path.exists(zip_path):
                st.error("Archive HTML introuvable. Relancez l'import.")
                return

            status_text.text("⚙️ Initialisation du pipeline (Multi-process)...")
            progress_bar.progress(10)

            if cached_run is not None and not force_run_refresh:
                status_text.text("⚡ Chargement du cache d'analyse...")
                progress_bar.progress(70)
                df_results = cached_run
                load_session_crawl_metadata()
            else:
                # Init Linker (V2 Pro)
                linker = SILOLinker(
                    gsc_csv_path=st.session_state.gsc_file_path,
                    html_zip_path=zip_path,
                    html_prefix=st.session_state.html_prefix,
                    crawl_csv_path=st.session_state.get("crawl_csv_path")
                )

                status_text.text("🧠 Analyse sémantique en cours...")
                progress_bar.progress(30)

                # Execution
                # Note: Streamlit n'aime pas trop le multiprocessing complexe.
                # Dans app.py, on fait confiance au script.
                df_results = linker.process()
                st.session_state.crawl_metadata = linker.data_loader.load_crawl_metadata() or {}

                if run_cache_key:
                    save_run_cache(
                        run_cache_key,
                        df_results,
                        {
                            "rows": len(df_results),
                            "gsc_file_path": st.session_state.gsc_file_path,
                            "html_zip_path": zip_path,
                            "html_prefix": st.session_state.html_prefix,
                            "crawl_csv_path": st.session_state.get("crawl_csv_path") or "",
                        },
                    )

            progress_bar.progress(100)
            status_text.text("✅ Analyse terminée !")

            if not df_results.empty:
                # Ajouter colonne 'Keep' pour la review par défaut True
                if "Keep" not in df_results.columns:
                    df_results.insert(0, 'Keep', True)
                st.session_state.opportunities_df = normalize_opportunities_dataframe(df_results)
                st.session_state.final_df = None
                st.session_state.run_cache_key = run_cache_key
                time.sleep(1)
                st.session_state.step = 3
                st.rerun()
            else:
                st.warning("Aucune opportunité trouvée. Vérifiez vos données.")
                if st.button("Retour"):
                    st.session_state.step = 1
                    st.rerun()
                        
        except Exception as e:
            st.error(f"Erreur technique : {e}")
            import traceback
            st.code(traceback.format_exc())

def render_review_step():
    st.markdown('<div class="step-header">✅ Étape 3 : Validation Interactive</div>', unsafe_allow_html=True)
    
    st.session_state.opportunities_df = normalize_opportunities_dataframe(st.session_state.opportunities_df)
    priority_target_urls, apply_priority_filter = render_priority_targets_panel(st.session_state.opportunities_df)
    st.session_state.priority_target_urls = priority_target_urls
    st.session_state.opportunities_df = normalize_opportunities_dataframe(st.session_state.opportunities_df)
    df = st.session_state.opportunities_df
    
    # --- FILTRES ---
    col_filter1, col_filter2, col_filter3, col_filter4 = st.columns([1.4, 0.9, 0.9, 0.9])
    with col_filter1:
        keyword_filter = st.text_input("🔍 Filtrer", placeholder="Mot-clé, ancre, source ou cible...")
    with col_filter2:
        priority_values = [value for value in ["High", "Medium", "Low"] if value in set(df.get("Priority", pd.Series(dtype=str)).dropna())]
        priority_filter = st.multiselect("Priorité", priority_values, default=priority_values)
    with col_filter3:
        risk_values = [value for value in ["Low", "Medium", "High"] if value in set(df.get("Risk_Level", pd.Series(dtype=str)).dropna())]
        risk_filter = st.multiselect("Risque", risk_values, default=risk_values)
    with col_filter4:
        target_type_values = sorted(df.get("Target_Type", pd.Series(dtype=str)).dropna().unique().tolist())
        target_type_filter = st.multiselect("Type cible", target_type_values, default=target_type_values)

    col_filter5, col_filter6 = st.columns([1, 1])
    with col_filter5:
        min_final_score = st.slider("Score final min", min_value=0, max_value=100, value=0, step=5)
    with col_filter6:
        min_clicks = st.number_input("📉 Trafic min (clics)", min_value=0, value=0)

    # --- ACTIONS DE MASSE ---
    col_msg, col_actions = st.columns([2, 2])
    
    # Identifier les indices correspondant au filtre *actuel*
    mask = pd.Series(True, index=df.index)
    if apply_priority_filter:
        normalized_targets = df['Target_URL'].astype(str).map(DataLoader.normalize_url_for_matching)
        mask &= normalized_targets.isin(priority_target_urls) | normalized_targets.str.rstrip('/').isin(priority_target_urls)
    if keyword_filter:
        searchable = (
            df.get('Keyword_GSC', pd.Series("", index=df.index)).astype(str) + " " +
            df.get('Suggested_Anchor', pd.Series("", index=df.index)).astype(str) + " " +
            df.get('Source_URL', pd.Series("", index=df.index)).astype(str) + " " +
            df.get('Target_URL', pd.Series("", index=df.index)).astype(str)
        )
        mask &= searchable.str.contains(keyword_filter, case=False, na=False)
    if priority_values:
        mask &= df.get('Priority', pd.Series("", index=df.index)).isin(priority_filter)
    if risk_values:
        mask &= df.get('Risk_Level', pd.Series("", index=df.index)).isin(risk_filter)
    if target_type_values:
        mask &= df.get('Target_Type', pd.Series("", index=df.index)).isin(target_type_filter)
    if min_final_score > 0:
        mask &= pd.to_numeric(df.get('Final_Score', pd.Series(0, index=df.index)), errors='coerce').fillna(0) >= min_final_score
    if min_clicks > 0:
        if 'Clicks' in df.columns:
            mask &= (df['Clicks'] >= min_clicks)
            
    filtered_indices = df[mask].index
    
    with col_actions:
        st.write("Actions sur le filtre :")
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("✅ Tout cocher"):
                st.session_state.opportunities_df.loc[filtered_indices, 'Keep'] = True
                st.rerun()
        with col_act2:
            if st.button("❌ Tout décocher"):
                st.session_state.opportunities_df.loc[filtered_indices, 'Keep'] = False
                st.rerun()
                
    with col_msg:
        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
        metric_col_1.metric("Affichées", f"{len(filtered_indices)} / {len(df)}")
        metric_col_2.metric("High priority", int((df.get("Priority") == "High").sum()) if "Priority" in df.columns else 0)
        metric_col_3.metric("Risques Medium+", int(df.get("Risk_Level", pd.Series(dtype=str)).isin(["Medium", "High"]).sum()))
        metric_col_4.metric("Éligibles crawl", int((df.get("Technical_Status") == "Eligible").sum()) if "Technical_Status" in df.columns else "N/A")
        st.info("Décochez les liens à exclure. L'export CSV reprend les mêmes colonnes métier que ce tableau.")
        
    filtered_df = st.session_state.opportunities_df.loc[filtered_indices].copy()
    review_column_source = REVIEW_COLUMNS if zen_mode else ADVANCED_REVIEW_COLUMNS
    visible_columns = [column for column in review_column_source if column in filtered_df.columns]
    filtered_df = filtered_df[visible_columns]

    if filtered_df.empty:
        st.warning("Aucune opportunité ne correspond aux filtres actuels.")
    else:
        # Interactive Data Editor
        edited_df = st.data_editor(
            filtered_df,
            column_config={
                "Keep": st.column_config.CheckboxColumn(
                    "Garder ?",
                    help="Cochez pour inclure dans l'export",
                    default=True,
                ),
                "Priority": st.column_config.TextColumn("Priorité", width="small"),
                "Final_Score": st.column_config.ProgressColumn(
                    "Score final",
                    help="Score combinant potentiel SEO, qualité éditoriale et confiance technique",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "Risk_Level": st.column_config.TextColumn("Risque", width="small"),
                "Priority_Target": st.column_config.TextColumn("Cible prioritaire", width="small"),
                "SEO_Potential_Score": st.column_config.ProgressColumn(
                    "Potentiel SEO",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "Editorial_Fit_Score": st.column_config.ProgressColumn(
                    "Qualité éditoriale",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "Clicks": st.column_config.NumberColumn("Clics", format="%d"),
                "Impressions": st.column_config.NumberColumn("Impressions", format="%d"),
                "Position": st.column_config.NumberColumn("Position", format="%.1f"),
                "Source_URL": st.column_config.LinkColumn("Source URL"),
                "Target_URL": st.column_config.LinkColumn("Target URL"),
                "Keyword_GSC": "Mot-clé",
                "Suggested_Anchor": st.column_config.TextColumn(
                    "Ancre suggérée",
                    help="Texte court à utiliser comme ancre du lien interne.",
                ),
                "Anchor_Context": st.column_config.TextColumn("Contexte de l'ancre", width="medium"),
                "Decision_Reason": st.column_config.TextColumn("Raison", width="large"),
                "Context_Snippet": st.column_config.TextColumn("Contexte", width="large"),
            },
            disabled=[column for column in visible_columns if column not in {"Keep", "Suggested_Anchor"}],
            column_order=visible_columns,
            hide_index=True,
            use_container_width=True,
        )
        
        # IMPORTANT : Réconcilier les modifications avec le DataFrame original
        # car st.data_editor ne retourne que les lignes affichées.
        if not edited_df.equals(filtered_df):
            for idx, row in edited_df.iterrows():
                st.session_state.opportunities_df.loc[idx, 'Keep'] = row['Keep']
                if 'Suggested_Anchor' in row:
                    st.session_state.opportunities_df.loc[idx, 'Suggested_Anchor'] = row['Suggested_Anchor']
            st.session_state.opportunities_df = normalize_opportunities_dataframe(st.session_state.opportunities_df)

    with st.expander("🧪 Contrôles qualité", expanded=False):
        quality_columns = [
            column for column in [
                "Priority",
                "Final_Score",
                "Risk_Level",
                "Technical_Status",
                "Technical_Reason",
                "Source_URL",
                "Target_URL",
                "Decision_Reason",
            ] if column in df.columns
        ]
        high_risk_df = df[
            df.get("Risk_Level", pd.Series("", index=df.index)).isin(["Medium", "High"]) |
            df.get("Technical_Status", pd.Series("", index=df.index)).isin(["Excluded", "Unknown"])
        ]
        if high_risk_df.empty:
            st.success("Aucun risque technique ou éditorial majeur détecté sur les opportunités courantes.")
        else:
            st.dataframe(high_risk_df[quality_columns].head(200), use_container_width=True, hide_index=True)

    
    # Boutton Validation
    selected_count = int(st.session_state.opportunities_df['Keep'].sum())
    st.write(f"**{selected_count}** liens sélectionnés sur {len(df)}.")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔄 Recommencer", type="secondary"):
             reset_pipeline()
    with col2:
        if st.button("⬅ Retour à l'analyse", type="secondary"):
            st.session_state.step = 2
            st.rerun()
    with col3:
        if st.button(f"Valider {selected_count} liens & Exporter ➡", type="primary"):
            # Filtrer et sauvegarder
            final_df = build_export_dataframe(st.session_state.opportunities_df)
            st.session_state.final_df = final_df
            st.session_state.step = 4
            st.rerun()

def render_export_step():
    st.markdown('<div class="step-header">💾 Étape 4 : Résultats</div>', unsafe_allow_html=True)
    
    final_df = st.session_state.get("final_df")
    if final_df is None:
        final_df = build_export_dataframe(st.session_state.opportunities_df)
        st.session_state.final_df = final_df
    
    st.success("Votre fichier d'optimisation est prêt !")
    
    # Statistiques finales
    st.metric("Liens validés", len(final_df))
    st.dataframe(final_df, use_container_width=True, hide_index=True)
    
    # Conversion CSV
    csv_data = final_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Télécharger le CSV Final",
        data=csv_data,
        file_name="silo_export_final.csv",
        mime="text/csv",
        type="primary"
    )
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⬅ Retour à la validation", type="secondary"):
            st.session_state.step = 3
            st.rerun()
    with col2:
        if st.button("↩ Retour à l'analyse", type="secondary"):
            st.session_state.step = 2
            st.rerun()
    with col3:
        if st.button("🔄 Lancer une nouvelle analyse"):
            reset_pipeline()

# --- MAIN RENDERER ---

if zen_mode:
    # WIZARD FLOW
    if st.session_state.step == 1:
        render_upload_step()
    elif st.session_state.step == 2:
        render_analysis_step()
    elif st.session_state.step == 3:
        render_review_step()
    elif st.session_state.step == 4:
        render_export_step()
else:
    # ADVANCED MODE (Old Tabs for Debugging)
    st.warning("⚠️ Mode Avancé activé (Outils Debug)")
    
    tab1, tab2 = st.tabs(["🧪 Test NLP (Unitaire)", "🔍 Test Parser (Unitaire)"])
    
    with tab1:
        st.subheader("Test NLP Unitaire")
        k = st.text_input("Mot-clé", "voiture")
        t = st.text_area("Texte", "J'aime les voitures rouges.")
        if st.button("Test NLP"):
             if st.session_state.nlp_model:
                 matcher = NLPMatcher(st.session_state.nlp_model)
                 res = matcher.find_matches(t, k)
                 st.write(res)
                 
    with tab2:
        st.subheader("Test Parser Unitaire")
        h = st.text_area("HTML", "<html><body><p>Text</p></body></html>")
        if st.button("Test Parser"):
            p = ContentParser()
            st.write(p.extract_valid_paragraphs(h))
    
    if st.button("⬅ Retour au Wizard"):
        # Just refresh page to default zen mode check
        st.rerun()
