"""France — `ansm_episodes` : les observations mensuelles ANSM regroupées en épisodes de pénurie.

Une fiche ANSM suit un médicament ; elle peut connaître plusieurs épisodes
(tension → remise à disposition → tension…). Un épisode est une suite d'observations
« actives » (rupture, tension, risque de rupture) d'une même fiche.

Règles (vérifiées sur les données le 08/10/2026) :
- Début : date « mise à jour » de la première observation active. À la première apparition
  d'une fiche, cette date tombe entre la photo précédente et la photo courante dans 98,5 % des
  cas : c'est la date de publication. On la borne à cet intervalle. Si la BDPM donne une date
  de début exacte (fichier de disponibilité, depuis 12/2023), on la préfère.
- Fin : date de remise à disposition affichée ; sinon date de mise à jour de l'observation
  « remise à disposition » ; sinon (fiche disparue sans remise) la dernière photo où elle était active.
- Une absence d'une seule photo ne coupe pas l'épisode (archives irrégulières).
- Fiche vue seulement au statut « remise à disposition » : la pénurie a eu lieu entre deux photos.
  L'épisode est gardé, avec un début inconnu (`debut` vide, `debut_au_plus_tot` = photo précédente).
- Épisode déjà en cours à la première photo (avril 2021) : `censure_gauche` = vrai.
- `premiere_photo` : première photo où l'épisode est visible (actif ou remis à disposition) :
  c'est la date à laquelle le public le sait.
- `fin_connue_le` : photo où l'on voit que l'épisode est terminé (remise à disposition ou arrêt
  affiché, ou première photo où la fiche a disparu). La table est complétée après coup, comme un
  « accumulating snapshot » : à une date d, `fin`, `type_fin` et `duree_jours` ne sont connus que si
  `fin_connue_le < d`. Une variable de prédiction ne doit pas les lire sans ce filtre.
- Épisode encore actif à la dernière photo : `en_cours` = vrai, `fin` vide.
"""
import pandas as pd

from .commun import CLEAN, enregistrer

ACTIFS = {"rupture", "tension", "risque_rupture"}
GRAVITE = {"risque_rupture": 1, "tension": 2, "rupture": 3}


def episodes_d_une_fiche(obs, photos, rang):
    """obs : observations d'une fiche triées par date. Renvoie une liste d'épisodes (dict)."""
    episodes, courant = [], None

    def fermer(fin, type_fin, fin_connue_le):
        courant.update(fin=fin, type_fin=type_fin, fin_connue_le=fin_connue_le)
        episodes.append(courant)

    def photo_apres(photo):
        return photos[rang[photo] + 1]

    precedent_rang = None
    for o in obs.itertuples():
        r = rang[o.date_photo]
        photo_precedente = photos[r - 1] if r > 0 else None
        # Absence de plus d'une photo : la fiche avait disparu, l'épisode en cours s'est terminé.
        if courant is not None and precedent_rang is not None and r - precedent_rang > 2:
            fermer(courant["derniere_photo_active"], "disparition", photo_apres(courant["derniere_photo_active"]))
            courant = None

        if o.statut in ACTIFS:
            if courant is None:
                if r == 0:
                    debut, censure = o.date_mise_a_jour, True
                else:
                    debut = min(max(o.date_mise_a_jour, photo_precedente), o.date_photo)
                    censure = False
                courant = {"debut": debut, "debut_au_plus_tot": photo_precedente, "censure_gauche": censure,
                           "premiere_photo": o.date_photo, "premiere_photo_active": o.date_photo,
                           "gravite_max": o.statut}
            if GRAVITE[o.statut] > GRAVITE[courant["gravite_max"]]:
                courant["gravite_max"] = o.statut
            courant["derniere_photo_active"] = o.date_photo
        elif o.statut == "remise_a_disposition":
            fin = o.date_remise_a_disposition if pd.notna(o.date_remise_a_disposition) else o.date_mise_a_jour
            if courant is not None:
                fermer(fin, "remise_a_disposition", o.date_photo)
                courant = None
            elif not episodes or episodes[-1]["type_fin"] != "remise_a_disposition" or r - precedent_rang > 2:
                # Pénurie apparue et résolue entre deux photos.
                episodes.append({"debut": None, "debut_au_plus_tot": photo_precedente, "censure_gauche": r == 0,
                                 "premiere_photo": o.date_photo,
                                 "premiere_photo_active": None, "derniere_photo_active": None,
                                 "gravite_max": None, "fin": fin, "type_fin": "remise_a_disposition",
                                 "fin_connue_le": o.date_photo})
        elif o.statut == "arret_commercialisation" and courant is not None:
            fermer(o.date_mise_a_jour, "arret_commercialisation", o.date_photo)
            courant = None
        precedent_rang = r

    if courant is not None:
        if precedent_rang == len(photos) - 1:
            courant.update(fin=None, type_fin="en_cours", fin_connue_le=None)
            episodes.append(courant)
        else:
            fermer(courant["derniere_photo_active"], "disparition", photo_apres(courant["derniere_photo_active"]))
    return episodes


def construire():
    observations = pd.read_parquet(CLEAN / "ansm_observations.parquet").sort_values(["fiche", "date_photo"])
    fiches = pd.read_parquet(CLEAN / "ansm_fiches.parquet")
    dispo = pd.read_parquet(CLEAN / "bdpm_dispo_observations.parquet")

    photos = sorted(observations["date_photo"].unique())
    rang = {photo: i for i, photo in enumerate(photos)}
    lignes = []
    for fiche, obs in observations.groupby("fiche", sort=False):
        for numero, episode in enumerate(episodes_d_une_fiche(obs, photos, rang), start=1):
            lignes.append({"fiche": fiche, "numero_episode": numero, **episode})
    episodes = pd.DataFrame(lignes)

    # Date de début exacte de la BDPM, quand elle existe et tombe dans la fenêtre de l'épisode.
    debuts_bdpm = dispo.dropna(subset=["fiche_ansm", "date_debut"])[["fiche_ansm", "date_debut"]].drop_duplicates()
    candidats = episodes.reset_index().merge(debuts_bdpm, left_on="fiche", right_on="fiche_ansm")
    reference = candidats["premiere_photo_active"].fillna(candidats["fin"])
    dans_fenetre = (candidats["date_debut"] <= reference) & (
        candidats["debut_au_plus_tot"].isna() | candidats["censure_gauche"]
        | (candidats["date_debut"] >= candidats["debut_au_plus_tot"] - pd.Timedelta(days=60)))
    exacts = candidats[dans_fenetre].groupby("index")["date_debut"].max()
    episodes["source_debut"] = "ansm"
    episodes.loc[exacts.index, "debut"] = exacts
    episodes.loc[exacts.index, "source_debut"] = "bdpm"
    episodes.loc[episodes["debut"].isna(), "source_debut"] = None

    episodes["en_cours"] = episodes["type_fin"] == "en_cours"
    episodes["duree_jours"] = (episodes["fin"] - episodes["debut"]).dt.days
    episodes = episodes.merge(fiches[["fiche", "medicament", "substance", "atc5", "methode_rapprochement"]],
                              on="fiche", how="left")
    enregistrer(episodes, "ansm_episodes")
    print("  fin des épisodes :", episodes["type_fin"].value_counts().to_dict())
    print("  origine du début :", episodes["source_debut"].value_counts(dropna=False).to_dict())
