"""Niveau 3 — `panel_fr` : la table d'entraînement, une ligne par substance (ATC5) et par mois t.

Cohorte : les substances qui ont au moins un médicament d'intérêt thérapeutique majeur (MITM)
commercialisé (les signalements ne concernent que ces médicaments : 24 % de cas positifs contre 3 %).
Mois t : de 01/2019 à 09/2025. Le dernier t a ses trois mois de cible complets (signalements publiés
jusqu'en 12/2025).

Cible `cible` : 1 si au moins un signalement de rupture est déclaré à l'ANSM pour la substance
entre t+1 et t+3.

Règle de temps : une variable d'une ligne (substance, t) n'utilise que ce qui était connu à la fin
du mois t. Un épisode de pénurie compte comme affiché de sa `publication` jusqu'à `fin_connue_le`
(date où l'on a vu qu'il avait disparu), jamais jusqu'à sa `fin` réelle, connue plus tard. Les
signalements ne servent qu'en cumul des années civiles précédentes (publiés avec retard).

Valeurs vides : une variable est vide quand la source ne couvre pas le mois (page ANSM avant
06/2021, Italie avant 12/2021, Allemagne avant 09/2024, consommation avant 2020 ou substance absente d'Open Medic). Ce n'est pas
un zéro.

Découpage `jeu` (temporel, avec trois mois d'écart car la cible regarde trois mois en avant) :
entraînement t ≤ 09/2023, écart, validation 01/2024 à 09/2024, écart, test 01/2025 à 09/2025.
Les lignes d'écart restent dans la table (jeu = "ecart") mais ne servent à aucun jeu.
"""
import shutil
from datetime import date

import numpy as np
import pandas as pd

from .commun import CLEAN, RACINE, enregistrer

FINAL = RACINE / "data" / "final"
MOIS = pd.period_range("2019-01", "2025-12", freq="M")  # période couverte par les signalements
HORIZON = 3
T = len(MOIS) - HORIZON  # dernier t : ses 3 mois de cible sont complets
PREMIER_MOIS = {  # premier t dont les 3 mois précédents sont couverts par la source
    "FR": pd.Period("2021-06", "M"), "IT": pd.Period("2021-12", "M"), "DE": pd.Period("2024-09", "M")}
DECOUPAGE = [("entrainement", "2019-01", "2023-09"), ("ecart", "2023-10", "2023-12"),
             ("validation", "2024-01", "2024-09"), ("ecart", "2024-10", "2024-12"), ("test", "2025-01", "2025-09")]


def lire(nom):
    return pd.read_parquet(CLEAN / f"{nom}.parquet")


def cohorte():
    """Substances avec au moins un MITM commercialisé, et celles sans."""
    produits, mitm = lire("produits"), lire("bdpm_mitm")
    commercialises = produits[(produits["etat_commercialisation"] == "Commercialisée") & produits["atc5"].str.len().eq(7)]
    avec = set(commercialises[commercialises["cis"].isin(mitm["cis"])]["atc5"])
    return sorted(avec), sorted(set(commercialises["atc5"]) - avec)


def presence_mensuelle(table, colonne_date, substances):
    """Matrice substances × mois (MOIS) : vrai si au moins une ligne dans le mois."""
    croisement = pd.crosstab(table["atc5"], table[colonne_date].dt.to_period("M"))
    return (croisement.reindex(index=substances, columns=MOIS, fill_value=0) > 0).to_numpy()


def affichage_mensuel(episodes, substances):
    """Matrice substances × mois : l'épisode figure sur la liste publiée pendant le mois.
    De la `publication` jusqu'au mois de `fin_connue_le` compris (jusqu'à la fin si l'on n'a pas vu sa fin)."""
    matrice = np.zeros((len(substances), len(MOIS)), dtype=bool)
    ligne = {s: i for i, s in enumerate(substances)}
    episodes = episodes.dropna(subset=["atc5", "publication"])
    def indice(dates):
        return (dates.dt.year - MOIS[0].year) * 12 + dates.dt.month - MOIS[0].month
    debut = indice(episodes["publication"]).clip(lower=0).to_numpy()
    fin = indice(episodes["fin_connue_le"]).fillna(len(MOIS) - 1).astype(int).to_numpy()
    for atc5, a, b in zip(episodes["atc5"], debut, fin):
        if atc5 in ligne and b >= a:
            matrice[ligne[atc5], a:min(b, len(MOIS) - 1) + 1] = True
    return matrice


