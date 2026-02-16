#!/usr/bin/env python3
"""
Test du pipeline complet avec un échantillon réduit pour validation rapide.
"""
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.silo_linker import SILOLinker
import tempfile
import os

def test_with_sample():
    """Test avec un échantillon réduit des données."""
    print("🧪 Test du pipeline complet avec échantillon\n")
    
    # Créer des fichiers temporaires avec échantillons
    print("📊 Préparation des échantillons...")
    
    # Charger le GSC complet
    from src.data_loader import DataLoader
    loader_full = DataLoader(
        "exemple-file/export_gsc.csv",
        "exemple-file/HTML Rendu.zip",
        html_prefix="rendu_"
    )
    gsc_full = loader_full.load_gsc_data()
    
    # Prendre un échantillon (100 premières lignes)
    gsc_sample = gsc_full.head(100)
    
    # Créer un CSV temporaire avec l'échantillon
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_gsc:
        gsc_sample.to_csv(tmp_gsc.name, index=False)
        tmp_gsc_path = tmp_gsc.name
    
    print(f"   ✅ Échantillon GSC : {len(gsc_sample)} lignes")
    
    # Créer un ZIP temporaire avec quelques fichiers HTML
    import zipfile
    mapping_full = loader_full.load_html_mapping()
    sample_urls = mapping_full.head(3)['URL'].tolist()  # 3 fichiers
    
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        tmp_zip_path = tmp_zip.name
    
    with zipfile.ZipFile("exemple-file/HTML Rendu.zip", 'r') as source_zip:
        with zipfile.ZipFile(tmp_zip_path, 'w') as target_zip:
            for url in sample_urls:
                # Trouver le fichier correspondant
                file_path = mapping_full[mapping_full['URL'] == url]['FilePath'].iloc[0]
                try:
                    content = source_zip.read(file_path)
                    target_zip.writestr(file_path, content)
                except:
                    pass
    
    print(f"   ✅ Échantillon HTML : {len(sample_urls)} fichiers")
    
    try:
        # Lancer le pipeline
        print("\n🚀 Lancement du pipeline...")
        silo = SILOLinker(
            gsc_csv_path=tmp_gsc_path,
            html_zip_path=tmp_zip_path,
            html_prefix="rendu_"
        )
        
        results_df = silo.process()
        
        # Exporter
        output_path = "data/output/opportunities_test_full.csv"
        silo.export_to_csv(results_df, output_path)
        
        print(f"\n✅ Test réussi !")
        print(f"   📊 {len(results_df)} opportunités trouvées")
        print(f"   💾 Fichier : {output_path}")
        
        if len(results_df) > 0:
            print(f"\n📋 Aperçu (5 premières) :")
            print(results_df[['Keyword_GSC', 'Source_URL', 'Target_URL', 'Score']].head().to_string(index=False))
        
        return True
        
    finally:
        # Nettoyer
        os.unlink(tmp_gsc_path)
        os.unlink(tmp_zip_path)

if __name__ == '__main__':
    try:
        test_with_sample()
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
