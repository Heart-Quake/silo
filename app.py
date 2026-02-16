"""
Application Streamlit pour SILO (Semantic Internal Link Optimizer).
Interface "Wizard" guidée pour une expérience utilisateur simplifiée.
"""
import streamlit as st
import pandas as pd
import tempfile
import os
import shutil
import time
from pathlib import Path
from io import BytesIO

from src.data_loader import DataLoader
from src.parser import ContentParser
from src.nlp_matcher import NLPMatcher
from src.silo_linker import SILOLinker
import spacy

# --- CONFIGURATION ---
st.set_page_config(
    page_title="SILO - Maillage Interne",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLE CSS (Minimalist / Zen) ---
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .step-header {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #333;
    }
    .block-container {
        padding-top: 5rem;
        max_width: 1000px;
    }
</style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if 'step' not in st.session_state:
    st.session_state.step = 1  # 1: Upload, 2: Analysis, 3: Review, 4: Export
if 'nlp_model' not in st.session_state:
    st.session_state.nlp_model = None
if 'opportunities_df' not in st.session_state:
    st.session_state.opportunities_df = None
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0

# --- SIDEBAR & INIT ---
with st.sidebar:
    st.title("🔗 SILO")
    st.caption("Optimisation Sémantique de Maillage Interne")
    
    st.markdown("---")
    
    # Progress du Wizard
    steps = {
        1: "📂 Import Données",
        2: "🚀 Analyse",
        3: "✅ Validation",
        4: "💾 Export"
    }
    
    current_step = st.session_state.step
    for step_num, step_name in steps.items():
        if step_num == current_step:
            st.markdown(f"**👉 {step_name}**")
        elif step_num < current_step:
            st.markdown(f"✅ ~~{step_name}~~")
        else:
            st.markdown(f"⬜ {step_name}")
            
    st.markdown("---")
    
    # Mode Avancé (Toggle)
    zen_mode = not st.checkbox("🔧 Mode Avancé (Debug)", value=False, help="Affiche les outils de test techniques")
    
    # Chargement du modèle NLP (Lazy load)
    if st.session_state.nlp_model is None:
        with st.spinner("Initialisation du moteur NLP..."):
            try:
                # Charger un modèle léger sans NER/parser
                st.session_state.nlp_model = spacy.load("fr_core_news_md", disable=["ner", "parser"])
            except Exception as e:
                st.error(f"Erreur NLP: {e}")

# --- HELPER FUNCTIONS ---
def reset_pipeline():
    st.session_state.step = 1
    st.session_state.opportunities_df = None
    st.rerun()

# --- STEPS RENDERING ---

def render_upload_step():
    st.markdown('<div class="step-header">📂 Étape 1 : Importez vos données</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("1️⃣ **Données GSC (Demande)**")
        gsc_file = st.file_uploader("Fichier CSV Google Search Console", type=['csv'])
        
    with col2:
        st.info("2️⃣ **Contenu HTML (Offre)**")
        html_file = st.file_uploader("Archive ZIP des rendus HTML", type=['zip'])
        html_prefix = st.text_input("Préfixe des fichiers", "rendu_", help="Ex: 'rendu_' pour rendu_url.html")

    # Bouton Demo (toujours utile pour tester)
    if st.button("🔄 Charger Données de Démo (Test)", type="secondary"):
        if os.path.exists("data/input/demo_gsc.csv") and os.path.exists("data/input/demo_html.zip"):
            st.session_state.gsc_file_path = "data/input/demo_gsc.csv"
            # Fake upload object for ZIP
            with open("data/input/demo_html.zip", "rb") as f:
                st.session_state.html_zip_bytes = f.read()
            st.session_state.html_prefix = "rendu_"
            st.session_state.step = 2
            st.rerun()
        else:
            st.error("Données de démo introuvables.")

    if gsc_file and html_file:
        if st.button("Suivant ➡", type="primary"):
            # Save files temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_gsc:
                tmp_gsc.write(gsc_file.getvalue())
                st.session_state.gsc_file_path = tmp_gsc.name
            
            st.session_state.html_zip_bytes = html_file.getvalue()
            st.session_state.html_prefix = html_prefix
            st.session_state.step = 2
            st.rerun()

def render_analysis_step():
    st.markdown('<div class="step-header">🚀 Étape 2 : Analyse Sémantique</div>', unsafe_allow_html=True)
    
    st.write("Le pipeline SILO croise vos données GSC avec le contenu de vos pages.")
    
    start_btn = st.button("Lancer l'analyse", type="primary")
    
    if start_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Setup temp dir for ZIP
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "content.zip")
                with open(zip_path, "wb") as f:
                    f.write(st.session_state.html_zip_bytes)
                
                status_text.text("⚙️ Initialisation du pipeline (Multi-process)...")
                progress_bar.progress(10)
                
                # Init Linker (V2 Pro)
                linker = SILOLinker(
                    gsc_csv_path=st.session_state.gsc_file_path,
                    html_zip_path=zip_path,
                    html_prefix=st.session_state.html_prefix
                )
                
                status_text.text("🧠 Analyse sémantique en cours...")
                progress_bar.progress(30)
                
                # Execution
                # Note: Streamlit n'aime pas trop le multiprocessing complexe.
                # Dans app.py, on fait confiance au script.
                df_results = linker.process()
                
                progress_bar.progress(100)
                status_text.text("✅ Analyse terminée !")
                
                if not df_results.empty:
                    # Ajouter colonne 'Keep' pour la review par défaut True
                    df_results.insert(0, 'Keep', True)
                    st.session_state.opportunities_df = df_results
                    time.sleep(1)
                    st.session_state.step = 3
                    st.rerun()
                else:
                    st.warning("Aucune opportunité trouvée. Vérifiez vos données.")
                    if st.button("Retour"):
                        st.session_state.step = 1
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Erreur technique : {e}")
            import traceback
            st.code(traceback.format_exc())

def render_review_step():
    st.markdown('<div class="step-header">✅ Étape 3 : Validation Interactive</div>', unsafe_allow_html=True)
    
    df = st.session_state.opportunities_df
    
    # --- FILTRES ---
    col_filter1, col_filter2 = st.columns([1, 1])
    with col_filter1:
        keyword_filter = st.text_input("🔍 Filtrer par mot-clé", placeholder="Ex: mutuelle...")
    with col_filter2:
        min_clicks = st.number_input("📉 Trafic min (clics)", min_value=0, value=0)
        
    # --- ACTIONS DE MASSE ---
    col_msg, col_actions = st.columns([2, 2])
    
    # Identifier les indices correspondant au filtre *actuel*
    mask = pd.Series(True, index=df.index)
    if keyword_filter:
        mask &= df['Keyword_GSC'].str.contains(keyword_filter, case=False, na=False)
    if min_clicks > 0:
        if 'Clicks' in df.columns:
            mask &= (df['Clicks'] >= min_clicks)
            
    filtered_indices = df[mask].index
    
    with col_actions:
        st.write("Actions sur le filtre :")
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("✅ Tout cocher"):
                st.session_state.opportunities_df.loc[filtered_indices, 'Keep'] = True
                st.rerun()
        with col_act2:
            if st.button("❌ Tout décocher"):
                st.session_state.opportunities_df.loc[filtered_indices, 'Keep'] = False
                st.rerun()
                
    with col_msg:
        st.success(f"🎉 **{len(filtered_indices)} opportunités affichées** (sur {len(df)} totales)")
        st.info("Décochez les liens que vous ne souhaitez pas conserver.")
        
    filtered_df = st.session_state.opportunities_df.loc[filtered_indices].copy()
    
    # Interactive Data Editor
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "Keep": st.column_config.CheckboxColumn(
                "Garder ?",
                help="Cochez pour inclure dans l'export",
                default=True,
            ),
            "Score": st.column_config.ProgressColumn(
                "Pertinence",
                help="Score calculé (0-100)",
                format="%d",
                min_value=0,
                max_value=100,
            ),
            "Clicks": st.column_config.NumberColumn(
                "Trafic",
                help="Nombre de clics GSC (30 derniers jours)",
                format="%d 🖱️"
            ),
            "Impressions": st.column_config.NumberColumn(
                "Impressions",
                help="Nb d'affichages dans Google",
                format="%d 👁️"
            ),
            "Keyword_GSC": "Mot-clé",
            "Anchor_Text": "Ancre trouvée",
            "Context_Snippet": st.column_config.TextColumn("Contexte", width="large"),
        },
        disabled=["Score", "Source_URL", "Target_URL", "Anchor_Text", "Keyword_GSC", "Context_Snippet", "Clicks", "Impressions"],
        hide_index=True,
    )
    
    # IMPORTANT : Réconcilier les modifications avec le DataFrame original
    # Car st.data_editor ne retourne que les lignes affichées (filtrées)
    # On doit mettre à jour les colonnes 'Keep' dans le session_state DF global
    
    if not edited_df.equals(filtered_df):
        # Trouver les lignes modifiées via l'index (si préservé) ou via une clé unique.
        # Ici reset_pipeline peut avoir cassé l'index si on a fait df.copy().
        # Pour simplifier dans l'immédiat, on met à jour en se basant sur une clé composite (Source+Target+Keyword)
        # Mais le plus simple est de ne pas filtrer "trop fort" ou d'accepter que l'édition ne se fasse que sur le visible.
        # V2 : On met à jour st.session_state.opportunities_df avec les valeurs de edited_df pour les lignes correspondantes.
        
        # Astuce : On récupère les index des lignes éditées (si filtre conserve l'index)
        for idx, row in edited_df.iterrows():
            st.session_state.opportunities_df.loc[idx, 'Keep'] = row['Keep']

    
    # Boutton Validation
    selected_count = edited_df['Keep'].sum()
    st.write(f"**{selected_count}** liens sélectionnés sur {len(df)}.")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Recommencer", type="secondary"):
             reset_pipeline()
                
    with col2:
        if st.button(f"Valider {selected_count} liens & Exporter ➡", type="primary"):
            # Filtrer et sauvegarder
            final_df = edited_df[edited_df['Keep'] == True].drop(columns=['Keep'])
            st.session_state.final_df = final_df
            st.session_state.step = 4
            st.rerun()

