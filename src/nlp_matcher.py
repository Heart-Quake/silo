"""
Moteur NLP pour le matching sémantique avec tolérance linguistique.
Utilise spaCy pour la lemmatisation et une fenêtre glissante pour le matching.
"""
from typing import List, Tuple, Optional, Dict
import spacy
from spacy.tokens import Doc
import difflib


class NLPMatcher:
    """
    Moteur de matching sémantique avec tolérance linguistique.
    
    Utilise :
    - Lemmatisation pour gérer les flexions
    - Suppression des stop-words
    - Fenêtre glissante pour tolérer les mots intercalés
    - Matching fuzzy sur les lemmes
    """
    
    def __init__(self, nlp_model: Optional[spacy.Language] = None, tolerance: int = 2, min_similarity: float = 0.8):
        """
        Initialise le matcher NLP.
        
        Args:
            nlp_model: Instance spaCy (si None, charge 'fr_core_news_md')
            tolerance: Nombre de mots supplémentaires autorisés dans la fenêtre (delta)
            min_similarity: Seuil de similitude pour le matching fuzzy des lemmes (0.0 à 1.0)
        """
        if nlp_model is None:
            # OPTIMISATION: Désactiver les composants inutiles pour gagner du temps
            self.nlp = spacy.load("fr_core_news_md", disable=["ner", "parser"])
        else:
            self.nlp = nlp_model
        
        self.tolerance = tolerance
        self.min_similarity = min_similarity
    
    def _lemmatize_keyword(self, keyword: str) -> List[str]:
        """
        Lemmatise un mot-clé en supprimant les stop-words.
        
        Args:
            keyword: Mot-clé à lemmatiser (peut contenir plusieurs mots)
            
        Returns:
            Liste des lemmes (sans stop-words)
        """
        doc = self.nlp(keyword.lower())
        lemmes = [
            token.lemma_ 
            for token in doc 
            if not token.is_stop and not token.is_punct and token.lemma_.strip()
        ]
        return lemmes
    
    def _lemmatize_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Lemmatise un texte et retourne les lemmes avec leurs positions.
        
        Args:
            text: Texte à lemmatiser
            
        Returns:
            Liste de tuples (lemme, position_originale)
        """
        doc = self.nlp(text.lower())
        lemmes = []
        for token in doc:
            if not token.is_stop and not token.is_punct and token.lemma_.strip():
                lemmes.append((token.lemma_, token.i))
        return lemmes
    
    def find_matches(
        self, 
        text: str, 
        keyword: str, 
        context_window: int = 50
    ) -> List[Tuple[int, int, str]]:
        """
        Trouve les occurrences d'un mot-clé dans un texte avec tolérance linguistique.
        
        Args:
            text: Texte dans lequel chercher
            keyword: Mot-clé à rechercher
            context_window: Taille de la fenêtre de contexte (en caractères)
            
        Returns:
            Liste de tuples (start_pos, end_pos, matched_text) pour chaque match
        """
        # Lemmatiser le mot-clé
        keyword_lemmes = self._lemmatize_keyword(keyword)
        
        if not keyword_lemmes:
            return []
        
        # Lemmatiser le texte
        text_lemmes = self._lemmatize_text(text)
        
        if len(text_lemmes) < len(keyword_lemmes):
            return []
        
        # Travailler avec le doc pour les positions de caractères
        text_doc = self.nlp(text.lower())
        
        return self.find_matches_optimized(
            text_lemmes,
            text_doc,
            keyword_lemmes,
            text,
            context_window
        )
    
    def _is_fuzzy_match(self, lemma1: str, lemma2: str) -> bool:
        """Vérifie si deux lemmes sont assez proches (fuzzy matching)."""
        if lemma1 == lemma2:
            return True
        
        # Si trop court, pas de fuzzy
        if len(lemma1) < 4 or len(lemma2) < 4:
            return False
            
        # Utiliser difflib pour la similarité
        ratio = difflib.SequenceMatcher(None, lemma1, lemma2).ratio()
        return ratio >= self.min_similarity

    def _check_lemma_match(self, keyword_lemmes: List[str], window_lemmes: List[str]) -> bool:
        """
        Vérifie si tous les lemmes du mot-clé sont présents dans la fenêtre.
        Supporte le matching fuzzy et l'ordre relatif.
        """
        # 1. Vérifier la présence de tous les lemmes (fuzzy)
        matched_indices = []
        for kw_lemma in keyword_lemmes:
            found = False
            for idx, win_lemma in enumerate(window_lemmes):
                if self._is_fuzzy_match(kw_lemma, win_lemma):
                    matched_indices.append(idx)
                    found = True
                    break
            if not found:
                return False
        
        # 2. Vérifier l'ordre approximatif
        # Les indices des matches dans la fenêtre doivent être croissants
        last_idx = -1
        keyword_idx = 0
        for win_lemma in window_lemmes:
            if keyword_idx < len(keyword_lemmes):
                if self._is_fuzzy_match(keyword_lemmes[keyword_idx], win_lemma):
                    keyword_idx += 1
        
        return keyword_idx == len(keyword_lemmes)
    
    def find_matches_optimized(
        self,
        text_lemmes: List[Tuple[str, int]],
        text_doc: Doc,
        keyword_lemmes: List[str],
        text: str,
        context_window: int = 50
    ) -> List[Tuple[int, int, str]]:
        """
        Version optimisée de find_matches qui accepte des lemmes pré-calculés.
        """
        if not keyword_lemmes:
            return []
        
        if len(text_lemmes) < len(keyword_lemmes):
            return []
        
        matches = []
        keyword_len = len(keyword_lemmes)
        # On autorise une fenêtre un peu plus large que le mot-clé + tolérance 
        # pour compenser les stop-words filtrés ou les mots intercalés.
        window_size = keyword_len + self.tolerance
        
        for i in range(len(text_lemmes) - keyword_len + 1):
            window = text_lemmes[i:i + window_size]
            window_lemmes = [lemme for lemme, _ in window]
            
            if self._check_lemma_match(keyword_lemmes, window_lemmes):
                start_token_idx = text_lemmes[i][1]
                
                # On essaie de trouver la fin réelle du match dans la fenêtre
                # (le dernier lemme du mot-clé qui a matché)
                last_match_idx = i
                kw_ptr = 0
                for j, (l, pos) in enumerate(window):
                    if kw_ptr < len(keyword_lemmes) and self._is_fuzzy_match(keyword_lemmes[kw_ptr], l):
                        last_match_idx = pos
                        kw_ptr += 1
                
                end_token_idx = last_match_idx
                
                if start_token_idx < len(text_doc) and end_token_idx < len(text_doc):
                    start_char = text_doc[start_token_idx].idx
                    # La fin est l'index du token suivant (ou la fin du doc)
                    end_char = text_doc[end_token_idx].idx + len(text_doc[end_token_idx])
                    
                    # Extraire le contexte
                    context_start = max(0, start_char - context_window)
                    context_end = min(len(text), end_char + context_window)
                    matched_text = text[context_start:context_end]
                    
                    matches.append((start_char, end_char, matched_text))
        
        return matches
    
    def prepare_keyword_patterns(self, keywords: List[str]) -> Dict[str, List[str]]:
        """Prépare les patterns lemmatisés pour une liste de mots-clés."""
        patterns = {}
        # nlp.pipe pour la perf ; on garde le keyword original comme clé pour la lookup
        for kw, doc in zip(keywords, self.nlp.pipe([k.lower() for k in keywords])):
            lemmes = [
                token.lemma_
                for token in doc
                if not token.is_stop and not token.is_punct and token.lemma_.strip()
            ]
            if lemmes:
                patterns[kw] = lemmes
        return patterns
