"""Photo actuelle des sources officielles (un fichier par source, à la date de collecte)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .commun import telecharger

BDPM = "https://base-donnees-publique.medicaments.gouv.fr/download/file/"
EMA = "https://www.ema.europa.eu/en/documents/"

# (source, url, nom du fichier dans data/raw/<source>/)
SOURCES = [
    # France — Base de données publique des médicaments (univers complet des médicaments)
    ("bdpm", BDPM + "CIS_bdpm.txt", "CIS_bdpm.txt"),                  # spécialités
    ("bdpm", BDPM + "CIS_CIP_bdpm.txt", "CIS_CIP_bdpm.txt"),          # présentations (CIP13, prix)
    ("bdpm", BDPM + "CIS_COMPO_bdpm.txt", "CIS_COMPO_bdpm.txt"),      # substances et dosages
    ("bdpm", BDPM + "CIS_GENER_bdpm.txt", "CIS_GENER_bdpm.txt"),      # groupes génériques
    ("bdpm", BDPM + "CIS_CIP_Dispo_Spec.txt", "CIS_CIP_Dispo_Spec.txt"),  # pénuries en cours
    ("bdpm", BDPM + "CIS_MITM.txt", "CIS_MITM.txt"),                  # intérêt thérapeutique majeur
    ("bdpm", BDPM + "Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v4.pdf",
     "documentation_BDPM_v4.pdf"),
    # France — liste des pénuries publiée par l'ANSM
    ("ansm", "https://ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments",
     "disponibilites_medicaments.html"),
    # Italie — liste des médicaments en pénurie (AIFA)
    ("aifa", "https://www.aifa.gov.it/documents/20142/847339/elenco_medicinali_carenti.csv",
     "elenco_medicinali_carenti.csv"),
    # Allemagne — déclarations de pénurie (BfArM)
    ("bfarm", "https://anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv",
     "lieferengpassmeldungen.csv"),
    # Union européenne — EMA
    ("ema", EMA + "report/shortages-output-json-report_en.json", "shortages.json"),
    ("ema", EMA + "report/medicines-output-medicines_json-report_en.json", "medicines.json"),
    ("ema", EMA + "other/union-list-critical-medicines-en.xlsx", "union_list_critical_medicines.xlsx"),
]


def collecter(session):
    jour = date.today().isoformat()

    def telecharger_source(entree):
        source, url, nom = entree
        # Le préfixe de date distingue les photos successives d'une même source.
        return source, nom, telecharger(session, url, f"{source}/actuel/{jour}_{nom}", source)

    # Sites tous différents : on peut tout lancer en même temps.
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as executeur:
        for source, nom, chemin in executeur.map(telecharger_source, SOURCES):
            print(f"  {source:6} {nom:40} {'ok' if chemin else 'ÉCHEC'}")
