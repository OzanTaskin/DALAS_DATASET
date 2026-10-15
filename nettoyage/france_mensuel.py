"""France — `penuries_fr_mensuel` : la jointure des deux vues françaises, par substance et par mois.

Une ligne = une substance (ATC5) × un mois. Les deux sources viennent de l'ANSM et se
recouvrent : on ne les empile pas, chacune apporte ses colonnes.
- Signalements officiels (`ansm_signalements`, 2019 à 2025) :
    nb_signalements, nb_laboratoires_signalants
- Page publique reconstruite par les archives (`shortage_events`, France, depuis 04/2021) :
    nb_penuries_affichees           épisodes en cours au moins un jour du mois
    nb_nouvelles_penuries_affichees épisodes qui débutent dans le mois
    gravite_max_affichee            risque_rupture < tension < rupture, parmi les épisodes en cours

Une valeur vide veut dire « mois non couvert par la source », pas zéro : les signalements
s'arrêtent à la dernière année publiée, la page ANSM commence à la première archive.
Les substances sont celles de la BDPM (`produits`) et celles vues dans l'une des deux sources.
Les lignes sans ATC5 des deux sources n'entrent pas dans la table.
"""
import pandas as pd

from .ansm_episodes import GRAVITE
from .commun import CLEAN, enregistrer, normaliser_texte


def mois_de(dates):
    return dates.dt.to_period("M").dt.to_timestamp()


def construire():
    lire = lambda nom: pd.read_parquet(CLEAN / f"{nom}.parquet")
    signalements = lire("ansm_signalements").dropna(subset=["atc5"])
    episodes = lire("shortage_events")
    episodes = episodes[(episodes["pays"] == "FR") & (episodes["type_episode"] == "penurie")]
    episodes = episodes.dropna(subset=["atc5", "debut"])
    photos = lire("ansm_observations")["date_photo"]
    produits = lire("produits")

    # Périodes couvertes : années entières pour les signalements, première à dernière photo pour la page.
    annees = signalements["annee"]
    mois_signalements = pd.date_range(f"{annees.min()}-01-01", f"{annees.max()}-12-01", freq="MS")
    mois_page = pd.date_range(photos.min().replace(day=1), photos.max().replace(day=1), freq="MS")
    tous_les_mois = mois_signalements.union(mois_page)

    signalements = signalements.assign(mois=mois_de(signalements["date_signalement"]),
                                       laboratoire=signalements["laboratoire"].map(normaliser_texte))
    par_signalements = (signalements.groupby(["atc5", "mois"])
                        .agg(nb_signalements=("date_signalement", "size"),
                             nb_laboratoires_signalants=("laboratoire", "nunique")).reset_index())

    # Un épisode compte pour chaque mois entre son début et sa fin (ou la dernière photo s'il est en cours).
    fin = episodes["fin"].fillna(photos.max())
    episodes = episodes.assign(mois_debut=mois_de(episodes["debut"]), gravite=episodes["gravite"].map(GRAVITE),
                               mois=[pd.date_range(d, f, freq="MS") for d, f in zip(mois_de(episodes["debut"]), mois_de(fin))])
    en_cours = episodes.explode("mois").dropna(subset=["mois"]).astype({"mois": "datetime64[ns]"})
    par_page = (en_cours.groupby(["atc5", "mois"])
                .agg(nb_penuries_affichees=("id_episode", "size"), gravite=("gravite", "max")).reset_index())
    nouvelles = (episodes.groupby(["atc5", "mois_debut"]).size().rename("nb_nouvelles_penuries_affichees")
                 .reset_index().rename(columns={"mois_debut": "mois"}))
    noms_gravite = {rang: nom for nom, rang in GRAVITE.items()}
    par_page["gravite_max_affichee"] = par_page.pop("gravite").map(noms_gravite)

    substances = sorted(set(produits["atc5"].dropna()) | set(signalements["atc5"]) | set(episodes["atc5"]))
    table = pd.MultiIndex.from_product([substances, tous_les_mois], names=["atc5", "mois"]).to_frame(index=False)
    table = (table.merge(par_signalements, on=["atc5", "mois"], how="left")
             .merge(par_page, on=["atc5", "mois"], how="left")
             .merge(nouvelles, on=["atc5", "mois"], how="left"))

    # Dans la période couverte, l'absence de ligne est un vrai zéro ; en dehors, la valeur reste vide.
    couvert = {"nb_signalements": mois_signalements, "nb_laboratoires_signalants": mois_signalements,
               "nb_penuries_affichees": mois_page, "nb_nouvelles_penuries_affichees": mois_page}
    for colonne, mois in couvert.items():
        dans_periode = table["mois"].isin(mois)
        table[colonne] = table[colonne].fillna(0).where(dans_periode).astype("Int64")
    table.insert(1, "atc4", table["atc5"].str[:5])
    table = table[["atc5", "atc4", "mois", "nb_signalements", "nb_laboratoires_signalants",
                   "nb_penuries_affichees", "nb_nouvelles_penuries_affichees", "gravite_max_affichee"]]
    enregistrer(table, "penuries_fr_mensuel")
    print(f"  {len(substances)} substances × {len(tous_les_mois)} mois"
          f" ; signalements {mois_signalements[0]:%m/%Y} → {mois_signalements[-1]:%m/%Y}"
          f" ; page ANSM {mois_page[0]:%m/%Y} → {mois_page[-1]:%m/%Y}")
