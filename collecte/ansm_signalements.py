"""France — signalements de rupture et de risque de rupture reçus par l'ANSM, par année.

Les laboratoires doivent déclarer à l'ANSM toute rupture ou tout risque de rupture d'un
médicament d'intérêt thérapeutique majeur (MITM). L'ANSM publie la liste de ces signalements
dans un classeur Excel par année (2021 à 2023 dans le même classeur). C'est l'historique
officiel des déclarations : une date par signalement, mais ni date de fin ni statut.

Les adresses contiennent la date de mise en ligne : elles ne se devinent pas. Le classeur
d'une année paraît au printemps suivant ; il faut alors l'ajouter ici (liste des classeurs :
https://ansm.sante.fr/page/impression/178).
"""
from .commun import telecharger

ANSM = "https://ansm.sante.fr/uploads/"

# (nom du fichier dans data/raw/ansm_signalements/, url)
CLASSEURS = [
    ("signalements_2019.xlsx", ANSM + "2021/10/18/20211018-signalements-ruptures-de-stock-2019.xlsx"),
    ("signalements_2020.xlsx", ANSM + "2021/09/09/20210909-signalements-ruptures-de-stock-2020-4.xlsx"),
    ("signalements_2021_2023.xlsx", ANSM + "2025/10/16/20251016-rs-liste-medicaments-2021-2022-2023.xlsx"),
    ("signalements_2024.xlsx", ANSM + "2026/04/01/20260401-rs-liste-ruptures-medicaments-2024.xlsx"),
    ("signalements_2025.xlsx", ANSM + "2026/04/01/20260401-rs-liste-ruptures-medicaments-2025.xlsx"),
]


def est_un_classeur(contenu):
    # Un .xlsx est une archive ZIP : une page d'erreur HTML n'en est pas une.
    return contenu[:4] == b"PK\x03\x04"


def collecter(session):
    echecs = []
    for nom, url in CLASSEURS:
        chemin = telecharger(session, url, f"ansm_signalements/{nom}", "ansm_signalements", valider=est_un_classeur)
        print(f"  ansm_signalements {nom:30} {'ok' if chemin else 'ÉCHEC'}")
        if not chemin:
            echecs.append(f"ansm_signalements/{nom}")
    return echecs
