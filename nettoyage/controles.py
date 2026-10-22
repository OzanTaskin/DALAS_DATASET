"""Contrôles des tables nettoyées, lancés en dernière étape de `python -m nettoyage`.

Une requête fausse ne donne pas d'erreur : elle donne un chiffre plausible. Chaque contrôle
vise une erreur silencieuse précise (cours « Building a Dataset from a Warehouse ») :
- grain : la clé annoncée identifie bien une seule ligne (sinon doublons, fan-out des jointures) ;
- codes ATC5 : 7 caractères, sinon un code de classe (niveau 4) passe pour une substance ;
- intervalles des dimensions historisées : pas de chevauchement, sinon une jointure as-of
  duplique des lignes sans message ;
- réconciliation : un total recalculé après jointure est égal au total de départ, et la part
  des lignes sans clé (ATC5 non trouvé) est mesurée et bornée ;
- dates de connaissance : publication et fin connue présentes, dans le bon ordre : ce sont les
  dates à utiliser pour les variables.
Le premier contrôle en échec arrête la construction, avec le détail. Si tout passe, le manifeste
des tables est copié dans manifestes/.
"""
import shutil
from datetime import date

import pandas as pd

from .commun import CLEAN, RACINE

# table : colonnes qui identifient une ligne
GRAINS = {
    "produits": ["cis"],
    "atc": ["atc5"],
    "consommation": ["atc5", "annee"],
    "cip_atc": ["cip13"],
    "ansm_fiches": ["fiche"],
    "ansm_episodes": ["fiche", "numero_episode"],
    "europe_episodes": ["pays", "id_episode"],
    "shortage_events": ["pays", "id_episode"],
    "penuries_fr_mensuel": ["atc5", "mois"],
    "ue_liste_critique": ["atc5"],
    "bdpm_specialites_historique": ["cis", "valid_from"],
    "bdpm_presentations_historique": ["cip13", "valid_from"],
    "bdpm_generiques_historique": ["groupe_generique", "cis", "valid_from"],
}
TABLES_ATC5 = ["produits", "ansm_fiches", "ansm_signalements", "shortage_events", "penuries_fr_mensuel",
               "ue_liste_critique"]
HISTORISEES = {"bdpm_specialites_historique": ["cis"], "bdpm_presentations_historique": ["cip13"],
               "bdpm_generiques_historique": ["groupe_generique", "cis"]}


def lire(nom):
    return pd.read_parquet(CLEAN / f"{nom}.parquet")


def controler_grains():
    for table, cle in GRAINS.items():
        lignes = lire(table)
        doublons = lignes.duplicated(cle).sum()
        yield f"grain {table} ({', '.join(cle)})", doublons == 0, f"{doublons} doublons sur {len(lignes)} lignes"


def controler_atc5():
    for table in TABLES_ATC5:
        codes = lire(table)["atc5"].dropna()
        mauvais = codes[~codes.str.fullmatch(r"[A-Z]\d{2}[A-Z]{2}\d{2}")]
        yield f"ATC5 valides dans {table}", mauvais.empty, f"{len(mauvais)} codes invalides : {sorted(set(mauvais))[:5]}"


def controler_intervalles():
    for table, cle in HISTORISEES.items():
        versions = lire(table).sort_values([*cle, "valid_from"])
        fin = versions["valid_to"].fillna(pd.Timestamp.max)
        vides = (fin <= versions["valid_from"]).sum()
        # La version suivante du même objet doit commencer après la fin de celle-ci.
        debut_suivant = versions.groupby(cle)["valid_from"].shift(-1)
        chevauchements = (debut_suivant < fin).sum()
        yield (f"intervalles de {table}", vides == 0 and chevauchements == 0,
               f"{vides} intervalles vides, {chevauchements} chevauchements")
        # Au plus une version encore valable par objet (pas de « trou » à tester : un objet absent
        # d'une photo a vraiment disparu de la base à cette date).
        courantes = versions[versions["valid_to"].isna()].duplicated(cle).sum()
        yield f"une seule version courante par objet dans {table}", courantes == 0, f"{courantes} en trop"


def controler_reconciliation():
    """Troncature (cours, diapos 43-44) : les lignes passent d'une table à l'autre sans perte
    ni doublon, ou la perte est mesurée et reste sous un seuil (clés non résolues, diapo 27)."""
    signalements = lire("ansm_signalements")
    dans_le_panel = lire("penuries_fr_mensuel")["nb_signalements"].sum()
    yield ("signalements avec ATC5 = total du panel mensuel", signalements["atc5"].notna().sum() == dans_le_panel,
           f"{signalements['atc5'].notna().sum()} signalements, {dans_le_panel} dans le panel")

    evenements = lire("shortage_events")
    for source, pays in (("ansm_episodes", ["FR"]), ("europe_episodes", ["IT", "DE"])):
        attendu, obtenu = len(lire(source)), evenements["pays"].isin(pays).sum()
        yield f"{source} → shortage_events sans perte", attendu == obtenu, f"{attendu} épisodes, {obtenu} gardés"

    for table, seuil in (("ansm_signalements", 0.05), ("ansm_fiches", 0.10), ("shortage_events", 0.10)):
        part = lire(table)["atc5"].isna().mean()
        yield f"part sans ATC5 dans {table} : {part:.1%} (seuil {seuil:.0%})", part <= seuil, f"{part:.1%}"


def controler_dates():
    """Dates de connaissance (fuite temporelle) : chaque épisode a une date de publication, et
    chaque épisode terminé une date à laquelle sa fin est connue, jamais avant sa publication."""
    evenements = lire("shortage_events")
    manquantes = evenements["publication"].isna().sum()
    yield "date de publication de chaque épisode", manquantes == 0, f"{manquantes} épisodes sans publication"
    termines = evenements[~evenements["en_cours"]]
    sans_date = termines["fin_connue_le"].isna().sum()
    yield "date de connaissance de la fin de chaque épisode terminé", sans_date == 0, f"{sans_date} sans date"
    avant = (termines["fin_connue_le"] < termines["publication"]).sum()
    yield "fin connue après la publication", avant == 0, f"{avant} épisodes"


def garder_le_manifeste():
    """Copie datée du manifeste dans manifestes/ (suivi par git) : il reste disponible pendant
    tout le projet pour comparer une exécution future à celle-ci (cours, diapos 65-66)."""
    dossier = RACINE / "manifestes"
    dossier.mkdir(exist_ok=True)
    copie = dossier / f"niveau2_{date.today().isoformat()}.json"
    shutil.copyfile(CLEAN / "manifeste.json", copie)
    print(f"  manifeste copié dans {copie.relative_to(RACINE)} (à commiter)")


def construire():
    for controles in (controler_grains, controler_atc5, controler_intervalles, controler_reconciliation,
                      controler_dates):
        for nom, reussi, detail in controles():
            if not reussi:
                raise SystemExit(f"Contrôle en échec : {nom} — {detail}")
            print(f"  ✓ {nom}")
    garder_le_manifeste()