def sur_3_mois(matrice):
    """Vrai à t si vrai à l'un des mois t-2, t-1, t."""
    sortie = matrice.copy()
    sortie[:, 1:] |= matrice[:, :-1]
    sortie[:, 2:] |= matrice[:, :-2]
    return sortie


def autres_de_la_classe(matrice, substances):
    """Nombre d'autres substances de la même classe ATC4 (5 premiers caractères) affichées."""
    classe = np.array([s[:5] for s in substances])
    sortie = np.zeros(matrice.shape, dtype=np.int16)
    for c in sorted(set(classe)):
        membres = np.where(classe == c)[0]
        total = matrice[membres].sum(axis=0)
        sortie[membres] = total - matrice[membres]
    return sortie


def variables_page(evenements, substances):
    """Variables issues des pénuries publiées (France, Italie, Allemagne), sur les 3 derniers mois."""
    pages = {pays: sur_3_mois(affichage_mensuel(evenements[evenements["pays"] == pays], substances)) for pays in PREMIER_MOIS}
    return {"fr_affichee_3m": pages["FR"], "fr_autres_classe_3m": autres_de_la_classe(pages["FR"], substances),
            "it_affichee_3m": pages["IT"], "de_affichee_3m": pages["DE"]}


def construire():
    avec, sans = cohorte()
    signalements = lire("ansm_signalements").dropna(subset=["atc5"])
    evenements = lire("shortage_events")
    evenements = evenements[evenements["type_episode"] == "penurie"]
    tout = sorted(set(avec) | set(sans) | set(signalements["atc5"]) | set(evenements["atc5"].dropna()))
    ligne = {s: i for i, s in enumerate(tout)}
    lignes = [ligne[s] for s in avec]
    mois = MOIS[:T]

    S = presence_mensuelle(signalements, "date_signalement", tout)
    cible = (S[:, 1:T + 1] | S[:, 2:T + 2] | S[:, 3:T + 3])[lignes]

    colonnes = {"atc5": np.repeat(avec, T), "mois": np.tile(mois.to_timestamp(), len(avec)),
                "cible": cible.ravel().astype("int8")}
    table = pd.DataFrame(colonnes)
    table["annee"] = table["mois"].dt.year.astype("int16")
    table["mois_num"] = table["mois"].dt.month.astype("int8")
    table["jeu"] = pd.Series("ecart", index=table.index)
    for jeu, a, b in DECOUPAGE:
        table.loc[(table["mois"] >= pd.Period(a, "M").to_timestamp()) & (table["mois"] <= pd.Period(b, "M").to_timestamp()), "jeu"] = jeu
    table["jeu"] = table["jeu"].astype(pd.CategoricalDtype(["entrainement", "validation", "test", "ecart"]))

    # Variables de la page (France, Italie, Allemagne) ; vides avant la couverture de la source
    for nom, matrice in variables_page(evenements, tout).items():
        valeurs = pd.array(matrice[lignes][:, :T].astype("int16").ravel(), dtype="Int16")
        pays = {"fr": "FR", "it": "IT", "de": "DE"}[nom[:2]]
        observe = np.tile(mois >= PREMIER_MOIS[pays], len(avec))
        table[nom] = pd.Series(valeurs).where(observe)
        if nom != "fr_autres_classe_3m":
            table[nom] = table[nom].astype("Int8")

    # Signalements des années civiles précédentes (publiés avec retard : ni mois en cours ni année en cours)
    par_annee = signalements.assign(a=signalements["annee"]).groupby(["atc5", "a"]).size().unstack(fill_value=0)
    par_annee = par_annee.reindex(index=avec, columns=range(2019, 2026), fill_value=0)
    cumul = par_annee.cumsum(axis=1)
    annee = table["annee"].to_numpy()
    base = pd.Series(np.repeat(np.arange(len(avec)), T))
    precedente = par_annee.to_numpy()[base, np.clip(annee - 2019 - 1, 0, None)]
    cumulee = cumul.to_numpy()[base, np.clip(annee - 2019 - 1, 0, None)]
    couvert = annee >= 2020
    table["sig_an_prec"] = pd.Series(precedente).where(couvert).astype("Int32")
    table["sig_cumul_avant"] = pd.Series(cumulee).where(couvert).astype("Int32")

    # Demande : année civile précédente (Open Medic, 2019 à 2025)
    conso = lire("consommation").set_index(["atc5", "annee"])
    cle = pd.MultiIndex.from_arrays([table["atc5"], table["annee"] - 1])
    table["conso_boites_an_prec"] = pd.array(conso["boites"].reindex(cle).to_numpy(), dtype="Int64")
    table["conso_presentations_an_prec"] = pd.array(conso["nb_presentations"].reindex(cle).to_numpy(), dtype="Int64")

    # Criticité : substance inscrite à la liste critique de l'UE à la fin du mois t
    ue = lire("ue_liste_critique").drop_duplicates("atc5").set_index("atc5")["date_inscription"]
    inscrite = table["atc5"].map(ue)
    table["ue_critique"] = (inscrite <= table["mois"] + pd.offsets.MonthEnd(0)).fillna(False).astype("int8")

    table = table.sort_values(["atc5", "mois"], ignore_index=True)
    FINAL.mkdir(parents=True, exist_ok=True)
    enregistrer(table, "panel_fr", dossier=FINAL)
    controler(table, avec, evenements, tout)
    dossier = RACINE / "manifestes"
    dossier.mkdir(exist_ok=True)
    copie = dossier / f"niveau3_{date.today().isoformat()}.json"
    shutil.copyfile(FINAL / "manifeste.json", copie)
    print(f"  manifeste copié dans {copie.relative_to(RACINE)} (à commiter)")


