Product Requirement Document (PRD) : Semantic Internal Linker (SILO)
====================================================================

**Date :** 12 Janvier 2026

**Version :** 1.0

**Owner :** Lead Data Scientist SEO

**Statut :** Draft / Ready for Dev

1\. Vision & Objectif
---------------------

Développer un pipeline ETL (Extract, Transform, Load) automatisé en Python capable d'identifier des opportunités de maillage interne à haute valeur ajoutée.

L'outil doit croiser la **demande réelle** (mots-clés performants issus de la GSC) avec **l'offre de contenu** (paragraphes de texte issus d'un crawl Screaming Frog). L'objectif est de pousser les pages stratégiques ("Money Pages") en détectant sémantiquement des ancres pertinentes dans le corps du texte des pages éditoriales, tout en excluant les éléments de navigation.

2\. Architecture des Données (Inputs)
-------------------------------------

### 2.1. Google Search Console (Demand Side)

*   **Format :** Fichier CSV ou API Dataframe.
    
*   **Granularité :** Par Page et par Query.
    
*   **Colonnes Requises :** Page (URL), Query (Mot-clé), Impressions, Clicks, Position.
    
*   **Critères de Qualité :**
    
    *   Les données doivent être nettoyées des "Brand queries".
        
    *   Focus sur les positions "frappantes" (ex: Top 20) ou fort potentiel de trafic.
        

### 2.2. Contenu HTML (Supply Side)

*   **Format :** Archive .zip (Export Screaming Frog "Bulk Export > HTML > Source").
    
*   **Mapping :** Un fichier CSV (internal\_html.csv) faisant la correspondance entre URL Publique <-> Chemin du fichier local.
    
*   **Contrainte :** Le contenu analysé doit être le **Rendu HTML** (ou source si le contenu est server-side) pour garantir que le texte est visible.
    

3\. Logique Algorithmique & Data Science
----------------------------------------

### 3.1. Parsing HTML & Ciblage DOM (Surgical Extraction)

L'outil ne doit pas être "aveugle". Il doit distinguer le contenu éditorial du bruit.

*   **Bibliothèque recommandée :** lxml (pour la performance et le support XPath complet).
    
*   **Sélecteurs d'Inclusion (Allowlist) :**
    
    *   Le texte doit provenir de balises sémantiques de contenu :
        
        ,
        
    *   ,
        
        ,
        
        > , .
        
    *   Ces balises doivent idéalement être enfants de
        
        ,
        
        , ou de div identifiés comme contenu (ex: class="entry-content").
        
*   **Sélecteurs d'Exclusion (Blocklist) :**
    
    *   Exclusion stricte des zones structurelles :
        
        ,
        
        ,
        
        ,
        
        , .sidebar, .menu, .comments.
        
    *   **Règle Critique :** Si le texte parent contient déjà une balise chevauchant l'opportunité détectée, ignorer (pas de lien dans un lien).
        
*   **Output Technique :** Pour chaque segment de texte identifié, extraire le **XPath absolu** permettant de retrouver précisément l'élément dans le DOM.
    

### 3.2. Moteur NLP & Fuzzy Matching (Le Cœur du Système)

Le matching strict (String Exact Match) est interdit. L'outil doit appliquer une tolérance linguistique pour maximiser les opportunités.

*   **Stack NLP :** spaCy (Modèle: fr\_core\_news\_md ou lg).
    
*   **Pipeline de Traitement :**
    
    1.  **Tokenization :** Découpage des phrases en mots.
        
    2.  **Stop-word Removal :** Suppression du bruit ("le", "la", "de", "pour", etc.).
        
    3.  **Lemmatization :** Transformation des mots en leur forme canonique (ex: "achetées" -> "acheter", "chevaux" -> "cheval").
        
*   **Algorithme de "Sliding Window" (Fenêtre Glissante) :**
    
    *   Soit $K$ la liste des lemmes du mot-clé GSC (ex: "voiture", "occasion").
        
    *   Soit $T$ la liste des lemmes du paragraphe source.
        
    *   L'algorithme doit scanner $T$ avec une fenêtre de taille $N$ (où $N = len(K) + \\delta$).
        
    *   $\\delta$ est la tolérance (ex: +2 mots) permettant des mots intercalés.
        
    *   _Exemple :_
        
        *   Query GSC : "Assurance Vie" -> Lemmes : \[assurance, vie\]
            
        *   Texte : "La meilleure **assurance** pour la **vie** courante."
            
        *   Match : Positif (malgré les mots intercalés).
            

4\. Règles Métier & Contraintes (Business Logic)
------------------------------------------------

1.  **Anti-Cannibalisation (Self-Reference) :**
    
    *   IF Source\_URL == Target\_URL THEN Skip.
        
    *   Une page ne doit jamais se faire de lien vers elle-même.
        
2.  **Unicité du Lien :**
    
    *   Une Source\_URL ne doit faire qu'**un seul lien** vers une Target\_URL spécifique. (On évite de spammer 5 liens vers la même page dans un article).
        
    *   Prioriser l'occurrence la plus haute dans le code (premier paragraphe).
        
3.  **Distinction Navigationnelle vs Contextuelle :**
    
    *   L'utilisation stricte du XPath et des balises (
        
        ) garantit que le lien est contextuel (dans le flux de lecture) et non navigationnel (menu/footer).
        
