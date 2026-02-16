"""
Script principal SILO (Semantic Internal Link Optimizer).

Pipeline ETL pour identifier des opportunités de maillage interne à haute valeur ajoutée.
"""
import argparse
import sys
import os
import re
import spacy
import pandas as pd
from pathlib import Path
from typing import List, Dict, Set, Tuple

from src.data_loader import DataLoader
from src.parser import ContentParser
from src.nlp_matcher import NLPMatcher

# Globals for worker processes
worker_nlp = None
worker_matcher = None

def worker_init(tolerance: int = 2, min_similarity: float = 0.8):
    """
    Initialisation globale pour chaque process worker.
    Charge le modèle spaCy une seule fois par process.
    """
    global worker_nlp, worker_matcher
    # Charger modèle léger sans NER/Parser
    worker_nlp = spacy.load("fr_core_news_md", disable=["ner", "parser"])
    worker_matcher = NLPMatcher(nlp_model=worker_nlp, tolerance=tolerance, min_similarity=min_similarity)

def process_single_file(
    args: Tuple[str, str],
    keywords_dict: Dict[str, List[str]], 
    keyword_patterns: Dict[str, List[str]],
    regex_patterns: Dict[str, re.Pattern],
    gsc_data: pd.DataFrame,
    nlp=None,
    matcher=None
) -> List[Dict]:
    """
    Traite un fichier HTML et retourne les opportunités.
    Si nlp et matcher sont fournis (ex: mode séquentiel), on les utilise.
    Sinon on utilise les globaux worker_nlp / worker_matcher (workers parallèles).
    """
    source_url, html_content = args
    
    global worker_nlp, worker_matcher
    use_nlp = nlp if nlp is not None else worker_nlp
    use_matcher = matcher if matcher is not None else worker_matcher
    if use_matcher is None:
        worker_init()
        use_nlp = worker_nlp
        use_matcher = worker_matcher
    
    parser = ContentParser()
    file_opportunities = []
    
    # Extraire les paragraphes valides
    paragraphs = parser.extract_valid_paragraphs(html_content)
    
    # Extraire les liens déjà présents pour éviter la cannibalisation
    existing_links = parser.extract_existing_links(html_content, base_url=source_url)
    
    if not paragraphs:
        return []
    
    for paragraph_text, xpath in paragraphs:
        # Pre-cleaning basic
        paragraph_text_lower = paragraph_text.lower()
        
        # 1. MEGA PRE-FILTRE REGEX (O(N))
        # Vérifier d'abord si au moins un mot-clé de TOUT le corpus est présent
        # On peut optimiser en vérifiant par target_url si nécessaire, 
        # mais ici on vérifie si le paragraphe mérite d'être traité.
        potential_targets = []
        
        for target_url, pattern in regex_patterns.items():
            if source_url == target_url:
                continue
            
            # Anti-cannibalisation : si le lien existe déjà, on zappe
            # On compare sans le slash final pour être prudent
            if target_url in existing_links or target_url.rstrip('/') in existing_links:
                continue
            
            # Si le pattern regex matche, on a une chance
            if pattern.search(paragraph_text_lower):
                potential_targets.append(target_url)
        
        if not potential_targets:
            continue
            
        # 2. Si on a des cibles potentielles, on lance le NLP lourd
        # Lemmatiser le paragraphe UNE SEULE FOIS
        paragraph_lemmes = use_matcher._lemmatize_text(paragraph_text)
        paragraph_doc = use_nlp(paragraph_text_lower)
        
        # Chercher seulement pour les cibles pré-filtrées
        for target_url in potential_targets:
            # Re-vérification (redondant mais sûr)
            if target_url in existing_links or target_url.rstrip('/') in existing_links:
                continue
                
            keywords = keywords_dict[target_url]
            
            best_match = None
            best_keyword = None
            
            for keyword in keywords[:10]:
                if keyword not in keyword_patterns:
                    continue
                
                keyword_lemmes = keyword_patterns[keyword]
                
                matches = use_matcher.find_matches_optimized(
                    paragraph_lemmes,
                    paragraph_doc,
                    keyword_lemmes,
                    paragraph_text
                )
                
                if matches:
                    match = matches[0]
                    if best_match is None or match[0] < best_match[0]:
                        best_match = match
                        best_keyword = keyword
            
            if best_match and best_keyword:
                # Calculer le score et récupérer les métriques
                score_data = _calculate_score_and_metrics_static(target_url, best_keyword, gsc_data)
                
                # Extraire ancre
                anchor_text = _extract_anchor_text_static(paragraph_text, best_match)
                
                file_opportunities.append({
                    'Score': score_data['score'],
                    'Keyword_GSC': best_keyword,
                    'Source_URL': source_url,
                    'Target_URL': target_url,
                    'Clicks': score_data['clicks'],
                    'Impressions': score_data['impressions'],
                    'Position': score_data['position'],
                    'Anchor_Text': anchor_text,
                    'Context_Snippet': paragraph_text[:200] + '...' if len(paragraph_text) > 200 else paragraph_text,
                    'XPath': xpath,
                    'Similarity_Type': 'Lemma_Fuzzy'
                })
                
    return file_opportunities

