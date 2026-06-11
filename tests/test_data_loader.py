"""
Tests unitaires pour le chargeur de données (DataLoader).
"""
import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from src.data_loader import DataLoader
from src.utils import parse_html_filename


@pytest.fixture
def sample_gsc_csv():
    """Crée un CSV GSC de test."""
    data = {
        'Page': ['https://example.com/page1', 'https://example.com/page2', 'https://example.com/page1'],
        'Query': ['voiture occasion', 'formation seo', 'voiture occasion'],
        'Impressions': [1000, 500, 800],
        'Clicks': [50, 30, 40],
        'Position': [5.2, 8.1, 6.3]
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_html_mapping_csv():
    """Crée un CSV de mapping HTML de test."""
    data = {
        'URL': ['https://example.com/page1', 'https://example.com/page2'],
        'FilePath': ['/tmp/page1.html', '/tmp/page2.html']
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_gsc_file(sample_gsc_csv):
    """Crée un fichier CSV GSC temporaire."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_gsc_csv.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_mapping_file(sample_html_mapping_csv):
    """Crée un fichier CSV de mapping temporaire."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_html_mapping_csv.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_html_zip():
    """Crée un ZIP HTML temporaire pour les tests."""
    import zipfile
    
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        zip_path = tmp_zip.name
    
    # Créer un ZIP avec des fichiers HTML de test
    with zipfile.ZipFile(zip_path, 'w') as zip_ref:
        # Fichier 1 : page d'accueil
        zip_ref.writestr(
            'rendu_https_example.com_.html',
            '<html><body><main><p>Page d\'accueil</p></main></body></html>'
        )
        # Fichier 2 : autre page
        zip_ref.writestr(
            'rendu_https_example.com_page1.html',
            '<html><body><main><p>Page 1</p></main></body></html>'
        )
        # Fichier 3 : page avec chemin
        zip_ref.writestr(
            'rendu_https_example.com_blog_article.html',
            '<html><body><main><p>Article</p></main></body></html>'
        )
    
    yield zip_path
    os.unlink(zip_path)


@pytest.fixture
def temp_crawl_csv():
    """Crée un export crawl Screaming Frog minimal."""
    crawl_data = pd.DataFrame({
        'Address': [
            'https://example.com/',
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/blog/article',
        ],
        'Status Code': [200, 200, 301, 404],
        'Indexability': ['Indexable', 'Indexable', 'Non-Indexable', 'Non-Indexable'],
    })
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        crawl_data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_french_crawl_csv():
    """Crée un export crawl Screaming Frog en français."""
    crawl_data = pd.DataFrame({
        'Adresse': [
            'https://example.com/',
            'https://example.com/page1',
            'https://example.com/page2',
        ],
        'Code HTTP': [200, 200, 301],
        'Indexabilité': ['Indexable', 'Indexable', 'Non-Indexable'],
    })
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
        crawl_data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_extended_crawl_csv():
    """Crée un export crawl avec robots et canonical."""
    crawl_data = pd.DataFrame({
        'Address': [
            'https://example.com/page1',
            'https://example.com/noindex',
            'https://example.com/canonicalized',
        ],
        'Status Code': [200, 200, 200],
        'Indexability': ['Indexable', 'Indexable', 'Indexable'],
        'Meta Robots': ['', 'noindex,follow', ''],
        'Canonical Link Element 1': [
            'https://example.com/page1',
            'https://example.com/noindex',
            'https://example.com/preferred',
        ],
        'Crawl Depth': [1, 2, 3],
        'Unique Inlinks': [10, 2, 1],
    })
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
        crawl_data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


class TestDataLoader:
    """Tests pour DataLoader."""
    
    def test_load_gsc_data(self, temp_gsc_file, temp_html_zip):
        """Test le chargement des données GSC."""
        loader = DataLoader(temp_gsc_file, temp_html_zip, html_prefix='rendu_')
        df = loader.load_gsc_data()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert 'Page' in df.columns
        assert 'Query' in df.columns
        assert 'Clicks' in df.columns
    
    def test_load_html_mapping(self, temp_html_zip):
        """Test la génération automatique du mapping HTML depuis le ZIP."""
        loader = DataLoader('/tmp/gsc.csv', temp_html_zip, html_prefix='rendu_')
        df = loader.load_html_mapping()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3  # 3 fichiers HTML dans le ZIP de test
        assert 'URL' in df.columns
        assert 'FilePath' in df.columns
        # Vérifier que les URLs sont correctement reconstruites
        assert 'https://example.com/' in df['URL'].values
        assert 'https://example.com/page1' in df['URL'].values
        assert 'https://example.com/blog/article' in df['URL'].values

    def test_load_html_mapping_filters_non_indexable_urls(self, temp_html_zip, temp_crawl_csv):
        """Test que les sources non 200/indexables sont exclues du mapping HTML."""
        loader = DataLoader('/tmp/gsc.csv', temp_html_zip, html_prefix='rendu_', crawl_csv_path=temp_crawl_csv)
        df = loader.load_html_mapping()

        assert 'https://example.com/' in df['URL'].values
        assert 'https://example.com/page1' in df['URL'].values
        assert 'https://example.com/blog/article' not in df['URL'].values

    def test_load_gsc_data_filters_non_indexable_targets(self, temp_gsc_file, temp_html_zip, temp_crawl_csv):
        """Test que les cibles GSC non 200/indexables sont exclues."""
        loader = DataLoader(temp_gsc_file, temp_html_zip, html_prefix='rendu_', crawl_csv_path=temp_crawl_csv)
        df = loader.load_gsc_data()

        assert set(df['Page'].unique()) == {'https://example.com/page1'}

    def test_load_indexable_urls_accepts_french_screaming_frog_headers(self, temp_french_crawl_csv):
        """Test les intitulés français de Screaming Frog."""
        loader = DataLoader('/tmp/gsc.csv', '/tmp/html.zip', crawl_csv_path=temp_french_crawl_csv)
        indexable_urls = loader.load_indexable_urls()

        assert 'https://example.com/' in indexable_urls
        assert 'https://example.com/page1' in indexable_urls
        assert 'https://example.com/page2' not in indexable_urls

    def test_crawl_metadata_excludes_noindex_and_canonical_mismatch(self, temp_extended_crawl_csv):
        """Test que robots noindex et canonical differente excluent les URLs."""
        loader = DataLoader('/tmp/gsc.csv', '/tmp/html.zip', crawl_csv_path=temp_extended_crawl_csv)
        metadata = loader.load_crawl_metadata()
        indexable_urls = loader.load_indexable_urls()

        assert metadata['https://example.com/page1']['crawl_depth'] == '1'
        assert 'https://example.com/page1' in indexable_urls
        assert 'https://example.com/noindex' not in indexable_urls
        assert 'https://example.com/canonicalized' not in indexable_urls

    def test_parse_html_filename_preserves_query_parameter_underscores(self):
        """Test que les underscores des paramètres de query ne deviennent pas des slashes."""
        url = parse_html_filename(
            "original_https_www.meilleurtaux.com_demande-simulation_credit-consommation_"
            "%3Ftp%3D4%26montant_projet%3D20000%26duree_pret%3D72.html",
            prefix="original_",
        )

        assert url == (
            "https://www.meilleurtaux.com/demande-simulation/credit-consommation/"
            "?tp=4&montant_projet=20000&duree_pret=72"
        )

    def test_parse_html_filename_handles_query_after_html_path(self):
        """Test les URLs où la query suit une page HTML."""
        url = parse_html_filename(
            "original_https_www.meilleurtaux.com_a-propos-de-meilleurtaux_"
            "contactez-nous.html%3Finterest%3Dfranchise.html",
            prefix="original_",
        )

        assert url == (
            "https://www.meilleurtaux.com/a-propos-de-meilleurtaux/"
            "contactez-nous.html?interest=franchise"
        )
    
    def test_get_keywords_dict(self, temp_gsc_file, temp_html_zip):
        """Test la construction du dictionnaire de mots-clés."""
        loader = DataLoader(temp_gsc_file, temp_html_zip, html_prefix='rendu_')
        keywords_dict = loader.get_keywords_dict()
        
        assert isinstance(keywords_dict, dict)
        assert 'https://example.com/page1' in keywords_dict
        # Vérifier que les mots-clés sont groupés par URL
        assert 'voiture occasion' in keywords_dict['https://example.com/page1']
    
    def test_missing_columns_raises_error(self, temp_html_zip):
        """Test qu'une erreur est levée si des colonnes sont manquantes."""
        # Créer un CSV avec des colonnes manquantes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            pd.DataFrame({'Page': ['url1'], 'Query': ['keyword1']}).to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            loader = DataLoader(temp_file, temp_html_zip, html_prefix='rendu_')
            with pytest.raises(ValueError, match="Colonnes manquantes"):
                loader.load_gsc_data()
        finally:
            os.unlink(temp_file)
