"""Chemins et outils communs au niveau 2 (tables nettoyées)."""
import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime
from functools import cache
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


@cache
def provenance():
    """Version du code (commit git, « +modifs » si des fichiers ne sont pas commités) et
    empreinte du manifeste brut : deux exécutions qui ont la même provenance lisent le même
    code et les mêmes données."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "--short", "HEAD") or "inconnu"
    if git("status", "--porcelain", "--", "collecte", "nettoyage"):
        commit += "+modifs"
    manifeste = RAW / "manifeste.csv"
    empreinte = hashlib.sha256(manifeste.read_bytes()).hexdigest()[:16] if manifeste.exists() else None
    return {"code": commit, "manifeste_brut": empreinte}


def enregistrer(table, nom):
    """Écrit la table en Parquet et la trace dans data/clean/manifeste.json (lignes, colonnes,
    valeurs vides, provenance), pour pouvoir comparer deux exécutions."""
    CLEAN.mkdir(parents=True, exist_ok=True)
    chemin = CLEAN / f"{nom}.parquet"
    table.to_parquet(chemin, index=False)

    manifeste = CLEAN / "manifeste.json"
    entrees = json.loads(manifeste.read_text()) if manifeste.exists() else {}
    entrees[nom] = {"construite_le": datetime.now().isoformat(timespec="seconds"),
                    "lignes": len(table), "colonnes": list(table.columns),
                    "valeurs_vides": int(table.isna().sum().sum()), **provenance()}
    manifeste.write_text(json.dumps(dict(sorted(entrees.items())), indent=1, ensure_ascii=False))

    print(f"  {nom:28} {len(table):>9,} lignes → {chemin.relative_to(RACINE)}".replace(",", " "))
    return chemin
