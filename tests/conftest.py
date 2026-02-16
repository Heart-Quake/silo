"""
Fixtures pour les tests du projet SILO.
Initialise les ressources partagées (NLP, HTML mock) pour éviter les rechargements.
"""
import pytest
import spacy


@pytest.fixture(scope="session")
def mock_nlp():
    """
    Instance unique de spacy pour tous les tests.
    Évite de recharger le modèle à chaque test (coûteux en temps).
    """
    nlp = spacy.load("fr_core_news_md")
    return nlp


@pytest.fixture
def mock_html_simple():
    """
    Fragment HTML simple pour les tests basiques.
    Contient du contenu éditorial minimal.
    """
    return """
    <html>
        <body>
            <main>
                <article>
                    <p>Nous vendons une superbe voiture occasion.</p>
                </article>
            </main>
        </body>
    </html>
    """


@pytest.fixture
def mock_html_complex():
    """
    Document HTML complet simulant une vraie page web.
    Contient : Header, Nav, Sidebar, Footer, Scripts, et Contenu imbriqué.
    Utilisé pour tester l'exclusion des zones non-éditoriales.
    """
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <title>Page de Test - Voiture Occasion</title>
        <script>console.log('tracking');</script>
    </head>
    <body>
        <header>
            <nav>
                <ul>
                    <li><a href="/">Voiture occasion</a></li>
                    <li><a href="/contact">Contact</a></li>
                </ul>
            </nav>
        </header>
        
        <main>
            <article class="entry-content">
                <h1>Bienvenue</h1>
                <p>Nous vendons une superbe voiture occasion.</p>
                <p>Découvrez notre gamme de <a href="/achat">voiture occasion pas chère</a> dès maintenant.</p>
                <section>
                    <p>Notre sélection de voiture occasion est exceptionnelle.</p>
                </section>
            </article>
        </main>
        
        <aside class="sidebar">
            <div class="widget">
                <p>Publicité : voiture occasion à vendre</p>
            </div>
        </aside>
        
        <footer>
            <p>Copyright Voiture occasion 2024</p>
            <nav>
                <a href="/mentions">Mentions légales</a>
            </nav>
        </footer>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                console.log('Page loaded');
            });
        </script>
    </body>
    </html>
    """


@pytest.fixture
def mock_html_nested_links():
    """
    HTML spécifique pour tester la protection contre les liens imbriqués.
    Contient un lien existant qui englobe le texte cible.
    """
    return """
    <html>
        <body>
            <main>
                <article>
                    <p>Découvrez notre gamme de <a href="/achat">voiture occasion pas chère</a> dès maintenant.</p>
                </article>
            </main>
        </body>
    </html>
    """
