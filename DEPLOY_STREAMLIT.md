# Déployer SILO sur Streamlit Community Cloud

## Prérequis

- Un compte [Streamlit Community Cloud](https://share.streamlit.io/)
- Le dépôt **silo** poussé sur GitHub (public)

## Étapes

### 1. Aller sur Streamlit Cloud

1. Ouvre **https://share.streamlit.io/**
2. Clique sur **Sign up** ou connecte-toi avec GitHub.

### 2. Créer une nouvelle app

1. Clique sur **New app**.
2. Renseigne :
   - **Repository** : `TON_USERNAME/silo` (ton compte GitHub + nom du repo).
   - **Branch** : `main`.
   - **Main file path** : `app.py`.
3. **Advanced settings** (optionnel) :
   - **Python version** : 3.9 ou 3.10 (recommandé).
4. Clique sur **Deploy**.

### 3. Premier déploiement

- Streamlit Cloud installe les dépendances depuis `requirements.txt` (dont le modèle spaCy français).
- Le premier déploiement peut prendre **5–10 minutes** (téléchargement du modèle NLP).
- Une fois terminé, l’app est accessible via une URL du type :  
  `https://ton-app-xxx.streamlit.app`

## Fichiers utilisés pour le déploiement

| Fichier | Rôle |
|--------|------|
| `app.py` | Point d’entrée de l’app Streamlit |
| `requirements.txt` | Dépendances Python + modèle spaCy `fr_core_news_md` |
| `.streamlit/config.toml` | Config serveur (headless, etc.) |

## En cas de problème

- **Erreur « Module not found »** : vérifier que toutes les dépendances sont dans `requirements.txt`.
- **Erreur spaCy « Can't find model »** : la ligne du modèle dans `requirements.txt` doit pointer vers le wheel (déjà ajouté).
- **Timeout au démarrage** : le premier lancement est long à cause du modèle ; les suivants sont plus rapides.

## Limites Streamlit Community Cloud

- Upload configuré à **1 Go** dans `.streamlit/config.toml` (`server.maxUploadSize = 1024`).
- Mémoire limitée : même si l'upload dépasse 200 Mo, éviter les CSV/HTML excessivement lourds sur Streamlit Community Cloud.
- Timeout des scripts : le pipeline peut être interrompu après plusieurs minutes ; privilégier des exports (ZIP/CSV) de taille raisonnable.
