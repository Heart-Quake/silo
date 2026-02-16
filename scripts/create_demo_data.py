import pandas as pd
import zipfile
import os

os.makedirs("data/input", exist_ok=True)

# 1. GSC Data
# We use simple, single words or common phrases to ensure NLP matching
gsc_data = pd.DataFrame({
    "Page": ["https://example.com/page-seo", "https://example.com/page-marketing"],
    "Query": ["agence seo", "marketing digital"],
    "Impressions": [1000, 500],
    "Clicks": [50, 10],
    "Position": [1, 5]
})
gsc_data.to_csv("data/input/demo_gsc.csv", index=False)
print("Created demo_gsc.csv")

# 2. HTML Zip
# We include the exact keywords in the text
html1 = """
<html><body><main>
<h1>Titre de la page</h1>
<p>Nous sommes une excellente <strong>agence seo</strong> basée à Paris.</p>
<p>L'optimisation pour les moteurs de recherche est cruciale.</p>
</main></body></html>
"""
html2 = """
<html><body><main>
<h1>Le Marketing</h1>
<p>Le <strong>marketing digital</strong> est essentiel de nos jours.</p>
<p>Il faut investir dans la publicité en ligne.</p>
</main></body></html>
"""

with zipfile.ZipFile("data/input/demo_html.zip", "w") as z:
    # Filenames that map to Source URLs
    # Source 1 -> https://example.com/blog-1
    z.writestr("rendu_https_example.com_blog-1.html", html1)
    # Source 2 -> https://example.com/blog-2
    z.writestr("rendu_https_example.com_blog-2.html", html2)

print("Created demo_html.zip")