def _calculate_score_and_metrics_static(target_url: str, keyword: str, gsc_data: pd.DataFrame) -> dict:
    """Calcul le score et retourne les métriques brutes."""
    # Note: Filtrage pandas peut être lent dans une boucle tight.
    filtered = gsc_data[
        (gsc_data['Page'] == target_url) & 
        (gsc_data['Query'] == keyword)
    ]
    
    defaults = {'score': 0, 'clicks': 0, 'impressions': 0, 'position': 100}
    
    if filtered.empty:
        return defaults
    
    row = filtered.iloc[0]
    clicks = row.get('Clicks', 0)
    # Impressions peut être absent si non chargé, on gère
    impressions = row.get('Impressions', 0) 
    position = row.get('Position', 100)
    
    click_score = min(clicks / 10, 50)
    position_score = max(0, 50 - position * 2)
    
    score = int(click_score + position_score)
    final_score = min(100, max(0, score))
    
    return {
        'score': final_score,
        'clicks': clicks,
        'impressions': impressions,
        'position': position
    }

def _extract_anchor_text_static(paragraph_text: str, match: tuple) -> str:
    """Version statique de extract_anchor_text."""
    start_pos, end_pos, matched_text = match
    context_start = max(0, start_pos - 30)
    context_end = min(len(paragraph_text), end_pos + 30)
    anchor_text = paragraph_text[context_start:context_end].strip()
    return re.sub(r'\s+', ' ', anchor_text)


