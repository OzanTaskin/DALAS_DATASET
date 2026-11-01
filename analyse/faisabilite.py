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


def facteurs():
    """Q1 et Q2 contrôlées : régression logistique entraînée sur la période d'entraînement, évaluée sur le test (2025),
    avec les variables de base (consommation, présentations, signalements passés, liste critique, substance déjà
    affichée) puis avec la variable de Q1 ou de Q2. Un écart d'AUC dit ce que le signal apporte de plus."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    t = pd.read_parquet(PANEL)
    t = t[t["jeu"] != "ecart"].copy()
    for entree, sortie in [("conso_boites_an_prec", "conso"), ("conso_presentations_an_prec", "presentations"),
                           ("sig_an_prec", "sig"), ("sig_cumul_avant", "sig_cumul")]:
        t[sortie] = np.log1p(t[entree].astype("float64"))
    t["conso_absente"] = t["conso"].isna().astype(int)
    t[["conso", "presentations"]] = t[["conso", "presentations"]].fillna(0)
    for c in ["fr_affichee_3m", "fr_autres_classe_3m", "it_affichee_3m"]:
        t[c] = t[c].astype("float64")
    base = ["conso", "presentations", "conso_absente", "ue_critique", "sig", "sig_cumul", "fr_affichee_3m"]

    def auc(donnees, colonnes):
        entrainement, test = (donnees[donnees["jeu"] == j] for j in ("entrainement", "test"))
        modele = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(entrainement[colonnes], entrainement["cible"])
        p = modele.predict_proba(test[colonnes])[:, 1]
        return {"auc": float(roc_auc_score(test["cible"], p)), "pr_auc": float(average_precision_score(test["cible"], p)),
                "coef": dict(zip(colonnes, modele[-1].coef_[0]))}

    france, italie = t.dropna(subset=["fr_affichee_3m"]), t.dropna(subset=["it_affichee_3m"])
    return {"Q1 sans": auc(france, base), "Q1 avec": auc(france, base + ["fr_autres_classe_3m"]),
            "Q2 Italie sans": auc(italie, base), "Q2 Italie avec": auc(italie, base + ["it_affichee_3m"])}


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
    print("\nSignaux contrôlés (régression logistique, test 2025) :")
    for nom, d in facteurs().items():
        print(f"  {nom:15} AUC {d['auc']:.3f}  PR-AUC {d['pr_auc']:.3f}")


if __name__ == "__main__":
    main()
