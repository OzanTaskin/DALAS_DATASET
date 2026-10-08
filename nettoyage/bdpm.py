"""France — Base de données publique des médicaments (BDPM) → tables `bdpm_*`.

Les fichiers n'ont pas d'en-tête : les noms de colonnes suivent la documentation officielle
(data/raw/bdpm/actuel/*_documentation_BDPM_v4.pdf). L'encodage varie selon le fichier
(UTF-8 pour CIS_CIP_bdpm.txt, Windows-1252 pour les autres) : il est détecté fichier par fichier.

Tables produites (photo du jour) :
- bdpm_specialites   une ligne par médicament (CIS)
- bdpm_presentations une ligne par boîte (CIP13), reliée à son CIS
- bdpm_compositions  substances actives de chaque médicament
- bdpm_generiques    appartenance aux groupes génériques
- bdpm_mitm          médicaments d'intérêt thérapeutique majeur (avec ATC)
et, à partir des archives :
- bdpm_dispo_observations  une ligne par signalement de disponibilité et par photo
"""
import io

import pandas as pd

from .commun import RAW, date_du_fichier, enregistrer, source_du_fichier

COLONNES = {
    "CIS_bdpm": ["cis", "denomination", "forme", "voies", "statut_amm", "procedure_amm",
                 "etat_commercialisation", "date_amm", "statut_bdm", "numero_autorisation_europeenne",
                 "titulaires", "surveillance_renforcee"],
    "CIS_CIP_bdpm": ["cis", "cip7", "libelle_presentation", "statut_administratif",
                     "etat_commercialisation", "date_declaration_commercialisation", "cip13",
                     "agrement_collectivites", "taux_remboursement", "prix_hors_honoraires",
                     "prix_avec_honoraires", "honoraires", "indications_remboursement"],
    "CIS_COMPO_bdpm": ["cis", "element_pharmaceutique", "code_substance", "substance", "dosage",
                       "reference_dosage", "nature_composant", "numero_liaison"],
    "CIS_GENER_bdpm": ["groupe_generique", "libelle_groupe", "cis", "type_generique", "numero_tri"],
    "CIS_MITM": ["cis", "atc5", "denomination", "lien_bdpm"],
    "CIS_CIP_Dispo_Spec": ["cis", "cip13", "code_statut", "statut", "date_debut",
                           "date_mise_a_jour", "date_remise_a_disposition", "url_ansm"],
}
TYPES_GENERIQUE = {"0": "princeps", "1": "generique", "2": "complementarite_posologique",
                   "4": "generique_substituable"}


def decoder(contenu):
    try:
        return contenu.decode("utf-8")
    except UnicodeDecodeError:
        return contenu.decode("cp1252")


def lire(chemin, fichier):
    """Lit un fichier BDPM (tabulations, sans en-tête) ; toutes les colonnes en texte."""
    colonnes = COLONNES[fichier]
    table = pd.read_csv(io.StringIO(decoder(chemin.read_bytes())), sep="\t", header=None,
                        dtype=str, keep_default_na=False, quoting=3, on_bad_lines="error",
                        names=colonnes, usecols=range(len(colonnes)))
    texte = table.columns
    table[texte] = table[texte].apply(lambda c: c.str.strip()).replace("", None)
    return table


def photo_du_jour(fichier):
    return sorted((RAW / "bdpm" / "actuel").glob(f"*_{fichier}.txt"))[-1]


def en_date(colonne):
    return pd.to_datetime(colonne, format="%d/%m/%Y", errors="coerce")


def construire():
    specialites = lire(photo_du_jour("CIS_bdpm"), "CIS_bdpm")
    specialites["date_amm"] = en_date(specialites["date_amm"])
    enregistrer(specialites, "bdpm_specialites")

    presentations = lire(photo_du_jour("CIS_CIP_bdpm"), "CIS_CIP_bdpm")
    presentations["date_declaration_commercialisation"] = en_date(presentations["date_declaration_commercialisation"])
    for prix in ("prix_hors_honoraires", "prix_avec_honoraires", "honoraires"):
        # Format français : « 1 024,34 » ou « 1.024,34 ».
        presentations[prix] = pd.to_numeric(
            presentations[prix].str.replace(r"[ .]", "", regex=True).str.replace(",", "."), errors="coerce")
    enregistrer(presentations, "bdpm_presentations")

    enregistrer(lire(photo_du_jour("CIS_COMPO_bdpm"), "CIS_COMPO_bdpm"), "bdpm_compositions")

    generiques = lire(photo_du_jour("CIS_GENER_bdpm"), "CIS_GENER_bdpm")
    generiques["type_generique"] = generiques["type_generique"].map(TYPES_GENERIQUE)
    enregistrer(generiques, "bdpm_generiques")

    enregistrer(lire(photo_du_jour("CIS_MITM"), "CIS_MITM"), "bdpm_mitm")

    # Signalements de disponibilité : archives + photo du jour.
    photos = sorted((RAW / "wayback" / "bdpm_dispo").glob("2*.txt")) + [photo_du_jour("CIS_CIP_Dispo_Spec")]
    morceaux = []
    for chemin in photos:
        morceau = lire(chemin, "CIS_CIP_Dispo_Spec")
        morceau.insert(0, "date_photo", pd.Timestamp(date_du_fichier(chemin)))
        morceau.insert(1, "origine_photo", source_du_fichier(chemin))
        morceaux.append(morceau)
    dispo = pd.concat(morceaux, ignore_index=True)
    for colonne in ("date_debut", "date_mise_a_jour", "date_remise_a_disposition"):
        dispo[colonne] = en_date(dispo[colonne])
    dispo["fiche_ansm"] = dispo["url_ansm"].str.rstrip("/").str.split("/").str[-1]
    enregistrer(dispo, "bdpm_dispo_observations")
