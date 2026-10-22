"""Union européenne — liste des médicaments critiques (EMA, HMA, Commission) → `ue_liste_critique`.

Une ligne = une substance (ATC5) inscrite sur la liste, avec sa voie d'administration et sa date
d'inscription. La date permet de savoir si une substance était déjà sur la liste à une date
donnée (première version : décembre 2023) : la variable « critique pour l'UE » ne fuit pas.

Format du classeur : une dizaine de lignes de titre, puis l'en-tête (« ATC level 5 », …).
Les lignes de classe (« A02B - … ») et les mentions de bas de page n'ont pas de code ATC5 : on ne
garde que les lignes dont la première cellule est un code ATC5 valide.
"""
import pandas as pd

from .commun import RAW, enregistrer
from .europe import atc5_valide


def construire():
    classeur = sorted((RAW / "ema" / "actuel").glob("*_union_list_critical_medicines.xlsx"))[-1]
    brut = pd.read_excel(classeur, header=None, usecols=range(4), dtype=str)
    brut.columns = ["atc5", "substance", "voie", "date_inscription"]
    table = brut[brut["atc5"].map(atc5_valide).notna()].copy()
    table["atc5"] = table["atc5"].map(atc5_valide)
    table["substance"] = table["substance"].str.strip()
    table["voie"] = table["voie"].str.strip()
    table["date_inscription"] = pd.to_datetime(table["date_inscription"])
    table = table.sort_values("atc5").reset_index(drop=True)
    enregistrer(table, "ue_liste_critique")
    print("  inscriptions par année :", table["date_inscription"].dt.year.value_counts().sort_index().to_dict())
