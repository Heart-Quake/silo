"""
Client Google Search Console pour SILO.

Le module garde les imports Google en lazy-loading pour préserver le fallback CSV
si les dépendances OAuth ne sont pas encore installées.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_DIMENSIONS = ["page", "query"]
DEFAULT_ROW_LIMIT = 25000
COUNTRY_ALIASES = {
    "fr": "fra",
    "be": "bel",
    "ch": "che",
    "ca": "can",
    "us": "usa",
    "uk": "gbr",
    "gb": "gbr",
    "es": "esp",
    "de": "deu",
    "it": "ita",
}


class GSCDependencyError(RuntimeError):
    """Erreur explicite quand les dépendances Google ne sont pas disponibles."""


def get_runtime_dir() -> Path:
    """Retourne le dossier local non versionné utilisé pour les tokens."""
    runtime_dir = Path(__file__).resolve().parents[1] / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    return runtime_dir


def default_token_path() -> Path:
    """Chemin du token OAuth local de SILO."""
    return get_runtime_dir() / "gsc_token.json"


def candidate_client_secret_paths() -> List[Path]:
    """Liste les emplacements probables du client OAuth Desktop."""
    project_root = Path(__file__).resolve().parents[1]
    github_root = project_root.parent
    candidates = []

    env_path = os.getenv("SILO_GSC_CLIENT_SECRET_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.extend(
        [
            get_runtime_dir() / "client_secret.json",
            project_root / "config" / "client_secret.json",
            github_root / "GSC-analyser" / "config" / "client_secret.json",
        ]
    )
    return candidates


def find_client_secret_path() -> Optional[Path]:
    """Retourne le premier fichier OAuth client disponible."""
    for path in candidate_client_secret_paths():
        if path.exists():
            return path
    return None


def dependencies_available() -> bool:
    """Vérifie si les librairies Google nécessaires sont installées."""
    try:
        import google.auth.transport.requests  # noqa: F401
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except Exception:
        return False
    return True


def build_dimension_filters(country: Optional[str] = None, device: Optional[str] = None) -> List[Dict[str, str]]:
    """Construit les filtres GSC optionnels."""
    filters = []
    if country and country.strip():
        normalized_country = country.strip().lower()
        filters.append(
            {
                "dimension": "country",
                "operator": "equals",
                "expression": COUNTRY_ALIASES.get(normalized_country, normalized_country),
            }
        )
    if device and device.strip() and device != "Tous":
        filters.append({"dimension": "device", "operator": "equals", "expression": device.strip().upper()})
    return filters


def rows_to_dataframe(rows: List[Dict[str, Any]], dimensions: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Convertit les lignes Search Analytics en format SILO.

    Format cible stable : Page, Query, Impressions, Clicks, Position.
    """
    selected_dimensions = dimensions or DEFAULT_DIMENSIONS
    records = []

    for row in rows:
        keys = row.get("keys", [])
        values_by_dimension = {
            dimension: keys[index] if index < len(keys) else ""
            for index, dimension in enumerate(selected_dimensions)
        }
        records.append(
            {
                "Page": values_by_dimension.get("page", ""),
                "Query": values_by_dimension.get("query", ""),
                "Impressions": int(row.get("impressions", 0) or 0),
                "Clicks": int(row.get("clicks", 0) or 0),
                "Position": float(row.get("position", 0.0) or 0.0),
            }
        )

    dataframe = pd.DataFrame.from_records(records, columns=["Page", "Query", "Impressions", "Clicks", "Position"])
    if dataframe.empty:
        return dataframe

    dataframe = dataframe.dropna(subset=["Page", "Query"])
    dataframe = dataframe[dataframe["Page"].astype(str).str.len() > 0]
    dataframe = dataframe[dataframe["Query"].astype(str).str.len() > 0]
    return dataframe.reset_index(drop=True)


class GSCClient:
    """Client OAuth local pour Google Search Console."""

    def __init__(
        self,
        client_secret_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
    ) -> None:
        self.client_secret_path = client_secret_path or find_client_secret_path()
        self.token_path = token_path or default_token_path()
        self._credentials = None
        self._service = None

    def authenticate(self):
        """Authentifie l'utilisateur et construit le service Search Console."""
        if not dependencies_available():
            raise GSCDependencyError(
                "Dépendances Google manquantes. Installez google-auth, google-auth-oauthlib et google-api-python-client."
            )
        if self.client_secret_path is None or not self.client_secret_path.exists():
            raise FileNotFoundError(
                "Aucun client_secret.json trouvé. Placez-le dans .runtime/client_secret.json, "
                "config/client_secret.json ou configurez SILO_GSC_CLIENT_SECRET_PATH."
            )

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        credentials = None
        if self.token_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(str(self.token_path), GSC_SCOPES)
            except Exception:
                credentials = None

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                except Exception:
                    credentials = None

            if not credentials:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), GSC_SCOPES)
                credentials = flow.run_local_server(port=0)

            self.token_path.write_text(credentials.to_json(), encoding="utf-8")

        self._credentials = credentials
        self._service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        return self._service

    def service(self):
        """Retourne le service authentifié."""
        if self._service is None:
            return self.authenticate()
        return self._service

    def is_connected(self) -> bool:
        """Indique si un token local existe."""
        return self.token_path.exists()

    def disconnect(self) -> None:
        """Supprime le token local."""
        self._credentials = None
        self._service = None
        if self.token_path.exists():
            self.token_path.unlink()

    def list_sites(self) -> List[str]:
        """Liste les propriétés Search Console accessibles."""
        response = self.service().sites().list().execute()
        sites = [item.get("siteUrl", "") for item in response.get("siteEntry", [])]
        return sorted(site for site in sites if site)

    def fetch_search_analytics(
        self,
        site_url: str,
        start_date: date,
        end_date: date,
        country: Optional[str] = None,
        device: Optional[str] = None,
        max_rows: int = 100000,
    ) -> pd.DataFrame:
        """Récupère les données GSC query/page avec pagination."""
        filters = build_dimension_filters(country=country, device=device)
        all_rows: List[Dict[str, Any]] = []
        start_row = 0

        while len(all_rows) < max_rows:
            remaining = max_rows - len(all_rows)
            row_limit = min(DEFAULT_ROW_LIMIT, remaining)
            body: Dict[str, Any] = {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": DEFAULT_DIMENSIONS,
                "rowLimit": row_limit,
                "startRow": start_row,
                "type": "web",
            }
            if filters:
                body["dimensionFilterGroups"] = [{"filters": filters}]

            response = self.service().searchanalytics().query(siteUrl=site_url, body=body).execute()
            rows = response.get("rows", [])
            if not rows:
                break

            all_rows.extend(rows)
            if len(rows) < row_limit:
                break
            start_row += row_limit

        return rows_to_dataframe(all_rows, DEFAULT_DIMENSIONS)
