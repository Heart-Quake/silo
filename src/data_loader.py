"""
Chargeur de données pour le projet SILO.
Gère le chargement des CSV GSC et génère automatiquement le mapping HTML depuis le ZIP.
"""
import csv
import zipfile
import os
from pathlib import Path
from typing import Any, Generator, Dict, Tuple, Optional
import pandas as pd
from src.scoring import assess_technical_metadata, is_indexable_crawl_metadata, normalize_url
from src.utils import generate_mapping_from_zip


class DataLoader:
    """
    Charge les données d'entrée pour le pipeline SILO.
    
    - Charge le CSV GSC (Google Search Console)
    - Génère automatiquement le mapping HTML depuis le ZIP
    - Fournit un générateur pour lire les fichiers HTML un par un
    """
    
    def __init__(
        self,
        gsc_csv_path: str,
        html_zip_path: str,
        html_prefix: str = "rendu_",
        crawl_csv_path: str = None,
    ):
        """
        Initialise le chargeur de données.
        
        Args:
            gsc_csv_path: Chemin vers le fichier CSV GSC
            html_zip_path: Chemin vers l'archive ZIP HTML (obligatoire)
            html_prefix: Préfixe des fichiers HTML dans le ZIP (défaut: "rendu_")
            crawl_csv_path: Chemin optionnel vers l'export Screaming Frog Internal HTML
        """
        self.gsc_csv_path = gsc_csv_path
        self.html_zip_path = html_zip_path
        self.html_prefix = html_prefix
        self.crawl_csv_path = crawl_csv_path
        self._gsc_data = None
        self._html_mapping = None
        self._indexable_urls = None
        self._crawl_metadata = None
    
    def load_gsc_data(self) -> pd.DataFrame:
        """
        Charge les données Google Search Console.
        
        Returns:
            DataFrame pandas avec les colonnes : Page, Query, Impressions, Clicks, Position
            
        Raises:
            FileNotFoundError: Si le fichier CSV n'existe pas
            ValueError: Si les colonnes requises sont manquantes
        """
        if self._gsc_data is not None:
            return self._gsc_data
        
        # Détecter automatiquement le délimiteur en lisant la première ligne
        with open(self.gsc_csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
            # Compter les séparateurs
            comma_count = first_line.count(',')
            semicolon_count = first_line.count(';')
            tab_count = first_line.count('\t')
            
            # Choisir le délimiteur le plus fréquent
            if semicolon_count > comma_count and semicolon_count > tab_count:
                detected_sep = ';'
            elif tab_count > comma_count:
                detected_sep = '\t'
            else:
                detected_sep = ','
        
        # Essayer différentes stratégies de lecture
        strategies = [
            # Stratégie 1 : Délimiteur détecté avec UTF-8
            {'encoding': 'utf-8', 'sep': detected_sep, 'decimal': ',' if detected_sep == ';' else '.'},
            # Stratégie 2 : Délimiteur détecté avec Latin-1 (pour caractères spéciaux)
            {'encoding': 'latin-1', 'sep': detected_sep, 'decimal': ',' if detected_sep == ';' else '.'},
            # Stratégie 3 : Point-virgule (format européen)
            {'encoding': 'utf-8', 'sep': ';', 'decimal': ','},
            # Stratégie 4 : Virgule (format US)
            {'encoding': 'utf-8', 'sep': ',', 'decimal': '.'},
        ]
        
        last_error = None
        for i, strategy in enumerate(strategies, 1):
            try:
                # Lire d'abord toutes les colonnes comme des strings pour éviter les conversions automatiques
                df = pd.read_csv(
                    self.gsc_csv_path,
                    encoding=strategy['encoding'],
                    sep=strategy['sep'],
                    on_bad_lines='skip',  # Ignorer les lignes mal formées
                    engine='python',  # Utiliser le moteur Python (plus tolérant)
                    dtype=str,  # Lire tout comme string d'abord
                    decimal=strategy.get('decimal', '.')
                )
                
                # Vérifier que nous avons des données
                if len(df) > 0:
                    # Normaliser les noms de colonnes (enlever espaces)
                    df.columns = df.columns.str.strip()
                    
                    # Essayer de trouver les colonnes même avec des variations
                    column_mapping = {}
                    required_columns = ['Page', 'Query', 'Impressions', 'Clicks', 'Position']
                    
                    for req_col in required_columns:
                        # Chercher la colonne (insensible à la casse)
                        found = None
                        for col in df.columns:
                            col_clean = col.lower().replace(' ', '_').replace('-', '_')
                            req_clean = req_col.lower()
                            if col_clean == req_clean or col.lower() == req_col.lower():
                                found = col
                                break
                        if found:
                            column_mapping[found] = req_col
                    
                    # Renommer les colonnes si nécessaire
                    if column_mapping:
                        df = df.rename(columns=column_mapping)
                    
                    # Vérifier les colonnes requises
                    missing = [col for col in required_columns if col not in df.columns]
                    if not missing:
                        # Nettoyer les colonnes numériques
                        for col in ['Impressions', 'Clicks', 'Position']:
                            if col in df.columns:
                                # Convertir en string pour le nettoyage
                                df[col] = df[col].astype(str)
                                
                                # Enlever espaces et %
                                df[col] = df[col].str.replace(' ', '', regex=False).str.replace('%', '', regex=False)
                                
                                # Gérer les séparateurs de milliers et décimaux selon le format
                                if col == 'Position':
                                    # Position : peut avoir des décimales (ex: "4.4")
                                    # Si le délimiteur est ';', Position utilise généralement '.' comme décimal
                                    # Remplacer les virgules par des points (au cas où)
                                    df[col] = df[col].str.replace(',', '.', regex=False)
                                    # Convertir en float (gère les décimales)
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                                else:
                                    # Clicks et Impressions : entiers avec séparateurs de milliers
                                    if strategy['sep'] == ';':
                                        # Format européen : "1,804" ou "690" (sans virgule si < 1000)
                                        # Enlever les virgules (séparateurs de milliers)
                                        df[col] = df[col].str.replace(',', '', regex=False)
                                        # Convertir en entier (les points ne devraient pas être présents pour les entiers)
                                        df[col] = pd.to_numeric(df[col], errors='coerce')
                                        # Arrondir et convertir en Int64 (supporte NaN)
                                        df[col] = df[col].round().astype('Int64')
                                    else:
                                        # Format US : "1,804" ou "690"
                                        # Enlever les virgules (séparateurs de milliers)
                                        df[col] = df[col].str.replace(',', '', regex=False)
                                        # Convertir en entier
                                        df[col] = pd.to_numeric(df[col], errors='coerce')
                                        # Arrondir et convertir en Int64
                                        df[col] = df[col].round().astype('Int64')
                        
                        # Filtrer les lignes avec des valeurs NaN dans les colonnes requises
                        initial_count = len(df)
                        df = df.dropna(subset=['Page', 'Query'])
                        if len(df) < initial_count:
                            print(f"   ⚠️  {initial_count - len(df)} lignes ignorées (données manquantes)")
                        
                        df = self.filter_dataframe_to_indexable_urls(df, url_column='Page')
                        self._gsc_data = df
                        if i > 1:
                            print(f"   ⚠️  Fichier lu avec la stratégie {i}")
                        return df
                    else:
                        last_error = f"Stratégie {i} : Colonnes manquantes : {missing}"
                else:
                    last_error = f"Stratégie {i} : Aucune donnée valide trouvée"
            except Exception as e:
                last_error = f"Stratégie {i} : {str(e)}"
                continue
        
        # Si toutes les stratégies ont échoué
        raise ValueError(
            f"Impossible de lire le fichier GSC '{self.gsc_csv_path}'. "
            f"Dernière erreur : {last_error}. "
            f"Vérifiez que le fichier est un CSV valide avec les colonnes : Page, Query, Impressions, Clicks, Position"
        )
    
    def load_html_mapping(self) -> pd.DataFrame:
        """
        Génère automatiquement le mapping entre URLs publiques et chemins de fichiers HTML
        à partir du ZIP HTML.
        
        Returns:
            DataFrame pandas avec les colonnes : URL, FilePath
            
        Raises:
            FileNotFoundError: Si le fichier ZIP n'existe pas
        """
        if self._html_mapping is not None:
            return self._html_mapping
        
        if not os.path.exists(self.html_zip_path):
            raise FileNotFoundError(f"Le fichier ZIP HTML '{self.html_zip_path}' n'existe pas")
        
        # Générer automatiquement le mapping depuis le ZIP
        print(f"📄 Génération automatique du mapping depuis {self.html_zip_path}...")
        self._html_mapping = generate_mapping_from_zip(
            self.html_zip_path, 
            output_csv=None,  # Pas de sauvegarde, juste en mémoire
            prefix=self.html_prefix
        )
        self._html_mapping = self.filter_dataframe_to_indexable_urls(self._html_mapping, url_column='URL')
        print(f"✅ {len(self._html_mapping)} URLs mappées automatiquement")
        
        return self._html_mapping

    def load_crawl_metadata(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Charge les metadonnees techniques depuis un export Screaming Frog.

        Les colonnes strictement requises sont l'adresse et le code HTTP. Les
        autres signaux sont exploites lorsqu'ils existent.
        """
        if self._crawl_metadata is not None:
            return self._crawl_metadata
        if not self.crawl_csv_path:
            return None
        if not os.path.exists(self.crawl_csv_path):
            raise FileNotFoundError(f"Le fichier de crawl '{self.crawl_csv_path}' n'existe pas")

        crawl_df = self.read_csv_with_detected_separator(self.crawl_csv_path)
        crawl_df.columns = crawl_df.columns.str.strip()

        address_column = self.find_column(crawl_df, ['Address', 'Adresse', 'URL', 'Url', 'Page'])
        status_column = self.find_column(
            crawl_df,
            ['Status Code', 'HTTP Status Code', 'Code HTTP', 'Code de statut HTTP', 'HTTP Code']
        )
        indexability_column = self.find_column(crawl_df, ['Indexability', 'Indexabilité'])
        canonical_column = self.find_column(
            crawl_df,
            [
                'Canonical',
                'Canonical URL',
                'Canonical Link Element 1',
                'URL canonique',
                'Adresse canonique',
            ],
        )
        meta_robots_column = self.find_column(
            crawl_df,
            ['Meta Robots', 'Meta Robots 1', 'Meta Robots Tag', 'Balise meta robots', 'Robots']
        )
        crawl_depth_column = self.find_column(
            crawl_df,
            ['Crawl Depth', 'Profondeur', 'Depth', 'Niveau de crawl']
        )
        unique_inlinks_column = self.find_column(
            crawl_df,
            ['Unique Inlinks', 'Inlinks', 'Liens entrants uniques', 'Liens entrants']
        )

        if not address_column or not status_column:
            raise ValueError(
                "L'export crawl doit contenir au minimum les colonnes `Address`/`Adresse` "
                "et `Status Code`/`Code HTTP`."
            )

        metadata_by_url = {}
        for _, row in crawl_df.iterrows():
            url = str(row.get(address_column) or '').strip()
            if not url:
                continue

            metadata = {
                'address': url,
                'status_code': row.get(status_column),
                'indexability': row.get(indexability_column) if indexability_column else '',
                'canonical': row.get(canonical_column) if canonical_column else '',
                'meta_robots': row.get(meta_robots_column) if meta_robots_column else '',
                'crawl_depth': row.get(crawl_depth_column) if crawl_depth_column else '',
                'unique_inlinks': row.get(unique_inlinks_column) if unique_inlinks_column else '',
            }

            technical_status, technical_confidence, technical_reason = assess_technical_metadata(url, metadata)
            metadata['technical_status'] = technical_status
            metadata['technical_confidence'] = technical_confidence
            metadata['technical_reason'] = technical_reason

            normalized_url = self.normalize_url_for_matching(url)
            metadata_by_url[normalized_url] = metadata
            metadata_by_url[normalized_url.rstrip('/')] = metadata

        self._crawl_metadata = metadata_by_url
        print(f"✅ {len(self._crawl_metadata)} variantes d'URLs chargees depuis le crawl")
        return self._crawl_metadata

    def load_indexable_urls(self) -> Optional[set]:
        """
        Charge les URLs indexables depuis un export Screaming Frog Internal HTML.

        Le filtre conserve uniquement les URLs techniquement eligibles au
        maillage : 200, indexables, non noindex et canonical coherente.
        """
        if self._indexable_urls is not None:
            return self._indexable_urls

        crawl_metadata = self.load_crawl_metadata()
        if not crawl_metadata:
            return None

        normalized_urls = set()
        for url, metadata in crawl_metadata.items():
            if is_indexable_crawl_metadata(url, metadata):
                normalized_urls.add(self.normalize_url_for_matching(url))
                normalized_urls.add(self.normalize_url_for_matching(url).rstrip('/'))

        self._indexable_urls = normalized_urls
        print(f"✅ {len(self._indexable_urls)} variantes d'URLs indexables chargées depuis le crawl")
        return self._indexable_urls

    def filter_dataframe_to_indexable_urls(self, dataframe: pd.DataFrame, url_column: str) -> pd.DataFrame:
        """Filtre un DataFrame sur les URLs 200 + indexables si un crawl est fourni."""
        indexable_urls = self.load_indexable_urls()
        if not indexable_urls or url_column not in dataframe.columns:
            return dataframe

        initial_count = len(dataframe)
        normalized_urls = dataframe[url_column].astype(str).map(self.normalize_url_for_matching)
        keep_mask = normalized_urls.isin(indexable_urls) | normalized_urls.str.rstrip('/').isin(indexable_urls)
        filtered = dataframe[keep_mask].copy()
        removed_count = initial_count - len(filtered)
        if removed_count:
            print(f"   🚫 {removed_count} ligne(s) exclue(s) car non 200/indexables dans le crawl")
        return filtered

    @staticmethod
    def read_csv_with_detected_separator(csv_path: str) -> pd.DataFrame:
        """Lit un CSV Screaming Frog ou GSC en détectant le séparateur principal."""
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()

        separators = {
            ',': first_line.count(','),
            ';': first_line.count(';'),
            '\t': first_line.count('\t'),
        }
        separator = max(separators, key=separators.get)
        return pd.read_csv(
            csv_path,
            encoding='utf-8-sig',
            sep=separator,
            on_bad_lines='skip',
            engine='python',
            dtype=str,
        )

    @staticmethod
    def find_column(dataframe: pd.DataFrame, candidates: list) -> Optional[str]:
        """Trouve une colonne avec tolérance aux espaces, tirets et casse."""
        normalized_candidates = {
            candidate.lower().replace(' ', '_').replace('-', '_'): candidate
            for candidate in candidates
        }
        for column in dataframe.columns:
            normalized_column = column.lower().replace(' ', '_').replace('-', '_')
            if normalized_column in normalized_candidates:
                return column
        return None

    @staticmethod
    def normalize_url_for_matching(url: str) -> str:
        """Normalise légèrement les URLs pour matcher GSC, crawl et fichiers HTML."""
        return normalize_url(url)
    
    def get_html_files_generator(self) -> Generator[Tuple[str, str], None, None]:
        """
        Génère les fichiers HTML un par un pour économiser la RAM.
        
        Yields:
            Tuple (url, html_content) pour chaque fichier HTML
            
        Raises:
            FileNotFoundError: Si les fichiers HTML ne sont pas trouvés
        """
        mapping_df = self.load_html_mapping()
        
        # Lire depuis le ZIP (obligatoire maintenant)
        if not os.path.exists(self.html_zip_path):
            raise FileNotFoundError(f"Le fichier ZIP HTML '{self.html_zip_path}' n'existe pas")
        
        if self.html_zip_path:
            # Lire depuis le ZIP
            with zipfile.ZipFile(self.html_zip_path, 'r') as zip_ref:
                for _, row in mapping_df.iterrows():
                    url = row['URL']
                    file_path = row['FilePath']
                    
                    # Ignorer les fichiers __MACOSX
                    if '__MACOSX' in file_path:
                        continue
                    
                    try:
                        # Extraire le fichier depuis le ZIP
                        html_content = zip_ref.read(file_path).decode('utf-8', errors='ignore')
                        yield (url, html_content)
                    except KeyError:
                        # Fichier non trouvé dans le ZIP
                        continue
                    except Exception as e:
                        # Erreur de lecture, on continue
                        continue
        else:
            # Lire depuis le système de fichiers
            for _, row in mapping_df.iterrows():
                url = row['URL']
                file_path = row['FilePath']
                
                # Vérifier si le fichier existe
                if not os.path.exists(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        html_content = f.read()
                    yield (url, html_content)
                except Exception as e:
                    # Erreur de lecture, on continue
                    continue
    
    def get_keywords_dict(self) -> Dict[str, list]:
        """
        Construit un dictionnaire des mots-clés GSC groupés par URL cible.
        
        Returns:
            Dictionnaire {target_url: [list of keywords]} avec les meilleurs mots-clés par URL
        """
        gsc_df = self.load_gsc_data()
        
        # Grouper par Page (URL cible) et agréger les queries
        # Prioriser par nombre de clics ou position
        keywords_dict = {}
        
        for page_url, group in gsc_df.groupby('Page'):
            # Trier par clics décroissants, puis par position croissante
            sorted_group = group.sort_values(['Clicks', 'Position'], ascending=[False, True])
            
            # Extraire les queries uniques
            queries = sorted_group['Query'].unique().tolist()
            keywords_dict[page_url] = queries
        
        return keywords_dict
