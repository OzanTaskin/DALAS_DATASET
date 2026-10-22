"""Contrôles des tables nettoyées, lancés en dernière étape de `python -m nettoyage`.

Une requête fausse ne donne pas d'erreur : elle donne un chiffre plausible. Chaque contrôle
vise une erreur silencieuse précise (cours « Building a Dataset from a Warehouse ») :
- grain : la clé annoncée identifie bien une seule ligne (sinon doublons, fan-out des jointures) ;
- codes ATC5 : 7 caractères, sinon un code de classe (niveau 4) passe pour une substance ;
- intervalles des dimensions historisées : pas de chevauchement, sinon une jointure as-of
  duplique des lignes sans message ;
- réconciliation : un total recalculé après jointure est égal au total de départ ;
- dates de publication : présentes partout, c'est la date à utiliser pour les variables.
Le premier contrôle en échec arrête la construction, avec le détail.
"""
import pandas as pd

from .commun import CLEAN

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


def controler_reconciliation():
    signalements = lire("ansm_signalements")["atc5"].notna().sum()
    dans_le_panel = lire("penuries_fr_mensuel")["nb_signalements"].sum()
    yield ("signalements avec ATC5 = total du panel mensuel", signalements == dans_le_panel,
           f"{signalements} signalements, {dans_le_panel} dans le panel")


def controler_publication():
    evenements = lire("shortage_events")
    manquantes = evenements["publication"].isna().sum()
    yield "date de publication de chaque épisode", manquantes == 0, f"{manquantes} épisodes sans publication"


def construire():
    for controles in (controler_grains, controler_atc5, controler_intervalles, controler_reconciliation,
                      controler_publication):
        for nom, reussi, detail in controles():
            if not reussi:
                raise SystemExit(f"Contrôle en échec : {nom} — {detail}")
            print(f"  ✓ {nom}")
