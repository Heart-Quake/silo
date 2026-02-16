#!/usr/bin/env python3
"""
Script utilitaire pour générer le mapping CSV à partir d'un ZIP HTML.
"""
import argparse
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import generate_mapping_from_zip


def main():
    parser = argparse.ArgumentParser(
        description='Génère un fichier CSV de mapping à partir d\'un ZIP HTML'
    )
    parser.add_argument(
        'zip_path',
        help='Chemin vers le ZIP HTML'
    )
    parser.add_argument(
        '-o', '--output',
        default='html_mapping.csv',
        help='Chemin du fichier CSV de sortie (défaut: html_mapping.csv)'
    )
    parser.add_argument(
        '-p', '--prefix',
        default='rendu_',
        help='Préfixe des fichiers HTML (défaut: rendu_)'
    )
    
    args = parser.parse_args()
    
    if not Path(args.zip_path).exists():
        print(f"❌ Erreur : Le fichier '{args.zip_path}' n'existe pas")
        sys.exit(1)
    
    try:
        df = generate_mapping_from_zip(args.zip_path, args.output, args.prefix)
        print(f"\n✅ Mapping généré avec succès !")
        print(f"   - {len(df)} URLs mappées")
        print(f"   - Fichier de sortie : {args.output}")
        print(f"\n📋 Aperçu (5 premières lignes) :")
        print(df.head().to_string(index=False))
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
