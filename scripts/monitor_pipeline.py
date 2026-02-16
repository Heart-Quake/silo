#!/usr/bin/env python3
"""
Script pour monitorer la progression du pipeline SILO.
"""
import time
import os
from pathlib import Path

output_file = "data/output/opportunities_export.csv"

print("🔍 Monitoring du pipeline SILO...")
print(f"📁 Fichier de sortie attendu : {output_file}\n")

start_time = time.time()
last_size = 0
check_count = 0

while True:
    check_count += 1
    elapsed = time.time() - start_time
    
    if os.path.exists(output_file):
        current_size = os.path.getsize(output_file)
        if current_size > last_size:
            # Compter les lignes
            with open(output_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f) - 1  # -1 pour l'en-tête
            
            print(f"✅ Fichier trouvé ! ({elapsed:.0f}s écoulés)")
            print(f"   📊 Taille : {current_size / 1024:.1f} KB")
            print(f"   📈 Opportunités : {line_count}")
            print(f"   💾 Dernière mise à jour : {time.ctime(os.path.getmtime(output_file))}")
            
            if current_size == last_size and line_count > 0:
                print("\n✨ Pipeline terminé !")
                break
            
            last_size = current_size
        else:
            print(f"⏳ En attente... ({elapsed:.0f}s)")
    else:
        print(f"⏳ Pipeline en cours... ({elapsed:.0f}s)")
    
    time.sleep(5)  # Vérifier toutes les 5 secondes
    
    # Timeout après 10 minutes
    if elapsed > 600:
        print("\n⚠️  Timeout atteint (10 minutes)")
        break
