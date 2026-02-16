# Scripts Utilitaires SILO

Ce dossier contient des scripts utilitaires pour faciliter l'utilisation du pipeline SILO.

## 📋 Scripts Disponibles

### `generate_mapping.py`

Génère automatiquement un fichier CSV de mapping à partir d'un ZIP HTML exporté depuis Screaming Frog.

**Format de nommage supporté :**
- `rendu_https_lilycare.fr_.html` → `https://lilycare.fr/`
- `rendu_https_lilycare.fr_a-propos-de-lilycare.html` → `https://lilycare.fr/a-propos-de-lilycare`

**Utilisation :**
```bash
python scripts/generate_mapping.py "exemple-file/HTML Rendu.zip" -o html_mapping.csv -p "rendu_"
```

**Options :**
- `-o, --output` : Chemin du fichier CSV de sortie (défaut: `html_mapping.csv`)
- `-p, --prefix` : Préfixe des fichiers HTML (défaut: `rendu_`)

**Exemple :**
```bash
# Pour les fichiers "rendu_"
python scripts/generate_mapping.py "HTML Rendu.zip" -o mapping_rendu.csv -p "rendu_"

# Pour les fichiers "original_"
python scripts/generate_mapping.py "HTLM.zip" -o mapping_original.csv -p "original_"
```

### `extract_gsc.py`

Tente d'extraire le CSV GSC depuis un fichier Numbers (.numbers).

**Note :** Les fichiers Numbers utilisent un format binaire complexe. Ce script tente de trouver des données CSV, mais il est **recommandé d'exporter manuellement depuis Numbers en CSV**.

**Utilisation :**
```bash
python scripts/extract_gsc.py "exemple-file/export_gsc.numbers" -o gsc_export.csv
```

**Options :**
- `-o, --output` : Chemin du fichier CSV de sortie (défaut: `gsc_export.csv`)

**Recommandation :**
Si le script ne fonctionne pas, exportez manuellement :
1. Ouvrez le fichier Numbers dans l'application Numbers
2. Fichier > Exporter vers > CSV...
3. Utilisez le fichier CSV exporté

## 🔧 Dépendances

Ces scripts utilisent les modules du projet SILO (`src/`), assurez-vous d'être dans le répertoire racine du projet lors de l'exécution.
