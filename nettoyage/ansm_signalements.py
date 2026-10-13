"""France — `ansm_signalements` : les signalements de rupture et de risque de rupture reçus par l'ANSM.

Une ligne = un signalement d'un laboratoire (classeurs annuels, 2019 à 2025). C'est
l'historique officiel des déclarations, limité aux médicaments d'intérêt thérapeutique majeur.
Il donne une date exacte, mais ni date de fin ni statut : une ligne peut être un simple risque.

Format des classeurs :
- 2019 à 2021 : date, laboratoire, spécialité, DCI (quelques lignes de texte avant l'en-tête
  en 2019 et 2020) ;
- depuis 2022 : date, laboratoire, CIP13, nom, DCI.
Les lignes identiques sont gardées : sans code CIP, deux boîtes d'un même médicament signalées le
même jour ne se distinguent pas, et les totaux publiés par l'ANSM les comptent.

ATC5, de la voie la plus sûre à la moins sûre (colonne `methode_rapprochement`) :
1. cip            le CIP13 est dans la BDPM : médicament (CIS), puis son ATC5 ;
2. cip_open_medic le CIP13 n'est plus dans la BDPM mais a un ATC5 dans Open Medic ;
3. nom, 4. substance, 5. marque : comme pour les fiches ANSM (voir `ansm_fiches.py`).
"""
import re

import pandas as pd

from .ansm_fiches import MOTS_GENERIQUES, atc_unique, mots_substance, reperes_atc
from .commun import CLEAN, RAW, enregistrer, normaliser_texte

COLONNES = {
    "Date Signalement": "date_signalement", "Date de déclaration": "date_signalement",
    "Laboratoire": "laboratoire", "Nom Laboratoire": "laboratoire",
    "Spécialité": "medicament", "Nom": "medicament", "CIP": "cip13", "DCI": "dci",
}
CIP13 = re.compile(r"3400\d{9}")


def lire_classeur(chemin):
    feuilles = []
    for feuille in pd.read_excel(chemin, sheet_name=None, header=None).values():
        en_tete = feuille.index[feuille[0].astype(str).str.startswith("Date")]
        if en_tete.empty:  # feuille de totaux
            continue
        table = feuille.iloc[en_tete[0] + 1:].copy()
        table.columns = [COLONNES[str(c).strip()] for c in feuille.iloc[en_tete[0]]]
        feuilles.append(table)
    return pd.concat(feuilles, ignore_index=True)


def nom_sans_boite(nom):
    """« ROSUVASTATINE SANDOZ 20 mg, comprimé pelliculé - boîte de 30 » → sans la boîte."""
    return normaliser_texte(re.split(r"\s[-_–]\s", nom or "")[0])


def construire():
    lire = lambda nom: pd.read_parquet(CLEAN / f"{nom}.parquet")
    produits, presentations, cip_atc = lire("produits"), lire("bdpm_presentations"), lire("cip_atc")

    classeurs = sorted((RAW / "ansm_signalements").glob("signalements_*.xlsx"))
    table = pd.concat([lire_classeur(c) for c in classeurs], ignore_index=True)
    table["date_signalement"] = pd.to_datetime(table["date_signalement"])
    for colonne in ("laboratoire", "medicament", "dci"):
        table[colonne] = table[colonne].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    # Quelques cellules CIP contiennent autre chose qu'un code (préparations hospitalières de
    # l'AP-HP, code suivi de texte) : on garde le code s'il y en a un, sinon le texte sert de nom.
    brut = table["cip13"].astype("string").str.strip()
    table["cip13"] = brut.str.extract(f"({CIP13.pattern})", expand=False)
    table["medicament"] = table["medicament"].fillna(brut.where(table["cip13"].isna()))

    atc_du_cis = produits.set_index("cis")["atc5"]
    cis_du_cip = presentations.drop_duplicates("cip13").set_index("cip13")["cis"]
    atc_open_medic = cip_atc[cip_atc["atc5"].str.len() == 7].set_index("cip13")["atc5"]
    cis_par_nom, atc_par_substance, atc_par_marque = reperes_atc(produits, lire("bdpm_compositions"), lire("atc"))

    def rapprocher(cip13, medicament, dci):
        cis, atc5, methode = [], None, None
        if cip13 in cis_du_cip.index:
            cis = [cis_du_cip[cip13]]
            atc5, methode = atc_du_cis.get(cis[0]), "cip"
        if pd.isna(atc5) and cip13 in atc_open_medic.index:
            atc5, methode = atc_open_medic[cip13], "cip_open_medic"
        for nom in (normaliser_texte(medicament), nom_sans_boite(medicament)):
            if pd.isna(atc5) and nom in cis_par_nom.index:
                cis = cis or cis_par_nom[nom]
                atc5, methode = atc_unique(atc_du_cis.reindex(cis)), "nom"
        if pd.isna(atc5) and mots_substance(dci):
            atc5, methode = atc_par_substance.get(mots_substance(dci)), "substance"
        if pd.isna(atc5):
            marque = normaliser_texte(medicament).split()[:1]
            if marque and marque[0] not in MOTS_GENERIQUES:
                atc5, methode = atc_par_marque.get(marque[0]), "marque"
        trouve = pd.notna(atc5)
        return "|".join(cis) or None, atc5 if trouve else None, methode if trouve else None

    # Le rapprochement ne dépend que de ces trois colonnes : on le fait une fois par combinaison.
    cles = ["cip13", "medicament", "dci"]
    combinaisons = table[cles].drop_duplicates()
    resultats = [rapprocher(*(None if pd.isna(v) else v for v in ligne))
                 for ligne in combinaisons.itertuples(index=False)]
    combinaisons[["cis", "atc5", "methode_rapprochement"]] = resultats
    table = table.merge(combinaisons, on=cles, how="left")

    table.insert(1, "annee", table["date_signalement"].dt.year)
    table = table.sort_values("date_signalement", kind="stable").reset_index(drop=True)
    table = table[["date_signalement", "annee", "laboratoire", "cip13", "medicament", "dci",
                   "cis", "atc5", "methode_rapprochement"]].astype({"laboratoire": object, "medicament": object,
                                                                     "dci": object, "cip13": object})
    enregistrer(table, "ansm_signalements")
    print("  signalements par année :", table["annee"].value_counts().sort_index().to_dict())
    print("  rapprochement ATC des signalements :",
          table["methode_rapprochement"].value_counts(dropna=False).to_dict())
