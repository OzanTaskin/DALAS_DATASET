"""France — la BDPM dans le temps → dimensions historisées `bdpm_*_historique` (SCD type 2).

Pourquoi : décrire le marché d'un mois passé avec la BDPM du jour ferait fuir de l'information
(un générique retiré à cause d'une pénurie disparaîtrait du passé). Les archives Wayback
(2015 → 2026) et la photo du jour donnent ce qui était publié à chaque date.

Tables produites (une ligne = une version d'un objet, valable sur [valid_from, valid_to)) :
- bdpm_specialites_historique   un médicament (CIS) : nom, forme, voies, titulaires, commercialisé ou non
- bdpm_presentations_historique une boîte (CIP13) : son CIS, commercialisée ou non
- bdpm_generiques_historique    l'appartenance d'un CIS à un groupe générique, avec son type

Règles :
- valid_from : première photo où la version est vue ; valid_to : première photo où elle ne l'est
  plus (attribut changé ou objet absent) ; vide si elle est encore valable à la dernière photo.
  Le vrai changement a eu lieu entre la photo précédente et valid_from : la date est approchée par
  excès, on n'utilise donc jamais une information avant sa publication.
- Jointure as-of à la date d : valid_from <= d < valid_to (ou valid_to vide).
- Photos tronquées écartées : la Wayback Machine a coupé à 1 Mio (1 048 576 octets) une partie
  des archives de 2019 à 2025. Un fichier tronqué ferait « disparaître » des milliers de
  médicaments : on ne garde que les fichiers qui se terminent par une fin de ligne.
- Seules les premières colonnes sont lues : elles sont stables depuis 2015, les suivantes (prix,
  honoraires) ont été ajoutées en cours de route.
"""
import pandas as pd

from .bdpm import TYPES_GENERIQUE, decoder
from .commun import RAW, date_du_fichier, enregistrer, normaliser_texte

TAILLE_TRONQUEE = 1_048_576  # 1 Mio : taille à laquelle la Wayback Machine coupe certaines archives

# fichier BDPM : (dossier Wayback, {position de la colonne: nom})
FICHIERS = {
    "CIS_bdpm": ("bdpm_cis", {0: "cis", 1: "denomination", 2: "forme", 3: "voies",
                              6: "etat_commercialisation", 10: "titulaires"}),
    "CIS_CIP_bdpm": ("bdpm_cip", {0: "cis", 4: "etat_commercialisation", 6: "cip13"}),
    "CIS_GENER_bdpm": ("bdpm_gener", {0: "groupe_generique", 2: "cis", 3: "type_generique"}),
}


def photos_completes(fichier):
    dossier, _ = FICHIERS[fichier]
    chemins = (sorted((RAW / "wayback" / dossier).glob("2*.txt"))
               + sorted((RAW / "bdpm" / "actuel").glob(f"*_{fichier}.txt")))
    # Tronqué = coupé à 1 Mio par la Wayback Machine. La coupure tombe parfois pile sur une fin de
    # ligne (CIS_bdpm du 28/09/2022) : la taille exacte compte autant que le dernier caractère.
    completes = [c for c in chemins
                 if c.read_bytes().endswith(b"\n") and c.stat().st_size != TAILLE_TRONQUEE]
    print(f"  {fichier:15} {len(completes)} photos complètes sur {len(chemins)} "
          f"({date_du_fichier(completes[0]):%m/%Y} → {date_du_fichier(completes[-1]):%m/%Y})")
    return completes


def lire_photo(chemin, fichier):
    # Découpage à la main : le nombre de colonnes varie selon l'année, et même d'une ligne à l'autre
    # (tabulation finale présente ou non), ce que read_csv refuse.
    colonnes = FICHIERS[fichier][1]
    lignes = [ligne.split("\t") for ligne in decoder(chemin.read_bytes()).splitlines() if ligne.strip()]
    table = pd.DataFrame([[l[i].strip() if i < len(l) else "" for i in colonnes] for l in lignes],
                         columns=list(colonnes.values())).replace("", None)
    table["date_photo"] = pd.Timestamp(date_du_fichier(chemin))
    return table


def historiser(photos, cle, attributs):
    """Photos successives (une ligne par objet et par photo) → une ligne par version."""
    dates = sorted(photos["date_photo"].unique())
    suivante = dict(zip(dates, dates[1:]))
    photos = photos.drop_duplicates([*cle, "date_photo"]).sort_values([*cle, "date_photo"])
    photos["rang"] = photos["date_photo"].map({d: i for i, d in enumerate(dates)})
    # Une nouvelle version commence quand l'objet apparaît, réapparaît après une absence, ou
    # quand un attribut change. On compare chaque photo à celle qui la précède dans la série.
    groupe = photos.groupby(cle, sort=False)
    reapparu = groupe["rang"].diff().fillna(len(dates)) > 1
    change = (groupe[attributs].shift().fillna("∅") != photos[attributs].fillna("∅")).any(axis=1)
    photos["version"] = (reapparu | change).groupby([photos[c] for c in cle]).cumsum()
    versions = (photos.groupby([*cle, "version"], sort=False)
                .agg(**{a: (a, "first") for a in attributs},
                     valid_from=("date_photo", "min"), derniere_photo=("date_photo", "max"))
                .reset_index())
    versions["valid_to"] = versions["derniere_photo"].map(suivante)
    versions["valid_to"] = pd.to_datetime(versions["valid_to"])
    return versions.drop(columns=["version", "derniere_photo"])


def commercialise(etat):
    """« Commercialisée » / « Non commercialisée » (médicament) ; « Déclaration de
    commercialisation » / « Déclaration d'arrêt de commercialisation » (boîte)."""
    texte = etat.map(normaliser_texte)
    return texte.str.startswith("commercialis") | (texte == "declaration de commercialisation")


def construire():
    lire = lambda fichier: pd.concat([lire_photo(c, fichier) for c in photos_completes(fichier)],
                                     ignore_index=True)

    specialites = lire("CIS_bdpm")
    specialites["commercialise"] = commercialise(specialites.pop("etat_commercialisation"))
    enregistrer(historiser(specialites, ["cis"], ["denomination", "forme", "voies", "titulaires",
                                                  "commercialise"]),
                "bdpm_specialites_historique")

    presentations = lire("CIS_CIP_bdpm").dropna(subset=["cip13"])
    presentations["commercialisee"] = commercialise(presentations.pop("etat_commercialisation"))
    enregistrer(historiser(presentations, ["cip13"], ["cis", "commercialisee"]),
                "bdpm_presentations_historique")

    generiques = lire("CIS_GENER_bdpm")
    generiques["type_generique"] = generiques["type_generique"].map(TYPES_GENERIQUE)
    enregistrer(historiser(generiques, ["groupe_generique", "cis"], ["type_generique"]),
                "bdpm_generiques_historique")