4.  **Priorisation des Targets :**
    
    *   Si un mot-clé correspond à plusieurs Pages Cibles potentielles dans la GSC, l'outil doit élire la **"Best Match URL"** (celle avec le plus de trafic ou la meilleure position) pour éviter de diluer le jus.
        

5\. Spécifications de Sortie (Deliverables)
-------------------------------------------

L'outil doit générer un fichier opportunities\_export.csv contenant :

Champ

Description

Exemple

**Score**

Métrique de priorisation (basée sur Vol. Recherche GSC)

85/100

**Keyword\_GSC**

Le mot-clé déclencheur (Target Query)

formation seo

**Source\_URL**

La page où placer le lien

site.com/blog/article-1

**Target\_URL**

La page vers laquelle faire le lien

site.com/services/formation

**Anchor\_Text**

Le texte exact trouvé dans le HTML (incluant flexions)

une formation au référencement

**Context\_Snippet**

Le paragraphe complet (pour validation humaine)

...Il est vital de suivre \*\*une formation au référencement\*\* pour...

**XPath**

Chemin technique pour injection ou repérage

/html/body/main/div/p\[3\]

**Similarity\_Type**

Type de match

Lemma\_Fuzzy ou Exact

6\. Guide d'Implémentation pour le Développeur (Cursor Context)
---------------------------------------------------------------

> _Copiez cette section dans le chat de votre IDE pour lancer le développement._

**Rôle :** Tu es un Expert Python Senior spécialisé en NLP et SEO Technique.

**Tâche :** Implémenter le script silo\_linker.py selon les spécifications ci-dessus.

**Instructions Techniques Spécifiques :**

1.  **Classe DataLoader :**
    
    *   Charge le CSV GSC.
        
    *   Charge le mapping HTML.
        
    *   Implémente un générateur pour lire les fichiers HTML un par un (pour économiser la RAM).
        
2.  **Classe ContentParser :**
    
    *   Utilise lxml.html.
        
    *   Crée une méthode extract\_valid\_paragraphs(html\_content) qui retourne une liste de tuples (texte\_brut, xpath).
        
    *   Assure-toi de nettoyer les espaces blancs et les retours à la ligne.
        
3.  **Classe NLPMatcher :**
    
    *   Initialise spacy.load('fr\_core\_news\_md') une seule fois.
        
    *   Prépare les "Patterns" à partir des mots-clés GSC (lemmatisation pré-calculée).
        
    *   Utilise Matcher de Spacy ou une logique custom de fenêtre glissante sur les lemmes.
        
4.  **Main Loop :**
    
    *   Itère sur chaque fichier HTML.
        
    *   Extrait les paragraphes.
        
    *   Compare avec le dictionnaire des mots-clés cibles.
        
    *   Stocke les résultats dans une liste de dictionnaires.
        
    *   Exporte en CSV/Pandas.
        

**Attention :** Le script doit gérer les erreurs d'encodage (UTF-8) et être robuste aux fichiers HTML mal formés.