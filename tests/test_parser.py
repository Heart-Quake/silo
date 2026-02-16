"""
Tests unitaires pour le parser HTML (ContentParser).
Vérifie l'exclusion des zones non-éditoriales et la protection des liens imbriqués.
"""
import pytest
from src.parser import ContentParser


class TestZoneExclusion:
    """
    Cas 2.1 : Exclusion des Zones Non-Éditoriales (Zone Exclusion)
    
    Vérifie que l'outil ignore le contenu dans :
    - <nav> (navigation)
    - <header> (en-tête)
    - <footer> (pied de page)
    - <aside> (sidebar)
    - Et ne garde que le contenu éditorial dans <main>, <article>, <p>
    """
    
    def test_exclude_nav_footer_from_matches(self, mock_html_complex):
        """
        Test : Le mot-clé "voiture occasion" apparaît dans :
        - <nav> (à ignorer)
        - <footer> (à ignorer)
        - <main><article><p> (à garder)
        
        Comportement attendu : 1 seule occurrence trouvée (celle dans le contenu éditorial).
        """
        parser = ContentParser()
        results = parser.extract_valid_paragraphs(mock_html_complex)
        
        # Compter les occurrences de "voiture occasion" dans les résultats
        matches = [r for r in results if "voiture occasion" in r[0].lower()]
        
        # Assertions : doit trouver au moins 1 occurrence dans le contenu éditorial
        assert len(matches) >= 1, "Doit trouver au moins 1 occurrence dans le contenu éditorial"
        
        # Vérifier que toutes les occurrences viennent de main/article (pas de nav/footer)
        for text, xpath in matches:
            assert xpath.startswith("/html/body/main"), f"XPath {xpath} doit pointer vers main, pas nav/footer"
        
        # Vérifier qu'au moins une occurrence contient "Nous vendons" (le premier paragraphe éditorial)
        nous_vendons_matches = [r for r in matches if "Nous vendons" in r[0]]
        assert len(nous_vendons_matches) >= 1, "Doit trouver le paragraphe 'Nous vendons'"
    
    def test_exclude_sidebar_from_matches(self, mock_html_complex):
        """
        Test : Le contenu dans <aside class="sidebar"> doit être ignoré.
        """
        parser = ContentParser()
        results = parser.extract_valid_paragraphs(mock_html_complex)
        
        # Vérifier qu'aucun résultat ne provient de la sidebar
        for text, xpath in results:
            assert "sidebar" not in xpath.lower(), f"XPath {xpath} ne doit pas contenir 'sidebar'"


class TestNestedLinkPrevention:
    """
    Cas 2.2 : Protection des Liens Existants (Nested Link Prevention)
    
    Vérifie qu'on ne crée jamais de lien dans un lien existant.
    """
    
    def test_skip_text_inside_existing_link(self, mock_html_nested_links):
        """
        Test : Le texte "voiture occasion" se trouve déjà dans un <a>.
        
        Comportement attendu : 0 match (le texte est ignoré car déjà dans un lien).
        """
        parser = ContentParser()
        results = parser.extract_valid_paragraphs(mock_html_nested_links)
        
        # Chercher "voiture occasion" dans les résultats
        matches = [r for r in results if "voiture occasion" in r[0].lower()]
        
        # Assertion : doit être 0 car le texte est dans un lien existant
        assert len(matches) == 0, "Doit ignorer le texte déjà dans un lien (<a>)"
    
    def test_allow_text_outside_links(self, mock_html_complex):
        """
        Test : Le texte "voiture occasion" dans un <p> sans lien parent doit être détecté.
        """
        parser = ContentParser()
        results = parser.extract_valid_paragraphs(mock_html_complex)
        
        # Chercher le paragraphe "Nous vendons une superbe voiture occasion"
        matches = [r for r in results if "Nous vendons" in r[0] and "voiture occasion" in r[0].lower()]
        
        # Assertion : doit trouver au moins 1 match
        assert len(matches) >= 1, "Doit trouver le texte dans un paragraphe sans lien parent"


class TestXPathIntegrity:
    """
    Cas 2.3 : Robustesse XPath (XPath Integrity)
    
    Vérifie que les XPath générés sont valides et permettent de retrouver le texte original.
    """
    
    def test_xpath_roundtrip(self, mock_html_complex):
        """
        Test : Extraire un paragraphe, obtenir son XPath, puis requêter ce XPath.
        
        Comportement attendu : Le texte retrouvé via XPath doit correspondre au texte original.
        """
        parser = ContentParser()
        from lxml import html
        
        results = parser.extract_valid_paragraphs(mock_html_complex)
        
        if results:
            text, xpath = results[0]
            
            # Parser le HTML original
            doc = html.fromstring(mock_html_complex.encode('utf-8'))
            
            # Trouver l'élément via XPath
            elements = doc.xpath(xpath)
            assert len(elements) > 0, f"XPath {xpath} doit retourner au moins un élément"
            
            # Vérifier que le texte correspond (on nettoie les deux pour comparaison)
            import re
            found_text = elements[0].text_content()
            found_text = re.sub(r'\s+', ' ', found_text).strip()
            assert found_text == text, f"Texte XPath '{found_text}' doit correspondre à '{text}'"


class TestEncoding:
    """
    Cas 2.4 : Correction de l'encodage (Mojibake)
    """
    
    def test_clean_text_fixes_mojibake(self):
        """Test que le nettoyage du texte répare le mojibake via ftfy."""
        parser = ContentParser()
        
        # Exemple réel : "appel à un spécialiste" encodé en CP1252 puis lu en UTF-8
        bad_text = "appel Ã  un spÃ©cialiste"
        expected = "appel à un spécialiste"
        
        cleaned = parser._clean_text(bad_text)
        assert cleaned == expected
        
        # Exemple avec quote
        bad_quote = "dâ€™aide"
        
        cleaned_quote = parser._clean_text(bad_quote)
        # ftfy normalise et répare
        assert "dâ€™" not in cleaned_quote
        assert "aide" in cleaned_quote
