# 🧪 Résultats des Tests - Pipeline SILO

## ✅ Tests Réussis

### Test Rapide (5 fichiers HTML, 100 lignes GSC)
- **Fichier de sortie** : `data/output/opportunities_test.csv`
- **Résultats** : 34 opportunités identifiées
- **Statut** : ✅ Réussi

### Test Pipeline Complet (3 fichiers HTML, 100 lignes GSC)
- **Fichier de sortie** : `data/output/opportunities_test_full.csv`
- **Résultats** : 4 opportunités identifiées
- **Statut** : ✅ Réussi

### Pipeline Complet (Toutes les données)
- **Fichier de sortie** : `data/output/opportunities_export.csv`
- **Statut** : ⏳ En cours d'exécution
- **Données** : 24,986 lignes GSC × 160 fichiers HTML
- **Temps estimé** : 10-30 minutes (selon la puissance CPU)

## 📊 Exemple de Résultats

### Format de Sortie

Le fichier CSV généré contient les colonnes suivantes :

| Colonne | Exemple |
|---------|---------|
| Score | 98 |
| Keyword_GSC | lilycare |
| Source_URL | https://lilycare.fr/a-propos-de-lilycare |
| Target_URL | https://lilycare.fr/ |
| Anchor_Text | Derrière Lilycare, il y a une équipe... |
| Context_Snippet | Derrière Lilycare, il y a une équipe de spécialistes... |
| XPath | /html/body/div[1]/div[1]/section[2]/div/div/div/div[1]/div[2]/p |
| Similarity_Type | Lemma_Fuzzy |

### Validation

✅ **Chargement GSC** : Fonctionne avec point-virgule et séparateurs de milliers
✅ **Génération mapping HTML** : Automatique depuis le ZIP
✅ **Extraction paragraphes** : Exclusion nav/footer fonctionnelle
✅ **Matching NLP** : Lemmatisation et fenêtre glissante opérationnelles
✅ **Calcul de score** : Basé sur Clicks et Position GSC
✅ **Export CSV** : Format conforme au PRD

## 🔍 Points de Validation

1. **Exclusion des zones** : ✅ Nav, footer, sidebar correctement ignorés
2. **Protection liens imbriqués** : ✅ Texte dans `<a>` ignoré
3. **Anti-cannibalisation** : ✅ Auto-référence rejetée
4. **Unicité** : ✅ 1 seul lien par paire source→target
5. **XPath valides** : ✅ Chemins utilisables pour injection

## ⚡ Performance

- **Test rapide** : ~5 secondes (5 fichiers)
- **Test complet (échantillon)** : ~30 secondes (3 fichiers, 100 lignes GSC)
- **Pipeline complet** : En cours (160 fichiers, 24,986 lignes GSC)

## 📝 Notes

Le pipeline complet prend du temps car :
- Chaque fichier HTML est parsé
- Chaque paragraphe est comparé avec tous les mots-clés GSC
- Le matching NLP (lemmatisation + fenêtre glissante) est coûteux en calculs

**Optimisations appliquées** :
- Limitation à 10 mots-clés par URL pour accélérer
- Vérification d'unicité avant le matching NLP
- Logs de progression toutes les 5 fichiers
