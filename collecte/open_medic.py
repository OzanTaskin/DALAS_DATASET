"""France — Open Medic (Assurance Maladie) : médicaments remboursés en ville, par année.

La base complète relie chaque présentation (CIP13) à sa classification ATC (niveaux 1 à 5,
avec libellés) et donne les boîtes remboursées. Les liens de téléchargement contiennent un
jeton temporaire : on lit d'abord la page de l'année pour le récupérer.

Le serveur refuse les téléchargements simultanés : il répond alors HTTP 200 avec un court
message « Téléchargement refusé » au lieu de l'archive. Les années sont donc téléchargées
l'une après l'autre, et on vérifie qu'on a bien reçu un ZIP avant de l'enregistrer.
"""
import re
import time

from .commun import telecharger

PAGE = ("https://open-data-assurance-maladie.ameli.fr/medicaments/"
        "download.php?Dir_Rep=Open_MEDIC_Base_Complete&Annee={}")
BASE = "https://open-data-assurance-maladie.ameli.fr/medicaments/"
ANNEES = range(2019, 2026)
TENTATIVES = 5
PAUSE_REFUS = 30  # secondes d'attente après un refus du serveur


def est_un_zip(contenu):
    return contenu[:4] == b"PK\x03\x04"


def telecharger_annee(session, annee):
    # Nouveau jeton à chaque tentative : il expire.
    page = session.get(PAGE.format(annee), timeout=60).text
    lien = re.search(r'download_file\.php\?token=[0-9a-f]+&file=[^"]+\.zip', page)
    if lien is None:
        return None
    return telecharger(session, BASE + lien.group(0), f"open_medic/OPEN_MEDIC_{annee}.zip",
                       "open_medic", timeout=900, valider=est_un_zip)


def collecter(session, annees=ANNEES):
    for annee in annees:
        for tentative in range(1, TENTATIVES + 1):
            if telecharger_annee(session, annee):
                print(f"  open_medic {annee} ok")
                break
            time.sleep(PAUSE_REFUS)
        else:
            print(f"  open_medic {annee} ÉCHEC après {TENTATIVES} tentatives")
