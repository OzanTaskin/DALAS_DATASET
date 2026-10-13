"""France — `ansm_fiches` : chaque fiche ANSM reliée à ses médicaments (CIS) et à un code ATC5.

L'ANSM ne donne ni code médicament ni ATC. On rapproche chaque fiche par quatre voies, de la
plus sûre à la moins sûre ; la colonne `methode_rapprochement` dit laquelle a servi :
1. lien_bdpm   la BDPM cite l'adresse de la fiche ANSM (colonne url_ansm) : lien exact ;
2. nom         le nom ANSM (« Alkonatrem 150 mg, gélule ») est identique à une dénomination BDPM ;
3. substance   la substance ANSM correspond à une substance de la BDPM ou à un libellé ATC5,
               une fois retirés les sels et formes chimiques (« chlorhydrate de », « sodique »…) ;
4. marque      le premier mot du nom (la marque) correspond à des médicaments BDPM d'un seul ATC5.
"""
import pandas as pd

from .commun import CLEAN, enregistrer, normaliser_texte

# Mots qui décrivent la forme chimique (sel, hydrate) et non la substance elle-même.
MOTS_SELS = set("""
de d du des l la le et chlorhydrate dichlorhydrate bromhydrate sodique disodique potassique
calcique magnesique sulfate disulfate phosphate acetate maleate tartrate bitartrate fumarate
succinate citrate mesilate besilate tosilate lactate gluconate nitrate hydrogenotartrate
monohydrate dihydrate trihydrate hemihydrate sesquihydrate anhydre base sel sels forme
""".split())
MOTS_GENERIQUES = {"specialites", "specialite", "a", "base", "medicaments", "tous", "dosages", "vaccin"}


def mots_substance(texte):
    return frozenset(m for m in normaliser_texte(texte).split() if m not in MOTS_SELS)


def atc_unique(atcs):
    """Un seul ATC5 parmi les candidats (le plus fréquent s'il domine nettement), sinon None."""
    comptes = atcs.dropna().value_counts()
    if comptes.empty:
        return None
    if len(comptes) == 1 or comptes.iloc[0] >= 2 * comptes.iloc[1]:
        return comptes.index[0]
    return None


def reperes_atc(produits, compositions, atc):
    """Tables de correspondance vers l'ATC5 pour les voies 2 à 4 : (cis par nom, ATC par substance, ATC par marque).

    Ajoute à `produits` les colonnes `nom_normalise` et `marque`.
    """
    # 2. Dénomination identique.
    produits["nom_normalise"] = produits["denomination"].map(normaliser_texte)
    cis_par_nom = produits.groupby("nom_normalise")["cis"].apply(list)

    # 3. Substance → ATC5 : via les médicaments BDPM mono-substance, puis via les libellés ATC5.
    mono = (compositions[compositions["nature_composant"] == "SA"]
            .merge(produits[produits["nb_substances"] == 1][["cis", "atc5"]], on="cis"))
    mono["mots"] = mono["substance"].map(mots_substance)
    atc_par_substance = mono.groupby("mots")["atc5"].agg(atc_unique).dropna().to_dict()
    for code, libelle in zip(atc["atc5"], atc["libelle_atc5"]):
        atc_par_substance.setdefault(mots_substance(libelle), code)

    # 4. Marque (premier mot du nom).
    produits["marque"] = produits["nom_normalise"].str.split().str[0]
    atc_par_marque = produits.groupby("marque")["atc5"].agg(atc_unique).dropna().to_dict()
    return cis_par_nom, atc_par_substance, atc_par_marque


def construire():
    lire = lambda nom: pd.read_parquet(CLEAN / f"{nom}.parquet")
    observations, produits = lire("ansm_observations"), lire("produits")
    compositions, dispo, atc = lire("bdpm_compositions"), lire("bdpm_dispo_observations"), lire("atc")

    fiches = (observations.sort_values("date_photo").groupby("fiche")
              .agg(medicament=("medicament", "last"),
                   substance=("substance", lambda s: s.dropna().iloc[-1] if s.notna().any() else None),
                   premiere_photo=("date_photo", "min"), derniere_photo=("date_photo", "max"))
              .reset_index())
    atc_du_cis = produits.set_index("cis")["atc5"]

    # 1. Lien exact fourni par la BDPM.
    cis_par_fiche = dispo.dropna(subset=["fiche_ansm"]).groupby("fiche_ansm")["cis"].apply(lambda s: sorted(set(s)))

    cis_par_nom, atc_par_substance, atc_par_marque = reperes_atc(produits, compositions, atc)

    resultats = []
    for fiche in fiches.itertuples():
        cis, atc5, methode = [], None, None
        if fiche.fiche in cis_par_fiche.index:
            cis = cis_par_fiche[fiche.fiche]
            atc5, methode = atc_unique(atc_du_cis.reindex(cis)), "lien_bdpm"
        if atc5 is None and normaliser_texte(fiche.medicament) in cis_par_nom.index:
            cis = cis or cis_par_nom[normaliser_texte(fiche.medicament)]
            atc5, methode = atc_unique(atc_du_cis.reindex(cis)), "nom"
        if atc5 is None and mots_substance(fiche.substance):
            atc5, methode = atc_par_substance.get(mots_substance(fiche.substance)), "substance"
        if atc5 is None:
            marque = normaliser_texte(fiche.medicament).split()[:1]
            if marque and marque[0] not in MOTS_GENERIQUES:
                atc5, methode = atc_par_marque.get(marque[0]), "marque"
        resultats.append({"fiche": fiche.fiche, "cis": "|".join(cis) or None,
                          "atc5": atc5, "methode_rapprochement": methode if atc5 else None})

    fiches = fiches.merge(pd.DataFrame(resultats), on="fiche")
    enregistrer(fiches, "ansm_fiches")
    print("  rapprochement ATC des fiches :",
          fiches["methode_rapprochement"].value_counts(dropna=False).to_dict())