class SILOLinker:
    """
    Classe principale orchestrant le pipeline SILO.
    """
    
    def __init__(self, gsc_csv_path: str, html_zip_path: str, html_prefix: str = "rendu_"):
        self.data_loader = DataLoader(gsc_csv_path, html_zip_path, html_prefix)
        self.opportunities = []
        self.opportunities_set = set()
        self.max_workers = min(os.cpu_count() or 4, 8)
        
        # Le NLP principal pour le thread maître (si besoin de pré-calculs)
        self.nlp = spacy.load("fr_core_news_md", disable=["ner", "parser"])
        self.nlp_matcher = NLPMatcher(nlp_model=self.nlp)
    
    def _compile_regex_patterns(self, keywords_dict: Dict[str, List[str]]) -> Dict[str, re.Pattern]:
        """Compile une regex optimisée pour chaque URL cible."""
        regex_patterns = {}
        for url, keywords in keywords_dict.items():
            # Échapper les keywords pour regex
            # On trie par longueur décroissante pour matcher les plus longs d'abord dans le OR
            kws_sorted = sorted(keywords[:10], key=len, reverse=True)
            if not kws_sorted:
                continue
                
            # Pattern: (?i)(kw1|kw2|kw3)
            # Utiliser \b pour bordure de mot si on veut être strict, 
            # mais pour pré-filtre substring simple c'est plus rapide sans si c'est juste pour éliminer.
            # On va utiliser un pré-filtre "loose" donc (kw1|kw2) est OK.
            escaped_kws = [re.escape(k) for k in kws_sorted]
            pattern_str = f"(?i)({'|'.join(escaped_kws)})"
            regex_patterns[url] = re.compile(pattern_str)
        return regex_patterns

    def process(self) -> pd.DataFrame:
        print("📊 Chargement des données GSC...")
        gsc_data = self.data_loader.load_gsc_data()
        
        # Optimisation GSC data pour lecture rapide (TODO futur)
        
        print("🔗 Construction du dictionnaire de mots-clés...")
        keywords_dict = self.data_loader.get_keywords_dict()
        
        print("🔗 Pré-calcul des patterns de mots-clés...")
        all_keywords = []
        for keywords in keywords_dict.values():
            all_keywords.extend(keywords[:10])
        
        keyword_patterns = self.nlp_matcher.prepare_keyword_patterns(all_keywords)
        
        print("⚡ Compilation des Regex de pré-filtrage...")
        regex_patterns = self._compile_regex_patterns(keywords_dict)
        
        print("📄 Préparation des fichiers HTML...")
        html_files = list(self.data_loader.get_html_files_generator())
        total_files = len(html_files)
        
        # Traitement séquentiel (évite BrokenProcessPool sous Streamlit / macOS)
        # Les optimisations regex + lemmes restent actives.
        print(f"🚀 Traitement en cours ({total_files} fichiers)...")
        processed_count = 0
        for args in html_files:
            file_opportunities = process_single_file(
                args,
                keywords_dict=keywords_dict,
                keyword_patterns=keyword_patterns,
                regex_patterns=regex_patterns,
                gsc_data=gsc_data,
                nlp=self.nlp,
                matcher=self.nlp_matcher
            )
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == 1:
                print(f"   📄 Traité ({processed_count}/{total_files})...")
            for opp in file_opportunities:
                if (opp['Source_URL'], opp['Target_URL']) not in self.opportunities_set:
                    self.opportunities.append(opp)
                    self.opportunities_set.add((opp['Source_URL'], opp['Target_URL']))

        print(f"\n✅ Traitement terminé : {processed_count} fichiers analysés")
        print(f"🎯 {len(self.opportunities)} opportunités identifiées")
        
        df = pd.DataFrame(self.opportunities)
        if not df.empty:
            df = df.sort_values('Score', ascending=False)
        return df

    def export_to_csv(self, df: pd.DataFrame, output_path: str):
        df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"💾 Résultats exportés vers : {output_path}")


def main():
    parser = argparse.ArgumentParser(description='SILO - Semantic Internal Link Optimizer (Pro V2)')
    parser.add_argument('--gsc-csv', required=True, help='Chemin vers le fichier CSV GSC')
    parser.add_argument('--html-zip', required=True, help='Chemin vers l\'archive ZIP HTML')
    parser.add_argument('--html-prefix', default='rendu_', help='Préfixe des fichiers HTML')
    parser.add_argument('--output', default='opportunities_export.csv', help='Fichier de sortie')
    
    args = parser.parse_args()
    
    if not Path(args.gsc_csv).exists() or not Path(args.html_zip).exists():
        print("❌ Erreur : Fichiers d'entrée manquants")
        sys.exit(1)
    
    silo = SILOLinker(args.gsc_csv, args.html_zip, args.html_prefix)
    
    try:
        opportunities_df = silo.process()
        silo.export_to_csv(opportunities_df, args.output)
        print("\n✨ Pipeline terminé avec succès !")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    # Protection pour Windows/Multiprocessing
    import multiprocessing
    multiprocessing.freeze_support()
    main()