def render_export_step():
    st.markdown('<div class="step-header">💾 Étape 4 : Résultats</div>', unsafe_allow_html=True)
    
    final_df = st.session_state.final_df
    
    st.success("Votre fichier d'optimisation est prêt !")
    
    # Statistiques finales
    st.metric("Liens validés", len(final_df))
    
    # Conversion CSV
    csv_data = final_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Télécharger le CSV Final",
        data=csv_data,
        file_name="silo_export_final.csv",
        mime="text/csv",
        type="primary"
    )
    
    st.markdown("---")
    if st.button("🔄 Lancer une nouvelle analyse"):
        reset_pipeline()

# --- MAIN RENDERER ---

if zen_mode:
    # WIZARD FLOW
    if st.session_state.step == 1:
        render_upload_step()
    elif st.session_state.step == 2:
        render_analysis_step()
    elif st.session_state.step == 3:
        render_review_step()
    elif st.session_state.step == 4:
        render_export_step()
else:
    # ADVANCED MODE (Old Tabs for Debugging)
    st.warning("⚠️ Mode Avancé activé (Outils Debug)")
    
    tab1, tab2 = st.tabs(["🧪 Test NLP (Unitaire)", "🔍 Test Parser (Unitaire)"])
    
    with tab1:
        st.subheader("Test NLP Unitaire")
        k = st.text_input("Mot-clé", "voiture")
        t = st.text_area("Texte", "J'aime les voitures rouges.")
        if st.button("Test NLP"):
             if st.session_state.nlp_model:
                 matcher = NLPMatcher(st.session_state.nlp_model)
                 res = matcher.find_matches(t, k)
                 st.write(res)
                 
    with tab2:
        st.subheader("Test Parser Unitaire")
        h = st.text_area("HTML", "<html><body><p>Text</p></body></html>")
        if st.button("Test Parser"):
            p = ContentParser()
            st.write(p.extract_valid_paragraphs(h))
    
    if st.button("⬅ Retour au Wizard"):
        # Just refresh page to default zen mode check
        st.rerun()
