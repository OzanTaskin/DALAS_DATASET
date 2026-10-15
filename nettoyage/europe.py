"""Italie (AIFA) et Allemagne (BfArM) → `europe_observations` et `europe_episodes`.

Ces listes servent de signaux européens (question 2). Chaque photo (archives Wayback + photo du
jour) donne les pénuries publiées à cette date.

Épisode :
- Italie : une période de présence continue d'un médicament (code AIC) sur la liste, comme pour
  la France : une absence d'une seule photo ne coupe pas l'épisode. L'AIFA révise souvent la date
  de début d'une pénurie déjà listée (2 857 médicaments, presque toujours vers plus tard) : la date
  ne peut donc pas servir à identifier l'épisode, sinon chaque révision crée un faux épisode ;
- Allemagne : une déclaration initiale (« Referenzierte Erstmeldung », ou le numéro de la
  déclaration elle-même si c'est la première, ce que le BfArM écrit vide ou « N/A »). Une déclaration couvre souvent plusieurs boîtes (PZN).

Dates :
- `publication` : première photo où l'épisode est publié. C'est la date à laquelle le signal est
  connu : c'est elle, et non le début déclaré, qu'il faut utiliser pour prédire ;
- `debut` : date de début déclarée. En Italie, la dernière déclarée (la plus à jour) ;
  `debut_declare_initial` garde la première. Elle peut être postérieure à la publication
  (pénurie annoncée à l'avance), voire à la fin si l'annonce a été retirée avant cette date ;
- `fin` : dernière photo où l'épisode est publié ; `fin_au_plus_tard` : la photo suivante, où il
  n'est plus publié. La fin réelle est entre les deux. S'il est publié dans la dernière photo, il
  est `en_cours`. Quand `debut` > `fin`, la pénurie annoncée a duré moins que l'intervalle entre
  deux photos, ou l'annonce a été retirée avant la date prévue.
ATC : seuls les codes ATC5 valides sont gardés. En Italie, la colonne ATC n'existe que depuis
fin 2024 : pour les photos plus anciennes, on reprend l'ATC connu du même code AIC, sinon
celui de la même substance.
Les arrêts définitifs de commercialisation (Italie) ne sont pas des pénuries :
`type_episode` = « arret_definitif ».
"""
import io
import re

import pandas as pd

from .commun import RAW, date_du_fichier, enregistrer

ATC5_VALIDE = re.compile(r"^[A-Z]\d{2}[A-Z]{2}\d{2}$")


def atc5_valide(code):
    code = (code or "").strip().upper() if isinstance(code, str) else ""
    return code if ATC5_VALIDE.match(code) else None


def photos(dossier_wayback, dossier_actuel):
    return (sorted((RAW / "wayback" / dossier_wayback).glob("2*.csv"))
            + sorted((RAW / dossier_actuel / "actuel").glob("*.csv")))


def lire_aifa(chemin):
    # Windows-1252, avec quelques octets invalides (0x9d) dans les lignes d'avertissement : remplacés.
    texte = chemin.read_bytes().decode("cp1252", errors="replace")
    # Deux lignes d'avertissement avant l'en-tête.
    table = pd.read_csv(io.StringIO(texte), sep=";", skiprows=2, dtype=str, keep_default_na=False)
    table = table[table["Codice AIC"].str.strip() != ""]
    return pd.DataFrame({
        "pays": "IT",
        "date_photo": pd.Timestamp(date_du_fichier(chemin)),
        "id_episode": table["Codice AIC"].str.strip() + "_" + table["Data inizio"].str.strip(),
        "code_produit": table["Codice AIC"].str.strip(),
        "medicament": table["Nome medicinale"].str.strip(),
        "substance": table["Principio attivo"].str.strip(),
        "atc5": table.get("Codice ATC", pd.Series(None, index=table.index)).map(atc5_valide),
        "debut": pd.to_datetime(table["Data inizio"], format="%d/%m/%Y", errors="coerce"),
        "fin_prevue": pd.to_datetime(table["Fine presunta"], format="%d/%m/%Y", errors="coerce"),
        "raison": table["Motivazioni"].str.strip().replace("", None),
        "criticite": None,
    })


