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
- 💾 Cache local des imports GSC par propriété, période, pays, device et limite de lignes
- 🚦 Filtrage optionnel via export Screaming Frog `Internal > HTML` pour garder uniquement les URLs `200` et indexables
- 🔍 Test du parser HTML en temps réel
- 🧠 Test du moteur NLP avec exemples
- 🚀 Pipeline complet avec export CSV

**Cache GSC :**
- Les imports Search Console sont stockés dans `.runtime/gsc_cache/`, dossier ignoré par Git.
- Si les paramètres GSC sont identiques, SILO réutilise le CSV local au lieu de rappeler l'API.
- Cochez `Forcer une nouvelle requête GSC` pour rafraîchir les données, ou utilisez `Vider cache GSC` pour repartir de zéro.

**Imports ZIP volumineux :**
- La limite Streamlit est configurée à **1 Go** via `.streamlit/config.toml` (`server.maxUploadSize = 1024`).
- L'archive HTML est sauvegardée sur disque temporaire au moment de l'import, au lieu d'être conservée en mémoire dans la session.
- Pour des ZIP très lourds, privilégier le lancement local avec suffisamment de RAM plutôt que Streamlit Community Cloud.

### Ligne de commande

Exécuter le pipeline complet :
```bash
python -m src.silo_linker \
    --gsc-csv data/input/gsc_data.csv \
    --html-zip data/input/html_export.zip \
    --crawl-csv data/input/screaming-frog-internal-html.csv \
    --html-prefix rendu_ \
    --output data/output/opportunities_export.csv
```

**Arguments :**
- `--gsc-csv` : Chemin vers le fichier CSV Google Search Console (requis)
- `--html-zip` : Chemin vers l'archive ZIP HTML (requis) - Le mapping sera généré automatiquement
- `--crawl-csv` : Export Screaming Frog `Internal > HTML` optionnel avec `Address`, `Status Code` et `Indexability`
- `--html-prefix` : Préfixe des fichiers HTML dans le ZIP (défaut: `rendu_`)
- `--output` : Chemin du fichier de sortie (défaut: `opportunities_export.csv`)

**Note :** Le mapping HTML est généré automatiquement depuis les noms de fichiers dans le ZIP. Vous n'avez plus besoin de fournir un fichier CSV de mapping séparé.
Si `--crawl-csv` est fourni, SILO exclut les pages sources et cibles qui ne sont pas en `200` ou qui ne sont pas `Indexable`.

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
| `Priority` | Priorité opérationnelle | High |
| `Final_Score` | Score final combinant potentiel SEO, qualité éditoriale et confiance technique | 82 |
| `Risk_Level` | Niveau de risque à vérifier | Medium |
| `Priority_Target` | Indique si la cible correspond aux critères GSC prioritaires | Yes |
| `Keyword_GSC` | Mot-clé déclencheur | formation seo |
| `Suggested_Anchor` | Ancre courte proposée | formation SEO |
| `Anchor_Context` | Contexte court autour de l'ancre | choisir une formation SEO adaptée |
| `Source_URL` | Page où placer le lien | site.com/blog/article-1 |
| `Target_URL` | Page vers laquelle faire le lien | site.com/services/formation |
| `Source_Type` | Typologie de la source | editorial |
| `Target_Type` | Typologie de la cible | business |
| `Clicks` | Clics GSC de la requête | 30 |
| `Impressions` | Impressions GSC de la requête | 1000 |
| `Position` | Position moyenne GSC | 8.4 |
| `SEO_Potential_Score` | Potentiel SEO calculé | 76 |
| `Editorial_Fit_Score` | Qualité éditoriale de l'ancre et du contexte | 84 |
| `Decision_Reason` | Justification exploitable de la recommandation | cible prioritaire GSC; fort potentiel SEO |

Le tableau de validation Streamlit et le CSV final utilisent les mêmes colonnes métier. Les anciennes colonnes techniques `Anchor_Text`, `XPath` et `Similarity_Type` restent hors export standard.

## 🧠 Cache et instance locale

- Le cache GSC évite de relancer une requête Search Console quand les paramètres sont inchangés.
- Le cache d'analyse évite de retraiter le ZIP HTML si les imports et le préfixe n'ont pas changé.
- En local, utilisez un seul port Streamlit actif pour éviter de tester une ancienne instance :

```bash
streamlit run app.py --server.port 8609
```

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
