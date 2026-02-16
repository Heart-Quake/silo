Spécifications de Tests (QA & Validation Strategy) - SILO Project
=================================================================

**Version :** 1.0
**Objectif :** Ce document définit les cas de tests critiques pour valider le pipeline SILO (Semantic Internal Link Optimizer). L'objectif est de prévenir les régressions, les faux positifs (hallucinations) et de garantir la sécurité SEO (pas de liens cassés ou toxiques).

**Framework Requis :** pytest

1\. Fixtures & Environnement de Test
------------------------------------

Avant d'exécuter les tests, le script de test (tests/conftest.py) doit initialiser :

*   **mock\_nlp** : Une instance unique de spacy.load("fr\_core\_news\_md") (pour éviter de recharger le modèle à chaque test).
    
*   **mock\_html\_simple** : Un fragment HTML propre pour les tests basiques.
    
*   **mock\_html\_complex** : Un document HTML complet simulant une vraie page (avec Header, Nav, Sidebar, Footer, Scripts, et Contenu imbriqué).
    

2\. Tests Unitaires : Parser HTML & Extraction (test\_parser.py)
----------------------------------------------------------------

**Responsabilité :** Vérifier que l'outil "voit" uniquement ce qu'il doit voir.

### Cas 2.1 : Exclusion des Zones Non-Éditoriales (Zone Exclusion)

*   *   [Voiture occasion](#)
    
    Bienvenue
    =========
    
    Nous vendons une superbe voiture occasion.
    
    Copyright Voiture occasion 2024
    
*   **Target Keyword :** "voiture occasion"
    
*   **Comportement Attendu :**
    
    *   L'outil doit trouver **1 seule occurrence**.
        
    *   L'occurrence dans
        
        doit être ignorée (Zone Navigation).
        
    *   L'occurrence dans
        
        doit être ignorée (Zone Boilerplate).
        
    *   L'occurrence dans
        
        doit être validée.
        

### Cas 2.2 : Protection des Liens Existants (Nested Link Prevention)

*   Découvrez notre gamme de [voiture occasion pas chère](/achat) dès maintenant.
    
*   **Target Keyword :** "voiture occasion"
    
*   **Comportement Attendu :**
    
    *   **Résultat : 0 match.**
        
    *   **Raison :** Le texte cible se trouve déjà à l'intérieur d'une balise . On ne doit jamais créer un lien imbriqué (interdit par la spec HTML).
        

### Cas 2.3 : Robustesse XPath (XPath Integrity)

*   **Input :** Un fichier HTML complexe.
    
*   **Action :** Extraire un paragraphe, obtenir son XPath calculé, puis utiliser lxml pour requêter ce XPath sur le document original.
    
*   **Comportement Attendu :** lxml.find(xpath).text\_content() == original\_extracted\_text.
    
*   **Raison :** Garantir que le chemin technique fourni en sortie est utilisable pour une injection future.
    

3\. Tests Unitaires : Moteur NLP & Matching (test\_nlp.py)
----------------------------------------------------------

**Responsabilité :** Vérifier la tolérance linguistique et la précision sémantique.

### Cas 3.1 : Lemmatisation & Flexions (Morphology)

*   **Target Keyword :** "cheval de course"
    
*   **Input Text :** "Les **chevaux de courses** sont rapides."
    
*   **Comportement Attendu :** **Match Positif.**
    
*   **Logique :** lemma(chevaux) == cheval, lemma(courses) == course.
    

### Cas 3.2 : Gestion des Stop-Words (Noise Resistance)

*   **Target Keyword :** "Consultant SEO"
    
*   **Input Text :** "Je suis un **consultant en SEO** expérimenté."
    
*   **Comportement Attendu :** **Match Positif.**
    
*   **Logique :** Le token "en" est un stop-word et doit être ignoré lors du calcul de proximité.
    

### Cas 3.3 : Fenêtre Glissante / Proximité (Sliding Window)

*   **Target Keyword :** "Achat Maison"
    
*   **Input Text A :** "Pour l'**achat** de votre future **maison**..." (3 mots d'écart).
    
*   **Input Text B :** "L'**achat** est finalisé. La **maison** est belle." (Phrases différentes).
    
*   **Comportement Attendu :**
    
    *   Text A : **Match Positif** (si tolérance <= 3 mots).
        
    *   Text B : **Match Négatif** (rupture de phrase ou distance trop grande).
        

4\. Tests Métier & Règles SEO (test\_logic.py)
----------------------------------------------

**Responsabilité :** Vérifier les règles business définies dans le PRD.

### Cas 4.1 : Anti-Cannibalisation (Self-Linking)

*   **Données :**
    
    *   Page Source : example.com/tutoriel-python
        
    *   Page Cible (Target) : example.com/tutoriel-python
        
    *   Keyword trouvé : "tutoriel python"
        
*   **Comportement Attendu :** L'opportunité doit être **rejetée** (supprimée de la liste finale).
    

### Cas 4.2 : Priorisation des Targets (Best Match)

*   **Données GSC :**
    
    *   Target A (/page-top) : Position 3, Clics 500 pour "Avocat Paris".
        
    *   Target B (/page-flop) : Position 25, Clics 10 pour "Avocat Paris".
        
*   **Input Text :** "Contactez un avocat paris dès aujourd'hui."
    
*   **Comportement Attendu :** L'outil doit proposer un lien vers **/page-top** uniquement. Target B est ignorée pour éviter la dilution.
    

### Cas 4.3 : Limitation du Volume (Spam Control)

*   **Input Text :** Un paragraphe répétant 10 fois le mot clé "Crédit Immo".
    
*   **Comportement Attendu :** L'outil ne doit retourner que **1 seule opportunité** (la première trouvée) pour ce paragraphe/page vers cette cible. On ne veut pas 10 liens identiques sur la même page.
    

5\. Protocole de "Golden Dataset" (Validation Humaine)
------------------------------------------------------

Pour valider la version finale avant mise en production (V1.0), le test suivant doit être effectué manuellement ou scripté :

1.  **Préparation :** Sélectionner 1 fichier HTML réel représentatif ("Golden File").
    
2.  **Annotation :** Un humain identifie 5 opportunités de liens évidentes dans ce fichier.
    
3.  **Exécution :** Lancer SILO sur ce fichier unique.
    
4.  **Critère de succès (Pass/Fail) :**
    
    *   L'outil doit trouver au moins 3 des 5 liens humains (Recall >= 60%).
        
    *   L'outil ne doit pas proposer de lien aberrant (ex: lien sur un verbe conjugué seul hors contexte).
        

**Instruction pour le Développeur (Cursor/AI) :**Commencez par implémenter tests/conftest.py et tests/test\_parser.py avant d'écrire la logique complexe du parser. Si les tests passent sur le mock HTML, vous pouvez passer au NLP.