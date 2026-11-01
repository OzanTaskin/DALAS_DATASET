"""Faisabilité du projet, chiffrée sur la table d'entraînement `panel_fr` (niveau 3).

Usage :
    python -m nettoyage panel      # construit data/final/panel_fr.parquet
    python -m analyse.faisabilite

Trois questions avant toute modélisation :
- la cible est-elle observable, avec assez de cas positifs, et comment évolue-t-elle ? ;
- Q1 (cascade) : combien de lignes sont exposées à une pénurie affichée dans la même classe ATC4 ? ;
- Q2 (importation) : combien de lignes sont exposées à une pénurie affichée en Italie, en Allemagne ?
Les taux avec et sans exposition sont des repères bruts, pas des résultats : ils ne tiennent pas compte
de la taille des classes, de la consommation ni de la hausse générale des signalements.
"""
from pathlib import Path

import pandas as pd

PANEL = Path(__file__).resolve().parent.parent / "data" / "final" / "panel_fr.parquet"

EXPOSITIONS = {  # nom : (colonne, exposée si)
    "Q1 cascade : autres substances de la classe affichées": ("fr_autres_classe_3m", lambda x: x > 0),
    "Q2 Italie : même substance affichée": ("it_affichee_3m", lambda x: x > 0),
    "Q2 Allemagne : même substance affichée": ("de_affichee_3m", lambda x: x > 0),
    "Contrôle : même substance affichée en France": ("fr_affichee_3m", lambda x: x > 0),
}


def calculer():
    panel = pd.read_parquet(PANEL)
    resultat = {"lignes": len(panel), "substances": int(panel["atc5"].nunique()), "mois": int(panel["mois"].nunique()),
                "positives": int(panel["cible"].sum()), "taux": float(panel["cible"].mean())}
    resultat["jeux"] = {jeu: {"lignes": len(g), "positives": int(g["cible"].sum()), "taux": float(g["cible"].mean())}
                        for jeu, g in panel.groupby("jeu", observed=True)}
    resultat["expositions"] = {}
    for nom, (colonne, regle) in EXPOSITIONS.items():
        observe = panel.dropna(subset=[colonne])
        exposee = regle(observe[colonne])
        resultat["expositions"][nom] = {
            "mois_couverts": int(observe["mois"].nunique()), "lignes": len(observe), "part_exposee": float(exposee.mean()),
            "positives_si_exposee": float(observe.loc[exposee, "cible"].mean()),
            "positives_sinon": float(observe.loc[~exposee, "cible"].mean())}
    return resultat


def pct(x):
    return f"{100 * x:.1f} %"


def main():
    r = calculer()
    print(f"panel_fr : {r['substances']} substances × {r['mois']} mois = {r['lignes']:,} lignes, "
          f"{r['positives']:,} positives ({pct(r['taux'])})".replace(",", " "))
    for jeu, d in r["jeux"].items():
        print(f"  {jeu:13} {d['lignes']:>7,} lignes, {d['positives']:>6,} positives ({pct(d['taux'])})".replace(",", " "))
    for nom, d in r["expositions"].items():
        print(f"{nom} : {d['mois_couverts']} mois, {d['lignes']:,} lignes ; exposées {pct(d['part_exposee'])} ; "
              f"positives {pct(d['positives_si_exposee'])} si oui, {pct(d['positives_sinon'])} sinon".replace(",", " "))


if __name__ == "__main__":
    main()
