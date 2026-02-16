#!/usr/bin/env python3
"""
Script utilitaire pour extraire le CSV GSC depuis un fichier Numbers.
Note: Les fichiers Numbers sont complexes, ce script tente d'extraire les données.
Si cela ne fonctionne pas, exportez manuellement depuis Numbers en CSV.
"""
import argparse
import sys
import zipfile
from pathlib import Path
import pandas as pd
from io import StringIO

# Ajouter le répertoire parent au path pour importer src
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_gsc_from_numbers(numbers_file: str, output_csv: str = None) -> pd.DataFrame:
    """
    Tente d'extraire le CSV GSC depuis un fichier Numbers.
    
    Note: Les fichiers Numbers utilisent un format binaire complexe.
    Cette fonction tente de trouver des données CSV, mais il est recommandé
    d'exporter manuellement depuis Numbers en CSV.
    """
    print(f"📂 Ouverture du fichier Numbers : {numbers_file}")
    
    with zipfile.ZipFile(numbers_file, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        
        # Chercher des fichiers qui pourraient contenir des données CSV
        # Les fichiers Numbers stockent parfois des previews en CSV
        csv_candidates = [f for f in file_list if 'csv' in f.lower() or 'preview' in f.lower()]
        
        if csv_candidates:
            print(f"✅ Fichiers candidats trouvés : {len(csv_candidates)}")
            for candidate in csv_candidates[:5]:  # Essayer les 5 premiers
                try:
                    content = zip_ref.read(candidate)
                    # Essayer de décoder
                    try:
                        text = content.decode('utf-8')
                    except:
                        text = content.decode('latin-1', errors='ignore')
                    
                    # Vérifier si ça ressemble à du CSV
                    if ',' in text and '\n' in text:
                        print(f"   📄 Tentative avec : {candidate}")
                        try:
                            df = pd.read_csv(StringIO(text))
                            if 'Page' in df.columns or 'Query' in df.columns:
                                print(f"   ✅ Données GSC trouvées !")
                                if output_csv:
                                    df.to_csv(output_csv, index=False)
                                    print(f"   💾 Sauvegardé dans : {output_csv}")
                                return df
                        except:
                            continue
                except:
                    continue
        
        print("⚠️  Aucun CSV trouvé dans le fichier Numbers.")
        print("💡 Solution recommandée :")
        print("   1. Ouvrez le fichier Numbers dans l'application Numbers")
        print("   2. Fichier > Exporter vers > CSV...")
        print("   3. Utilisez le fichier CSV exporté")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Tente d\'extraire le CSV GSC depuis un fichier Numbers'
    )
    parser.add_argument(
        'numbers_file',
        help='Chemin vers le fichier .numbers'
    )
    parser.add_argument(
        '-o', '--output',
        default='gsc_export.csv',
        help='Chemin du fichier CSV de sortie (défaut: gsc_export.csv)'
    )
    
    args = parser.parse_args()
    
    if not Path(args.numbers_file).exists():
        print(f"❌ Erreur : Le fichier '{args.numbers_file}' n'existe pas")
        sys.exit(1)
    
    try:
        df = extract_gsc_from_numbers(args.numbers_file, args.output)
        if df is not None:
            print(f"\n✅ Extraction réussie !")
            print(f"   - {len(df)} lignes extraites")
            print(f"   - Colonnes : {', '.join(df.columns)}")
            print(f"\n📋 Aperçu (5 premières lignes) :")
            print(df.head().to_string(index=False))
        else:
            print("\n❌ Impossible d'extraire automatiquement les données.")
            print("   Veuillez exporter manuellement depuis Numbers en CSV.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
