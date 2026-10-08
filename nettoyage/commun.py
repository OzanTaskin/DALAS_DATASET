"""Chemins et outils communs au niveau 2 (tables nettoyées)."""
import re
import unicodedata
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RAW = RACINE / "data" / "raw"
CLEAN = RACINE / "data" / "clean"


def date_du_fichier(chemin):
    """Date de la photo : horodatage Wayback (20210405012028.html) ou préfixe (2026-10-05_...)."""
    nom = Path(chemin).name
    if re.match(r"\d{14}\.", nom):
        return datetime.strptime(nom[:8], "%Y%m%d").date()
    return datetime.strptime(nom[:10], "%Y-%m-%d").date()


def source_du_fichier(chemin):
    return "wayback" if "wayback" in Path(chemin).parts else "actuel"


def normaliser_texte(texte):
    """Minuscules, sans accents ni ponctuation superflue : sert aux jointures par nom."""
    if not isinstance(texte, str):  # valeur manquante (None ou NaN)
        return ""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    texte = re.sub(r"[^a-z0-9]+", " ", texte)
    return texte.strip()


def enregistrer(table, nom):
    CLEAN.mkdir(parents=True, exist_ok=True)
    chemin = CLEAN / f"{nom}.parquet"
    table.to_parquet(chemin, index=False)
    print(f"  {nom:28} {len(table):>9,} lignes → {chemin.relative_to(RACINE)}".replace(",", " "))
    return chemin
