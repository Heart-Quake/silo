#!/usr/bin/env python3
"""
Script de test rapide du pipeline SILO avec un échantillon réduit.
"""
import sys
import pandas as pd
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_loader import DataLoader
from src.parser import ContentParser
from src.nlp_matcher import NLPMatcher
import spacy

def test_pipeline_quick():
    """Test rapide avec un échantillon réduit."""
    print("🧪 Test rapide du pipeline SILO\n")
    
    # 1. Charger les données GSC (échantillon)
    print("📊 Étape 1 : Chargement GSC...")
    loader = DataLoader(
        "exemple-file/export_gsc.csv",
        "exemple-file/HTML Rendu.zip",
        html_prefix="rendu_"
    )
    gsc_df = loader.load_gsc_data()
    print(f"   ✅ {len(gsc_df)} lignes GSC chargées")
    
    # Prendre un échantillon pour le test rapide
    sample_gsc = gsc_df.head(100)  # 100 premières lignes
    print(f"   📝 Échantillon : {len(sample_gsc)} lignes pour le test")
    
    # 2. Générer le mapping HTML
    print("\n🔗 Étape 2 : Génération du mapping HTML...")
    mapping_df = loader.load_html_mapping()
    print(f"   ✅ {len(mapping_df)} URLs mappées")
    
    # Prendre quelques fichiers HTML pour le test
    sample_mapping = mapping_df.head(5)  # 5 premiers fichiers
    print(f"   📝 Échantillon : {len(sample_mapping)} fichiers HTML pour le test")
    
    # 3. Initialiser les composants
    print("\n🔧 Étape 3 : Initialisation des composants...")
    parser = ContentParser()
    nlp = spacy.load("fr_core_news_md")
    matcher = NLPMatcher(nlp_model=nlp, tolerance=2)
    print("   ✅ Parser, NLP et Matcher initialisés")
    
    # 4. Traiter les fichiers HTML
    print("\n📄 Étape 4 : Traitement des fichiers HTML...")
    opportunities = []
    html_gen = loader.get_html_files_generator()
    
    processed = 0
    for source_url, html_content in html_gen:
        # Limiter au nombre de fichiers de l'échantillon
        if source_url not in sample_mapping['URL'].values:
            continue
        
        processed += 1
        if processed > len(sample_mapping):
            break
        
        print(f"   📄 Traitement de {source_url}...")
        
        # Extraire les paragraphes
        paragraphs = parser.extract_valid_paragraphs(html_content)
        print(f"      → {len(paragraphs)} paragraphes éditoriaux extraits")
        
        if not paragraphs:
            continue
        
        # Construire le dictionnaire de mots-clés depuis l'échantillon GSC
        keywords_dict = {}
        for _, row in sample_gsc.iterrows():
            target_url = row['Page']
            keyword = row['Query']
            if target_url not in keywords_dict:
                keywords_dict[target_url] = []
            keywords_dict[target_url].append(keyword)
        
        # Chercher des matches
        matches_found = 0
        for paragraph_text, xpath in paragraphs:
            for target_url, keywords in keywords_dict.items():
                # Éviter l'auto-référence
                if source_url == target_url:
                    continue
                
                # Chercher le meilleur match
                for keyword in keywords[:5]:  # Limiter à 5 mots-clés par URL
                    matches = matcher.find_matches(paragraph_text, keyword)
                    if matches:
                        matches_found += 1
                        opportunity = {
                            'Score': 50,  # Score simplifié pour le test
                            'Keyword_GSC': keyword,
                            'Source_URL': source_url,
                            'Target_URL': target_url,
                            'Anchor_Text': paragraph_text[:50] + '...',
                            'Context_Snippet': paragraph_text[:200] + '...' if len(paragraph_text) > 200 else paragraph_text,
                            'XPath': xpath,
                            'Similarity_Type': 'Lemma_Fuzzy'
                        }
                        opportunities.append(opportunity)
                        break  # Un seul match par paragraphe
        
        if matches_found > 0:
            print(f"      → {matches_found} opportunité(s) trouvée(s)")
    
    print(f"\n✅ Traitement terminé : {processed} fichiers analysés")
    print(f"🎯 {len(opportunities)} opportunités identifiées au total")
    
    # 5. Exporter les résultats
    if opportunities:
        print("\n💾 Étape 5 : Export des résultats...")
        df_results = pd.DataFrame(opportunities)
        output_path = "data/output/opportunities_test.csv"
        df_results.to_csv(output_path, index=False, encoding='utf-8')
        print(f"   ✅ Résultats exportés vers : {output_path}")
        print(f"\n📋 Aperçu des résultats ({len(df_results)} opportunités) :")
        print(df_results[['Keyword_GSC', 'Source_URL', 'Target_URL', 'Score']].head(10).to_string(index=False))
        return True
    else:
        print("\n⚠️  Aucune opportunité trouvée dans l'échantillon testé")
        return False

if __name__ == '__main__':
    try:
        success = test_pipeline_quick()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
