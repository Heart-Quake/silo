"""
Utilitaires pour le projet SILO.
Fonctions helper pour la génération de mapping et le traitement des fichiers.
"""
import zipfile
import csv
import re
from pathlib import Path
from typing import List, Tuple
import pandas as pd


def generate_mapping_from_zip(zip_path: str, output_csv: str = None, prefix: str = "rendu_") -> pd.DataFrame:
    """
    Génère un fichier CSV de mapping à partir d'un ZIP HTML.
    
    Les fichiers HTML sont nommés selon le format :
    - rendu_https_lilycare.fr_.html (page d'accueil)
    - rendu_https_lilycare.fr_a-propos-de-lilycare.html (autres pages)
    
    Args:
        zip_path: Chemin vers le ZIP HTML
        output_csv: Chemin du CSV de sortie (optionnel)
        prefix: Préfixe des fichiers HTML (ex: "rendu_" ou "original_")
        
    Returns:
        DataFrame avec les colonnes URL et FilePath
    """
    mapping_data = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.namelist():
            # Ignorer les fichiers __MACOSX et les fichiers non-HTML
            if '__MACOSX' in file_info or not file_info.endswith('.html'):
                continue
            
            # Extraire l'URL du nom de fichier
            filename = Path(file_info).name
            
            if not filename.startswith(prefix):
                continue
            
            # Utiliser la fonction de parsing
            url = parse_html_filename(filename, prefix)
            
            if not url:
                continue
            
            mapping_data.append({
                'URL': url,
                'FilePath': file_info
            })
    
    df = pd.DataFrame(mapping_data)
    
    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"✅ Mapping généré : {len(df)} URLs mappées -> {output_csv}")
    
    return df


def extract_gsc_from_numbers(numbers_file: str, output_csv: str = None) -> pd.DataFrame:
    """
    Extrait le CSV GSC depuis un fichier Numbers (.numbers).
    
    Les fichiers Numbers sont des archives ZIP contenant des fichiers XML/CSV.
    
    Args:
        numbers_file: Chemin vers le fichier .numbers
        output_csv: Chemin du CSV de sortie (optionnel)
        
    Returns:
        DataFrame GSC
    """
    # Les fichiers Numbers sont des ZIP
    # On cherche généralement dans preview.csv ou dans les fichiers XML
    with zipfile.ZipFile(numbers_file, 'r') as zip_ref:
        # Lister tous les fichiers
        file_list = zip_ref.namelist()
        
        # Chercher un fichier CSV
        csv_files = [f for f in file_list if f.endswith('.csv')]
        
        if csv_files:
            # Prendre le premier CSV trouvé
            csv_file = csv_files[0]
            content = zip_ref.read(csv_file).decode('utf-8', errors='ignore')
            
            # Lire le CSV
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            
            if output_csv:
                df.to_csv(output_csv, index=False)
                print(f"✅ CSV GSC extrait -> {output_csv}")
            
            return df
        else:
            raise ValueError("Aucun fichier CSV trouvé dans le fichier Numbers")


def parse_html_filename(filename: str, prefix: str = "rendu_") -> str:
    """
    Parse un nom de fichier HTML pour extraire l'URL.
    
    Format attendu:
    - rendu_https_lilycare.fr_.html -> https://lilycare.fr/
    - rendu_https_lilycare.fr_a-propos-de-lilycare.html -> https://lilycare.fr/a-propos-de-lilycare
    
    Args:
        filename: Nom du fichier (ex: "rendu_https_lilycare.fr_a-propos.html")
        prefix: Préfixe à enlever (ex: "rendu_")
        
    Returns:
        URL reconstruite (ex: "https://lilycare.fr/a-propos")
    """
    if not filename.startswith(prefix):
        return None
    
    # Enlever le préfixe et l'extension
    url_part = filename[len(prefix):-5]  # -5 pour enlever .html
    
    # Le format est: https_lilycare.fr_ ou https_lilycare.fr_path
    # Les underscores dans le path représentent des slashes dans l'URL
    # Exemple: "https_lilycare.fr_blog_arret-de-travail" -> "https://lilycare.fr/blog/arret-de-travail"
    
    # Pattern regex pour capturer: https_<domain>_<path?>
    match = re.match(r'^https_([^_]+)_(.*)$', url_part)
    
    if match:
        domain = match.group(1)
        path = match.group(2)
        
        if path == '':
            # Page d'accueil
            url = f"https://{domain}/"
        else:
            # Autres pages : convertir les underscores en slashes
            path_with_slashes = path.replace('_', '/')
            url = f"https://{domain}/{path_with_slashes}"
    else:
        # Fallback: essayer de reconstruire manuellement
        # Remplacer tous les _ sauf le premier (https_) par /
        parts = url_part.split('_')
        if len(parts) >= 3:
            # https, domain, path...
            domain = parts[1]
            path = '/'.join(parts[2:]) if len(parts) > 2 else ''
            url = f"https://{domain}/{path}" if path else f"https://{domain}/"
        else:
            # Format inattendu
            url = url_part.replace('_', '://')
            if not url.startswith('http'):
                url = 'https://' + url.lstrip('/')
    
    return url