def lire_bfarm(chemin):
    table = pd.read_csv(chemin, sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
    initiale = table["Referenzierte Erstmeldung"].str.strip()
    return pd.DataFrame({
        "pays": "DE",
        "date_photo": pd.Timestamp(date_du_fichier(chemin)),
        # « N/A » (environ un quart des lignes) veut dire « pas de déclaration initiale » : la ligne est
        # elle-même la première déclaration. Sinon, toutes ces lignes formeraient un seul faux épisode.
        "id_episode": initiale.where(~initiale.isin(["", "N/A"]), table["Bearbeitungsnummer"].str.strip()),
        "code_produit": table["PZN"].str.strip(),
        "medicament": table["Arzneimittlbezeichnung"].str.strip(),
        "substance": table["Wirkstoffe"].str.strip(),
        "atc5": table["Atc Code"].map(atc5_valide),
        "debut": pd.to_datetime(table["Beginn"], format="%d.%m.%Y", errors="coerce"),
        "fin_prevue": pd.to_datetime(table["Ende"], format="%d.%m.%Y", errors="coerce"),
        "raison": table["Art des Grundes"].str.strip().replace("", None),
        # Colonne ajoutée en cours de route : absente des archives les plus anciennes.
        "criticite": table["klassifikation"].str.strip().replace("", None) if "klassifikation" in table else None,
    })


def episodes_italiens(observations):
    """Identifiant d'épisode italien : AIC + mois de la première photo d'une présence continue.

    Un nouvel épisode commence quand le médicament était absent de plus d'une photo, ou quand il
    passe de pénurie à arrêt définitif (ou l'inverse).
    """
    italie = observations["pays"] == "IT"
    it = observations[italie].copy()
    it["arret"] = it["raison"].fillna("").str.contains("Cessata commercializzazione definitiva")
    rang = {photo: i for i, photo in enumerate(sorted(it["date_photo"].unique()))}
    it["rang"] = it["date_photo"].map(rang)

    presences = (it.groupby(["code_produit", "rang"], as_index=False).agg(arret=("arret", "max"))
                 .sort_values(["code_produit", "rang"]))
    par_produit = presences.groupby("code_produit")
    presences["nouveau"] = (par_produit["rang"].diff().isna() | (par_produit["rang"].diff() > 2)
                            | (par_produit["arret"].shift() != presences["arret"]))
    presences["numero"] = presences.groupby("code_produit")["nouveau"].cumsum()
    premiere = presences.groupby(["code_produit", "numero"])["rang"].transform("min")
    photos = sorted(rang)
    presences["id_episode"] = (presences["code_produit"] + "_"
                               + premiere.map(lambda r: f"{pd.Timestamp(photos[r]):%Y%m}"))

    # Affectation en place : l'ordre des lignes ne change pas.
    ids = presences.set_index(["code_produit", "rang"])["id_episode"]
    observations = observations.copy()
    observations.loc[italie, "id_episode"] = ids.reindex(
        pd.MultiIndex.from_frame(it[["code_produit", "rang"]])).to_numpy()
    return observations


def construire():
    observations = pd.concat(
        [lire_aifa(c) for c in photos("aifa_carenti", "aifa")]
        + [lire_bfarm(c) for c in photos("bfarm_lieferengpaesse", "bfarm")], ignore_index=True)

    # Italie : ATC repris du même code AIC quand la photo n'a pas encore la colonne ATC.
    atc_par_produit = (observations.dropna(subset=["atc5"]).sort_values("date_photo")
                       .drop_duplicates(["pays", "code_produit"], keep="last")
                       .set_index(["pays", "code_produit"])["atc5"])
    manquant = observations["atc5"].isna()
    cles = pd.MultiIndex.from_frame(observations.loc[manquant, ["pays", "code_produit"]])
    observations.loc[manquant, "atc5"] = atc_par_produit.reindex(cles).to_numpy()
    # Sinon, ATC le plus fréquent pour la même substance dans le même pays.
    atc_par_substance = (observations.dropna(subset=["atc5"])
                         .groupby(["pays", "substance"])["atc5"].agg(lambda s: s.mode().iloc[0]))
    manquant = observations["atc5"].isna()
    cles = pd.MultiIndex.from_frame(observations.loc[manquant, ["pays", "substance"]])
    observations.loc[manquant, "atc5"] = atc_par_substance.reindex(cles).to_numpy()
    observations = episodes_italiens(observations.drop_duplicates())
    enregistrer(observations, "europe_observations")

    derniere_photo = observations.groupby("pays")["date_photo"].max()
    episodes = (observations.sort_values("date_photo").groupby(["pays", "id_episode"])
                .agg(medicament=("medicament", "last"), substance=("substance", "last"),
                     atc5=("atc5", lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None),
                     nb_produits=("code_produit", "nunique"),
                     debut_min=("debut", "min"), debut_declare_initial=("debut", "first"),
                     debut_dernier=("debut", "last"), fin_prevue=("fin_prevue", "last"),
                     premiere_photo=("date_photo", "min"), derniere_photo=("date_photo", "max"),
                     raison=("raison", "last"), criticite=("criticite", "last"))
                .reset_index())
    # Italie : la date la plus à jour ; Allemagne : la plus ancienne déclarée pour la déclaration initiale.
    episodes.insert(episodes.columns.get_loc("debut_min"), "debut",
                    episodes["debut_dernier"].where(episodes["pays"] == "IT", episodes["debut_min"]))
    episodes = episodes.drop(columns=["debut_min", "debut_dernier"])
    episodes["publication"] = episodes["premiere_photo"]
    # Un arrêt définitif de commercialisation n'est pas une pénurie : on le distingue.
    arret = episodes["raison"].fillna("").str.contains("Cessata commercializzazione definitiva")
    episodes["type_episode"] = arret.map({True: "arret_definitif", False: "penurie"})
    episodes["en_cours"] = episodes["derniere_photo"] == episodes["pays"].map(derniere_photo)
    episodes["fin"] = episodes["derniere_photo"].where(~episodes["en_cours"])
    photos_par_pays = observations.groupby("pays")["date_photo"].unique().map(sorted)
    photo_suivante = {(pays, photo): suivante for pays, photos in photos_par_pays.items()
                      for photo, suivante in zip(photos, photos[1:])}
    episodes["fin_au_plus_tard"] = [photo_suivante.get((pays, fin)) if pd.notna(fin) else pd.NaT
                                    for pays, fin in zip(episodes["pays"], episodes["fin"])]
    episodes["fin_au_plus_tard"] = pd.to_datetime(episodes["fin_au_plus_tard"])
    enregistrer(episodes, "europe_episodes")
    for pays, groupe in episodes.groupby("pays"):
        print(f"  {pays} : {len(groupe)} épisodes, ATC5 connu pour {groupe['atc5'].notna().mean():.0%}")
