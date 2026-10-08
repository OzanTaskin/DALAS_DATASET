"""France — `produits` : chaque médicament (CIS) de la BDPM avec son code ATC5.

La BDPM ne donne pas l'ATC. On l'obtient par trois voies, de la plus sûre à la moins sûre ;
la colonne `source_atc` dit laquelle a servi :
1. open_medic      les boîtes (CIP13) du médicament remboursées en ville ont un ATC dans Open Medic ;
2. mitm            le médicament est sur la liste MITM, qui fournit l'ATC ;
3. memes_substances un autre médicament contenant exactement les mêmes substances actives a un ATC
                   (cas fréquent : médicaments hospitaliers, absents d'Open Medic).
Quand une voie propose plusieurs ATC pour un même CIS, on garde le plus fréquent.
"""
import pandas as pd

from .commun import CLEAN, enregistrer


def plus_frequent(table, cle, valeur):
    return (table.groupby([cle, valeur]).size().rename("n").reset_index()
            .sort_values([cle, "n"], ascending=[True, False]).drop_duplicates(cle)[[cle, valeur]])


def construire():
    lire = lambda nom: pd.read_parquet(CLEAN / f"{nom}.parquet")
    specialites, presentations = lire("bdpm_specialites"), lire("bdpm_presentations")
    compositions, mitm, cip_atc = lire("bdpm_compositions"), lire("bdpm_mitm"), lire("cip_atc")

    # 1. Open Medic (seulement les codes ATC5 complets, 7 caractères).
    via_open_medic = plus_frequent(
        presentations.merge(cip_atc[cip_atc["atc5"].str.len() == 7], on="cip13"), "cis", "atc5")
    # 2. Liste MITM.
    via_mitm = plus_frequent(mitm.dropna(subset=["atc5"]), "cis", "atc5")
    connus = pd.concat([via_open_medic.assign(source_atc="open_medic"),
                        via_mitm.assign(source_atc="mitm")]).drop_duplicates("cis")

    # 3. Même ensemble de substances actives (SA). Les fractions thérapeutiques (FT) décrivent la
    #    même substance sous une autre forme : on ne les compte pas.
    substances = (compositions[compositions["nature_composant"] == "SA"]
                  .groupby("cis")["code_substance"].apply(lambda s: "|".join(sorted(set(s))))
                  .rename("cle_substances").reset_index())
    par_substances = plus_frequent(substances.merge(connus, on="cis"), "cle_substances", "atc5")
    via_substances = (substances[~substances["cis"].isin(connus["cis"])]
                      .merge(par_substances, on="cle_substances")[["cis", "atc5"]])
    connus = pd.concat([connus, via_substances.assign(source_atc="memes_substances")])

    produits = (specialites.merge(connus, on="cis", how="left")
                .merge(substances, on="cis", how="left"))
    produits["nb_substances"] = produits["cle_substances"].str.count(r"\|") + 1
    enregistrer(produits, "produits")

    commercialises = produits[produits["etat_commercialisation"] == "Commercialisée"]
    print("  couverture ATC des médicaments commercialisés :",
          commercialises["source_atc"].value_counts(dropna=False).to_dict())
