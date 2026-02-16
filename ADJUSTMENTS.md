# 🔧 Ajustements Basés sur les Données Réelles

Ce document décrit les ajustements apportés au code après l'analyse des fichiers d'exemple fournis.

## 📁 Structure des Fichiers d'Exemple

### Fichiers HTML (ZIP)

**Format de nommage :**
- `rendu_https_lilycare.fr_.html` → Page d'accueil (`https://lilycare.fr/`)
- `rendu_https_lilycare.fr_a-propos-de-lilycare.html` → `https://lilycare.fr/a-propos-de-lilycare`
- `rendu_https_lilycare.fr_blog_arret-de-travail-carpimko.html` → `https://lilycare.fr/blog/arret-de-travail-carpimko`

**Règles de parsing :**
1. Préfixe : `rendu_` ou `original_` (à ignorer)
2. Format : `{prefix}https_{domain}_{path}.html`
3. Les underscores (`_`) dans le path représentent des slashes (`/`) dans l'URL
4. Page d'accueil : se termine par `_` (ex: `https_lilycare.fr_`)

**Exemples :**
- `rendu_https_lilycare.fr_.html` → `https://lilycare.fr/`
- `rendu_https_lilycare.fr_blog_article.html` → `https://lilycare.fr/blog/article`
- `rendu_https_lilycare.fr_a-propos.html` → `https://lilycare.fr/a-propos`

### Fichier GSC

**Format :** Fichier Numbers (.numbers)
- Format binaire d'Apple
- Nécessite une exportation manuelle en CSV depuis Numbers
- Script `scripts/extract_gsc.py` fourni (fonctionnalité expérimentale)

## 🔨 Modifications Apportées

### 1. Nouveau Module `src/utils.py`

Fonctions utilitaires ajoutées :
- `generate_mapping_from_zip()` : Génère automatiquement le mapping CSV depuis un ZIP HTML
- `parse_html_filename()` : Parse les noms de fichiers HTML pour reconstruire les URLs
- `extract_gsc_from_numbers()` : Tente d'extraire le CSV depuis un fichier Numbers

### 2. Script `scripts/generate_mapping.py`

Script en ligne de commande pour générer le mapping :
```bash
python scripts/generate_mapping.py "HTML Rendu.zip" -o html_mapping.csv -p "rendu_"
```

**Fonctionnalités :**
- Parse automatiquement les noms de fichiers dans le ZIP
- Reconstruit les URLs correctement
- Ignore les fichiers `__MACOSX/` (métadonnées macOS)
- Génère un CSV prêt à l'emploi

### 3. Amélioration de `src/data_loader.py`

- Ajout de la gestion des fichiers `__MACOSX/` dans les ZIP
- Meilleure gestion des erreurs lors de la lecture des fichiers HTML

### 4. Mise à Jour de l'Application Streamlit

**Nouvelles fonctionnalités :**
- Support des fichiers Numbers (.numbers) pour GSC (avec avertissement)
- Génération automatique du mapping depuis un ZIP HTML
- Interface améliorée avec options radio pour choisir le mode de mapping

### 5. Documentation Mise à Jour

- `README.md` : Ajout d'informations sur la génération automatique du mapping
- `scripts/README.md` : Documentation des scripts utilitaires

## 📊 Format de Mapping Généré

Le mapping CSV généré suit ce format :

```csv
URL,FilePath
https://lilycare.fr/,rendu_https_lilycare.fr_.html
https://lilycare.fr/a-propos-de-lilycare,rendu_https_lilycare.fr_a-propos-de-lilycare.html
https://lilycare.fr/blog/arret-de-travail-carpimko,rendu_https_lilycare.fr_blog_arret-de-travail-carpimko.html
```

## ✅ Tests

Tous les tests existants passent toujours :
```bash
pytest tests/ -v
# ========================== 16 passed ==========================
```

## 🚀 Utilisation

### Génération du Mapping

```bash
# Depuis le ZIP "HTML Rendu.zip"
python scripts/generate_mapping.py "exemple-file/HTML Rendu.zip" -o html_mapping.csv -p "rendu_"

# Depuis le ZIP "HTLM.zip" (original)
python scripts/generate_mapping.py "exemple-file/HTLM.zip" -o html_mapping_original.csv -p "original_"
```

### Utilisation avec le Pipeline

Une fois le mapping généré, utilisez-le normalement :

```bash
python -m src.silo_linker \
    --gsc-csv gsc_export.csv \
    --html-mapping-csv html_mapping.csv \
    --html-zip "HTML Rendu.zip" \
    --output opportunities_export.csv
```

## 📝 Notes Importantes

1. **Fichiers Numbers** : L'extraction automatique depuis Numbers est expérimentale. Il est recommandé d'exporter manuellement en CSV depuis l'application Numbers.

2. **Préfixes** : Vérifiez le préfixe de vos fichiers HTML (`rendu_` ou `original_`) avant de générer le mapping.

3. **Fichiers __MACOSX** : Ces fichiers sont automatiquement ignorés lors du traitement.

4. **Encodage** : Les fichiers HTML sont lus en UTF-8 avec fallback sur latin-1 en cas d'erreur.

## 🔍 Validation

Pour valider que le mapping est correct, vérifiez quelques URLs :
```bash
# Vérifier que les URLs sont bien formatées
head -10 html_mapping.csv
```

Les URLs doivent :
- Commencer par `https://`
- Avoir des slashes (`/`) dans les chemins (pas d'underscores)
- Correspondre aux URLs canoniques dans les fichiers HTML