def controler(table, avec, evenements, tout):
    """Contrôles du niveau 3 ; le premier en échec arrête la construction."""
    def verifier(nom, reussi, detail):
        if not reussi:
            raise SystemExit(f"Contrôle en échec : {nom} — {detail}")
        print(f"  ✓ {nom}")

    doublons = table.duplicated(["atc5", "mois"]).sum()
    verifier("grain panel_fr (atc5, mois)", doublons == 0, f"{doublons} doublons")
    verifier("une ligne par substance de la cohorte et par mois", len(table) == len(avec) * T,
             f"{len(table)} lignes, attendu {len(avec) * T}")
    taux = table["cible"].mean()
    verifier("taux de cas positifs plausible (15 % à 35 %)", 0.15 < taux < 0.35, f"{taux:.3f}")
    ordre = [("entrainement", "validation"), ("validation", "test")]
    for avant, apres in ordre:
        fin_avant = table.loc[table["jeu"] == avant, "mois"].max()
        debut_apres = table.loc[table["jeu"] == apres, "mois"].min()
        ecart = (debut_apres.year - fin_avant.year) * 12 + debut_apres.month - fin_avant.month
        verifier(f"écart d'au moins {HORIZON} mois entre {avant} et {apres}", ecart > HORIZON, f"{ecart} mois")

    # Variables annuelles : recalcul indépendant depuis les tables sources, ligne par ligne.
    signalements = lire("ansm_signalements").dropna(subset=["atc5"])
    par = signalements.groupby(["atc5", "annee"]).size()
    echantillon = table[table["annee"] >= 2021].sample(2000, random_state=0)
    attendu = [int(par.get((a, y - 1), 0)) for a, y in zip(echantillon["atc5"], echantillon["annee"])]
    verifier("sig_an_prec = signalements de l'année civile précédente", list(echantillon["sig_an_prec"]) == attendu, "écart")
    cumul = [int(sum(par.get((a, k), 0) for k in range(2019, y))) for a, y in zip(echantillon["atc5"], echantillon["annee"])]
    verifier("sig_cumul_avant = signalements des années civiles précédentes", list(echantillon["sig_cumul_avant"]) == cumul, "écart")
    conso = lire("consommation").set_index(["atc5", "annee"])["boites"]
    attendu = [conso.get((a, y - 1), pd.NA) for a, y in zip(echantillon["atc5"], echantillon["annee"])]
    egal = all((pd.isna(x) and pd.isna(y)) or x == y for x, y in zip(echantillon["conso_boites_an_prec"], attendu))
    verifier("conso_boites_an_prec = consommation de l'année civile précédente", egal, "écart")

    # Aucune fuite : recalculer les variables en ne gardant que ce qui était publié à la fin de t0
    # doit redonner exactement les valeurs du mois t0 (un épisode terminé après t0 y est « en cours »).
    t0 = pd.Period("2024-06", "M")
    fin_t0 = t0.end_time
    tronque = evenements[evenements["publication"] <= fin_t0].copy()
    tronque.loc[tronque["fin_connue_le"] > fin_t0, "fin_connue_le"] = pd.NaT
    index_t0 = int((t0 - MOIS[0]).n)
    lignes = [tout.index(s) for s in avec]
    complet, partiel = variables_page(evenements, tout), variables_page(tronque, tout)
    for nom in complet:
        egal = np.array_equal(complet[nom][lignes][:, index_t0], partiel[nom][lignes][:, index_t0])
        verifier(f"{nom} au mois {t0} ne lit rien de postérieur", egal, "valeur différente après troncature")
