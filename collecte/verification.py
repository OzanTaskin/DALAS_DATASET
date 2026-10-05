"""Vérifie que la couche brute est complète et intacte.

- chaque fichier attendu est présent (sources actuelles, pages CIMA, années Open Medic,
  captures Wayback listées dans _captures.json) ;
- chaque fichier présent est tracé dans le manifeste, avec la même empreinte SHA-256 ;
- aucun téléchargement interrompu (.part) ne traîne ;
- les captures qui ne ressemblent pas au format attendu sont signalées (sans être supprimées).
"""
import json
import zipfile

from . import open_medic, sources_actuelles
from .commun import MANIFESTE, RAW, lire_manifeste, sha256
from .wayback import CIBLES, chemin_capture

# .DS_Store : fichiers créés par le Finder de macOS à l'ouverture d'un dossier.
IGNORES = {MANIFESTE.name, "_captures.json", ".DS_Store"}


def verifier_manifeste(problemes):
    # En cas de retéléchargement, la dernière ligne d'un fichier fait foi.
    empreintes = {ligne["fichier"]: ligne["sha256"] for ligne in lire_manifeste()}
    for chemin in sorted(RAW.rglob("*")):
        if not chemin.is_file() or chemin.name in IGNORES:
            continue
        relatif = str(chemin.relative_to(RAW))
        if chemin.suffix == ".part":
            problemes.append(f"téléchargement interrompu : {relatif}")
        elif relatif not in empreintes:
            problemes.append(f"absent du manifeste : {relatif}")
        elif sha256(chemin.read_bytes()) != empreintes[relatif]:
            problemes.append(f"empreinte différente du manifeste : {relatif}")


def verifier_actuelles(problemes):
    for source, _, nom in sources_actuelles.SOURCES:
        if not list((RAW / source / "actuel").glob(f"*_{nom}")):
            problemes.append(f"source actuelle manquante : {source}/{nom}")

    # CIMA : l'union des lignes doit être stable sur les deux derniers passages (voir cima.py).
    pages = sorted((RAW / "cima" / "actuel").glob("*_passage*_p*.json"))
    if not pages:
        problemes.append("CIMA : aucune page")
        return
    derniere_date = pages[-1].name.split("_")[0]
    passages = {}
    for page in pages:
        if page.name.startswith(derniere_date):
            passage = page.name.split("_")[1]
            lignes = json.loads(page.read_bytes())["resultados"]
            passages.setdefault(passage, set()).update(json.dumps(l, sort_keys=True) for l in lignes)
    ordre = sorted(passages)
    union_avant = set().union(*(passages[p] for p in ordre[:-2]))
    if len(ordre) < 3 or not (passages[ordre[-1]] | passages[ordre[-2]]) <= union_avant:
        problemes.append("CIMA : union des passages non stabilisée")


def verifier_open_medic(problemes):
    for annee in open_medic.ANNEES:
        chemin = RAW / "open_medic" / f"OPEN_MEDIC_{annee}.zip"
        if not chemin.exists():
            problemes.append(f"Open Medic {annee} manquant")
            continue
        try:
            with zipfile.ZipFile(chemin) as archive:
                if archive.testzip() is not None:
                    problemes.append(f"Open Medic {annee} : archive corrompue")
        except zipfile.BadZipFile:
            problemes.append(f"Open Medic {annee} : ce n'est pas une archive ZIP")


def ressemble_au_format(chemin, extension):
    debut = chemin.read_bytes()[:500].lstrip().lower()
    if extension == "html":
        return b"<html" in debut or b"<!doctype" in debut
    # Un .txt ou .csv qui commence comme une page HTML est une page d'erreur archivée.
    return bool(debut) and not debut.startswith((b"<html", b"<!doctype"))


def verifier_wayback(problemes, alertes):
    for nom, extension, _ in CIBLES:
        index = RAW / "wayback" / nom / "_captures.json"
        if not index.exists():
            problemes.append(f"Wayback {nom} : liste des captures absente")
            continue
        captures = json.loads(index.read_text(encoding="utf-8"))
        manquantes, suspectes = [], []
        for capture in captures:
            chemin = RAW / chemin_capture(nom, extension, capture["horodatage"])
            if not chemin.exists():
                manquantes.append(capture["horodatage"])
            elif not ressemble_au_format(chemin, extension):
                suspectes.append(capture["horodatage"])
        mois = [c["horodatage"][:6] for c in captures]
        print(f"  {nom:22} {len(captures) - len(manquantes):3} / {len(captures):3} captures"
              f"  ({mois[0][:4]}-{mois[0][4:]} → {mois[-1][:4]}-{mois[-1][4:]})" if mois else "")
        if manquantes:
            problemes.append(f"Wayback {nom} : {len(manquantes)} capture(s) manquante(s) : {manquantes}")
        if suspectes:
            alertes.append(f"Wayback {nom} : {len(suspectes)} capture(s) au format inattendu : {suspectes}")


def verifier():
    problemes, alertes = [], []
    verifier_actuelles(problemes)
    verifier_open_medic(problemes)
    verifier_wayback(problemes, alertes)
    verifier_manifeste(problemes)

    for alerte in alertes:
        print(f"  ALERTE   {alerte}")
    for probleme in problemes:
        print(f"  PROBLÈME {probleme}")
    if problemes:
        raise SystemExit(f"Couche brute incomplète : {len(problemes)} problème(s). Relancer la collecte.")
    print("  Couche brute complète.")
