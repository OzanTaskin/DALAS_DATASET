"""France — Open Medic (Assurance Maladie) → `atc`, `cip_atc`, `consommation`.

Chaque archive annuelle (~1,9 million de lignes) détaille les boîtes remboursées par
présentation (CIP13), âge, sexe, région et spécialité du prescripteur. On n'a besoin ni de
l'âge, ni du sexe, ni de la région : on agrège par CIP13 et par année.

Tables produites :
- atc          une ligne par code ATC5, avec ses niveaux 1 à 4 et leurs libellés
- cip_atc      une ligne par boîte (CIP13) : son ATC5 et son statut générique
- consommation une ligne par ATC5 × année : boîtes et montants remboursés
"""
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from .commun import RAW, enregistrer

NIVEAUX = ["ATC1", "l_ATC1", "ATC2", "L_ATC2", "ATC3", "L_ATC3", "ATC4", "L_ATC4", "ATC5", "L_ATC5"]
COLONNES = NIVEAUX + ["CIP13", "l_cip13", "TOP_GEN", "GEN_NUM", "BOITES", "REM", "BSE"]


def nombre(colonne):
    """Nombres au format français : « 1.234,56 » → 1234.56."""
    return pd.to_numeric(colonne.str.replace(".", "", regex=False).str.replace(",", "."), errors="coerce")


def lire_annee(chemin):
    annee = int(chemin.stem.split("_")[-1])
    morceaux = []
    lecteur = pd.read_csv(chemin, compression="zip", sep=";", encoding="latin-1", dtype=str,
                          chunksize=500_000, keep_default_na=False)
    for morceau in lecteur:
        # La casse des en-têtes varie selon l'année (SEXE / sexe, l_ATC1 / L_ATC1).
        morceau.columns = [c if c in COLONNES else next((x for x in COLONNES if x.lower() == c.lower()), c)
                           for c in morceau.columns]
        for colonne in ("BOITES", "REM", "BSE"):
            morceau[colonne] = nombre(morceau[colonne])
        cles = NIVEAUX + ["CIP13", "l_cip13", "TOP_GEN", "GEN_NUM"]
        morceaux.append(morceau.groupby(cles, as_index=False)[["BOITES", "REM", "BSE"]].sum())
    table = pd.concat(morceaux).groupby(cles, as_index=False)[["BOITES", "REM", "BSE"]].sum()
    table.insert(0, "annee", annee)
    return table


def construire():
    archives = sorted((RAW / "open_medic").glob("OPEN_MEDIC_*.zip"))
    with ProcessPoolExecutor() as executeur:
        annees = pd.concat(executeur.map(lire_annee, archives), ignore_index=True)
    annees.columns = [c.lower() for c in annees.columns]
    annees = annees.rename(columns={"boites": "boites", "rem": "montant_rembourse",
                                    "bse": "base_remboursement", "l_cip13": "libelle_cip13",
                                    "top_gen": "generique", "gen_num": "groupe_generique"})

    # Libellés ATC, niveau par niveau : le plus récent qui n'est pas abîmé à la source
    # (certaines années remplacent les accents par le caractère \x1a : « syst\x1amique »).
    atc = annees.drop_duplicates("atc5")[[f"atc{i}" for i in range(1, 6)]]
    for i in range(1, 6):
        libelles = annees[["annee", f"atc{i}", f"l_atc{i}"]].drop_duplicates()
        libelles["abime"] = libelles[f"l_atc{i}"].str.contains("\x1a", regex=False)
        libelles = (libelles.sort_values(["abime", "annee"], ascending=[False, True])
                    .drop_duplicates(f"atc{i}", keep="last"))
        atc = atc.merge(libelles[[f"atc{i}", f"l_atc{i}"]].rename(columns={f"l_atc{i}": f"libelle_atc{i}"}),
                        on=f"atc{i}", how="left")
    atc = atc[atc["atc5"].str.len() == 7].sort_values("atc5")
    enregistrer(atc, "atc")

    cip_atc = (annees.sort_values("annee").drop_duplicates("cip13", keep="last")
               [["cip13", "libelle_cip13", "atc5", "generique", "groupe_generique", "annee"]]
               .rename(columns={"annee": "derniere_annee_remboursee"}))
    cip_atc["generique"] = cip_atc["generique"].eq("1")
    enregistrer(cip_atc, "cip_atc")

    consommation = (annees.groupby(["atc5", "annee"], as_index=False)
                    .agg(boites=("boites", "sum"), montant_rembourse=("montant_rembourse", "sum"),
                         nb_presentations=("cip13", "nunique")))
    # Des montants en euros : arrondis au centime. Sans cela, le dernier chiffre d'une somme en
    # virgule flottante dépend de l'ordre des additions, et deux exécutions identiques diffèrent.
    consommation["montant_rembourse"] = consommation["montant_rembourse"].round(2)
    enregistrer(consommation, "consommation")
