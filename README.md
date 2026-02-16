# 🔗 SILO - Semantic Internal Link Optimizer

Pipeline ETL automatisé en Python pour identifier des opportunités de maillage interne à haute valeur ajoutée.

## 📋 Description

SILO croise la **demande réelle** (mots-clés performants issus de Google Search Console) avec **l'offre de contenu** (paragraphes de texte issus d'un crawl Screaming Frog) pour détecter sémantiquement des ancres pertinentes dans le corps du texte des pages éditoriales.

## ✨ Fonctionnalités

- ✅ Extraction chirurgicale du contenu éditorial (exclusion nav/footer/sidebar)
- ✅ Protection contre les liens imbriqués (pas de lien dans un lien)
- ✅ Matching sémantique avec tolérance linguistique (flexions, stop-words)
- ✅ Fenêtre glissante pour gérer les mots intercalés
- ✅ Anti-cannibalisation (pas d'auto-référence)
- ✅ Priorisation des targets (best match)
- ✅ Limitation du volume (1 lien par paire source→target)

## 🚀 Installation

### Prérequis

- Python 3.9+
- pip

### Étapes

1. **Cloner le repository** (ou utiliser le dossier existant)

2. **Créer l'environnement virtuel** :
```bash
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

3. **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

4. **Télécharger le modèle spaCy français** :
```bash
python -m spacy download fr_core_news_md
```

## 🧪 Tests

Exécuter tous les tests :
```bash
pytest tests/ -v
```

Exécuter un fichier de tests spécifique :
```bash
pytest tests/test_parser.py -v
pytest tests/test_nlp.py -v
pytest tests/test_data_loader.py -v
pytest tests/test_logic.py -v
```

## 💻 Utilisation

### Application Streamlit (Interface Web)

Lancer l'application web pour tester le pipeline :
```bash
streamlit run app.py
```

L'application s'ouvrira dans votre navigateur à `http://localhost:8501`

**Fonctionnalités de l'app :**
- 📊 Chargement des données GSC et mapping HTML
- 🔍 Test du parser HTML en temps réel
- 🧠 Test du moteur NLP avec exemples
- 🚀 Pipeline complet avec export CSV

### Ligne de commande

Exécuter le pipeline complet :
```bash
python -m src.silo_linker \
    --gsc-csv data/input/gsc_data.csv \
    --html-zip data/input/html_export.zip \
    --html-prefix rendu_ \
    --output data/output/opportunities_export.csv
```

**Arguments :**
- `--gsc-csv` : Chemin vers le fichier CSV Google Search Console (requis)
- `--html-zip` : Chemin vers l'archive ZIP HTML (requis) - Le mapping sera généré automatiquement
- `--html-prefix` : Préfixe des fichiers HTML dans le ZIP (défaut: `rendu_`)
- `--output` : Chemin du fichier de sortie (défaut: `opportunities_export.csv`)

**Note :** Le mapping HTML est généré automatiquement depuis les noms de fichiers dans le ZIP. Vous n'avez plus besoin de fournir un fichier CSV de mapping séparé.

## 📁 Structure du Projet

```
silo/
├── src/
│   ├── parser.py          # Parser HTML (extraction contenu éditorial)
│   ├── data_loader.py    # Chargeur de données (GSC, mapping)
│   ├── nlp_matcher.py    # Moteur NLP (matching sémantique)
│   └── silo_linker.py     # Script principal (orchestration)
├── tests/
│   ├── conftest.py       # Fixtures pytest
│   ├── test_parser.py    # Tests parser HTML
│   ├── test_nlp.py       # Tests moteur NLP
│   ├── test_data_loader.py  # Tests chargeur de données
│   └── test_logic.py     # Tests règles métier
├── data/
│   ├── input/            # Données d'entrée
│   └── output/           # Résultats générés
├── app.py                # Application Streamlit
├── requirements.txt      # Dépendances Python
├── PRD.md               # Product Requirement Document
├── TEST_SPEC.md         # Spécifications des tests
└── README.md            # Ce fichier
```

## 📊 Format des Données d'Entrée

### CSV Google Search Console

Colonnes requises :
- `Page` : URL de la page
- `Query` : Mot-clé de recherche
- `Impressions` : Nombre d'impressions
- `Clicks` : Nombre de clics
- `Position` : Position moyenne

**Note :** Si vous avez un fichier Numbers (.numbers), exportez-le manuellement en CSV depuis l'application Numbers, ou utilisez le script `scripts/extract_gsc.py` (fonctionnalité expérimentale).

### Archive ZIP HTML

**Format attendu :** Archive ZIP contenant les fichiers HTML exportés depuis Screaming Frog.

**Nommage des fichiers :** Les fichiers doivent suivre le format :
- `rendu_https_lilycare.fr_.html` → `https://lilycare.fr/`
- `rendu_https_lilycare.fr_a-propos.html` → `https://lilycare.fr/a-propos`
- `rendu_https_lilycare.fr_blog_article.html` → `https://lilycare.fr/blog/article`

**Génération automatique du mapping :** Le mapping est généré automatiquement par le système. Vous n'avez pas besoin de créer un fichier CSV de mapping manuellement.

**Préfixe :** Par défaut, le système cherche les fichiers avec le préfixe `rendu_`. Si vos fichiers utilisent un autre préfixe (ex: `original_`), utilisez l'option `--html-prefix`.

## 📤 Format de Sortie

Le fichier `opportunities_export.csv` contient :

| Colonne | Description | Exemple |
|---------|-------------|---------|
| `Score` | Métrique de priorisation (0-100) | 85 |
| `Keyword_GSC` | Mot-clé déclencheur | formation seo |
| `Source_URL` | Page où placer le lien | site.com/blog/article-1 |
| `Target_URL` | Page vers laquelle faire le lien | site.com/services/formation |
| `Anchor_Text` | Texte exact trouvé | une formation au référencement |
| `Context_Snippet` | Paragraphe complet | ...Il est vital de suivre **une formation au référencement** pour... |
| `XPath` | Chemin technique pour injection | /html/body/main/div/p[3] |
| `Similarity_Type` | Type de match | Lemma_Fuzzy |

## 🔧 Configuration

### Tolérance NLP

Ajuster la tolérance pour les mots intercalés dans `src/nlp_matcher.py` :
```python
matcher = NLPMatcher(nlp_model=nlp, tolerance=2)  # 2 mots supplémentaires autorisés
```

### Zones Exclues

Modifier les zones exclues dans `src/parser.py` :
```python
EXCLUDED_TAGS = {'nav', 'header', 'footer', 'aside', 'script', 'style'}
```

## 📝 Documentation

- **PRD.md** : Spécifications complètes du produit
- **TEST_SPEC.md** : Spécifications détaillées des tests

## 🐛 Dépannage

### Erreur : "ModuleNotFoundError: No module named 'spacy'"
```bash
pip install spacy
python -m spacy download fr_core_news_md
```

### Erreur : "Colonnes manquantes dans le CSV GSC"
Vérifiez que votre CSV contient les colonnes : `Page`, `Query`, `Impressions`, `Clicks`, `Position`

### Erreur d'encodage
Le système essaie automatiquement UTF-8 puis latin-1. Si le problème persiste, convertissez votre CSV en UTF-8.

## 📄 Licence

Ce projet est un outil interne pour l'optimisation SEO.

## 👥 Contribution

Pour contribuer :
1. Créer une branche
2. Ajouter des tests pour les nouvelles fonctionnalités
3. S'assurer que tous les tests passent (`pytest tests/ -v`)
4. Créer une pull request

---

**Développé avec ❤️ pour l'optimisation SEO**
