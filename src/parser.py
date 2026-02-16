"""
Parser HTML pour extraire le contenu éditorial valide.
Exclut les zones de navigation, footer, sidebar, etc.
"""
import re
from typing import List, Tuple
from typing import List, Tuple
from lxml import html, etree
import ftfy
from urllib.parse import urljoin, urlparse


class ContentParser:
    """
    Parseur HTML pour extraire uniquement le contenu éditorial.
    
    Exclut automatiquement :
    - Zones de navigation (nav, header, footer, aside)
    - Scripts et styles
    - Contenu déjà dans des liens (<a>)
    """
    
    # Zones à exclure (blocklist)
    EXCLUDED_TAGS = {'nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'}
    
    # Balises de contenu valides (allowlist)
    VALID_CONTENT_TAGS = {'p', 'article', 'section', 'main', 'div'}
    
    def __init__(self):
        """Initialise le parser."""
        pass
    
    def _get_xpath(self, element: etree._Element) -> str:
        """
        Génère le XPath absolu pour un élément.
        
        Args:
            element: Élément lxml
            
        Returns:
            XPath absolu sous forme de chaîne
        """
        parts = []
        while element is not None:
            parent = element.getparent()
            if parent is None:
                break
            
            # Compter la position parmi les frères du même nom
            siblings = [s for s in parent if s.tag == element.tag]
            if len(siblings) > 1:
                index = siblings.index(element) + 1
                parts.append(f"{element.tag}[{index}]")
            else:
                parts.append(element.tag)
            
            element = parent
        
        parts.append('html')
        parts.reverse()
        return '/' + '/'.join(parts)
    
    def _is_in_excluded_zone(self, element: etree._Element) -> bool:
        """
        Vérifie si un élément est dans une zone exclue.
        
        Args:
            element: Élément à vérifier
            
        Returns:
            True si l'élément est dans une zone exclue
        """
        current = element
        while current is not None:
            tag = current.tag.lower()
            # Vérifier les tags exclus
            if tag in self.EXCLUDED_TAGS:
                return True
            # Vérifier les classes CSS communes pour les zones exclues
            classes = current.get('class', '').lower()
            if any(excluded in classes for excluded in ['menu', 'navigation', 'sidebar', 'footer', 'header']):
                return True
            current = current.getparent()
        return False
    
    def _is_inside_link(self, element: etree._Element) -> bool:
        """
        Vérifie si un élément est déjà à l'intérieur d'un lien (<a>).
        
        Args:
            element: Élément à vérifier
            
        Returns:
            True si l'élément est dans un lien
        """
        current = element
        while current is not None:
            if current.tag.lower() == 'a':
                return True
            current = current.getparent()
        return False
    
    def _clean_text(self, text: str) -> str:
        """
        Nettoie le texte : supprime les espaces multiples et les retours à la ligne.
        
        Args:
            text: Texte à nettoyer
            
        Returns:
            Texte nettoyé
        """
        if not text:
            return ""
        # Remplacer les retours à la ligne et espaces multiples par un espace unique
        text = re.sub(r'\s+', ' ', text)
        
        # Réparer l'encodage (mojibake)
        text = ftfy.fix_text(text)
        
        return text.strip()
    
    def extract_valid_paragraphs(self, html_content: str) -> List[Tuple[str, str]]:
        """
        Extrait les paragraphes valides du HTML.
        
        Args:
            html_content: Contenu HTML à parser
            
        Returns:
            Liste de tuples (texte_brut, xpath) pour chaque paragraphe éditorial valide
        """
        try:
            # Parser le HTML
            doc = html.fromstring(html_content.encode('utf-8') if isinstance(html_content, str) else html_content)
        except Exception as e:
            # Gérer les erreurs de parsing (HTML mal formé)
            return []
        
        results = []
        
        # XPath pour trouver uniquement les paragraphes <p> individuels
        # On ne prend que les <p> qui sont dans des zones valides (main, article, section)
        xpath_query = ".//main//p | .//article//p | .//section//p"
        elements = doc.xpath(xpath_query)
        
        for element in elements:
            # Ignorer si dans une zone exclue
            if self._is_in_excluded_zone(element):
                continue
            
            # Ignorer si déjà dans un lien
            if self._is_inside_link(element):
                continue
            
            # Extraire le texte en excluant le contenu des liens <a>
            # On prend le texte direct et celui des enfants non-links
            text_parts = []
            if element.text:
                text_parts.append(element.text)
            
            # Parcourir les enfants pour extraire le texte (sauf les liens)
            for child in element:
                if child.tag.lower() != 'a':
                    # Pour les enfants non-links, prendre leur texte
                    if child.text:
                        text_parts.append(child.text)
                    # Et le texte après l'enfant (tail)
                    if child.tail:
                        text_parts.append(child.tail)
                else:
                    # Pour les liens, on ignore leur contenu mais on garde le texte après (tail)
                    if child.tail:
                        text_parts.append(child.tail)
            
            text = ' '.join(text_parts)
            text = self._clean_text(text)
            
            # Si le texte est vide après exclusion des liens, ignorer
            if not text or len(text) < 10:
                continue
            
            # Pour le XPath roundtrip, on garde aussi le texte complet
            # (mais on utilisera le texte nettoyé pour la recherche de mots-clés)
            text_for_xpath = element.text_content()
            text_for_xpath = self._clean_text(text_for_xpath)
            
            # Ignorer les paragraphes vides ou trop courts
            if not text or len(text) < 10:
                continue
            
            # Générer le XPath
            xpath = self._get_xpath(element)
            
            # Stocker le texte nettoyé (sans liens) pour la recherche de mots-clés
            results.append((text, xpath))
        
        return results

    def extract_existing_links(self, html_content: str, base_url: str = None) -> set:
        """
        Extrait tous les liens sortants (href) de la page pour éviter la cannibalisation.
        
        Args:
            html_content: Contenu HTML
            base_url: URL de la page courante pour résoudre les liens relatifs
            
        Returns:
            Set des URLs cibles (normalisées en absolu si base_url est fourni)
        """
        try:
            doc = html.fromstring(html_content.encode('utf-8') if isinstance(html_content, str) else html_content)
        except Exception:
            return set()
            
        links = set()
        for href in doc.xpath('//a/@href'):
            href = href.strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
                
            if base_url:
                try:
                    # Résoudre lien relatif -> absolu
                    full_url = urljoin(base_url, href)
                    # Retirer ancre si présente
                    full_url = full_url.split('#')[0]
                    # Retirer slash final pour comparaison laxe
                    if full_url.endswith('/'):
                        full_url = full_url[:-1]
                    links.add(full_url)
                except Exception:
                    continue
            else:
                links.add(href)
                
        return links
