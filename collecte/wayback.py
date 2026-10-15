"""Historique reconstruit à partir des archives de la Wayback Machine (Internet Archive).

Les sources officielles ne publient que les pénuries en cours. Les captures archivées de
leurs listes permettent de savoir ce qui était publié à chaque date passée.
On garde une capture par mois (la première du mois), téléchargée sans la barre
d'outils de la Wayback Machine (suffixe `id_`), donc identique à l'original.
"""
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .commun import RAW, telecharger

CDX = "https://web.archive.org/cdx/search/cdx"
BDPM_ANCIEN = "base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier="
BDPM_NOUVEAU = "base-donnees-publique.medicaments.gouv.fr/download/file/"

# (nom de la cible, extension, URLs archivées). Plusieurs URLs quand le site a changé d'adresse.
CIBLES = [
    ("ansm_disponibilites", "html", ["ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments"]),
    ("aifa_carenti", "csv", ["www.aifa.gov.it/documents/20142/847339/elenco_medicinali_carenti.csv"]),
    ("bfarm_lieferengpaesse", "csv", ["anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv"]),
    ("bdpm_dispo", "txt", [BDPM_ANCIEN + "CIS_CIP_Dispo_Spec.txt", BDPM_NOUVEAU + "CIS_CIP_Dispo_Spec.txt"]),
    # Versions passées de l'univers des médicaments : structure du marché connue à chaque date.
    ("bdpm_cis", "txt", [BDPM_ANCIEN + "CIS_bdpm.txt", BDPM_NOUVEAU + "CIS_bdpm.txt"]),
    ("bdpm_cip", "txt", [BDPM_ANCIEN + "CIS_CIP_bdpm.txt", BDPM_NOUVEAU + "CIS_CIP_bdpm.txt"]),
    ("bdpm_gener", "txt", [BDPM_ANCIEN + "CIS_GENER_bdpm.txt", BDPM_NOUVEAU + "CIS_GENER_bdpm.txt"]),
]
PAUSE = 1.5  # secondes entre deux requêtes, pour respecter le service


def lister_captures(session, url):
    """Une capture HTTP 200 par mois : liste de (horodatage, url originale)."""
    params = {
        "url": url,
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "timestamp:6",
        "fl": "timestamp,original",
    }
    lignes = session.get(CDX, params=params, timeout=120).json()
    return [tuple(ligne) for ligne in lignes[1:]]  # la première ligne est l'en-tête


def chemin_capture(nom, extension, horodatage):
    return f"wayback/{nom}/{horodatage}.{extension}"


def captures_attendues(session, nom, urls):
    """Liste mensuelle des captures d'une cible, enregistrée dans wayback/<nom>/_captures.json
    (trace de ce qui était disponible le jour de la collecte)."""
    captures = {}
    for url in urls:
        for horodatage, originale in lister_captures(session, url):
            # Si les deux adresses ont une capture le même mois, on garde la première.
            captures.setdefault(horodatage[:6], (horodatage, originale))
        time.sleep(PAUSE)
    liste = [{"horodatage": h, "url": u} for h, u in sorted(captures.values())]
    fichier = RAW / "wayback" / nom / "_captures.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(liste, indent=1), encoding="utf-8")
    return liste


def collecter(session):
    paralleles = 4
    with ThreadPoolExecutor(max_workers=paralleles) as executeur:
        listes = executeur.map(lambda cible: captures_attendues(session, cible[0], cible[2]), CIBLES)
        taches = [(nom, extension, capture)
                  for (nom, extension, _), liste in zip(CIBLES, listes)
                  for capture in liste]

    def telecharger_capture(tache):
        nom, extension, capture = tache
        archive = f"https://web.archive.org/web/{capture['horodatage']}id_/{capture['url']}"
        chemin = telecharger(session, archive, chemin_capture(nom, extension, capture["horodatage"]),
                             f"wayback_{nom}")
        time.sleep(PAUSE)
        return nom, capture["horodatage"], chemin is not None

    # Quelques téléchargements simultanés seulement : au-delà, la Wayback Machine renvoie des 429.
    bilan, echecs = Counter(), []
    with ThreadPoolExecutor(max_workers=paralleles) as executeur:
        for nom, horodatage, reussi in executeur.map(telecharger_capture, taches):
            bilan[nom, reussi] += 1
            if not reussi:
                echecs.append(f"wayback/{nom}/{horodatage}")
    for nom, *_ in CIBLES:
        total = bilan[nom, True] + bilan[nom, False]
        if total:
            print(f"  {nom:22} {bilan[nom, True]} / {total} captures mensuelles")
    return echecs
