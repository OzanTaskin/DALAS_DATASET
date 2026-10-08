"""`shortage_events` : la table centrale du niveau 2. Une ligne = un épisode de pénurie,
dans un pays, au même format pour la France, l'Italie et l'Allemagne.

Colonnes communes :
    pays, id_episode, medicament, substance, atc5, atc4, debut, fin, en_cours,
    type_episode (penurie / arret_definitif), gravite (FR), criticite (DE), raison (IT, DE),
    debut_connu (faux si le début n'est connu qu'approximativement)
La France vient de `ansm_episodes`, l'Italie et l'Allemagne de `europe_episodes`.
"""
import pandas as pd

from .commun import CLEAN, enregistrer

COLONNES = ["pays", "id_episode", "medicament", "substance", "atc5", "atc4", "debut", "fin",
            "en_cours", "type_episode", "gravite", "criticite", "raison", "debut_connu"]


def construire():
    france = pd.read_parquet(CLEAN / "ansm_episodes.parquet")
    europe = pd.read_parquet(CLEAN / "europe_episodes.parquet")

    france = france.assign(
        pays="FR",
        id_episode=france["fiche"] + "_" + france["numero_episode"].astype(str),
        # Épisode vu seulement à sa remise à disposition : début borné par la photo précédente.
        debut_connu=france["debut"].notna(),
        debut=france["debut"].fillna(france["debut_au_plus_tot"]),
        type_episode="penurie", gravite=france["gravite_max"], criticite=None, raison=None)
    europe = europe.assign(gravite=None, debut_connu=True)

    evenements = pd.concat([france, europe], ignore_index=True)
    evenements["atc4"] = evenements["atc5"].str[:5]
    evenements = evenements[COLONNES].sort_values(["pays", "debut"]).reset_index(drop=True)
    enregistrer(evenements, "shortage_events")
    print("  " + evenements.groupby(["pays", "type_episode"]).size().to_string().replace("\n", "\n  "))
