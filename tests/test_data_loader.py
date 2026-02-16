"""
Tests unitaires pour le chargeur de données (DataLoader).
"""
import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from src.data_loader import DataLoader


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

