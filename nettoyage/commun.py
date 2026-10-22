"""Chemins et outils communs au niveau 2 (tables nettoyées)."""
import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime
from functools import cache
from pathlib import Path

import pandas as pd

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


def empreinte(contenu):
    return hashlib.sha256(contenu).hexdigest()[:16]


@cache
def provenance():
    """D'où vient une table : le code qui l'a construite et les données brutes qu'il a lues.

    - commit : version git (« +modifs » si des fichiers du code ne sont pas commités) ;
    - empreinte_code : empreinte du texte de tous les modules de nettoyage, exacte même avec des
      modifications non commitées (l'équivalent du hash de la requête du cours) ;
    - empreinte_brut : empreinte du manifeste de la couche brute.
    Deux exécutions de même provenance lisent le même code et les mêmes données : si leurs
    sorties diffèrent, la cause est ailleurs. Si seule l'empreinte du brut change, ce sont les
    données ; si seule celle du code change, c'est le code."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "--short", "HEAD") or "inconnu"
    if git("status", "--porcelain", "--", "collecte", "nettoyage"):
        commit += "+modifs"
    code = b"".join(p.read_bytes() for p in sorted((RACINE / "nettoyage").glob("*.py")))
    manifeste = RAW / "manifeste.csv"
    return {"commit": commit, "empreinte_code": empreinte(code),
            "empreinte_brut": empreinte(manifeste.read_bytes()) if manifeste.exists() else None}


def resume(table):
    """Ce qui permet de dire si deux exécutions ont produit la même table : nombre de lignes,
    valeurs vides, somme de chaque colonne numérique et empreinte du contenu."""
    nombres = table.select_dtypes(include=["number", "bool"])
    return {"lignes": len(table), "colonnes": list(table.columns),
            "valeurs_vides": int(table.isna().sum().sum()),
            "sommes": {c: round(float(nombres[c].sum()), 2) for c in nombres.columns},
            "empreinte_contenu": empreinte(pd.util.hash_pandas_object(table, index=False).to_numpy().tobytes())}


def enregistrer(table, nom):
    """Écrit la table en Parquet et la trace dans data/clean/manifeste.json (résumé du contenu
    et provenance), pour pouvoir comparer deux exécutions (cours, diapo 65)."""
    CLEAN.mkdir(parents=True, exist_ok=True)
    chemin = CLEAN / f"{nom}.parquet"
    table.to_parquet(chemin, index=False)

    manifeste = CLEAN / "manifeste.json"
    entrees = json.loads(manifeste.read_text()) if manifeste.exists() else {}
    entrees[nom] = {"construite_le": datetime.now().isoformat(timespec="seconds"),
                    **resume(table), **provenance()}
    manifeste.write_text(json.dumps(dict(sorted(entrees.items())), indent=1, ensure_ascii=False))

    print(f"  {nom:28} {len(table):>9,} lignes → {chemin.relative_to(RACINE)}".replace(",", " "))
    return chemin
