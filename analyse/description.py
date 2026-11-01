"""Description quantitative du dataset : dimensions, couverture, distributions (rapport, section « Le dataset »).

Usage :
    python -m analyse.description

Les nombres affichés sont ceux cités dans le rapport du livrable 1.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from nettoyage.panel import cohorte

RACINE = Path(__file__).resolve().parent.parent
CLEAN = RACINE / "data" / "clean"
TABLES = ["shortage_events", "ansm_signalements", "produits", "consommation"]


def lire(nom):
    return pd.read_parquet(CLEAN / f"{nom}.parquet")


def durees_france(episodes):
    """Durée (en jours) des pénuries françaises terminées, dont le début est connu et pas censuré à gauche."""
    termines = episodes[(~episodes["en_cours"]) & (~episodes["censure_gauche"]) & episodes["debut_connu"]]
    jours = (termines["fin"] - termines["debut"]).dt.days
    return jours[jours >= 0]


def calculer():
    resultat = {"dimensions": {n: {"lignes": len(t), "colonnes": t.shape[1]} for n in TABLES for t in [lire(n)]}}

    evenements = lire("shortage_events")
    penuries = evenements[evenements["type_episode"] == "penurie"]
    europe = lire("europe_observations")
    photos = {"FR": lire("ansm_observations")["date_photo"],
              "IT": europe[europe["pays"] == "IT"]["date_photo"], "DE": europe[europe["pays"] == "DE"]["date_photo"]}
    resultat["pays"] = {}
    for pays, g in penuries.groupby("pays", observed=True):
        p = photos[pays]
        resultat["pays"][pays] = {
            "episodes": len(g), "en_cours": int(g["en_cours"].sum()), "substances": int(g["atc5"].nunique()),
            "atc_connu": float(g["atc5"].notna().mean()), "photos": int(p.nunique()),
            "premiere_photo": p.min(), "derniere_photo": p.max()}

    france = penuries[penuries["pays"] == "FR"]
    jours = durees_france(france)
    resultat["france"] = {
        "durees_n": int(len(jours)), "mediane": float(jours.median()), "q1": float(jours.quantile(0.25)),
        "q3": float(jours.quantile(0.75)), "plus_d_un_an": float((jours > 365).mean()),
        "gravite": {str(k): float(v) for k, v in france["gravite"].value_counts(normalize=True).items()}}
    for pays in ("IT", "DE"):
        raisons = penuries[penuries["pays"] == pays]["raison"]
        resultat[f"raisons_{pays}"] = {"renseignee": float(raisons.notna().mean()),
                                       "principales": {str(k): float(v) for k, v in
                                                       raisons.value_counts(normalize=True).head(3).items()}}

    signalements = lire("ansm_signalements")
    resultat["signalements"] = {
        "par_annee": {int(a): int(n) for a, n in signalements["annee"].value_counts().sort_index().items()},
        "laboratoires": int(signalements["laboratoire"].nunique()), "atc_connu": float(signalements["atc5"].notna().mean()),
        "substances": int(signalements["atc5"].nunique())}

    produits = lire("produits")
    commercialises = produits[produits["etat_commercialisation"] == "Commercialisée"]
    resultat["medicaments"] = {"commercialises": len(commercialises), "atc_connu": float(commercialises["atc5"].notna().mean()),
                               "substances": int(commercialises["atc5"].nunique())}
    resultat["part_substances_touchees"] = float(len(set(france["atc5"].dropna()) & set(commercialises["atc5"].dropna()))
                                                 / commercialises["atc5"].nunique())

    resultat["eda"] = eda(france, penuries)
    atc = lire("atc").drop_duplicates("atc2").set_index("atc2")["libelle_atc2"]
    classes = france["atc5"].dropna().str[:3].value_counts().head(6)
    resultat["classes"] = [(code, str(atc.get(code, "")), int(n)) for code, n in classes.items()]
    return resultat


def eda(france, penuries):
    """Statistiques exploratoires : forme des durées, valeurs manquantes, lien consommation-signalements."""
    jours = durees_france(france)
    q1, q3 = jours.quantile([0.25, 0.75])
    haut = q3 + 1.5 * (q3 - q1)
    log = np.log(jours.clip(lower=1))
    manquantes = penuries.groupby("pays", observed=True)[["atc5", "fin", "debut"]].apply(lambda g: g.isna().mean())
    consommation, signalements = lire("consommation"), lire("ansm_signalements")
    cohorte_mitm, _ = cohorte()
    consommation = consommation[consommation["atc5"].isin(cohorte_mitm)]
    par_substance = consommation.groupby("atc5").agg(boites=("boites", "sum"), presentations=("nb_presentations", "max"))
    par_substance["signalements"] = signalements.groupby("atc5").size().reindex(par_substance.index).fillna(0)
    return {
        "moyenne": float(jours.mean()), "asymetrie": float(jours.skew()), "asymetrie_log": float(log.skew()),
        "hors_iqr": int((jours > haut).sum()), "seuil_iqr": float(haut), "hors_3sigma": int((jours > jours.mean() + 3 * jours.std()).sum()),
        "hors_3sigma_log": int(((log - log.mean()).abs() > 3 * log.std()).sum()), "durees_nulles": int((jours == 0).sum()),
        "manquantes": {k: {c: float(v) for c, v in r.items()} for k, r in manquantes.iterrows()},
        "doublons": int(penuries.duplicated().sum()), "boites_nulles": int((consommation["boites"] == 0).sum()),
        "boites_moyenne_sur_mediane": float(consommation["boites"].mean() / consommation["boites"].median()),
        "substances_conso": len(par_substance),
        "signalements_dans_cohorte": float(signalements["atc5"].dropna().isin(cohorte_mitm).mean()),
        "spearman": par_substance.corr("spearman").round(2).to_dict(), "pearson": par_substance.corr("pearson").round(2).to_dict()}


def pct(x):
    return f"{100 * x:.1f} %"


def main():
    r = calculer()
    print("Dimensions (lignes × colonnes) :", {n: f"{d['lignes']} × {d['colonnes']}" for n, d in r["dimensions"].items()})
    for pays, d in r["pays"].items():
        print(f"{pays} : {d['episodes']} épisodes, {d['en_cours']} en cours, {d['substances']} substances, ATC connu {pct(d['atc_connu'])}, "
              f"{d['photos']} photos ({d['premiere_photo']:%m/%Y} → {d['derniere_photo']:%m/%Y})")
    f = r["france"]
    print(f"France, durées ({f['durees_n']} épisodes terminés) : médiane {f['mediane']:.1f} j, quartiles {f['q1']:.0f} et {f['q3']:.0f} j, "
          f"> 1 an : {pct(f['plus_d_un_an'])} ; gravité : { {k: pct(v) for k, v in f['gravite'].items()} }")
    for pays in ("IT", "DE"):
        d = r[f"raisons_{pays}"]
        print(f"{pays}, raison renseignée {pct(d['renseignee'])} ; principales : { {k: pct(v) for k, v in d['principales'].items()} }")
    s = r["signalements"]
    print(f"Signalements : {s['par_annee']}, {s['laboratoires']} laboratoires, {s['substances']} substances, ATC connu {pct(s['atc_connu'])}")
    m = r["medicaments"]
    print(f"Médicaments commercialisés : {m['commercialises']}, ATC connu {pct(m['atc_connu'])}, {m['substances']} substances")
    print(f"Part des substances commercialisées ayant connu une pénurie en France : {pct(r['part_substances_touchees'])}")
    e = r["eda"]
    print(f"EDA durées : moyenne {e['moyenne']:.0f} j, asymétrie {e['asymetrie']:.2f} (log : {e['asymetrie_log']:.2f}), "
          f"hors règle IQR (> {e['seuil_iqr']:.0f} j) : {e['hors_iqr']}, hors 3 sigma : {e['hors_3sigma']} (log : {e['hors_3sigma_log']}), "
          f"durées nulles : {e['durees_nulles']}")
    print("EDA manquantes par pays (atc5, fin, debut) :", e["manquantes"], "; doublons :", e["doublons"], "; boîtes nulles :", e["boites_nulles"])
    print(f"Part des signalements (ATC connu) sur une substance de la cohorte : {pct(e['signalements_dans_cohorte'])}, {e['substances_conso']} substances avec consommation")
    print(f"EDA consommation : moyenne/médiane = {e['boites_moyenne_sur_mediane']:.1f} ; Spearman {e['spearman']} ; Pearson boîtes/signalements {e['pearson']['boites']['signalements']}")
    print("Classes ATC2 les plus touchées (France) :", r["classes"])


if __name__ == "__main__":
    main()
